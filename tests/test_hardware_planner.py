"""任务三：硬件智能分配打通证据——planner 进入真实启动路径。

修复项（2026-08-13 模块接通检查发现）：plan_allocation 此前只被冒烟
脚本调用，模型启动路径未接入。接入后：用户未显式指定 GPU 层（-1）时，
LocalModelManager（翻译）与 ReviewModelService（审核）启动前用静态档位
规划结论覆盖，运行时回退链继续兜底。
"""
from __future__ import annotations

import hanhua.core.hardware_planner as hw
from hanhua.core.local_model import _planned_gpu_layers


def test_planned_gpu_layers_honors_4to6gb_band(monkeypatch):
    """4~6GB 档：4B 审核拿唯一 GPU 名额，1.8B 翻译 CPU（防 OOM）。"""
    monkeypatch.setattr(
        hw, "probe_hardware",
        lambda: hw.HardwareProfile(gpu_total_gb=6.0, gpu_free_gb=5.0,
                                   ram_gb=32.0))
    assert _planned_gpu_layers(".", "translate") == 0   # 翻译走 CPU
    assert _planned_gpu_layers(".", "review") != 0      # 审核拿 GPU 名额


def test_planned_gpu_layers_full_gpu_on_high_vram(monkeypatch):
    """≥8GB 档：双 GPU 常驻，翻译/审核全层。"""
    monkeypatch.setattr(
        hw, "probe_hardware",
        lambda: hw.HardwareProfile(gpu_total_gb=12.0, gpu_free_gb=8.9,
                                   ram_gb=32.0))
    assert _planned_gpu_layers(".", "translate") == -1
    assert _planned_gpu_layers(".", "review") == -1


def test_planned_gpu_layers_no_gpu_means_cpu(monkeypatch):
    """无 GPU：全 CPU（不白试 GPU 组合）。"""
    monkeypatch.setattr(
        hw, "probe_hardware",
        lambda: hw.HardwareProfile(gpu_total_gb=None, gpu_free_gb=None,
                                   ram_gb=32.0))
    assert _planned_gpu_layers(".", "translate") == 0
    assert _planned_gpu_layers(".", "review") == 0


def test_planned_gpu_layers_probe_failure_returns_none(monkeypatch):
    """探测失败返回 None——调用方回退用户配置 + 运行时回退链。"""

    def _boom():
        raise RuntimeError("探测失败")

    monkeypatch.setattr(hw, "probe_hardware", _boom)
    assert _planned_gpu_layers(".", "translate") is None


def test_plan_allocation_outputs_four_models():
    """plan_allocation 恒输出四模型完整方案（含回退理由）。"""
    plans = hw.simulate(12.0, 8.9, 32.0)
    assert set(plans) == {"translate", "review", "rerank", "embed"}
    # 0.6B×2 恒 CPU（实施计划硬约束）
    assert plans["rerank"].backend == "cpu"
    assert plans["embed"].backend == "cpu"
    assert plans["translate"].rationale and plans["review"].rationale
