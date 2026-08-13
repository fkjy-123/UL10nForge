# -*- coding: utf-8 -*-
"""消费者—字体—字符覆盖引擎（Phase 0：锁定「部分命中 ≠ PASS」语义）。

审计核心缺陷：install_static_fonts 只要 replaced > 0，project 层就把
整个项目标记 runtime_verified=True——「至少一个对象被改写」被当成
「所有承载中文的文本对象都有字体」。本模块以逐消费者结果聚合整体覆盖：
任何消费者未完全覆盖 → 整体 CANDIDATE_ONLY/BLOCKED（§8 发布门决策表）。

整体状态（severity 升序，§8.2 决策表）：
  COVERED                   所有消费者静态完整覆盖（或运行时已 attest）
  PENDING_RUNTIME_ATTESTATION  runtime 已部署但尚未运行验证——禁止称
                            正式完成，测试候选允许
  CANDIDATE_ONLY             已知缺字/未覆盖消费者——禁止发布，
                            测试候选允许（红色警告）
  BLOCKED                    IL2CPP 动态且无 provider / 未知渲染栈严格模式

reason code 全集见 hanhua.core.font.contracts（§9 Phase 1 清单，
单一来源——coverable/inventory 均从此导入）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from hanhua.core.font.contracts import (  # noqa: F401（包导出兼容）
    ATLAS_REFERENCE_UNRESOLVED, BITMAP_FONT_INJECTION_REQUIRED,
    DYNAMIC_FONT_REQUIRES_RUNTIME, MATERIAL_REFERENCE_UNRESOLVED,
    MISSING_CODEPOINT, NOT_A_CJK_TARGET, RUNTIME_PROVIDER_UNAVAILABLE,
    STALE_RUNTIME_ATTESTATION, TMP_LAYOUT_MISMATCH,
    UNKNOWN_UNITY_VERSION, UNSUPPORTED_RENDERER,
)
from hanhua.core.font.glyph_set import RequiredGlyphSet


class CoverageState(IntEnum):
    """整体/单消费者覆盖终态（severity 升序，发布门决策表 §8.2）。"""

    COVERED = 0
    PENDING_RUNTIME_ATTESTATION = 1
    CANDIDATE_ONLY = 2
    BLOCKED = 3


#: 模块级别名（包导出与测试断言用）
COVERED = CoverageState.COVERED
PENDING_RUNTIME_ATTESTATION = CoverageState.PENDING_RUNTIME_ATTESTATION
CANDIDATE_ONLY = CoverageState.CANDIDATE_ONLY
BLOCKED = CoverageState.BLOCKED

#: 阻塞正式发布的终态（§8.2：已知缺字/未覆盖/无 provider 均禁止）
_BLOCKING = (CoverageState.CANDIDATE_ONLY, CoverageState.BLOCKED)


@dataclass(frozen=True)
class FontConsumer:
    """一个字体消费者（渲染中文的文本对象 → 字体 → 材质 → 图集引用链）。"""

    consumer_id: str
    kind: str                       # legacy_font / tmp_font / dynamic_tmp /
                                    # textmesh / ngui_bitmap / unknown
    static_replaced: bool = False   # 静态替换是否命中该对象
    font_scalars: frozenset[int] = frozenset()  # 替换后字体实际覆盖码点
    atlas_resolved: bool = True     # 字形→图集引用链（跨文件引用）
    material_resolved: bool = True  # 字体→材质引用链（m_Material）
    layout_ok: bool = True          # TMP 布局代匹配（tmp1/2/3）
    unity_version: str | None = None  # 游戏 Unity 版本（TMP 静态 patch 依据）
    runtime_provider_available: bool = False  # Mono 插件已部署？
    runtime_attested: bool = False  # 插件启动后逐字符 attestation 完成
    sprite_icon: bool = False       # 图标字体/纯 sprite——非 CJK 替换目标
    ref: str = ""                   # 资产引用描述（atlas 路径等，可审计）


@dataclass
class ConsumerCoverage:
    consumer: FontConsumer
    state: CoverageState
    reason: str = ""
    missing_scalars: frozenset[int] = frozenset()


@dataclass
class FontCoverageOutcome:
    consumers: list[ConsumerCoverage]
    overall: CoverageState

    def blocks_publish(self) -> bool:
        """正式发布门：任一消费者 CANDIDATE_ONLY/BLOCKED → 阻断。"""
        return any(c.state in _BLOCKING for c in self.consumers)

    def pending_runtime(self) -> bool:
        """runtime 已部署未验证（禁止称正式完成，测试候选允许）。"""
        return self.overall == CoverageState.PENDING_RUNTIME_ATTESTATION

    def summary_text(self) -> str:
        """审计报告行：逐消费者终态 + 缺字/未覆盖统计。"""
        covered = sum(c.state == CoverageState.COVERED for c in self.consumers)
        missing = sum(len(c.missing_scalars) for c in self.consumers)
        uncovered = sum(c.state in _BLOCKING for c in self.consumers)
        return (f"覆盖 {self.overall.name}：{covered} 个消费者完整，"
                f"{uncovered} 个未覆盖，缺字 {missing} 个码点")


def compute_coverage(consumers, required: RequiredGlyphSet) \
        -> FontCoverageOutcome:
    """逐消费者逐码点覆盖计算（§7.4 静态覆盖证明）。

    聚合规则：整体 = 最差消费者终态（severity 取 max）。任何消费者
    CANDIDATE_ONLY/BLOCKED → blocks_publish() = True——「替换一个对象」
    不再能代表全局成功（样本 1 缺陷锁）。
    """
    per: list[ConsumerCoverage] = []
    for c in consumers:
        per.append(_consumer_coverage(c, required))
    overall = CoverageState(
        max((c.state for c in per), default=CoverageState.COVERED))
    return FontCoverageOutcome(per, overall)


def coverage_blocks_publish(outcome: FontCoverageOutcome) -> bool:
    """发布门契约函数（Phase 4 接入 _evaluate_writeback_gates 前，
    test_writeback_gates 先锁定语义：coverage 不完整必须阻断发布）。"""
    return outcome.blocks_publish()


def _consumer_coverage(c: FontConsumer,
                       required: RequiredGlyphSet) -> ConsumerCoverage:
    """单消费者覆盖判定（决策表逐行落地）。"""
    if c.sprite_icon:
        # 图标字体不得被当作普通 CJK 替换目标（样本 10）——不是失败
        return ConsumerCoverage(c, CoverageState.COVERED,
                                NOT_A_CJK_TARGET)
    if not c.layout_ok:
        return ConsumerCoverage(c, CoverageState.CANDIDATE_ONLY,
                                TMP_LAYOUT_MISMATCH)
    if c.kind == "dynamic_tmp":
        # 动态字体：静态无法证明字形覆盖（样本 5/6）
        if not c.runtime_provider_available:
            return ConsumerCoverage(
                c, CoverageState.BLOCKED, RUNTIME_PROVIDER_UNAVAILABLE)
        if c.runtime_attested:
            return ConsumerCoverage(c, CoverageState.COVERED,
                                    "RUNTIME_ATTESTED")
        return ConsumerCoverage(c, CoverageState.PENDING_RUNTIME_ATTESTATION,
                                DYNAMIC_FONT_REQUIRES_RUNTIME)
    if c.kind == "ngui_bitmap" and not c.static_replaced:
        # 位图字体可注入（Phase 5 专用 provider）——未注入即未覆盖；
        # 已注入/审计已覆盖（static_replaced=True，Phase 5 反哺）则走
        # 下方正常码点覆盖判定。
        return ConsumerCoverage(c, CoverageState.CANDIDATE_ONLY,
                                BITMAP_FONT_INJECTION_REQUIRED)
    if c.kind == "unknown":
        # 未识别渲染栈：明确进 unsupported 路径，不得静默消失
        return ConsumerCoverage(c, CoverageState.CANDIDATE_ONLY,
                                UNSUPPORTED_RENDERER)
    if not c.material_resolved:
        return ConsumerCoverage(c, CoverageState.CANDIDATE_ONLY,
                                MATERIAL_REFERENCE_UNRESOLVED)
    if not c.atlas_resolved:
        return ConsumerCoverage(c, CoverageState.CANDIDATE_ONLY,
                                ATLAS_REFERENCE_UNRESOLVED)
    if c.kind == "tmp_font" and not c.unity_version:
        # 未知 Unity 版本无法选 bundle——静态无法证明
        return ConsumerCoverage(c, CoverageState.CANDIDATE_ONLY,
                                UNKNOWN_UNITY_VERSION)
    if not c.static_replaced:
        # 静态替换未命中的可替换对象（布局匹配失败等已单独列出）
        return ConsumerCoverage(c, CoverageState.CANDIDATE_ONLY,
                                "STATIC_NOT_REPLACED")
    if c.runtime_attested:
        # 已 attest 的静态消费者：运行时证明优先（Phase 3 真实化）
        return ConsumerCoverage(c, CoverageState.COVERED, "RUNTIME_ATTESTED")
    missing = required.missing_from(c.font_scalars)
    if missing:
        return ConsumerCoverage(c, CoverageState.CANDIDATE_ONLY,
                                MISSING_CODEPOINT, missing)
    return ConsumerCoverage(c, CoverageState.COVERED)
