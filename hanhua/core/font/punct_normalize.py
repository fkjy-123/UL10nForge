# -*- coding: utf-8 -*-
"""字体标点兼容归一化（hickory 实证：用户 SDF 字符表缺 U+2013 –）。

用户自制 TMP SDF bundle 的字符表覆盖全部常用汉字，但个别西文标点
（en dash、NBSP）不在其中——写回译文含这些码点时游戏渲染 □（缺字）。
与其让发布门永久 BLOCKED（MISSING_CODEPOINT），不如在写回入口把
「缺失标点」归一化为「中文排版等价且 bundle 必含的标点」：
  U+2013 – EN DASH → U+2014 — EM DASH（中文排版标准长划线）
  U+00A0 NBSP     → U+0020 SPACE（中文无需不可断空格）

原则：
- 只在写回入口一次性归一化（project.write_all → store 级 pass），
  译文、重开验证、运行时插件表、字形需求集全部读 store——单一接缝零漂移；
- 映射只覆盖「视觉等价、语义不变」的标点；无安全映射的缺失码点
  （如 U+2021 ‡）不归一化，发布门继续 BLOCKED 诚实阻断；
- 函数必须幂等（归一化后文本再次归一化不变），重试写回安全。
"""
from __future__ import annotations

#: 缺失标点 → bundle 必含等价标点（不可逆映射；仅安全对）
_FONT_PUNCT_MAP: dict[int, int] = {
    0x2013: 0x2014,   # – EN DASH → — EM DASH
    0x00A0: 0x0020,   # NBSP → SPACE
}


def normalize_font_punctuation(text: str) -> str:
    """把写回文本中缺失字体支持的标点替换为等价标点（幂等）。"""
    if not text or not _FONT_PUNCT_MAP:
        return text
    return text.translate(_FONT_PUNCT_MAP)


def needs_normalization(text: str) -> bool:
    """文本是否含需归一化的标点（store pass 只更新有变化的条目）。"""
    return bool(text) and any(ord(ch) in _FONT_PUNCT_MAP for ch in text)
