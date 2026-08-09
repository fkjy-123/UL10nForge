"""外部 CLI 的隔离执行、超时、输入保护与缓存编排。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import threading
import time
import uuid
from typing import Callable, Iterable

from hanhua.core.tooling.cache import VerifiedArtifactCache
from hanhua.core.tooling.manifest import ToolSpec


class ToolRunError(RuntimeError):
    pass


class ToolTimeout(ToolRunError):
    pass


class ToolExecutionError(ToolRunError):
    pass


class ToolIntegrityError(ToolRunError):
    pass


class ToolCancelled(ToolRunError):
    pass


class ToolProcessCleanupError(ToolRunError):
    pass


class ToolOutputError(ToolRunError):
    pass


class ToolInputModified(ToolRunError):
    pass


@dataclass(frozen=True)
class ToolRunResult:
    tool_id: str
    artifact_dir: Path
    cache_hit: bool
    elapsed_ms: int
    stdout_log: Path
    stderr_log: Path


class _WindowsJob:
    """把完整子进程树绑定到 kill-on-close Job Object。"""

    def __init__(self, process: subprocess.Popen):
        if os.name != "nt":
            raise RuntimeError("Windows Job Object 仅适用于 Windows")
        import ctypes
        from ctypes import wintypes

        class BasicLimit(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class ExtendedLimit(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimit),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class BasicAccounting(ctypes.Structure):
            _fields_ = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]

        self._ctypes = ctypes
        self._accounting_type = BasicAccounting
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self._kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self._kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self._kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD)]
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self._kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            raise ToolProcessCleanupError("无法创建 Windows Job Object")
        info = ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = 0x00002000
        if not self._kernel32.SetInformationJobObject(
                self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise ToolProcessCleanupError("无法设置 Job Object kill-on-close")
        if not self._kernel32.AssignProcessToJobObject(
                self.handle, wintypes.HANDLE(process._handle)):  # noqa: SLF001
            error = ctypes.get_last_error()
            self.close()
            raise ToolProcessCleanupError(f"无法绑定进程树到 Job Object（WinError {error}）")

    def active_processes(self) -> int:
        info = self._accounting_type()
        returned = self._ctypes.c_ulong()
        if not self._kernel32.QueryInformationJobObject(
                self.handle, 1, self._ctypes.byref(info), self._ctypes.sizeof(info),
                self._ctypes.byref(returned)):
            raise ToolProcessCleanupError("无法查询 Job Object 进程状态")
        return int(info.ActiveProcesses)

    def close(self) -> None:
        if getattr(self, "handle", None):
            self._kernel32.CloseHandle(self.handle)
            self.handle = None


def _resume_suspended_process(process: subprocess.Popen) -> None:
    import ctypes
    from ctypes import wintypes

    class ThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
    kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
    kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenThread.restype = wintypes.HANDLE
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if not snapshot or snapshot == invalid_handle:
        raise ToolProcessCleanupError("无法枚举暂停工具进程的主线程")
    resumed = 0
    try:
        entry = ThreadEntry32()
        entry.dwSize = ctypes.sizeof(entry)
        has_entry = bool(kernel32.Thread32First(snapshot, ctypes.byref(entry)))
        while has_entry:
            if entry.th32OwnerProcessID == process.pid:
                thread = kernel32.OpenThread(0x0002, False, entry.th32ThreadID)
                if thread:
                    try:
                        result = kernel32.ResumeThread(thread)
                        if result != 0xFFFFFFFF:
                            resumed += 1
                    finally:
                        kernel32.CloseHandle(thread)
            has_entry = bool(kernel32.Thread32Next(snapshot, ctypes.byref(entry)))
    finally:
        kernel32.CloseHandle(snapshot)
    if resumed == 0:
        raise ToolProcessCleanupError(
            f"无法恢复已绑定 Job Object 的工具进程（WinError {ctypes.get_last_error()}）")


def _close_job_and_wait(tree_guard: _WindowsJob, process: subprocess.Popen) -> None:
    tree_guard.close()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as exc:
        raise ToolProcessCleanupError("关闭 Job Object 后工具进程仍未退出") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _safe_input_name(name: str) -> bool:
    return bool(name) and Path(name).name == name and name not in {".", ".."}


def _is_reparse_point(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", lambda: False)
    return path.is_symlink() or is_junction()


class IsolatedToolRunner:
    def __init__(self, app_data: str | Path, *, max_output_files: int = 10_000,
                 max_output_bytes: int = 1024 * 1024 * 1024):
        self.app_data = Path(app_data)
        self.jobs_root = self.app_data / "tool-jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.failures_root = self.app_data / "tool-failures"
        self.failures_root.mkdir(parents=True, exist_ok=True)
        self.cache = VerifiedArtifactCache(self.app_data / "tool-cache")
        self.max_output_files = max_output_files
        self.max_output_bytes = max_output_bytes

    @staticmethod
    def _verify_tool_sources(spec: ToolSpec) -> None:
        records = [(spec.entry, spec.size, spec.sha256)] + [
            (item.path, item.size, item.sha256) for item in spec.required_files
        ]
        for path, size, expected_sha in records:
            if not path.is_file():
                raise ToolIntegrityError(f"工具文件不存在：{path.name}")
            if path.stat().st_size != size:
                raise ToolIntegrityError(f"{path.name} 文件大小不符")
            if _sha256(path) != expected_sha:
                raise ToolIntegrityError(f"{path.name} SHA-256 不符")

    @staticmethod
    def _cache_key(spec: ToolSpec, inputs: dict[str, Path], config: dict) -> str:
        try:
            config_json = json.dumps(config, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ToolRunError("适配器配置必须可确定性 JSON 序列化") from exc
        payload = {
            "tool": spec.tool_id,
            "tool_sha256": spec.sha256,
            "companions": [(item.path.name, item.sha256) for item in spec.required_files],
            "adapter_version": spec.adapter_version,
            "config": config_json,
            "inputs": [(name, _sha256(path)) for name, path in sorted(inputs.items())],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _kill_tree(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0 and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
                raise ToolProcessCleanupError(
                    f"无法确认子进程树已终止（taskkill={result.returncode}）")
        else:
            process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    @staticmethod
    def _sanitized_environment(temp_dir: Path) -> dict[str, str]:
        allowed = {key: os.environ[key] for key in (
            "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT"
        ) if key in os.environ}
        allowed.update({"TEMP": str(temp_dir), "TMP": str(temp_dir), "PATH": ""})
        return allowed

    def run(
        self,
        spec: ToolSpec,
        inputs: dict[str, str | Path],
        adapter_config: dict,
        *,
        command: Callable[[Path, dict[str, Path], Path], list[str]],
        validate: Callable[[Path], Iterable[Path]],
        prepare: Callable[[Path, dict[str, Path], Path], None] | None = None,
        cancel_event: threading.Event | None = None,
        timeout_s: float = 120,
    ) -> ToolRunResult:
        if timeout_s <= 0:
            raise ToolRunError("timeout_s 必须大于 0")
        self._verify_tool_sources(spec)
        normalized: dict[str, Path] = {}
        for name, raw_path in inputs.items():
            if not _safe_input_name(name):
                raise ToolRunError(f"输入名称不安全：{name}")
            path = Path(raw_path).resolve()
            if not path.is_file():
                raise ToolRunError(f"输入不存在：{path}")
            normalized[name] = path
        original_hashes = {path: _sha256(path) for path in normalized.values()}
        key = self._cache_key(spec, normalized, adapter_config)
        cached = self.cache.lookup(key)
        if cached is not None:
            changed = [path for path, digest in original_hashes.items()
                       if not path.is_file() or _sha256(path) != digest]
            if changed:
                raise ToolInputModified(f"原始输入被修改：{changed[0]}")
            return ToolRunResult(spec.tool_id, cached, True, 0,
                                 cached / "stdout.log", cached / "stderr.log")

        job = Path(tempfile.mkdtemp(prefix=f"{spec.tool_id}-", dir=self.jobs_root))
        output_dir = job / "output"
        tool_dir = job / "tool"
        input_dir = job / "inputs"
        temp_dir = job / "temp"
        for directory in (output_dir, tool_dir, input_dir, temp_dir):
            directory.mkdir()
        expected_output_root = output_dir.resolve(strict=True)
        stdout_log = job / "stdout.log"
        stderr_log = job / "stderr.log"
        started = time.perf_counter()
        try:
            staged_entry = tool_dir / spec.entry.name
            shutil.copy2(spec.entry, staged_entry)
            if staged_entry.stat().st_size != spec.size or _sha256(staged_entry) != spec.sha256:
                raise ToolIntegrityError(f"{spec.entry.name} 隔离副本完整性验证失败")
            used_names = {staged_entry.name.casefold()}
            for companion in spec.required_files:
                if companion.path.name.casefold() in used_names:
                    raise ToolRunError("工具文件名发生 Windows 大小写冲突")
                used_names.add(companion.path.name.casefold())
                staged_companion = tool_dir / companion.path.name
                shutil.copy2(companion.path, staged_companion)
                if (staged_companion.stat().st_size != companion.size
                        or _sha256(staged_companion) != companion.sha256):
                    raise ToolIntegrityError(
                        f"{companion.path.name} 隔离副本完整性验证失败")
            staged_inputs: dict[str, Path] = {}
            for name, source in normalized.items():
                staged = input_dir / name
                shutil.copy2(source, staged)
                staged.chmod(stat.S_IREAD)
                if _sha256(staged) != original_hashes[source]:
                    raise ToolInputModified(f"隔离输入与原始输入不一致：{source}")
                staged_inputs[name] = staged
            if prepare is not None:
                prepare(job, staged_inputs, staged_entry)
            if cancel_event is not None and cancel_event.is_set():
                raise ToolCancelled(f"{spec.tool_id} 已取消")
            argv = command(staged_entry, staged_inputs, output_dir)
            if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
                raise ToolRunError("工具命令必须是非空参数数组")
            try:
                argv_entry = Path(argv[0]).resolve(strict=True)
            except OSError as exc:
                raise ToolIntegrityError("工具命令入口不存在") from exc
            if argv_entry != staged_entry.resolve(strict=True):
                raise ToolIntegrityError("工具命令入口必须是已验证的隔离副本")
            if (staged_entry.stat().st_size != spec.size
                    or _sha256(staged_entry) != spec.sha256):
                raise ToolIntegrityError(f"{spec.entry.name} 执行前完整性验证失败")
            for companion in spec.required_files:
                staged_companion = tool_dir / companion.path.name
                if (staged_companion.stat().st_size != companion.size
                        or _sha256(staged_companion) != companion.sha256):
                    raise ToolIntegrityError(
                        f"{companion.path.name} 执行前完整性验证失败")
            for name, staged in staged_inputs.items():
                source = normalized[name]
                if _sha256(staged) != original_hashes[source]:
                    raise ToolInputModified(f"隔离输入执行前发生变化：{name}")
            if (_is_reparse_point(output_dir)
                    or output_dir.resolve(strict=True) != expected_output_root):
                raise ToolOutputError("工具输出根目录被替换")
            with stdout_log.open("wb") as stdout, stderr_log.open("wb") as stderr:
                process = subprocess.Popen(
                    argv,
                    cwd=job,
                    env=self._sanitized_environment(temp_dir),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    shell=False,
                    creationflags=((getattr(subprocess, "CREATE_NO_WINDOW", 0) | 0x00000004)
                                   if os.name == "nt" else 0),
                )
                tree_guard = None
                if os.name == "nt":
                    try:
                        tree_guard = _WindowsJob(process)
                    except Exception:
                        self._kill_tree(process)
                        raise
                    try:
                        _resume_suspended_process(process)
                    except Exception:
                        _close_job_and_wait(tree_guard, process)
                        raise
                deadline = time.monotonic() + timeout_s
                try:
                    while True:
                        if cancel_event is not None and cancel_event.is_set():
                            if tree_guard is not None:
                                _close_job_and_wait(tree_guard, process)
                            else:
                                self._kill_tree(process)
                            raise ToolCancelled(f"{spec.tool_id} 已取消")
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            if tree_guard is not None:
                                _close_job_and_wait(tree_guard, process)
                            else:
                                self._kill_tree(process)
                            raise ToolTimeout(f"{spec.tool_id} 执行超时（{timeout_s:g}s）")
                        return_code = process.poll()
                        active = (tree_guard.active_processes() if tree_guard is not None
                                  else (0 if return_code is not None else 1))
                        if return_code is not None and active == 0:
                            break
                        time.sleep(min(0.05, remaining))
                finally:
                    if tree_guard is not None:
                        tree_guard.close()
            if return_code != 0:
                raise ToolExecutionError(f"{spec.tool_id} 退出码 {return_code}")
            if (_is_reparse_point(output_dir)
                    or output_dir.resolve(strict=True) != expected_output_root):
                raise ToolOutputError("工具输出根目录被替换")
            output_root = expected_output_root
            validated = list(validate(output_dir))
            validated_files: set[Path] = set()
            for artifact in validated:
                path = Path(artifact)
                try:
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(output_root)
                except (OSError, ValueError) as exc:
                    raise ToolOutputError("验证产物必须位于工具输出目录内") from exc
                if _is_reparse_point(path) or not resolved.is_file():
                    raise ToolOutputError("验证产物必须是普通文件")
                validated_files.add(resolved)
            actual_files: set[Path] = set()
            total_bytes = 0
            for path in output_dir.rglob("*"):
                if _is_reparse_point(path):
                    raise ToolOutputError("工具输出不允许符号链接")
                if path.is_file():
                    resolved = path.resolve()
                    actual_files.add(resolved)
                    total_bytes += path.stat().st_size
            if len(actual_files) > self.max_output_files or total_bytes > self.max_output_bytes:
                raise ToolOutputError("工具输出超过文件数量或总大小限制")
            if actual_files != validated_files:
                raise ToolOutputError("工具生成了未验证的输出文件")
            for path, digest in original_hashes.items():
                if not path.is_file() or _sha256(path) != digest:
                    raise ToolInputModified(f"原始输入被修改：{path}")
            artifact_dir = self.cache.promote(key, output_dir, (stdout_log, stderr_log))
            elapsed = int((time.perf_counter() - started) * 1000)
            return ToolRunResult(spec.tool_id, artifact_dir, False, elapsed,
                                 artifact_dir / "stdout.log", artifact_dir / "stderr.log")
        except Exception as exc:
            failure_dir = self.failures_root / f"{spec.tool_id}-{uuid.uuid4().hex}"
            failure_dir.mkdir()
            for source, name in ((stdout_log, "stdout.log"), (stderr_log, "stderr.log")):
                if source.is_file():
                    with source.open("rb") as stream:
                        data = stream.read(4 * 1024 * 1024 + 1)
                    if len(data) > 4 * 1024 * 1024:
                        data = data[:4 * 1024 * 1024] + b"\n[LOG TRUNCATED]\n"
                    (failure_dir / name).write_bytes(data)
            if exc.args:
                exc.args = (f"{exc.args[0]}；日志：{failure_dir}", *exc.args[1:])
            raise
        finally:
            changed = [path for path, digest in original_hashes.items()
                       if not path.is_file() or _sha256(path) != digest]
            shutil.rmtree(job, ignore_errors=True)
            if changed:
                raise ToolInputModified(f"原始输入被修改：{changed[0]}")
