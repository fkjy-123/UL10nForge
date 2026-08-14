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
