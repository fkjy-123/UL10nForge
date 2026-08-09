"""Application-managed llama.cpp runtime for local GGUF translation."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import threading
import time

import httpx

from hanhua.core.models import ApiConfig


class LocalModelError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

    @property
    def status(self) -> str:
        return self.code


def sanitize_exception(exc: BaseException, secrets_to_redact=()) -> dict[str, str | int | None]:
    """Return a bounded diagnostic without credentials or response bodies."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is None:
        status = getattr(exc, "code", None)
    message = " ".join(str(exc).split())
    for secret in secrets_to_redact:
        if secret:
            message = message.replace(str(secret), "<redacted>")
    message = re.sub(r"(?i)\bAuthorization\s*[:=]\s*\S+(?:\s+\S+)?", "<redacted>", message)
    message = re.sub(r"(?i)\bBearer\s+\S+", "Bearer <redacted>", message)
    message = re.sub(r"(https?://)(?:[^/@\s]+@)?([^/?\s]+)(?:/[^?\s]*)?(?:\?\S*)?", r"\1\2", message)
    message = re.sub(r"(?i)\b(?:response\s+)?body\s*[:=].*$", "body: <redacted>", message)
    if "{" in message or "}" in message or "[" in message or "]" in message:
        message = "request failed"
    return {"type": type(exc).__name__, "status": status, "message": message[:240]}


@dataclass(frozen=True)
class LocalRuntimeInfo:
    endpoint: str
    api_key: str
    model: str
    model_path: Path
    server_path: Path
    port: int
    backend: str
    pid: int | None = None
    parallel: int = 1


_RUNTIME_REQUIRED = (
    "llama-server.exe", "llama-server-impl.dll", "llama-common.dll",
    "llama.dll", "ggml.dll", "ggml-base.dll",
)
_CUDA_REQUIRED = (
    "ggml-cuda.dll", "cublas64_13.dll", "cublasLt64_13.dll",
    "cudart64_13.dll",
)
# 前缀缓存 token 数：本地翻译请求的 prompt 前缀（指令文本）完全一致，
# KV 前缀复用可大幅减少 prompt 处理量（零采样差异 → 零质量损失）
_CACHE_REUSE_TOKENS = 512


def validate_runtime_manifest(
        directory: str | Path, *, cuda: bool = True) -> tuple[str, ...]:
    root = Path(directory)
    missing = [name for name in _RUNTIME_REQUIRED if not (root / name).is_file()]
    if not any(root.glob("ggml-cpu-*.dll")):
        missing.append("ggml-cpu-*.dll")
    if cuda:
        missing.extend(name for name in _CUDA_REQUIRED if not (root / name).is_file())
    return tuple(missing)


def _existing_file(value: str | Path, code: str, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise LocalModelError(code, f"{label}不存在或不是文件：{path}")
    return path


def discover_server(explicit: str | Path, app_dir: str | Path) -> Path:
    if str(explicit).strip():
        return _existing_file(explicit, "server_not_found", "llama-server")
    root = Path(app_dir).resolve()
    candidates = (
        root / "runtime" / "llama" / "llama-server.exe",
        root / "llama.cpp" / "build" / "bin" / "Release" / "llama-server.exe",
        root / "llama.cpp" / "build" / "bin" / "llama-server.exe",
        root / "llama.cpp" / "llama-server.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    from_path = shutil.which("llama-server") or shutil.which("llama-server.exe")
    if from_path:
        return Path(from_path).resolve()
    raise LocalModelError(
        "server_not_found",
        "未找到 llama-server.exe；请先运行本地运行时安装脚本或在设置中选择文件。",
    )


def discover_model(explicit: str | Path, app_dir: str | Path) -> Path:
    if str(explicit).strip():
        path = _existing_file(explicit, "model_not_found", "GGUF 模型")
        if path.suffix.casefold() != ".gguf":
            raise LocalModelError("invalid_model", f"本地模型必须是 GGUF 文件：{path}")
        return _validate_gguf(path)
    model_dir = Path(app_dir).resolve() / "models"
    candidates = sorted(
        model_dir.glob("*.gguf"),
        key=lambda path: ("hy-mt2" not in path.name.casefold(), path.name.casefold()),
    )
    if candidates:
        return _validate_gguf(candidates[0].resolve())
    raise LocalModelError(
        "model_not_found", f"models 目录中没有找到 GGUF 模型：{model_dir}")


def _validate_gguf(path: Path) -> Path:
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            header = stream.read(24)
    except OSError as exc:
        raise LocalModelError(
            "invalid_model", f"无法读取 GGUF 模型：{path}（{exc}）") from exc
    if size < 1024 * 1024 or len(header) != 24:
        raise LocalModelError("invalid_model", f"GGUF 模型文件过小或已截断：{path}")
    magic, version, tensor_count, metadata_count = struct.unpack("<4sIQQ", header)
    if (magic != b"GGUF" or version not in {2, 3}
            or tensor_count <= 0 or metadata_count <= 0):
        raise LocalModelError("invalid_model", f"GGUF 头或基础元数据无效：{path}")
    return path


def build_server_command(
        server_path: str | Path, model_path: str | Path, *, port: int,
        api_key: str, context_size: int, gpu_layers: int,
        parallel: int = 1, cache_reuse: int = 0) -> list[str]:
    server = _existing_file(server_path, "server_not_found", "llama-server")
    model = _existing_file(model_path, "model_not_found", "GGUF 模型")
    if not 1 <= int(port) <= 65535:
        raise LocalModelError("invalid_port", f"本地端口无效：{port}")
    if not api_key:
        raise LocalModelError("invalid_token", "本地服务访问 token 不能为空")
    if int(context_size) < 512:
        raise LocalModelError("invalid_context", "上下文长度不能小于 512")
    if int(parallel) < 1:
        raise LocalModelError("invalid_parallel", "本地并发数不能小于 1")
    command = [
        str(server), "--model", str(model), "--host", "127.0.0.1",
        "--port", str(int(port)), "--ctx-size", str(int(context_size)),
        "--n-gpu-layers", str(int(gpu_layers)), "--parallel", str(int(parallel)),
        "--jinja", "--api-key", api_key,
    ]
    if cache_reuse > 0:
        # 前缀缓存：本地每条请求的 prompt 前缀（指令文本）完全相同，
        # 多个并发 slot 复用共享前缀的 KV 计算 → 处理量大幅下降。
        # 旧版 llama-server 不认识该参数会启动失败 → _start_once 自动降级。
        command.extend(["--cache-reuse", str(int(cache_reuse))])
    return command


def resolve_local_parallel(config: ApiConfig, backend: str) -> int:
    # 默认单槽：本地推理服务是多 slot 串行处理，多 slot 的 KV 显存按倍数
    # 占用（n_slots × ctx 的 KV cache），并发请求还会排队。长文本后半段
    # 会让槽位占用时间变长 → 排队 → httpx 超时 → 超时请求仍占用槽位 →
    # 后续请求全部超时（雪崩）。默认 1 保证单条串行、每一条都有完整 GPU
    # 与 KV 显存；显存富余的用户可在设置里手动调高 local_concurrency。
    maximum = 4 if backend == "gpu" else 2
    default = 1
    requested = int(getattr(config, "local_concurrency", 0) or 0)
    return min(maximum, max(1, requested or default))


def choose_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_probe(base_url: str, api_key: str, expected_model: str) -> bool:
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        health = httpx.get(
            base_url.rstrip("/") + "/health",
            headers=headers, timeout=1.5,
        )
        if health.status_code != 200:
            return False
        models = httpx.get(
            base_url.rstrip("/") + "/v1/models",
            headers=headers, timeout=1.5,
        )
        if models.status_code != 200:
            return False
        expected = expected_model.casefold()
        model_ids = [
            str(item.get("id", ""))
            for item in models.json().get("data", [])
            if isinstance(item, dict)
        ]
        return any(
            model_id.casefold() == expected
            or Path(model_id).stem.casefold() == expected
            for model_id in model_ids
        )
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return False


class LocalModelManager:
    """Own exactly one loopback llama-server process for the application."""

    def __init__(
            self, app_dir: str | Path, *, process_factory=None, probe=None,
            sleep=None, token_factory=None, startup_timeout: float = 120.0,
            state_dir: str | Path | None = None):
        self.app_dir = Path(app_dir).resolve()
        self.state_dir = Path(state_dir or app_dir).resolve()
        self._process_factory = process_factory or subprocess.Popen
        self._probe = probe or _http_probe
        self._sleep = sleep or time.sleep
        self._token_factory = token_factory or (
            lambda: secrets.token_urlsafe(24))
        self.startup_timeout = max(1.0, float(startup_timeout))
        self._process = None
        self._log_handle = None
        self._runtime: LocalRuntimeInfo | None = None
        self._signature: tuple | None = None
        self._last_config: ApiConfig | None = None
        self._lock = threading.RLock()
        self._start_lock = threading.Lock()
        self._cancel_start = threading.Event()

    @property
    def runtime(self) -> LocalRuntimeInfo | None:
        with self._lock:
            if self._process is not None and self._process.poll() is not None:
                self._clear_stopped()
            return self._runtime

    def ensure_running(self, config: ApiConfig, cancellation_event=None) -> LocalRuntimeInfo:
        if config.mode != "local":
            raise LocalModelError("invalid_mode", "当前配置不是本地模型模式")
        self._last_config = config
        with self._start_lock:
            self._cancel_start.clear()
            if cancellation_event is not None and cancellation_event.is_set():
                raise LocalModelError("startup_cancelled", "本地模型启动已取消")
            server = discover_server(config.local_server_path, self.app_dir)
            model = discover_model(config.local_model_path, self.app_dir)
            core_missing = validate_runtime_manifest(server.parent, cuda=False)
            if core_missing:
                raise LocalModelError(
                    "runtime_incomplete",
                    "llama.cpp 运行时不完整，缺少：" + "、".join(core_missing),
                )
            signature = (
                server, model, int(config.local_port),
                int(config.local_context_size), int(config.local_gpu_layers),
                int(config.local_concurrency),
            )
            with self._lock:
                if (self._process is not None and self._process.poll() is None
                        and self._runtime is not None
                        and self._signature == signature):
                    return self._runtime
                self._stop_locked()
            requested_layers = int(config.local_gpu_layers)
            cuda_missing = validate_runtime_manifest(server.parent, cuda=True)
            layers_to_try = [
                0 if requested_layers != 0 and cuda_missing else requested_layers
            ]
            if layers_to_try[0] != 0:
                layers_to_try.append(0)
            # 参数组合：优先带前缀缓存（新版 llama-server 支持，KV 复用提速）；
            # 旧版不认识 --cache-reuse 会报错退出 → 降级为不带缓存再试
            attempts: list[tuple[int, int]] = []
            for gpu_layers in layers_to_try:
                attempts.append((gpu_layers, _CACHE_REUSE_TOKENS))
            for gpu_layers in layers_to_try:
                attempts.append((gpu_layers, 0))
            errors: list[str] = []
            for gpu_layers, cache_reuse in attempts:
                if self._cancel_start.is_set() or (cancellation_event is not None and cancellation_event.is_set()):
                    raise LocalModelError(
                        "startup_cancelled", "本地模型启动已取消")
                try:
                    runtime = self._start_once(
                        server, model, config, gpu_layers, cache_reuse,
                        cancellation_event)
                except LocalModelError as exc:
                    with self._lock:
                        self._stop_locked()
                    if exc.code == "startup_cancelled":
                        raise
                    errors.append(str(exc))
                    continue
                with self._lock:
                    if self._cancel_start.is_set() or (cancellation_event is not None and cancellation_event.is_set()):
                        self._stop_locked()
                        raise LocalModelError(
                            "startup_cancelled", "本地模型启动已取消")
                    self._runtime = runtime
                    self._signature = signature
                return runtime
            detail = "；".join(errors) or "未知启动错误"
            raise LocalModelError("startup_failed", f"本地模型启动失败：{detail}")

    def _start_once(
            self, server: Path, model: Path, config: ApiConfig,
            gpu_layers: int, cache_reuse: int,
            cancellation_event=None, *, token_override: str | None = None,
            parallel_override: int | None = None) -> LocalRuntimeInfo:
        port = int(config.local_port) or choose_port()
        token = token_override or self._token_factory()
        parallel = (
            parallel_override
            if parallel_override is not None
            else resolve_local_parallel(
                config, "cpu" if gpu_layers == 0 else "gpu"))
        command = build_server_command(
            server, model, port=port, api_key=token,
            context_size=int(config.local_context_size),
            gpu_layers=gpu_layers, cache_reuse=cache_reuse,
            parallel=parallel,
        )
        log_dir = self.state_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "llama-server.log"
        creationflags = 0
        if os.name == "nt":
            creationflags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        with self._lock:
            self._log_handle = log_path.open(
                "a", encoding="utf-8", errors="replace")
            try:
                process = self._process_factory(
                    command, cwd=str(server.parent), stdout=self._log_handle,
                    stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                    errors="replace", creationflags=creationflags,
                )
            except OSError as exc:
                self._close_log()
                raise LocalModelError(
                    "process_start_failed", f"无法启动 llama-server：{exc}") from exc
            self._process = process
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self._cancel_start.is_set() or (cancellation_event is not None and cancellation_event.is_set()):
                raise LocalModelError(
                    "startup_cancelled", "本地模型启动已取消")
            returncode = process.poll()
            if returncode is not None:
                raise LocalModelError(
                    "server_exited",
                    f"llama-server 提前退出（{returncode}）：{self._log_tail(log_path)}",
                )
            if self._probe(base_url, token, model.stem):
                return LocalRuntimeInfo(
                    endpoint=base_url + "/v1", api_key=token,
                    model=model.stem, model_path=model, server_path=server,
                    port=port, backend="cpu" if gpu_layers == 0 else "gpu",
                    pid=getattr(process, "pid", None),
                    parallel=parallel,
                )
            self._sleep(0.2)
        raise LocalModelError(
            "startup_timeout",
            f"llama-server 在 {self.startup_timeout:g} 秒内未就绪："
            f"{self._log_tail(log_path)}",
        )

    @staticmethod
    def _log_tail(path: Path, limit: int = 2000) -> str:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "无启动日志"
        return text[-limit:].strip() or "无启动日志"

    def restart_conservative(
            self, cancellation_event=None) -> LocalRuntimeInfo | None:
        """OOM/坏状态恢复：用最小显存配置重启（单槽 + CPU 推理 + 无前缀缓存）。

        复用原端口与 token → 翻译客户端连接无需重建。GPU 显存溢出后仍能
        在 CPU 上串行跑完剩余条目；启动失败时抛出原错误（由调用方决定
        放弃或重试）。成功后将 signature 置空，下次 ensure_running 重新
        评估完整配置（显存恢复后自动回到 GPU 全速）。
        """
        config = self._last_config
        runtime = self._runtime
        if config is None or runtime is None:
            return None
        conservative = config
        if int(getattr(config, "local_port", 0) or 0) == 0:
            conservative = replace(config, local_port=runtime.port)
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                self._stop_locked()
        restarted = self._start_once(
            runtime.server_path, runtime.model_path, conservative,
            gpu_layers=0, cache_reuse=0,
            token_override=runtime.api_key, parallel_override=1,
            cancellation_event=cancellation_event,
        )
        with self._lock:
            self._runtime = restarted
            self._signature = None
        return restarted

    def stop(self) -> None:
        self.cancel_start()
        with self._lock:
            self._stop_locked()

    def cancel_start(self) -> None:
        self._cancel_start.set()

    def _stop_locked(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except (subprocess.TimeoutExpired, TimeoutError):
                process.kill()
                process.wait(timeout=5)
        self._clear_stopped()

    def _clear_stopped(self) -> None:
        self._process = None
        self._runtime = None
        self._signature = None
        self._close_log()

    def _close_log(self) -> None:
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None
