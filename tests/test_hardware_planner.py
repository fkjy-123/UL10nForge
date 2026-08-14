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


# ── 部分卸载（2026-08-14 自动档语义：优先 GPU，塞不下分部分到 CPU）──

def _partial_est(_model_path=None, model_gb=3.0, layers=36, kv_gb=0.5,
                 compute_gb=1.0, **_ignored):
    """36 层 3GB 模型的显存预估 stub（review 档位规模）。"""
    from hanhua.core.vram import VramEstimate
    return VramEstimate(
        model_gb=model_gb, kv_gb=kv_gb, kv_per_slot_gb=kv_gb,
        compute_gb=compute_gb, total_gb=model_gb + kv_gb + compute_gb,
        layers=layers)


def _partial_plans(monkeypatch, tmp_path, free_gb, est_fn=None):
    from hanhua.core.hardware_planner import (
        HardwareProfile, ModelRegistry, plan_allocation)
    monkeypatch.setattr(
        "hanhua.core.hardware_planner.estimate_vram",
        est_fn or _partial_est)
    registry = ModelRegistry(tmp_path)
    return plan_allocation(
        HardwareProfile(gpu_total_gb=free_gb + 4.0, gpu_free_gb=free_gb,
                        ram_gb=32.0), registry)


def test_partial_offload_when_gpu_cannot_fit_full(monkeypatch, tmp_path):
    """全量放不下（4.5G 预估 > 4.0×0.9）但能容纳 ≥50% 层 →
    部分卸载 25/36 层 GPU、其余 CPU（keep_alive 按需防挤压）。"""
    plans = _partial_plans(monkeypatch, tmp_path, free_gb=4.0)
    review = plans["review"]
    assert review.backend == "gpu"
    assert 0 < review.gpu_layers < 36
    assert review.gpu_layers == 25      # (3.6-1.5)/(3.0/36) = 25 层
    assert review.keep_alive == 0
    assert "部分卸载" in review.rationale
    # 翻译与审核共存：review 部分卸载后 translate 拿不到显存 → CPU
    assert plans["translate"].backend == "cpu"


def test_partial_offload_abandons_below_half_layers(monkeypatch, tmp_path):
    """只能容纳 <50% 层（14 层）→ 收益太小 → 全 CPU。"""
    plans = _partial_plans(monkeypatch, tmp_path, free_gb=3.0)
    assert plans["review"].backend == "cpu"
    assert plans["review"].gpu_layers == 0


def test_partial_offload_abandons_when_overhead_exceeds_budget(
        monkeypatch, tmp_path):
    """连 KV+计算缓冲都放不下（budget 1.08G < 1.5G）→ 全 CPU。"""
    plans = _partial_plans(monkeypatch, tmp_path, free_gb=1.2)
    assert plans["review"].backend == "cpu"


def test_partial_offload_abandons_when_layers_unknown(monkeypatch, tmp_path):
    """层数未知（几何读不出来 layers=0）→ 无法分摊 → 全 CPU。"""
    plans = _partial_plans(
        monkeypatch, tmp_path, free_gb=4.0,
        est_fn=lambda *_a, **_k: _partial_est(layers=0))
    assert plans["review"].backend == "cpu"


def test_partial_offload_translate_full_gpu_kept_when_room(
        monkeypatch, tmp_path):
    """6GB 档：review 全量 GPU 放得下（4.5 ≤ 5.4）→ 常驻全层；
    translate 剩余空间也足够（3.0 预估 ≤ 5.4-4.5=0.9？放不下）→
    部分卸载或 CPU——断言不会出现「双全量超卖」。"""
    plans = _partial_plans(monkeypatch, tmp_path, free_gb=6.0)
    review = plans["review"]
    assert review.backend == "gpu" and review.gpu_layers == -1
    assert review.keep_alive == -1
    translate = plans["translate"]
    assert translate.backend == "cpu"      # 4.5 被 review 占后无余量
