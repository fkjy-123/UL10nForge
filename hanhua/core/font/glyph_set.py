# -*- coding: utf-8 -*-
"""RequiredGlyphSet：本次真实译文的 Unicode scalar 需求集（Phase 0 基础版）。

字体决策必须围绕「实际译文字符集」而不是字形总数（审计 §1：TMP 静态验证
只比 glyph 数，字形很多但缺译文生僻字照样方框）。本模块锁定字符集语义：

- 以 Python str 迭代（Unicode scalar values）为准——非 BMP 字符是单个
  scalar（如 😀 = 0x1F600），绝不是两个 surrogate（0xD83D/0xDE00）。
  与字体字形表按 int 码点比较，不拆 surrogate（样本 9）。
- TMP 富文本标签（<b>、<size=24>、<color=#fff>…）不产生字形需求；
  <sprite=...> 是图集图标引用，必须整体排除——图标字体不得被当作普通
  CJK 替换目标（样本 10）。
- 需求集带来源 locator（file_id:key_path），任意缺字可回溯到译文
  （Phase 1 完成标准：任意缺字都能回溯到至少一个译文 locator）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from hanhua.core.models import TextEntry
from hanhua.core.protected_spans import _RICH_TAG

#: TMP <sprite=...> 标签——引用图集图标（icon），不是文本字形
_SPRITE_TAG = re.compile(r"<sprite\b[^>]*>", re.IGNORECASE)


def strip_rich_text(text: str) -> str:
    """去掉 TMP 富文本标签，保留可渲染文本（与 protected_spans 同源正则）。"""
    return _RICH_TAG.sub("", text)


def text_codepoints(text: str) -> frozenset[int]:
    """字符串的全部 Unicode scalar（int）。

    Python str 迭代天然产出 scalar value——非 BMP 字符单值，不拆
    surrogate。任何按 UTF-16 code unit 构建字形表的比较都必须在此
    归一（样本 9：RequiredGlyphSet 不能拆成两个 surrogate）。
    """
    return frozenset(ord(ch) for ch in text)


def rendered_codepoints(text: str) -> frozenset[int]:
    """渲染字形需求：去富文本 + 去空白后的 scalar 集。

    空白（空格/制表/换行/全角空格）任何字体都有，不构成 tofu；
    标签剥离后残留的布局空白（<sprite=2> <sprite=5> 中间的空格）
    也不得计入需求集。"""
    return frozenset(
        ord(ch) for ch in strip_rich_text(text) if not ch.isspace())


@dataclass(frozen=True)
class RequiredGlyphSet:
    """需求字形集：scalars + 来源回溯。"""

    scalars: frozenset[int]
    locators: dict[int, list[str]] = field(default_factory=dict)

    def __contains__(self, scalar: int) -> bool:
        return scalar in self.scalars

    def __len__(self) -> int:
        return len(self.scalars)

    def missing_from(self, font_codepoints: set[int]) -> frozenset[int]:
        """字体字形表缺失的需求码点。"""
        return frozenset(s for s in self.scalars if s not in font_codepoints)

    def sprite_only(self) -> bool:
        """无任何字形需求——全部内容来自 <sprite> 图标引用/空串。

        图标字体不得被当作普通 CJK 替换目标（样本 10）。"""
        return not self.scalars

    def sources_of(self, scalar: int) -> list[str]:
        """某码点的来源 locator（Phase 1 完成标准：缺字可回溯）。"""
        return list(self.locators.get(scalar, ()))


def build_required_glyph_set(entries) -> RequiredGlyphSet:
    """从本次真实译文构建需求集。

    entries: 可迭代的 TextEntry（或带 original/translation/file_id/
    key_path 的对象）。渲染文本 = 译文（非空时），否则保留原文
    （未翻译条目原样写回仍会被渲染）。<sprite> 图标与富文本标签不产生
    字形需求；空白/纯标签串不产生需求。
    """
    scalars: set[int] = set()
    locators: dict[int, list[str]] = {}
    for e in entries:
        translation = getattr(e, "translation", None)
        text = translation if translation and str(translation).strip() \
            else getattr(e, "original", "")
        if not text:
            continue
        if not str(text).strip():
            continue
        locator = f"{e.file_id}:{e.key_path}"
        for scalar in rendered_codepoints(str(text)):
            scalars.add(scalar)
            locators.setdefault(scalar, []).append(locator)
    return RequiredGlyphSet(frozenset(scalars), locators)
