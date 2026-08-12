"""阶段 0 T0-2/T0-5 测试：模型注册表 + 硬件智能分配器。

验收（实施计划 T0-5）：六档硬件（无 GPU/4/6/8/12GB/低内存）模拟均
得出可运行方案；回退路径触发正确；0.6B×2 恒为 CPU。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hanhua.core.hardware_planner import (
    HardwareProfile,
    ModelPlan,
    plan_allocation,
    simulate,
)
from hanhua.core.model_registry import (
    DEFAULT_CTX,
    DEFAULT_PORTS,
    ModelRegistry,
    build_specs,
)

APP_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registry() -> ModelRegistry:
    return ModelRegistry(APP_DIR)


# ── 注册表 ──────────────────────────────────────────────────────────
def test_registry_registers_four_models(registry: ModelRegistry):
    assert len(registry.all()) == 4
    kinds = {spec.kind for spec in registry.all()}
    assert kinds == {"translate", "review", "rerank", "embed"}


def test_registry_kinds_and_ports(registry: ModelRegistry):
    for kind, port in DEFAULT_PORTS.items():
        assert registry.by_kind(kind).port == port


def test_registry_missing_reporting(registry: ModelRegistry):
    # 缺失模型 = 文件不存在；构造时不要求 models 目录存在
    empty = ModelRegistry(Path(APP_DIR) / "no_such_dir_xyz")
    assert empty.missing
    assert not empty.all_ready
    assert len(empty.missing) == 4


def test_spec_defaults(registry: ModelRegistry):
    for spec in registry.all():
        assert spec.default_ctx == DEFAULT_CTX[spec.kind]
        assert spec.max_concurrency >= 1
        assert spec.path.suffix == ".gguf"


def test_rerank_embed_fixed_cpu_flags(registry: ModelRegistry):
    assert registry.by_kind("rerank").fixed_cpu
    assert registry.by_kind("embed").fixed_cpu
    assert not registry.by_kind("translate").fixed_cpu
    assert not registry.by_kind("review").fixed_cpu


# ── 六档硬件模拟 ────────────────────────────────────────────────────
def test_no_gpu_all_cpu(registry: ModelRegistry):
    plans = plan_allocation(HardwareProfile(None, None, 16.0), registry)
    for plan in plans.values():
        assert plan.backend == "cpu"
        assert plan.gpu_layers == 0
    # 无 GPU 时审核模型按需加载（300s 窗口），避免反复读 3GB
    assert plans["review"].keep_alive == 300


def test_low_ram_all_cpu_on_demand(registry: ModelRegistry):
    # 低内存（2GB RAM，无 GPU）：全 CPU 按需 + 并发 1，可运行但省内存
    plans = plan_allocation(HardwareProfile(None, None, 2.0), registry)
    for plan in plans.values():
        assert plan.backend == "cpu"
        assert plan.parallel == 1
        assert plan.keep_alive == 0
    assert plans["rerank"].keep_alive == 0


def test_4gb_tier_review_gpu_translate_cpu(registry: ModelRegistry):
    plans = plan_allocation(HardwareProfile(4.0, 4.0, 16.0), registry)
    assert plans["review"].backend == "gpu"
    assert plans["translate"].backend == "cpu"
    # 显存紧张档：4B 降 ctx/并发（审核单条逐条审不需并行槽）
    assert plans["review"].ctx <= 4096
    assert plans["review"].parallel == 1
    # 0.6B×2 恒 CPU
    assert plans["rerank"].backend == "cpu"
    assert plans["embed"].backend == "cpu"


def test_6gb_tier_review_resident_translate_ondemand(registry: ModelRegistry):
    plans = plan_allocation(HardwareProfile(6.0, 6.0, 16.0), registry)
    assert plans["review"].backend == "gpu"
    assert plans["review"].keep_alive == -1
    assert plans["translate"].backend == "cpu"   # 6GB 放不下双模型
    assert plans["rerank"].backend == "cpu"


def test_8gb_tier_both_gpu(registry: ModelRegistry):
    plans = plan_allocation(HardwareProfile(8.0, 8.0, 16.0), registry)
    assert plans["review"].backend == "gpu"
    assert plans["translate"].backend == "gpu"
    assert plans["review"].keep_alive == -1
    assert plans["translate"].keep_alive == -1


def test_12gb_tier_both_resident(registry: ModelRegistry):
    plans = plan_allocation(HardwareProfile(12.0, 12.0, 16.0), registry)
    assert plans["review"].backend == "gpu"
    assert plans["translate"].backend == "gpu"
    assert plans["review"].keep_alive == -1
    assert plans["translate"].keep_alive == -1


def test_zero_free_vram_falls_back_cpu(registry: ModelRegistry):
    # 显存耗尽（free=0.1GB）→ 全部 CPU，不崩溃
    plans = plan_allocation(HardwareProfile(4.0, 0.1, 16.0), registry)
    for plan in plans.values():
        assert plan.backend == "cpu"


def test_simulate_six_tiers_all_runnable():
    """六档硬件（无 GPU/4/6/8/12GB/低内存）均得出可运行方案。"""
    tiers = [
        (None, None, 16.0),      # 无 GPU
        (4.0, 4.0, 16.0),        # 4GB 卡
        (6.0, 6.0, 16.0),        # 6GB 卡
        (8.0, 8.0, 16.0),        # 8GB 卡
        (12.0, 12.0, 16.0),      # 12GB 卡
        (None, None, 2.0),       # 低内存（无 GPU 2GB RAM）
    ]
    for total, free, ram in tiers:
        plans = simulate(total, free, ram, app_dir=APP_DIR)
        assert set(plans) == {"translate", "review", "rerank", "embed"}
        for plan in plans.values():
            assert isinstance(plan, ModelPlan)
            assert plan.ctx >= 512
            assert plan.parallel >= 1
            assert plan.gpu_layers in (0, -1)
            assert plan.keep_alive in (0, -1, 300)


def test_rerank_embed_never_gpu():
    """0.6B×2 恒为 CPU（跨六档硬件的硬约束）。"""
    tiers = [(None, None, 16.0), (4.0, 4.0, 16.0), (6.0, 6.0, 16.0),
             (8.0, 8.0, 16.0), (12.0, 12.0, 16.0), (None, None, 2.0)]
    for total, free, ram in tiers:
        plans = simulate(total, free, ram, app_dir=APP_DIR)
        assert plans["rerank"].backend == "cpu"
        assert plans["embed"].backend == "cpu"


def test_huge_vram_keeps_plan_sane():
    """超大显存（假想 24GB）→ 翻译/审核 GPU 常驻，ctx 不溢出；
    0.6B×2 仍恒 CPU。"""
    plans = simulate(24.0, 24.0, 32.0, app_dir=APP_DIR)
    assert plans["translate"].backend == "gpu"
    assert plans["review"].backend == "gpu"
    for plan in plans.values():
        assert plan.keep_alive == -1
        assert plan.ctx <= 8192
    assert plans["rerank"].backend == "cpu"
    assert plans["embed"].backend == "cpu"


def test_plans_are_immutable(registry: ModelRegistry):
    plans = plan_allocation(HardwareProfile(12.0, 12.0, 16.0), registry)
    plan = plans["translate"]
    with pytest.raises(Exception):
        plan.backend = "cpu"  # type: ignore[misc]
