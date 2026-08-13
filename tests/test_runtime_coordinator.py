# -*- coding: utf-8 -*-
"""RuntimeCoordinator 统一运行时基座（审计 Phase D，P1-10/11/12）。

覆盖：fixed_cpu 断言、sha256 签名、refcount 复用、签名变化重启、
dead owned 清理、跨实例借用、authenticated probe、端口清场、取消/
超时清理（不留孤儿）、TTL 回收、stop_all、app_dir 单例共享。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading
import time

import pytest

from hanhua.core.local_model import LocalModelError
from hanhua.core.runtime_coordinator import (
    EffectiveRunConfig,
    OwnedProcess,
    RuntimeCoordinator,
    build_effective_config,
    get_coordinator,
    reset_coordinators,
)


# ── 假进程 / 假工厂 / 假探测 ───────────────────────────────────────

class _FakeProc:
    """模拟 subprocess.Popen：alive 直到 terminate/kill。"""

    def __init__(self, pid=4242):
        self.pid = pid
        self.returncode = None
        self._stopped = False

    def poll(self):
        return self.returncode if self._stopped else None

    def terminate(self):
        self._stopped = True
        self.returncode = 0

    def kill(self):
        self._stopped = True
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


class _FakeProcFactory:
    """记录所有启动的进程（acquire 复用断言用）。"""

    def __init__(self):
        self.procs = []

    def __call__(self, cmd, **kwargs):
        proc = _FakeProc(pid=7000 + len(self.procs))
        self.procs.append(proc)
        return proc


def _always_ok_probe(base, api_key, expected_model):
    return True


def _always_fail_probe(base, api_key, expected_model):
    return False


def _cfg(tmp_path, kind="embed", **kw):
    server = tmp_path / "llama-server.exe"
    server.write_bytes(b"")        # build_server_command 校验文件存在
    kw.setdefault("server_path", server)
    kw.setdefault("model_path", tmp_path / "model.gguf")
    if not kw["model_path"].exists():
        kw["model_path"].write_bytes(b"")
    return build_effective_config(kind, source="test", **kw)


# ── 配置工厂：fixed_cpu 断言 + sha256 签名 ─────────────────────────

def test_build_effective_config_forces_fixed_cpu():
    """P1-10：rerank/embed 无论传什么 gpu_layers 一律强制 0。"""
    for kind in ("rerank", "embed"):
        cfg = build_effective_config(
            kind, model_path="m.gguf", server_path="s.exe", gpu_layers=-1)
        assert cfg.gpu_layers == 0
        cfg2 = build_effective_config(
            kind, model_path="m.gguf", server_path="s.exe", gpu_layers=99)
        assert cfg2.gpu_layers == 0
    # 非 fixed_cpu kind 不受限
    cfg3 = build_effective_config(
        "translate", model_path="m.gguf", server_path="s.exe",
        gpu_layers=-1)
    assert cfg3.gpu_layers == -1


def test_signature_changes_with_model_sha256(tmp_path):
    """P1-12：模型文件内容变化 → sha256 变化 → 签名变化（不复用旧实例）。"""
    model = tmp_path / "m.gguf"
    model.write_bytes(b"v1-content")
    cfg1 = build_effective_config(
        "embed", model_path=model, server_path=tmp_path / "s.exe")
    sig1 = cfg1.signature()
    model.write_bytes(b"v2-other-content")
    cfg2 = build_effective_config(
        "embed", model_path=model, server_path=tmp_path / "s.exe")
    assert cfg2.model_sha256 != cfg1.model_sha256
    assert cfg2.signature() != sig1
    # 任一要素变化 → 签名不同
    cfg3 = build_effective_config(
        "embed", model_path=model, server_path=tmp_path / "s.exe",
        ctx=2048)
    assert cfg3.signature() != cfg2.signature()


def test_signature_reproducible(tmp_path):
    model = tmp_path / "m.gguf"
    model.write_bytes(b"stable")
    cfg1 = build_effective_config(
        "embed", model_path=model, server_path=tmp_path / "s.exe")
    cfg2 = build_effective_config(
        "embed", model_path=model, server_path=tmp_path / "s.exe")
    assert cfg1.signature() == cfg2.signature()
    assert len(cfg1.model_sha256) == 64   # 完整 sha256 hex


# ── acquire：复用 / 重启 / 借用 ────────────────────────────────────

def test_acquire_refcount_reuse(tmp_path):
    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory, probe=_always_ok_probe,
        startup_timeout=10.0)
    cfg = _cfg(tmp_path)
    e1 = coord.acquire(cfg)
    e2 = coord.acquire(cfg)
    assert e1["pid"] == e2["pid"]
    assert len(factory.procs) == 1          # 未重复启动
    assert coord._owned["embed"].refcount == 2
    coord.release("embed")
    assert coord._owned["embed"].refcount == 1
    coord.release("embed")
    assert coord._owned["embed"].refcount == 0
    coord.stop_all()


def test_acquire_signature_change_restarts(tmp_path):
    """模型更新（sha256 变）→ 旧实例终止，启动新实例（无进程泄漏）。"""
    model = tmp_path / "m.gguf"
    model.write_bytes(b"v1")
    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory, probe=_always_ok_probe,
        startup_timeout=10.0)
    cfg1 = _cfg(tmp_path, model_path=model)
    e1 = coord.acquire(cfg1)
    model.write_bytes(b"v2-newer")
    cfg2 = _cfg(tmp_path, model_path=model)
    e2 = coord.acquire(cfg2)
    assert e1["pid"] != e2["pid"]
    assert len(factory.procs) == 2
    assert factory.procs[0]._stopped      # 旧实例被终止，未失管
    assert coord._owned["embed"].config.signature() == cfg2.signature()
    coord.stop_all()


def test_acquire_drops_dead_owned(tmp_path):
    """owned 进程已死 → 下次 acquire 清理 stale 引用。"""
    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory, probe=_always_ok_probe,
        startup_timeout=10.0)
    cfg = _cfg(tmp_path)
    e1 = coord.acquire(cfg)
    assert coord._owned["embed"] is not None
    factory.procs[0].terminate()          # 进程被外部杀死
    # drop dead owned 时清 state（指向死进程）→ 无法借用 → 启动新实例
    e2 = coord.acquire(cfg)
    assert e2["pid"] == factory.procs[1].pid
    assert e2["pid"] != e1["pid"]
    assert coord._owned["embed"].proc is factory.procs[1]  # stale 引用已清理
    coord.stop_all()


def test_acquire_borrows_external_same_signature(tmp_path):
    """跨实例复用：state 文件同签名 + probe 通过 → 借用，不启动新进程。"""
    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory, probe=_always_ok_probe,
        startup_timeout=10.0)
    cfg = _cfg(tmp_path)
    ext = OwnedProcess(
        kind="embed", config=cfg, proc=_FakeProc(pid=9001),
        port=cfg.port, api_key="ext-key",
        log_path=tmp_path / "logs" / "x.log")
    coord._save_state(ext)                # 模拟外部实例落盘
    endpoint = coord.acquire(cfg)
    assert endpoint["pid"] is None
    assert endpoint["api_key"] == "ext-key"
    assert len(factory.procs) == 0        # 未启动
    assert coord._owned.get("embed") is None   # 未拥有 → release 无操作
    coord.stop_all()


def test_acquire_state_signature_mismatch_starts_fresh(tmp_path):
    """state 文件签名不同（旧模型）→ 不借用，正常启动新实例。"""
    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory, probe=_always_ok_probe,
        startup_timeout=10.0)
    old = _cfg(tmp_path)
    old_frozen = EffectiveRunConfig(
        kind="embed", model_path=str(tmp_path / "old.gguf"),
        model_sha256="oldhash", server_path=old.server_path,
        port=old.port, ctx=old.ctx, gpu_layers=0, parallel=1)
    ext = OwnedProcess(
        kind="embed", config=old_frozen, proc=_FakeProc(pid=9002),
        port=old.port, api_key="old-key",
        log_path=tmp_path / "logs" / "x.log")
    coord._save_state(ext)
    endpoint = coord.acquire(_cfg(tmp_path))
    assert endpoint["pid"] == factory.procs[0].pid   # 新启动
    assert endpoint["api_key"] != "old-key"
    coord.stop_all()


# ── fixed_cpu acquire 兜底断言 ─────────────────────────────────────

def test_acquire_rejects_gpu_layers_violation(tmp_path):
    coord = RuntimeCoordinator(str(tmp_path), startup_timeout=10.0)
    cfg = EffectiveRunConfig(
        kind="embed", model_path="m", model_sha256="x", server_path="s",
        port=8083, ctx=4096, gpu_layers=1, parallel=1)
    with pytest.raises(LocalModelError, match="固定 CPU"):
        coord.acquire(cfg)


# ── authenticated probe（P1-10：hickory 401 实证场景） ──────────────

def test_http_probe_carries_authorization(monkeypatch):
    from hanhua.core import runtime_coordinator as rc

    calls = []

    class _Resp:
        def __init__(self, status, payload=None):
            self.status_code = status
            self._payload = payload if payload is not None else {}

        def json(self):
            return self._payload

    def fake_get(url, timeout=0, headers=None):
        calls.append((url, headers))
        if url.endswith("/health"):
            return _Resp(200)
        return _Resp(200, {"data": [{"id": "qwen3-embed-0.6b-q8_0"}]})

    monkeypatch.setattr(rc.httpx, "get", fake_get)
    ok = rc.RuntimeCoordinator._http_probe(
        "http://127.0.0.1:8083", "k-abc", "qwen3-embed")
    assert ok is True
    # /health 公开无鉴权；/v1/models 必须携带 Authorization（hickory 401 实证）
    assert len(calls) == 2
    models_call = [h for url, h in calls if url.endswith("/v1/models")]
    assert len(models_call) == 1
    assert models_call[0].get("Authorization") == "Bearer k-abc"

    # 401（未鉴权服务/错误 key）→ False——不允许误判可用
    def fake_401(url, timeout=0, headers=None):
        return _Resp(401)

    monkeypatch.setattr(rc.httpx, "get", fake_401)
    assert rc.RuntimeCoordinator._http_probe(
        "http://127.0.0.1:8083", "k", "m") is False

    # 模型不匹配 → False
    def fake_other_model(url, timeout=0, headers=None):
        if url.endswith("/health"):
            return _Resp(200)
        return _Resp(200, {"data": [{"id": "other-model"}]})

    monkeypatch.setattr(rc.httpx, "get", fake_other_model)
    assert rc.RuntimeCoordinator._http_probe(
        "http://127.0.0.1:8083", "k", "qwen3-embed") is False

    # 网络异常 → False（不抛）
    def fake_raise(url, timeout=0, headers=None):
        raise rc.httpx.HTTPError("conn refused")

    monkeypatch.setattr(rc.httpx, "get", fake_raise)
    assert rc.RuntimeCoordinator._http_probe(
        "http://127.0.0.1:8083", "k", "m") is False


# ── 端口清场（统一强杀策略） ───────────────────────────────────────

def test_clear_port_kills_foreign_owner_only(tmp_path, monkeypatch):
    from hanhua.core import runtime_coordinator as rc

    killed = []
    monkeypatch.setattr(rc, "_port_in_use", lambda p: True)
    monkeypatch.setattr(
        rc.RuntimeCoordinator, "_kill_port_owner",
        staticmethod(lambda p: killed.append(p)))
    coord = rc.RuntimeCoordinator(str(tmp_path))
    cfg = _cfg(tmp_path)
    coord._clear_port(8083, "embed")
    assert killed == [8083]
    # 自己 owned 的进程占用 → 不动（避免误杀）
    coord._owned["embed"] = OwnedProcess(
        kind="embed", config=cfg, proc=_FakeProc(), port=8083,
        api_key="k", log_path=tmp_path / "logs" / "x.log")
    coord._clear_port(8083, "embed")
    assert killed == [8083]
    # 端口未被占用 → 不触发清场
    monkeypatch.setattr(rc, "_port_in_use", lambda p: False)
    coord._clear_port(8084, "embed")
    assert killed == [8083]


# ── 取消 / 超时清理（不留孤儿） ────────────────────────────────────

def test_acquire_cancelled_before_start(tmp_path):
    event = threading.Event()
    event.set()
    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory, probe=_always_ok_probe,
        startup_timeout=10.0)
    with pytest.raises(RuntimeError, match="已取消"):
        coord.acquire(_cfg(tmp_path), cancellation_event=event)
    assert factory.procs == []            # 未启动任何进程


def test_acquire_cancelled_during_startup(tmp_path):
    event = threading.Event()

    class _CancelProbe:
        def __init__(self, event):
            self.event = event
            self.calls = 0

        def __call__(self, base, api_key, expected_model):
            self.calls += 1
            if self.calls == 1:
                self.event.set()
            return False

    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory,
        probe=_CancelProbe(event), startup_timeout=10.0)
    with pytest.raises(RuntimeError, match="已取消"):
        coord.acquire(_cfg(tmp_path), cancellation_event=event)
    assert len(factory.procs) == 1
    assert factory.procs[0]._stopped      # 进程被终止，不留孤儿
    assert coord.endpoints() == {}
    assert not coord._state_file("embed").exists()


def test_acquire_timeout_cleans_up(tmp_path):
    """探测始终失败 → 启动超时 → 终止进程 + 清租约 + 清状态。"""
    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory,
        probe=_always_fail_probe, startup_timeout=10.0)
    with pytest.raises(RuntimeError, match="启动超时"):
        coord.acquire(_cfg(tmp_path))
    assert len(factory.procs) == 1
    assert factory.procs[0]._stopped
    assert coord.endpoints() == {}
    assert not coord._state_file("embed").exists()


def test_acquire_spawn_failure_cleans_state(tmp_path):
    def boom(cmd, **kwargs):
        raise OSError("no such server executable")

    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=boom, probe=_always_ok_probe,
        startup_timeout=10.0)
    with pytest.raises(RuntimeError, match="启动失败"):
        coord.acquire(_cfg(tmp_path))
    assert not coord._state_file("embed").exists()


# ── release / TTL 回收 ─────────────────────────────────────────────

def test_release_zero_ttl_keeps_running(tmp_path):
    """ttl=0（keep-alive -1 语义）→ release 后常驻保留给后续复用。"""
    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory, probe=_always_ok_probe,
        startup_timeout=10.0)
    coord.acquire(_cfg(tmp_path, ttl=0.0))
    coord.release("embed")
    assert "embed" in coord._owned            # 常驻
    assert coord.reap_idle() == 0
    assert len(factory.procs) == 1
    coord.stop_all()


def test_reap_idle_after_ttl(tmp_path):
    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory, probe=_always_ok_probe,
        startup_timeout=10.0)
    coord.acquire(_cfg(tmp_path, ttl=0.05))
    coord.release("embed")
    assert coord.reap_idle() == 0             # 未到 TTL
    time.sleep(0.12)
    assert coord.reap_idle() == 1             # 超 TTL → 回收
    assert coord.endpoints() == {}
    assert factory.procs[0]._stopped
    coord.stop_all()


def test_stop_all_terminates_all_and_closes_handles(tmp_path):
    factory = _FakeProcFactory()
    coord = RuntimeCoordinator(
        str(tmp_path), process_factory=factory, probe=_always_ok_probe,
        startup_timeout=10.0)
    coord.acquire(_cfg(tmp_path, kind="embed"))
    coord.acquire(_cfg(tmp_path, kind="rerank"))
    assert len(factory.procs) == 2
    assert coord.stop_all() == 2
    assert all(p._stopped for p in factory.procs)
    assert coord.endpoints() == {}
    assert len(coord._log_handles) == 0


def test_stop_all_idempotent(tmp_path):
    coord = RuntimeCoordinator(str(tmp_path), startup_timeout=10.0)
    assert coord.stop_all() == 0
    assert coord.stop_all() == 0


# ── 按 app_dir 单例共享 ────────────────────────────────────────────

def test_get_coordinator_singleton_per_app_dir():
    reset_coordinators()
    try:
        a1 = get_coordinator("C:/tmp/coord-singleton")
        a2 = get_coordinator("C:/tmp/coord-singleton")
        b = get_coordinator("C:/tmp/coord-other")
        assert a1 is a2
        assert a1 is not b
        reset_coordinators()
        a3 = get_coordinator("C:/tmp/coord-singleton")
        assert a3 is not a1                 # reset 后重建
    finally:
        reset_coordinators()


def test_services_share_coordinator(tmp_path):
    """EmbeddingService/RerankService 同 app_dir → 共享同一协调器。"""
    reset_coordinators()
    try:
        from hanhua.core.rerank_gate import RerankService
        from hanhua.core.vector_store import EmbeddingService

        app_dir = tmp_path / "shared-app"
        embed = EmbeddingService(app_dir, startup_timeout=20.0)
        rerank = RerankService(app_dir, startup_timeout=30.0)
        assert embed._coord is rerank._coord
        assert embed.startup_timeout == 20.0  # 首建者生效（基座语义）
    finally:
        reset_coordinators()


def test_app_state_close_stops_coordinator(tmp_path):
    """P1-10 退出政策：AppState.close 统一终止审核/重排/嵌入实例。"""
    reset_coordinators()
    try:
        from PySide6.QtWidgets import QApplication
        from hanhua.core.settings import SettingsStore
        from hanhua.ui.app_state import AppState

        QApplication.instance() or QApplication([])
        factory = _FakeProcFactory()
        coord = get_coordinator(
            str(tmp_path), process_factory=factory,
            probe=_always_ok_probe, startup_timeout=10.0)
        coord.acquire(_cfg(tmp_path))       # 模拟 embed 常驻实例
        assert coord.endpoints()
        settings = SettingsStore(tmp_path / "settings.json")
        settings.load()
        state = AppState(tmp_path, settings)
        state.close()
        assert coord.endpoints() == {}      # close → 全部 owned 终止
        assert factory.procs[0]._stopped
    finally:
        reset_coordinators()
