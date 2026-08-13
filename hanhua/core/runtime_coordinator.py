# -*- coding: utf-8 -*-
"""RuntimeCoordinator：四模型统一运行时基座（审计 Phase D，P1-10/11/12）。

背景（P1-10）：review/rerank/embed 各复制一份进程管理，已发生策略漂移：
- review probe 带 Authorization，rerank/embed probe 不带——无鉴权探测在
  带鉴权服务上 401 → 误判「实例不可用」→ 并行 runner 各自重复启动 4B；
  Windows llama-server SO_REUSEADDR 多实例绑同一端口，连接被最新实例
  接收，复用者拿旧 key → Invalid API Key → 审核静默 0 判定（hickory
  2026-08-13 实证）；
- registry 声称 rerank/embed fixed CPU，启动仍 gpu_layers=-1；
- release 丢进程引用，AppState.close 只停翻译模型；
- keep_alive 计划值没有真正落进 llama-server 生命周期；
- review 会按固定端口强杀占用 PID，rerank/embed 没有同等清场策略；
- 取消/超时路径可能留下进程、日志句柄或 runtime state。

本模块统一：EffectiveRunConfig（可复现签名）、端口租约（固定端口 +
被占清场 + 空闲端口兜底）、owned PID + refcount、idle TTL、authenticated
probe（统一带 Authorization）、fixed_cpu 断言（命令构建处 gpu_layers==0）、
取消/超时清理、退出政策（stop_all）、manifest 固定路由（exact path +
sha256，P1-12——不再按文件名模糊匹配排序取第一个）。

EmbeddingService / RerankService 已迁移到本基座（对外 API 不变）；
ReviewModelService / LocalModelManager 复用 effective_signature 增强
签名（模型 sha256 进签名 → 模型文件变化自动不复用旧实例）。

用法：
    coord = RuntimeCoordinator(app_dir)          # 按 app_dir 单例共享
    cfg = build_effective_config("embed", model_path=..., server_path=...)
    endpoint = coord.acquire(cfg, cancellation_event=cancel)
    ... use endpoint["base_url"] / endpoint["api_key"] ...
    coord.release("embed")                       # refcount-1，TTL 后回收
    coord.stop_all()                             # 退出/切项目时统一清理
"""
from __future__ import annotations

import json
import secrets
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .local_model import (
    LocalModelError,
    build_server_command,
    choose_port,
    sha256_of,
)
from .model_registry import DEFAULT_PORTS, DEFAULT_CTX

_RUNTIME_STATE_PREFIX = "coord_runtime_"


# ── 生效配置（P1-11 统一：CLI override > settings > defaults） ─────

@dataclass(frozen=True)
class EffectiveRunConfig:
    """一次运行的完整生效配置——快照可复现（写报告/审计用）。"""
    kind: str                        # translate/review/rerank/embed
    model_path: str                  # exact path（manifest 固定路由）
    model_sha256: str                # 模型文件 sha256（P1-12）
    server_path: str
    port: int
    ctx: int
    gpu_layers: int                  # fixed_cpu 断言：rerank/embed == 0
    parallel: int
    cache_reuse: int = 0
    backend: str = "cpu"
    extra_args: tuple = ()           # --embeddings / --rerank / --reasoning off
    ttl: float = 0.0                 # idle TTL 秒；0 = 常驻（keep-alive -1）
    probe_auth: bool = True          # authenticated probe（统一开启）
    source: str = "default"          # 配置来源（cli/settings/default）

    def signature(self) -> tuple:
        """可复现签名：任一要素变化 → 不复用旧实例（自动重启）。"""
        return (
            self.kind, str(self.server_path), str(self.model_path),
            self.model_sha256, int(self.port), int(self.ctx),
            int(self.gpu_layers), int(self.parallel), int(self.cache_reuse),
            str(self.backend), tuple(self.extra_args),
        )

    def summary(self) -> str:
        return (f"{self.kind} model={Path(self.model_path).name}"
                f"(sha256={self.model_sha256[:8]}…) ctx={self.ctx}"
                f" layers={self.gpu_layers} par={self.parallel}"
                f" port={self.port} ttl={self.ttl}s [{self.source}]")


def build_effective_config(
        kind: str, *, model_path: str | Path, server_path: str | Path,
        port: int | None = None, ctx: int | None = None,
        gpu_layers: int | None = None, parallel: int = 1,
        cache_reuse: int = 0, extra_args: tuple = (),
        ttl: float = 0.0, backend: str = "cpu",
        source: str = "default") -> EffectiveRunConfig:
    """统一配置工厂：端口/ctx 缺省取 registry 模板值（defaults 层）。

    P1-10 fixed_cpu 断言在此落地：rerank/embed（registry fixed_cpu=True）
    无论调用方传什么 gpu_layers，一律强制 0——断言发生在命令构建之前，
    杜绝「声称固定 CPU 启动却 gpu_layers=-1」的漂移。
    """
    if kind in ("rerank", "embed"):
        gpu_layers = 0
    return EffectiveRunConfig(
        kind=kind,
        model_path=str(Path(model_path).resolve()),
        model_sha256=sha256_of(model_path),
        server_path=str(Path(server_path).resolve()),
        port=int(port if port is not None else DEFAULT_PORTS.get(kind, 8080)),
        ctx=int(ctx if ctx is not None else DEFAULT_CTX.get(kind, 4096)),
        gpu_layers=int(gpu_layers if gpu_layers is not None else -1),
        parallel=int(max(1, parallel)),
        cache_reuse=int(max(0, cache_reuse)),
        backend=backend, extra_args=tuple(extra_args),
        ttl=float(ttl), probe_auth=True, source=source)


# ── 端口租约（四 kind 互不撞端口 + 统一清场） ──────────────────────

def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", int(port)))
            return False
        except OSError:
            return True


class PortLease:
    """进程内端口租约表：固定端口优先，被占 → 空闲端口兜底。

    kind 级联（acquire 分配后该 kind 的后续请求同端口）；release 归还
    固定端口判定。四 kind 的分配互不干扰（同一协调器共享本表）。
    """

    def __init__(self, default_ports: dict | None = None):
        self._defaults = dict(default_ports or DEFAULT_PORTS)
        self._assigned: dict[str, int] = {}
        self._lock = threading.RLock()

    def reserve(self, kind: str) -> int:
        with self._lock:
            if kind in self._assigned:
                return self._assigned[kind]
            fixed = self._defaults.get(kind)
            if fixed and not _port_in_use(fixed):
                self._assigned[kind] = fixed
                return fixed
            port = choose_port()
            self._assigned[kind] = port
            return port

    def release(self, kind: str, port: int) -> None:
        with self._lock:
            if self._assigned.get(kind) == int(port):
                self._assigned.pop(kind, None)


# ── owned 进程（refcount + idle TTL） ──────────────────────────────

@dataclass
class OwnedProcess:
    kind: str
    config: EffectiveRunConfig
    proc: subprocess.Popen
    port: int
    api_key: str
    log_path: Path
    refcount: int = 1
    idle_since: float = 0.0          # refcount==0 时刻（TTL 计时起点）

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    @property
    def endpoint(self) -> dict:
        base = f"http://127.0.0.1:{self.port}"
        return {
            "base_url": base + "/v1",
            "api_key": self.api_key,
            "port": self.port,
            "pid": self.proc.pid,
            "model": self.config.model_path,
            "kind": self.kind,
        }


# ── 统一协调器 ────────────────────────────────────────────────────

class RuntimeCoordinator:
    """四模型统一运行时：acquire（复用→启动）/ release（refcount+TTL）/
    stop_all（退出政策）/ 取消与超时清理。

    线程安全（RLock）；同 app_dir 的多个服务实例共享同一协调器
    （模块级缓存 _get_coordinator），端口租约与 owned 进程统一。
    """

    def __init__(self, app_dir: str | Path, *,
                 process_factory=None, probe=None, sleep=None,
                 token_factory=None, startup_timeout: float = 180.0):
        self.app_dir = Path(app_dir).resolve()
        self._process_factory = process_factory or subprocess.Popen
        self._probe = probe or self._http_probe
        self._sleep = sleep or time.sleep
        self._token_factory = token_factory or (
            lambda: secrets.token_urlsafe(24))
        self.startup_timeout = max(10.0, float(startup_timeout))
        self._owned: dict[str, OwnedProcess] = {}
        self._ports = PortLease(DEFAULT_PORTS)
        self._lock = threading.RLock()
        self._log_handles: set = set()

    # ── authenticated probe（统一带 Authorization，P1-10） ──────────
    @staticmethod
    def _http_probe(base: str, api_key: str, expected_model: str) -> bool:
        """探测实例：/health 200 且 /v1/models 含目标模型。

        必须携带 Authorization 头——hickory 实证：不带 key 的探测对带
        鉴权的 llama-server 返回 401 → 误判不可用 → 重复启动 → 端口
        多实例混乱。统一基座后四个 kind 全部带鉴权探测。
        """
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            health = httpx.get(base + "/health", timeout=2)
            if health.status_code != 200:
                return False
            models = httpx.get(base + "/v1/models", timeout=2,
                               headers=headers)
            if models.status_code != 200:
                return False
            ids = [str(m.get("id", ""))
                   for m in models.json().get("data", [])]
            return any(expected_model.casefold() in i.casefold()
                       for i in ids)
        except httpx.HTTPError:
            return False

    # ── 跨实例运行时状态（coord_runtime_<kind>.json） ──────────────
    def _state_file(self, kind: str) -> Path:
        return self.app_dir / f"{_RUNTIME_STATE_PREFIX}{kind}.json"

    def _save_state(self, owned: OwnedProcess) -> None:
        try:
            self._state_file(owned.kind).write_text(
                json.dumps({
                    "port": int(owned.port),
                    "api_key": owned.api_key,
                    "model": owned.config.model_path,
                    "signature": [str(item) for item in
                                  owned.config.signature()],
                    "sha256": owned.config.model_sha256,
                    "effective": owned.config.summary(),
                    "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # 状态文件只是加速复用，失败不影响启动

    def _load_state(self, kind: str) -> dict | None:
        try:
            if not self._state_file(kind).is_file():
                return None
            data = json.loads(self._state_file(kind).read_text(
                encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(
                    data.get("port"), int):
                return None
            return data
        except (OSError, ValueError):
            return None

    def _clear_state(self, kind: str) -> None:
        try:
            self._state_file(kind).unlink(missing_ok=True)
        except OSError:
            pass

    # ── 端口清场（统一：review 的强杀策略迁移到基座） ──────────────
    def _clear_port(self, port: int, kind: str) -> None:
        """固定端口被「非本协调器 owned」进程占用 → 终止回收。

        Windows llama-server SO_REUSEADDR 多实例绑同端口的实证：残留
        进程会导致新实例连接被劫持。owned 进程自己管理，不清。
        """
        if not _port_in_use(port):
            return
        with self._lock:
            existing = self._owned.get(kind)
            if existing is not None and existing.port == int(port):
                return  # 自己的进程占用 → 不动
        self._kill_port_owner(port)

    @staticmethod
    def _kill_port_owner(port: int) -> None:
        """按监听端口终止占用进程（Windows netstat + taskkill）。"""
        if sys.platform != "win32":
            return
        try:
            import subprocess as _sp
            out = _sp.check_output(
                ["netstat", "-ano"], text=True, errors="replace")
            pids = set()
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "TCP" \
                        and parts[1].endswith(f":{int(port)}") \
                        and parts[3] == "LISTENING":
                    pids.add(parts[4])
            for pid in pids:
                if pid.isdigit() and int(pid) > 0:
                    _sp.run(["taskkill", "/PID", pid, "/F"],
                            capture_output=True)
        except (OSError, subprocess.SubprocessError):
            pass

    # ── 主入口 ────────────────────────────────────────────────────
    def acquire(self, config: EffectiveRunConfig, *,
                cancellation_event=None) -> dict:
        """确保 config.signature() 对应的实例在运行，返回 endpoint dict。

        1) 本协调器已拥有同签名存活进程 → refcount+1 复用；
        2) 跨实例复用：state 文件同签名 → authenticated probe 通过则复用；
        3) 否则启动：fixed_cpu 断言 → 端口清场 → 命令构建 → 启动 →
           探测成功落盘；失败/取消 → 终止进程 + 清租约（不留孤儿）。

        返回 {"base_url", "api_key", "port", "pid", "model", "kind"}。
        """
        cfg = config
        # P1-10 fixed_cpu 断言（命令构建处）：registry 固定 CPU 的 kind
        # 绝不允许 gpu_layers != 0（工厂已强制，此处兜底防误用）
        if cfg.kind in ("rerank", "embed") and cfg.gpu_layers != 0:
            raise LocalModelError(
                "fixed_cpu_violation",
                f"{cfg.kind} 固定 CPU：不允许 gpu_layers={cfg.gpu_layers}")
        with self._lock:
            owned = self._owned.get(cfg.kind)
            if (owned is not None and owned.alive
                    and owned.config.signature() == cfg.signature()):
                owned.refcount += 1
                owned.idle_since = 0.0
                return dict(owned.endpoint)
            if owned is not None:
                # 签名变化（模型更新/端口变化）或进程已死 → 旧实例失管，
                # 终止回收；否则新实例会覆盖 _owned 造成进程泄漏
                self._drop_owned(cfg.kind)
        # 跨实例复用（同签名 + probe 通过）
        state = self._load_state(cfg.kind)
        if state is not None and tuple(state.get("signature", ())) \
                == tuple(str(item) for item in cfg.signature()):
            base = f"http://127.0.0.1:{int(state['port'])}"
            if self._probe(base, str(state.get("api_key", "")),
                           Path(cfg.model_path).stem):
                with self._lock:
                    self._owned.pop(cfg.kind, None)  # 借用外部实例
                return {
                    "base_url": base + "/v1",
                    "api_key": str(state.get("api_key", "")),
                    "port": int(state["port"]),
                    "pid": None,
                    "model": cfg.model_path,
                    "kind": cfg.kind,
                }
        if cancellation_event is not None and cancellation_event.is_set():
            raise RuntimeError(f"{cfg.kind} 服务启动已取消")
        # 启动新实例
        port = self._ports.reserve(cfg.kind)
        self._clear_port(port, cfg.kind)
        api_key = self._token_factory()
        cmd = build_server_command(
            cfg.server_path, cfg.model_path, port=port,
            api_key=api_key, context_size=cfg.ctx,
            gpu_layers=cfg.gpu_layers, parallel=cfg.parallel,
            cache_reuse=cfg.cache_reuse)
        cmd.extend(cfg.extra_args)
        log_path = self.app_dir / "logs" / f"{cfg.kind}-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handle = log_path.open("a", encoding="utf-8", errors="replace")
        creationflags = 0
        if sys.platform == "win32":
            creationflags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP",
                                       0))
        try:
            proc = self._process_factory(
                cmd, cwd=str(Path(cmd[0]).parent), stdout=handle,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", creationflags=creationflags)
        except OSError as exc:
            handle.close()
            self._clear_state(cfg.kind)
            raise RuntimeError(f"{cfg.kind} 服务启动失败：{exc}") from exc
        owned = OwnedProcess(
            kind=cfg.kind, config=cfg, proc=proc, port=port,
            api_key=api_key, log_path=log_path)
        with self._lock:
            self._owned[cfg.kind] = owned
            self._log_handles.add(handle)
        # 探测等待（取消/退出超时 → 清理不留孤儿）
        deadline = time.monotonic() + self.startup_timeout
        base = f"http://127.0.0.1:{port}"
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                tail = self._log_tail(log_path)
                with self._lock:
                    self._drop_owned(cfg.kind)
                raise RuntimeError(
                    f"{cfg.kind} 服务异常退出（{proc.returncode}）："
                    f"{tail[-400:]}")
            if cancellation_event is not None \
                    and cancellation_event.is_set():
                self.stop(cfg.kind)
                raise RuntimeError(f"{cfg.kind} 服务启动已取消")
            if self._probe(base, api_key, Path(cfg.model_path).stem):
                self._save_state(owned)
                return dict(owned.endpoint)
            self._sleep(0.5)
        # 启动超时：终止进程 + 清租约 + 清状态
        self.stop(cfg.kind)
        raise RuntimeError(f"{cfg.kind} 服务启动超时（{self.startup_timeout:.0f}s）")

    def release(self, kind: str) -> None:
        """refcount-1；归零后按 TTL 回收（0 = 常驻保留）。"""
        with self._lock:
            owned = self._owned.get(kind)
            if owned is None:
                return  # 借用外部实例（本协调器未拥有）→ 无操作
            owned.refcount = max(0, owned.refcount - 1)
            if owned.refcount == 0:
                owned.idle_since = time.monotonic()
                if owned.config.ttl <= 0.0:
                    return  # 常驻（keep-alive -1 语义）：保留给后续复用
                if time.monotonic() - owned.idle_since \
                        >= owned.config.ttl:
                    self._drop_owned(kind)

    def reap_idle(self) -> int:
        """回收所有超 TTL 的空闲实例（定时器/退出前调用）。返回终止数。"""
        now = time.monotonic()
        stopped = 0
        with self._lock:
            for kind, owned in list(self._owned.items()):
                if (owned.refcount == 0 and owned.config.ttl > 0.0
                        and now - owned.idle_since >= owned.config.ttl):
                    self._drop_owned(kind)
                    stopped += 1
        return stopped

    def stop(self, kind: str) -> None:
        """终止指定 kind 的 owned 进程（取消/超时/显式关闭）。"""
        with self._lock:
            self._drop_owned(kind)

    def stop_all(self) -> int:
        """终止全部 owned 进程（退出政策，P1-10：AppState.close 统一）。"""
        stopped = 0
        with self._lock:
            for kind in list(self._owned.keys()):
                self._drop_owned(kind)
                stopped += 1
        for handle in list(self._log_handles):
            try:
                handle.close()
            except OSError:
                pass
        self._log_handles.clear()
        return stopped

    def endpoints(self) -> dict:
        """当前存活实例摘要（审计/状态报告）。"""
        with self._lock:
            return {
                kind: {**owned.endpoint, "refcount": owned.refcount,
                       "ttl": owned.config.ttl,
                       "sha256": owned.config.model_sha256[:8],
                       "signature": list(owned.config.signature())}
                for kind, owned in self._owned.items() if owned.alive
            }

    # ── 内部 ──────────────────────────────────────────────────────
    def _drop_owned(self, kind: str) -> None:
        """终止 owned 进程 + 清状态/日志句柄（不抛异常）。"""
        owned = self._owned.pop(kind, None)
        if owned is None:
            return
        try:
            if owned.proc.poll() is None:
                owned.proc.terminate()
                try:
                    owned.proc.wait(timeout=8.0)
                except subprocess.TimeoutExpired:
                    owned.proc.kill()
        except OSError:
            pass
        self._clear_state(kind)

    @staticmethod
    def _log_tail(path: Path, limit: int = 2000) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[-limit:]
        except OSError:
            return ""


# ── 按 app_dir 的共享协调器（同库目录多服务共享端口租约） ──────────

_COORDINATORS: dict[str, RuntimeCoordinator] = {}
_COORDINATORS_LOCK = threading.Lock()


def get_coordinator(app_dir: str | Path, **kwargs) -> RuntimeCoordinator:
    """同 app_dir 返回同一协调器实例（端口租约/owned 进程共享）。

    测试可用 kwargs 注入 process_factory/probe（首建者生效）。"""
    key = str(Path(app_dir).resolve())
    with _COORDINATORS_LOCK:
        coord = _COORDINATORS.get(key)
        if coord is None:
            coord = RuntimeCoordinator(key, **kwargs)
            _COORDINATORS[key] = coord
        return coord


def reset_coordinators() -> None:
    """清空共享协调器缓存（测试用）。"""
    with _COORDINATORS_LOCK:
        for coord in _COORDINATORS.values():
            coord.stop_all()
        _COORDINATORS.clear()
