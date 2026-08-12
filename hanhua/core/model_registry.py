"""模型注册表：四 GGUF 模型统一描述与定位（阶段 0 T0-2）。

四模型分工（本地 llama.cpp 全本地推理）：
- translate: Hy-MT2-1.8B  —— 主翻译（已有链路）
- review:    Qwen3.5-4B   —— 语义深审（四级分级，阶段 1 接入）
- rerank:    Qwen3-Reranker-0.6B —— 候选语境排序（阶段 3，固定 CPU）
- embed:     Qwen3-Embedding-0.6B —— 向量检索（阶段 4，固定 CPU）

本模块只做「描述 + 定位」：具体 backend/gpu_layers/ctx 分配由
hardware_planner 按用户硬件输出；服务启停复用 LocalModelManager
（llama-server 单实例 + model_runtime.json 跨实例复用机制）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ModelKind = Literal["translate", "review", "rerank", "embed"]

# 各模型建议端口（llama-server 每模型一实例；翻译沿用现状 8080 起，
# 实际端口由 LocalModelManager 按 model_runtime.json 复用机制决定）
DEFAULT_PORTS: dict[ModelKind, int] = {
    "translate": 8080,
    "review": 8081,
    "rerank": 8082,
    "embed": 8083,
}

# 默认上下文长度：8192——调高可解决长文本/大 batch 截断问题
# （deadbeat 歌词 3183 字符 1099 tokens 超 1024 槽位被拒实证；大
# local_batch_size 下 prompt 更长，ctx 不足直接失败/截断）。KV 显存
# 代价：1.8B 8192 ≈ 0.5GB、4B 8192 ≈ 0.75GB，12GB 卡富余；低档硬件
# 由 hardware_planner 按显存预估自动降 4096（见 _gpu_or_cpu）。
# 0.6B×2 语义检索/重排输入短，4096 封顶。
DEFAULT_CTX: dict[ModelKind, int] = {
    "translate": 8192,
    "review": 8192,
    "rerank": 4096,
    "embed": 4096,
}

# 模型文件名定位线索（models/ 目录 glob，按 kind 匹配，兼容改名后缀
# 与大小写变体；多命中取排序后第一个）
_FILENAME_HINTS: dict[ModelKind, tuple[str, ...]] = {
    "translate": ("hy-mt2",),
    "review": ("qwen3.5-4b", "qwen3-4b"),
    "rerank": ("reranker",),
    "embed": ("embedding",),
}


@dataclass(frozen=True)
class ModelSpec:
    """单个 GGUF 模型的静态描述。

    backend/gpu_layers/ctx/keep_alive 是「建议模板值」，实际生效值由
    HardwarePlanner 按本机硬件与 vram 预估动态决定（ModelPlan）。
    """
    name: str                          # 逻辑名：translate/review/rerank/embed
    kind: ModelKind
    path: Path                         # GGUF 文件绝对路径
    default_ctx: int                   # 建议上下文（KV 显存随其增长）
    default_keep_alive: int            # -1 常驻 / 0 即用即卸 / N 秒空闲卸载
    max_concurrency: int               # 建议并发槽位上限（显存紧张时降到 1）
    fixed_cpu: bool                    # 0.6B×2 恒 CPU（毫秒级任务不上 GPU）
    port: int                          # 建议端口
    budget_gb: float                   # 模型权重占用（GiB ≈ GGUF 文件大小）
    server_args: tuple[str, ...] = ()  # llama-server 启动附加参数（按模型特性）

    @property
    def display_name(self) -> str:
        return self.path.stem

    @property
    def is_available(self) -> bool:
        return self.path.is_file()


def _resolve_hint(app_dir: Path, hints: tuple[str, ...]) -> Path | None:
    """在 models/ 目录按文件名线索定位 GGUF（casefold 匹配，防改后缀）。"""
    model_dir = app_dir / "models"
    if not model_dir.is_dir():
        return None
    candidates: list[Path] = []
    for hint in hints:
        candidates.extend(
            path for path in model_dir.glob("*.gguf")
            if hint in path.name.casefold())
    if not candidates:
        return None
    candidates.sort(key=lambda path: path.name.casefold())
    return candidates[0].resolve()


def build_specs(app_dir: str | Path) -> tuple[ModelSpec, ...]:
    """按 models/ 目录实际文件构建四模型注册表（缺失模型 path 指向
    不存在文件，is_available=False，由调用方决定告警/降级）。"""
    root = Path(app_dir).resolve()

    def make(kind: ModelKind, *, keep_alive: int, concurrency: int,
             fixed_cpu: bool = False, server_args: tuple[str, ...] = ()) -> ModelSpec:
        return ModelSpec(
            name=kind, kind=kind,
            path=_resolve_hint(root, _FILENAME_HINTS[kind]) or (root / "models" / f"{kind}.gguf"),
            default_ctx=DEFAULT_CTX[kind],
            default_keep_alive=keep_alive,
            max_concurrency=concurrency,
            fixed_cpu=fixed_cpu,
            port=DEFAULT_PORTS[kind],
            budget_gb=0.0,
            server_args=server_args,
        )

    specs = (
        make("translate", keep_alive=-1, concurrency=1),
        # Qwen3.5 系 thinking 模型：默认开启思考会把输出预算全耗在
        # reasoning_content 上（content 空串、finish=length，冒烟实证）。
        # 审核是结构化 JSON 判定，关闭思考后稳定直接输出
        make("review", keep_alive=-1, concurrency=1,
             server_args=("--reasoning", "off")),
        # 0.6B×2：毫秒~秒级任务（批量嵌入、top-100 重排各一次前向），
        # 占 GPU 无收益 → 固定 CPU（实施计划 §4.4）；常驻 CPU 内存
        # ~1GB，避免重复加载
        make("rerank", keep_alive=-1, concurrency=1, fixed_cpu=True),
        make("embed", keep_alive=-1, concurrency=1, fixed_cpu=True),
    )
    # 实际权重占用按文件大小回填（hardware_planner 预算核算用）
    with_budget = []
    for spec in specs:
        if spec.path.is_file():
            spec = ModelSpec(
                **{**spec.__dict__, "budget_gb": spec.path.stat().st_size / 2**30})
        with_budget.append(spec)
    return tuple(with_budget)


class ModelRegistry:
    """四模型注册表：按 kind/name 查询，报告缺失模型。"""

    def __init__(self, app_dir: str | Path):
        self.app_dir = Path(app_dir).resolve()
        self._specs: dict[ModelKind, ModelSpec] = {}
        for spec in build_specs(self.app_dir):
            self._specs[spec.kind] = spec

    def all(self) -> tuple[ModelSpec, ...]:
        return tuple(self._specs.values())

    def by_kind(self, kind: ModelKind) -> ModelSpec:
        """按 kind 取模型；未注册（理论上不可能）返回占位规格。"""
        return self._specs[kind]

    def get(self, name: str) -> ModelSpec | None:
        return self._specs.get(name)  # type: ignore[arg-type]

    @property
    def missing(self) -> tuple[ModelSpec, ...]:
        return tuple(spec for spec in self._specs.values()
                     if not spec.is_available)

    @property
    def all_ready(self) -> bool:
        return not self.missing

    def describe(self) -> str:
        lines = ["模型注册表："]
        for spec in self.all():
            mark = "[OK]" if spec.is_available else "[缺失]"
            lines.append(
                f"  [{spec.kind:<9}] {spec.display_name:<28} "
                f"{spec.budget_gb:>4.1f}GiB {mark}")
        return "\n".join(lines)
