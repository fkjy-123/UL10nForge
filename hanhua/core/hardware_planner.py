"""硬件智能分配器（阶段 0 T0-5）：探测本机 GPU/内存 → 输出四模型分配方案。

决策要点（实施计划 §4.4）：
- 0.6B×2（rerank/embed）恒为 CPU：毫秒~秒级任务，占 GPU 无收益
- 4B 审核 / 1.8B 翻译按可用显存决策表分配：
  无 GPU → 全 CPU；4~6GB → 4B GPU 按需 + 1.8B CPU；6~8GB → 4B 常驻 +
  1.8B 按需；≥8GB → 全常驻
- 显存预估（vram.estimate_vram）≤ 可用显存 90% 才上 GPU；超限降
  ctx/并发再试，仍超则 CPU（GPU 加载失败的回退由 LocalModelManager
  现有 cuda_missing 回退链承接，本模块只做静态规划）
- 常驻/按需用 llama.cpp --keep-alive 实现（-1 常驻 / 0 即用即卸），
  不做手动杀进程
"""
from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from hanhua.core.model_registry import ModelKind, ModelRegistry
from hanhua.core.vram import estimate_vram, gpu_memory_info

# 可用显存安全线：预估占用 ≤ free × 90% 才允许上 GPU
_GPU_FREE_RATIO = 0.9
# 显存紧张档位（GB）：决策表 4~6GB 档 —— 4B 只能按需 + 降 ctx/并发
_TIGHT_VRAM_GB = 6.0
# 低系统内存保护（GB）：内存不足时全部按需加载，避免多模型常驻挤爆 RAM
_LOW_RAM_GB = 8.0
# 审核/翻译按需加载后的空闲卸载宽限（秒）：批次间反复加载 3GB 模型
# 代价高，给 300 秒窗口复用
_OND_DEMAND_KEEP_ALIVE_S = 300


@dataclass(frozen=True)
class HardwareProfile:
    """本机硬件快照（单位 GiB；None 表示探测不到）。"""
    gpu_total_gb: float | None = None
    gpu_free_gb: float | None = None
    ram_gb: float | None = None


def _system_ram_gb() -> float | None:
    """系统物理内存（GiB）：Windows GlobalMemoryStatusEx / Unix sysconf；
    探测失败返回 None（调用方按未知处理，不做低内存保护降级）。"""
    try:
        if os.name == "nt":
            class _MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            status = _MemoryStatusEx()
            status.dwLength = ctypes.sizeof(_MemoryStatusEx)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.ullTotalPhys / 2**30
            return None
        total = os.sysconf("SC_PHYS_PAGES")
        page = os.sysconf("SC_PAGE_SIZE")
        if total > 0 and page > 0:
            return total * page / 2**30
        return None
    except (OSError, AttributeError, ValueError, TypeError):
        return None


def probe_hardware() -> HardwareProfile:
    """探测本机硬件：GPU 显存（nvidia-smi）+ 系统内存。"""
    gpu = gpu_memory_info()
    return HardwareProfile(
        gpu_total_gb=gpu[0] if gpu else None,
        gpu_free_gb=gpu[1] if gpu else None,
        ram_gb=_system_ram_gb(),
    )


@dataclass(frozen=True)
class ModelPlan:
    """单个模型的运行时分配方案（hardware_planner 输出）。"""
    name: str                       # translate/review/rerank/embed
    kind: ModelKind
    backend: Literal["cpu", "gpu"]
    gpu_layers: int                 # -1 全部层 / 0 CPU
    ctx: int                        # --ctx-size
    keep_alive: int                 # --keep-alive（-1 常驻 / 0 即用即卸）
    parallel: int                   # --parallel
    rationale: str                  # 决策理由（报告/冒烟记录用）

    @property
    def label(self) -> str:
        return f"{self.name}:{self.backend}:ctx{self.ctx}:ka{self.keep_alive}:p{self.parallel}"


def _fits_gpu(spec, *, free_gb: float, ctx: int, parallel: int) -> bool:
    """vram 预估 ≤ 可用显存 90% 才允许上 GPU。"""
    if free_gb is None or free_gb <= 0:
        return False
    estimate = estimate_vram(
        spec.path, context_size=ctx, slots=parallel)
    return estimate.total_gb <= free_gb * _GPU_FREE_RATIO


def _gpu_or_cpu(spec, *, free_gb: float, preferred_ctx: int,
                tight: bool, used_gb: float = 0.0) -> ModelPlan:
    """按显存预估决定 GPU 方案；放不下时降 ctx/并发，仍不行回退 CPU。

    tight=True（4~6GB 档）：4B 审核直接降 --ctx-size 4096 / --parallel 1
    （审核单条逐条审，不需并行槽；实施计划 §4.4）。
    used_gb：其他已规划模型的预估占用——共存校验（6~8GB 档 4B 常驻
    后 1.8B 换入需要余量，防静态规划超卖）。
    """
    ctx = preferred_ctx
    parallel = spec.max_concurrency
    if tight:
        ctx = min(ctx, 4096)
        parallel = 1
    if _fits_gpu(spec, free_gb=free_gb - used_gb, ctx=ctx, parallel=parallel):
        return ModelPlan(
            name=spec.name, kind=spec.kind, backend="gpu", gpu_layers=-1,
            ctx=ctx, keep_alive=-1, parallel=parallel,
            rationale=f"显存预估 ≤ 可用{free_gb:g}GB×{_GPU_FREE_RATIO} → GPU 常驻")
    # 降 ctx 再试（长文本翻译批次需要大 ctx，审核/检索不需要）
    if ctx > 4096 and _fits_gpu(spec, free_gb=free_gb - used_gb, ctx=4096,
                                parallel=1):
        return ModelPlan(
            name=spec.name, kind=spec.kind, backend="gpu", gpu_layers=-1,
            ctx=4096, keep_alive=-1, parallel=1,
            rationale=f"默认 ctx{preferred_ctx} 超限 → 降 ctx4096/p1 后 GPU 可容纳")
    # 按需模式再试：模型只在请求期间驻留显存（keep_alive=0），
    # 计算缓冲仍在但权重换入换出——对放不下常驻但仍可能一次性加载的
    # 场景（如 4GB 卡边缘）不再尝试，直接 CPU（本地模型失败回退链兜底）
    return ModelPlan(
        name=spec.name, kind=spec.kind, backend="cpu", gpu_layers=0,
        ctx=ctx, keep_alive=0, parallel=1,
        rationale=f"GPU 放不下（预估>{free_gb:g}×{_GPU_FREE_RATIO}）→ CPU 回退")


def plan_allocation(
        profile: HardwareProfile, registry: ModelRegistry,
) -> dict[ModelKind, ModelPlan]:
    """按硬件档位 + 显存预估输出四模型分配方案（含回退理由）。"""
    free = profile.gpu_free_gb
    ram = profile.ram_gb
    low_ram = ram is not None and ram < _LOW_RAM_GB
    plans: dict[ModelKind, ModelPlan] = {}

    # 0.6B×2：恒 CPU（实施计划硬约束）；低内存时按需加载防挤爆 RAM
    for kind in ("rerank", "embed"):
        spec = registry.by_kind(kind)
        keep = 0 if low_ram else spec.default_keep_alive
        plans[kind] = ModelPlan(
            name=spec.name, kind=kind, backend="cpu", gpu_layers=0,
            ctx=spec.default_ctx, keep_alive=keep, parallel=1,
            rationale=("固定 CPU（0.6B 毫秒级任务占 GPU 无收益）"
                       + ("；低内存按需加载" if low_ram else "；常驻 CPU")))

    translate = registry.by_kind("translate")
    review = registry.by_kind("review")
    if free is None:
        # 无 GPU → 全 CPU；审核模型按需加载（4B CPU 慢但可用，
        # 每次会话加载一次 300 秒窗口复用，避免反复读 3GB；低内存档
        # 收紧为即用即卸，防 4B 权重挤爆 RAM）
        keep = 0 if low_ram else _OND_DEMAND_KEEP_ALIVE_S
        for spec in (translate, review):
            plans[spec.kind] = ModelPlan(
                name=spec.name, kind=spec.kind, backend="cpu", gpu_layers=0,
                ctx=spec.default_ctx, keep_alive=keep, parallel=1,
                rationale=("无 GPU → 全 CPU（"
                           + ("低内存按需加载" if low_ram
                              else "审核按需加载，300s 空闲卸载") + ")"))
        return plans
    if free < 4:
        for spec in (translate, review):
            plans[spec.kind] = ModelPlan(
                name=spec.name, kind=spec.kind, backend="cpu", gpu_layers=0,
                ctx=spec.default_ctx, keep_alive=0, parallel=1,
                rationale=f"可用显存仅 {free:g}GB < 4GB → 全 CPU 按需加载")
        return plans
    if free < 6:
        # 4~6GB：4B 审核 GPU 按需（唯一名额，降 ctx/并发）+ 1.8B CPU
        plans[review.kind] = _gpu_or_cpu(
            review, free_gb=free, preferred_ctx=review.default_ctx,
            tight=True)
        plans[translate.kind] = ModelPlan(
            name=translate.name, kind=translate.kind, backend="cpu",
            gpu_layers=0, ctx=translate.default_ctx, keep_alive=0,
            parallel=1,
            rationale="4~6GB 档：唯一 GPU 名额给审核，翻译 CPU 按需加载")
        return plans
    review_plan = _gpu_or_cpu(
        review, free_gb=free, preferred_ctx=review.default_ctx,
        tight=False)
    plans[review.kind] = review_plan
    # 共存校验：4B 已上 GPU 时，1.8B 只在剩余显存内评估（防静态规划
    # 超卖——6GB 卡 4B 常驻后 1.8B 换入必 OOM，静态规划直接 CPU，
    # 避免启动后靠 LocalModelManager 回退链兜底）
    review_used = (
        estimate_vram(review.path, context_size=review_plan.ctx,
                      slots=review_plan.parallel).total_gb
        if review_plan.backend == "gpu" else 0.0)
    translate_plan = _gpu_or_cpu(
        translate, free_gb=free, preferred_ctx=translate.default_ctx,
        tight=False, used_gb=review_used)
    # 6~8GB 档：1.8B 按需加载（keep_alive=0，批次间卸载）——
    # 4B 常驻 + 1.8B 短驻不共存，避免峰值超限
    if free < 8 and translate_plan.backend == "gpu":
        translate_plan = ModelPlan(
            **{**translate_plan.__dict__, "keep_alive": 0,
               "rationale": translate_plan.rationale + "；按需加载（批次间卸载）"})
    plans[translate.kind] = translate_plan
    return plans


def simulate(gpu_total_gb: float | None, gpu_free_gb: float | None,
             ram_gb: float | None,
             app_dir: str | Path | None = None) -> dict[ModelKind, ModelPlan]:
    """纯函数入口：按指定硬件档位规划（六档硬件冒烟与测试用）。

    不依赖本机真实硬件，直接构造 HardwareProfile 走同一决策路径。
    app_dir 缺省用当前目录（开发环境 models/ 与 main.py 同级）。
    """
    registry = ModelRegistry(app_dir or Path.cwd())
    return plan_allocation(
        HardwareProfile(gpu_total_gb, gpu_free_gb, ram_gb), registry)


def describe_plan(plans: dict[ModelKind, ModelPlan]) -> str:
    """方案的人类可读描述（冒烟/报告输出）。"""
    lines = ["硬件分配方案："]
    for plan in plans.values():
        lines.append(f"  [{plan.kind:<9}] {plan.backend:<3} "
                     f"gpu_layers={plan.gpu_layers:<3} ctx={plan.ctx:<5} "
                     f"keep_alive={plan.keep_alive:<4} parallel={plan.parallel}  "
                     f"· {plan.rationale}")
    return "\n".join(lines)
