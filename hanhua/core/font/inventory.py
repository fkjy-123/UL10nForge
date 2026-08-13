# -*- coding: utf-8 -*-
"""FontConsumerInventory：字体消费者与资产引用清单（Phase 1，审计 §7.2）。

从容器扫描证据（fingerprint/extractor 层输出）建立结构化消费者清单：
- 每个承载文本的字体对象 → FontConsumer（renderer 分类、字形表、布局代、
  atlas/material 引用链、动态/静态判别、sprite 图标排除）；
- 未识别对象同时进 consumers（kind=unknown → UNSUPPORTED_RENDERER 终态）
  与 unknown_objects 审计清单——不得静默消失（Phase 1 完成标准）；
- state_counts 会计恒等式：消费者总数 == 各终态之和（完成标准）。

动态 TMP 判别：TMP 静态字体资产必有字形表；glyph_count==0 且无字形
码点 = dynamic（运行时按 TTF 生成字形，静态无法证明覆盖——样本 1/5/6）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from hanhua.core.font.contracts import CoverageEvidence
from hanhua.core.font.coverable import (FontConsumer, compute_coverage)
from hanhua.core.font.glyph_set import (RequiredGlyphSet,
                                        build_required_glyph_set)


@dataclass(frozen=True)
class FontObjectEvidence:
    """容器内一个字体对象的扫描证据（extractor 层输出形态）。"""

    asset_id: str
    container: str
    renderer: str               # legacy_font / textmesh / tmp_font /
                                # dynamic_tmp / ngui / bmfont / unknown
    glyph_count: int = 0
    font_codepoints: frozenset[int] = frozenset()
    layout_version: str = ""    # tmp1 / tmp2 / tmp3
    atlas_ref: str = ""         # m_StreamData.path（跨文件引用时非空）
    material_ref: str = ""      # m_Material 引用
    replaced: bool = False      # 静态替换是否命中该对象（Phase 2 由
                                # FontReplaceResult 反哺；false = 未替换）
    sprite_icon: bool = False   # 图标字体/纯 sprite——非 CJK 替换目标


@dataclass(frozen=True)
class ContainerEvidence:
    """一个容器的字体证据（容器相对路径 + 字体对象列表）。"""

    path: str
    font_objects: tuple[FontObjectEvidence, ...] = ()


@dataclass
class FontConsumerInventory:
    """结构化消费者清单：消费者 + 未识别对象 + 本次译文需求集。"""

    consumers: list[FontConsumer]
    unknown_objects: list[FontObjectEvidence]
    required: RequiredGlyphSet
    unity_version: str | None = None
    runtime: str = "unknown"    # mono / il2cpp / unknown

    def __len__(self) -> int:
        return len(self.consumers)

    def coverage(self) -> object:
        """逐消费者逐码点覆盖计算（覆盖引擎，Phase 2 验证入口）。"""
        return compute_coverage(self.consumers, self.required)

    def state_counts(self) -> dict[str, int]:
        """终态分布。完成标准：消费者总数 == 各终态之和。"""
        counts: dict[str, int] = {}
        for per in self.coverage().consumers:
            counts[per.state.name] = counts.get(per.state.name, 0) + 1
        return counts


def inventory_font_consumers(containers, translations, *,
                             unity_version: str | None = None,
                             runtime: str = "unknown",
                             available_streams: set[str] | None = None) \
        -> FontConsumerInventory:
    """从容器证据 + 本次译文构建消费者清单（审计 §7.2 关键接口）。

    containers:       ContainerEvidence 列表（每容器含 FontObjectEvidence）
    translations:     本次真实译文（TextEntry 可迭代）→ RequiredGlyphSet
    available_streams: 已知图集流文件集（含容器内 .resS/外部流）——
                       atlas_ref 不在其中 → ATLAS_REFERENCE_UNRESOLVED
    """
    consumers: list[FontConsumer] = []
    unknown_objects: list[FontObjectEvidence] = []
    streams = available_streams or set()
    for container in containers:
        for obj in container.font_objects:
            if obj.sprite_icon:
                consumers.append(FontConsumer(
                    consumer_id=f"{container.path}#{obj.asset_id}",
                    kind="tmp_font", sprite_icon=True,
                    ref=f"{obj.renderer} 图标字体"))
                continue
            kind, consumer = _classify(obj, container, streams,
                                       unity_version)
            if kind == "unknown":
                unknown_objects.append(obj)
            consumers.append(consumer)
    return FontConsumerInventory(
        consumers, unknown_objects,
        build_required_glyph_set(translations),
        unity_version=unity_version, runtime=runtime)


def _classify(obj: FontObjectEvidence, container: ContainerEvidence,
              streams: set[str], unity_version: str | None) \
        -> tuple[str, FontConsumer]:
    """单个字体对象 → FontConsumer（未识别 renderer → unknown）。"""
    cid = f"{container.path}#{obj.asset_id}"
    atlas_resolved = (not obj.atlas_ref) or obj.atlas_ref in streams
    material_resolved = not obj.material_ref
    if obj.renderer in ("ngui", "bmfont"):
        return "ngui_bitmap", FontConsumer(
            cid, "ngui_bitmap", ref=f"位图字体（{obj.renderer}）")
    if obj.renderer == "dynamic_tmp" or (
            obj.renderer == "tmp_font" and obj.glyph_count == 0
            and not obj.font_codepoints):
        # 0 glyph = TMP dynamic（运行时生成字形）
        return "dynamic_tmp", FontConsumer(
            cid, "dynamic_tmp",
            runtime_provider_available=False,
            ref=f"TMP 动态字体（{obj.glyph_count} glyph）")
    if obj.renderer == "tmp_font":
        return "tmp_font", FontConsumer(
            cid, "tmp_font", static_replaced=obj.replaced,
            font_scalars=obj.font_codepoints,
            layout_ok=bool(obj.layout_version),
            unity_version=unity_version,
            atlas_resolved=atlas_resolved,
            material_resolved=material_resolved,
            ref=f"TMP {obj.layout_version} 布局 · atlas={obj.atlas_ref or '内置'}"
                f" · material={obj.material_ref or '内置'}"
                + (" · 已替换" if obj.replaced else " · 未替换"))
    if obj.renderer in ("legacy_font", "textmesh"):
        return obj.renderer, FontConsumer(
            cid, obj.renderer, static_replaced=obj.replaced,
            font_scalars=obj.font_codepoints,
            atlas_resolved=atlas_resolved,
            ref="Legacy Font 内嵌 TTF" + (" · 已替换" if obj.replaced else ""))
    return "unknown", FontConsumer(
        cid, "unknown", ref=f"未识别渲染栈（{obj.renderer}）")
