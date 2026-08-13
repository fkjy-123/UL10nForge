# -*- coding: utf-8 -*-
"""方框字症状分类（Phase 0：四大症状可区分，不再统一报「字体失败」）。

审计 §2.2 判别表落为代码——看到方框必须先分类，不得直接替换字体：

- DATA_CORRUPTION     上游文本已丢失：数据本身含方框码点（□ U+25A1、
  ▯ U+25AF、� U+FFFD）——这是编码/写回数据问题，归因字体是误诊
- MISSING_GLYPH       字体缺字形/tofu：Unicode 正确，字体字形表缺需求码点
- ATLAS_MISSING       字形→图集引用链断裂：atlas/material 无法解析
- UNCOVERED_CONSUMER  消费者无任何覆盖路径：动态字体无 provider / 未知渲染器
- SPRITE_ONLY         整串是 <sprite> 图标引用——不是 CJK 文本目标
- OK

注意：口（U+53E3）是合法汉字（拟声/歌词常见），不自动判损坏——「口口口口」
需人工/上下文确认，避免误报（数据层只认无歧义方框码点）。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from hanhua.core.font.glyph_set import (RequiredGlyphSet, rendered_codepoints,
                                        strip_rich_text)

#: 无歧义的「方框/丢失字符」码点——数据损坏信号（§2.2 判别表行 2）
TOFU_CODEPOINTS = frozenset({0x25A1, 0x25AF, 0xFFFD})  # □ ▯ �


class FontSymptom(str, Enum):
    OK = "OK"
    MISSING_GLYPH = "MISSING_GLYPH"          # 字体缺字形/tofu
    DATA_CORRUPTION = "DATA_CORRUPTION"      # 上游文本已丢失/方框码点已写入
    ATLAS_MISSING = "ATLAS_MISSING"          # 图集引用无法解析
    UNCOVERED_CONSUMER = "UNCOVERED_CONSUMER"  # 消费者无覆盖路径
    SPRITE_ONLY = "SPRITE_ONLY"              # 图标引用，非 CJK 文本目标


#: 模块级别名（包导出与测试断言用）
OK = FontSymptom.OK
MISSING_GLYPH = FontSymptom.MISSING_GLYPH
DATA_CORRUPTION = FontSymptom.DATA_CORRUPTION
ATLAS_MISSING = FontSymptom.ATLAS_MISSING
UNCOVERED_CONSUMER = FontSymptom.UNCOVERED_CONSUMER
SPRITE_ONLY = FontSymptom.SPRITE_ONLY


@dataclass
class Diagnosis:
    """单消费者单文本的渲染诊断。"""

    symptom: FontSymptom
    detail: str = ""
    missing_scalars: frozenset[int] = frozenset()


def classify_data(text: str) -> FontSymptom | None:
    """数据层分类：方框码点 → DATA_CORRUPTION；纯 sprite → SPRITE_ONLY。

    返回 None 表示数据本身没问题（进入渲染层诊断）。
    优先级：数据损坏 > 图标引用（数据层即排除，不得进字体替换目标）。"""
    if any(ord(ch) in TOFU_CODEPOINTS for ch in text):
        return FontSymptom.DATA_CORRUPTION
    if "<sprite" in text and not strip_rich_text(text).strip():
        return FontSymptom.SPRITE_ONLY
    return None


def diagnose_render(text: str, *, font_scalars: set[int],
                    atlas_resolved: bool = True,
                    consumer_known: bool = True,
                    dynamic: bool = False,
                    provider_available: bool = True) -> Diagnosis:
    """单消费者渲染诊断（§2.2 四大症状可区分）。

    输入：
      text              渲染文本（译文/原文）
      font_scalars      该消费者字体实际覆盖的码点（无字体时为空集）
      atlas_resolved    字形→图集引用链是否解析（跨文件引用等）
      consumer_known    消费者渲染栈是否可识别（NGUI/BMFont/自定义 → False）
      dynamic           是否动态字体（TMP dynamic：静态无法证明字形覆盖）
      provider_available 动态字体是否有运行时 provider（Mono 插件有，
                        IL2CPP 无）

    返回唯一主症状——诊断必须能区分四种情况，不再统一报「字体失败」。
    """
    data_symptom = classify_data(text)
    if data_symptom is not None:
        return Diagnosis(data_symptom,
                         "数据层问题：方框码点已写入/纯图标引用，"
                         "非字体覆盖问题")
    if not consumer_known:
        return Diagnosis(
            FontSymptom.UNCOVERED_CONSUMER,
            "未识别渲染栈（NGUI/BMFont/自定义）——无覆盖路径")
    if dynamic and not provider_available:
        return Diagnosis(
            FontSymptom.UNCOVERED_CONSUMER,
            "动态字体且无运行时 provider——当前无法自动保证动态字体")
    if not atlas_resolved:
        return Diagnosis(FontSymptom.ATLAS_MISSING,
                         "字形→图集引用链无法解析（atlas/material 缺失）")
    required = RequiredGlyphSet(rendered_codepoints(text))
    missing = required.missing_from(font_scalars)
    if missing:
        return Diagnosis(
            FontSymptom.MISSING_GLYPH,
            f"字体缺字形 {len(missing)} 个码点（字形总数大≠覆盖完整）",
            missing)
    return Diagnosis(FontSymptom.OK, "全部需求码点有字形")
