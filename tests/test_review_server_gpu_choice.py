# -*- coding: utf-8 -*-
"""审核服务 gpu_choice 映射（环境设置页四模型卡片 2026-08-14）。

ReviewModelService.ensure_running(gpu_choice=...) 的 GPU/CPU 选择：
- auto（缺省）→ hardware_planner 决策（探测失败回退 -1 全层）
- cpu       → gpu_layers=0 强制 CPU
- gpu       → gpu_layers=999 强制全层（llama.cpp clamp 到全部层，
  绕过 planner 对 -1 的接管）
"""
import subprocess
from pathlib import Path

import pytest

from hanhua.core.model_registry import ModelSpec
from hanhua.core.review_server import ReviewModelService


def _make_spec(tmp_path: Path) -> ModelSpec:
    model = tmp_path / "models" / "Qwen3.5-4B-Q4_K_M.gguf"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b"fake-model")
    return ModelSpec(
        name="review", kind="review", path=model, default_ctx=8192,
        default_keep_alive=-1, max_concurrency=1, fixed_cpu=False,
        port=8081, budget_gb=3.0, server_args=("--reasoning", "off"))


class _FakeProc:
    def poll(self):
        return None

    def terminate(self):
        pass

    def wait(self, timeout=10):
        pass

    def kill(self):
        pass


@pytest.fixture
def review_svc(monkeypatch, tmp_path):
    """构造 ReviewModelService：全部外部依赖注入/替换，启动即成功。"""
    spec = _make_spec(tmp_path)

    class _Registry:
        def by_kind(self, _kind):
            return spec

    monkeypatch.setattr(
        "hanhua.core.review_server.ModelRegistry", lambda _dir: _Registry())
    monkeypatch.setattr(
        "hanhua.core.review_server.discover_server",
        lambda _explicit, _app_dir: "llama-server.exe")

    def _no_plan(*_args):
        return None

    monkeypatch.setattr(
        "hanhua.core.hardware_planner.probe_hardware", _no_plan)
    monkeypatch.setattr(
        "hanhua.core.hardware_planner.plan_allocation", _no_plan)

    captured: dict = {}

    def _capture_cmd(server, model_path, *, port, api_key, context_size,
                     gpu_layers, parallel, cache_reuse):
        captured.update(
            gpu_layers=gpu_layers, context_size=context_size, port=port)
        return ["llama-server.exe", "--port", str(port)]

    monkeypatch.setattr(
        "hanhua.core.review_server.build_server_command", _capture_cmd)
    monkeypatch.setattr(
        "hanhua.core.review_server.sha256_of", lambda _p: "hash")

    svc = ReviewModelService(
        tmp_path, process_factory=lambda *_a, **_k: _FakeProc(),
        probe=lambda *_a, **_k: True)
    svc._clear_stale_review_port = lambda _port: None  # noqa: SLF001 测试隔离
    svc._process_factory = lambda *_a, **_k: _FakeProc()
    return svc, captured


def test_review_gpu_choice_cpu_forces_gpu_layers_0(review_svc):
    svc, captured = review_svc
    info = svc.ensure_running(gpu_choice="cpu")
    assert info["port"] == 8081
    assert captured["gpu_layers"] == 0


def test_review_gpu_choice_gpu_forces_full_layers(review_svc):
    svc, captured = review_svc
    svc.ensure_running(gpu_choice="gpu")
    assert captured["gpu_layers"] == 999


def test_review_gpu_choice_auto_falls_back_to_planner(review_svc):
    """auto + 探测失败 → -1（全层，llama.cpp 语义）→ planner 接管。"""
    svc, captured = review_svc
    svc.ensure_running(gpu_choice="auto")
    assert captured["gpu_layers"] == -1


def test_review_gpu_choice_defaults_to_auto(review_svc):
    svc, captured = review_svc
    svc.ensure_running()
    assert captured["gpu_layers"] == -1


# ── 在线 API 端点（2026-08-14：审核在线模式不启动本地 4B） ────────

def test_review_online_cfg_returns_external_endpoint_without_starting(
        monkeypatch, tmp_path):
    """online_cfg 齐全 → ensure_running 直接返回外部端点，零本地启动：
    不探测模型文件、不调 build_server_command、不 spawn 进程。"""
    from hanhua.core.models import ApiConfig
    called = {"spec": 0, "cmd": 0, "spawn": 0}

    class _BoomRegistry:
        def by_kind(self, _kind):
            called["spec"] += 1
            raise RuntimeError("在线模式不应触碰模型注册表")

    monkeypatch.setattr(
        "hanhua.core.review_server.ModelRegistry", lambda _dir: _BoomRegistry())

    def _boom_cmd(*_args, **_kwargs):
        called["cmd"] += 1
        raise AssertionError("在线模式不应构建启动命令")

    monkeypatch.setattr(
        "hanhua.core.review_server.build_server_command", _boom_cmd)

    def _boom_spawn(*_args, **_kwargs):
        called["spawn"] += 1
        raise AssertionError("在线模式不应启动进程")

    svc = ReviewModelService(
        tmp_path, process_factory=_boom_spawn,
        online_cfg=ApiConfig(
            provider="anthropic", base_url="https://api.example.com/",
            api_key="online-key", model="claude-sonnet-4"))
    info = svc.ensure_running(gpu_choice="cpu")
    assert info == {"base_url": "https://api.example.com",
                    "api_key": "online-key", "model": "claude-sonnet-4"}
    assert called == {"spec": 0, "cmd": 0, "spawn": 0}
    # stop() 对在线端点 no-op（不杀任何进程）
    svc.stop()


def test_review_online_cfg_incomplete_falls_back_to_local(
        review_svc, tmp_path):
    """online_cfg 缺 base_url（未配齐）→ 回退本地启动路径（现有行为）。"""
    from hanhua.core.models import ApiConfig
    # 复用 review_svc fixture 的注入环境（registry/探测全 stub），
    # 重新构造缺 base_url 的在线配置实例
    svc2 = ReviewModelService(
        tmp_path, process_factory=lambda *_a, **_k: _FakeProc(),
        probe=lambda *_a, **_k: True,
        online_cfg=ApiConfig(provider="openai", base_url="",
                             api_key="k", model="m"))
    svc2._clear_stale_review_port = lambda _port: None  # noqa: SLF001
    info = svc2.ensure_running(gpu_choice="cpu")
    assert info["port"] == 8081      # 本地启动路径（端口来自 spec）


def test_review_online_chat_uses_configured_model(monkeypatch, tmp_path):
    """在线 chat：请求体 model 用配置的模型名（而非 local 占位）。"""
    from hanhua.core.models import ApiConfig
    sent: dict = {}

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "通过"}}]}

    def _post(url, *, headers, json, timeout, trust_env, verify):
        sent["url"] = url
        sent["model"] = json["model"]
        sent["headers"] = headers
        return _FakeResp()

    monkeypatch.setattr("hanhua.core.review_server.httpx.post", _post)
    svc = ReviewModelService(
        tmp_path, online_cfg=ApiConfig(
            provider="openai", base_url="https://api.example.com/v1",
            api_key="k", model="deepseek-r1"))
    out = svc.chat("你好")
    assert out == "通过"
    assert sent["url"] == "https://api.example.com/v1/chat/completions"
    assert sent["model"] == "deepseek-r1"
    assert sent["headers"]["Authorization"] == "Bearer k"
