"""staging 启动冒烟与日志扫描（写回安全闸门 P0-5）。

发布前对 staging 副本做进程级冒烟：启动玩家可执行文件，存活到超时视为
能启动，崩溃/异常退出视为失败；同时增量扫描 Unity Player.log 与进程
stderr 中的异常、资源加载错误和 CRC mismatch。结果进发布报告的游戏性
状态（gameplay gate）。

状态语义：
- passed       存活到超时且无新增错误日志
- warn         存活到超时但有新增错误日志（或快速以 0 退出，疑似无头环境）
- blocked      进程崩溃 / 非 0 退出 → 不得发布
- unverifiable 找不到可执行文件或进程根本起不来（CreateProcess 失败）→
               不作为阻断证据，报告标注 N/A
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

SMOKE_PASSED = "passed"
SMOKE_WARN = "warn"
SMOKE_BLOCKED = "blocked"
SMOKE_UNVERIFIABLE = "unverifiable"

# Unity 启动/资源加载时的致命错误特征；匹配到只升级为 WARN，进程崩溃才是 BLOCKED
_LOG_ERROR_PATTERNS = (
    re.compile(r"CRC Mismatch|CRC mismatch", re.IGNORECASE),
    re.compile(r"Failed to (load|initialize|open|create)", re.IGNORECASE),
    re.compile(r"NullReferenceException|MissingMethodException"),
    re.compile(r"TypeLoadException|FileNotFoundException"),
    re.compile(r"Unhandled exception|Assertion failed"),
    re.compile(r"Unable to load", re.IGNORECASE),
    re.compile(r"ERROR: ", re.IGNORECASE),
)


@dataclass(frozen=True)
class SmokeResult:
    status: str                                  # passed / warn / blocked / unverifiable
    detail: str = ""
    exit_code: int | None = None                 # 进程退出码（崩溃时非 0）
    elapsed_ms: int = 0
    log_errors: tuple[str, ...] = ()             # 日志扫描命中的新增错误行
    log_scan: str = ""                           # 扫描到的日志文件（未扫描为空）

    @property
    def passed(self) -> bool:
        return self.status == SMOKE_PASSED

    @property
    def blocked(self) -> bool:
        return self.status == SMOKE_BLOCKED

    @property
    def unverifiable(self) -> bool:
        return self.status == SMOKE_UNVERIFIABLE


def find_player_executable(
        staging: Path, executable_rel: Path | None = None) -> Path | None:
    """在 staging 中定位玩家主可执行文件。

    优先与扫描时记录的相对路径一致（避免多个 exe 时选错）；没有相对路径
    时，取根目录下唯一一个 *.exe；仍不唯一则选与 *_Data 目录同名的 exe。
    """
    root = Path(staging)
    if executable_rel is not None:
        relative = Path(executable_rel)
        if relative.is_absolute():
            # 防御：调用方可能误传源目录的绝对路径（staging 是源目录的
            # 完整拷贝，根结构一致，取文件名即可）；绝对路径拼接会让
            # pathlib 直接返回原路径，导致启动原游戏而非汉化副本。
            relative = Path(relative.name)
        candidate = root / relative
        if candidate.is_file():
            return candidate
    exes = sorted(p for p in root.glob("*.exe") if p.is_file())
    if len(exes) == 1:
        return exes[0]
    data_dirs = sorted(d for d in root.iterdir() if d.is_dir())
    for exe in exes:
        for data_dir in data_dirs:
            if data_dir.name == exe.stem + "_Data":
                return exe
    return None


def _unity_log_candidates() -> list[Path]:
    """Unity 标准日志目录下的 Player.log 候选（LocalLow 布局）。"""
    local_low = os.environ.get(
        "LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    root = Path(local_low) / ".." / "LocalLow"
    try:
        return sorted(p for p in root.rglob("Player.log") if p.is_file())
    except OSError:
        return []


def _scan_log_errors(
        log_path: Path, start_size: int, start_wall: float) -> tuple[list[str], int]:
    """扫描日志自启动以来的新增段，返回 (错误行, 新增字节数)。

    start_wall 必须与日志 mtime 同源（time.time() 墙钟），不能传
    perf_counter。判断依据是增量大小；mtime 只用于排除启动前就已被
    其他进程追加的情况。
    """
    try:
        stat = log_path.stat()
    except OSError:
        return [], 0
    if stat.st_size <= start_size or stat.st_mtime < start_wall - 2.0:
        return [], 0
    try:
        with open(log_path, "rb") as handle:
            handle.seek(start_size)
            new_bytes = handle.read()
    except OSError:
        return [], 0
    errors: list[str] = []
    for line in new_bytes.decode("utf-8", errors="replace").splitlines():
        if any(pattern.search(line) for pattern in _LOG_ERROR_PATTERNS):
            errors.append(line.strip()[:300])
    return errors, len(new_bytes)


def _snapshot_logs() -> dict[Path, int]:
    return {path: path.stat().st_size for path in _unity_log_candidates()}


def run_staging_smoke(
        staging: Path,
        executable_rel: Path | None = None,
        *,
        timeout: float = 20.0,
        log_paths: tuple[Path, ...] | None = None,
        launcher: callable | None = None,
) -> SmokeResult:
    """启动 staging 副本做冒烟，返回 SmokeResult。

    launcher 可注入（测试）：launcher(exe, cwd, stderr_path) -> Popen。
    默认用 subprocess.Popen。stderr 重定向到临时文件，避免管道缓冲区
    填满导致进程死锁。
    """
    exe = find_player_executable(staging, executable_rel)
    if exe is None:
        return SmokeResult(
            SMOKE_UNVERIFIABLE, f"未找到玩家可执行文件（{executable_rel or '*.exe'}）")

    if log_paths is None:
        log_paths = tuple(_snapshot_logs().keys())
    start_sizes = {path: (path.stat().st_size if path.exists() else 0)
                   for path in log_paths}
    started = time.perf_counter()
    started_wall = time.time()
    stderr_path = staging.parent / f".{staging.name}.smoke-stderr.log"
    stderr_handle = None
    try:
        if launcher is not None:
            proc = launcher(exe, str(staging), str(stderr_path))
        else:
            stderr_handle = open(stderr_path, "wb")
            proc = subprocess.Popen(
                [str(exe)],
                cwd=str(staging),
                stdout=subprocess.DEVNULL,
                stderr=stderr_handle,
                close_fds=True,
            )
    except OSError as exc:
        if stderr_handle is not None:
            stderr_handle.close()
        return SmokeResult(
            SMOKE_UNVERIFIABLE, f"无法启动玩家进程：{exc}",
            elapsed_ms=int((time.perf_counter() - started) * 1000))

    try:
        deadline = started + max(1.0, timeout)
        while time.perf_counter() < deadline:
            exit_code = proc.poll()
            if exit_code is not None:
                elapsed = int((time.perf_counter() - started) * 1000)
                if stderr_handle is not None:
                    stderr_handle.close()
                    stderr_handle = None
                if exit_code == 0:
                    # 快速以 0 退出：疑似无头环境/初始化即完成，不视为崩溃
                    return SmokeResult(
                        SMOKE_WARN,
                        f"进程在 {elapsed // 1000}s 内正常退出（exit 0）",
                        exit_code=exit_code, elapsed_ms=elapsed)
                return SmokeResult(
                    SMOKE_BLOCKED,
                    f"玩家进程崩溃退出（exit code {exit_code}）",
                    exit_code=exit_code, elapsed_ms=elapsed)
            time.sleep(0.4)
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)
    finally:
        if stderr_handle is not None:
            stderr_handle.close()
            stderr_handle = None
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5.0)

    if stderr_handle is not None:
        stderr_handle.close()
    elapsed = int((time.perf_counter() - started) * 1000)
    errors: list[str] = []
    scanned: str = ""
    for path in log_paths:
        if not path.exists():
            continue
        new_errors, _new_bytes = _scan_log_errors(
            path, start_sizes.get(path, 0), started_wall)
        if new_errors:
            errors.extend(f"{path.name}: {line}" for line in new_errors)
            scanned = str(path)
    try:
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        stderr_text = ""
    try:
        stderr_path.unlink(missing_ok=True)
    except OSError:
        pass
    if stderr_text:
        for line in stderr_text.splitlines():
            if any(pattern.search(line) for pattern in _LOG_ERROR_PATTERNS):
                errors.append(f"stderr: {line.strip()[:300]}")
        if not scanned:
            scanned = "进程 stderr"
    if errors:
        return SmokeResult(
            SMOKE_WARN,
            f"进程存活到 {int(timeout)}s 超时，但日志扫描发现错误",
            elapsed_ms=elapsed, log_errors=tuple(errors), log_scan=scanned)
    return SmokeResult(
        SMOKE_PASSED,
        f"进程存活到 {int(timeout)}s 超时，日志无异常",
        elapsed_ms=elapsed, log_scan=scanned or "未找到 Player.log")


__all__ = [
    "SmokeResult",
    "run_staging_smoke",
    "find_player_executable",
    "SMOKE_PASSED", "SMOKE_WARN", "SMOKE_BLOCKED", "SMOKE_UNVERIFIABLE",
]
