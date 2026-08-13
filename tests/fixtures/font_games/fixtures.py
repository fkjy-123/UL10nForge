# -*- coding: utf-8 -*-
"""方框字反馈环合成 fixtures（审计 §9 Phase 0 样本 1-10）。

纯数据构建器：消费者（FontConsumer 形态）+ 译文条目 + 数据层文本。
与 README.md 的样本表一一对应，无 Unity 二进制依赖——可复现、可审计。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from hanhua.core.font.coverable import FontConsumer  # noqa: E402
from hanhua.core.models import TextEntry  # noqa: E402

# 译文需求码点（样本共用）
COMMON_TEXT = "继续游戏"

#: 样本统一 Unity 版本（Phase 1：tmp_font 消费者必须带版本，
#: 否则 UNKNOWN_UNITY_VERSION 检查把静态可证明消费者打成 CANDIDATE_ONLY）
UNITY_VERSION = "2021.3"

#: 中文需求码点（继续游戏）——供字体字形表构造
REQUIRED = frozenset(ord(ch) for ch in COMMON_TEXT)

RARE_CHAR = "饕"  # 生僻字（样本 2：字形总数大但缺这一个）
RARE_CP = ord(RARE_CHAR)


def make_entry(translation: str, *, key_path: str = "k1",
               original: str = "Continue") -> TextEntry:
    return TextEntry(
        "f", key_path, original, translation=translation,
        status="translated", meta={"role": "display"})


def make_entries(translations: list[str]) -> list[TextEntry]:
    return [make_entry(t, key_path=f"k{i}") for i, t in enumerate(translations)]


def cjk_font(glyphs: set[int] | None = None) -> frozenset[int]:
    """含需求码点的字形表；缺 RARE_CHAR 的可传 subset。"""
    base = set(REQUIRED)
    if glyphs:
        base |= glyphs
    return frozenset(base)


# ── 样本 1：一可替换 + 一 dynamic 0 glyph（旧逻辑假 PASS） ───────
def sample1_consumers() -> list[FontConsumer]:
    return [
        FontConsumer(consumer_id="tmp_replaceable", kind="tmp_font",
                     static_replaced=True, font_scalars=cjk_font(),
                     unity_version=UNITY_VERSION),
        FontConsumer(consumer_id="tmp_dynamic_zero_glyph", kind="dynamic_tmp",
                     runtime_provider_available=False),
    ]


# ── 样本 2：静态 TMP 字形总数大但缺生僻字 ────────────────────────
def sample2_consumer() -> FontConsumer:
    return FontConsumer(
        consumer_id="tmp_big_table_missing_rare", kind="tmp_font",
        static_replaced=True,
        font_scalars=cjk_font() - {RARE_CP},   # 字形表很大，唯独缺「饕」
        unity_version=UNITY_VERSION,
        ref="f_tmp_bundle/atlas.resS")


# ── 样本 3：atlas 跨文件引用无法解析 ─────────────────────────────
def sample3_consumer() -> FontConsumer:
    return FontConsumer(
        consumer_id="tmp_cross_file_atlas", kind="tmp_font",
        static_replaced=True, font_scalars=cjk_font(),
        unity_version=UNITY_VERSION,
        atlas_resolved=False, ref="atlas → missing.resS (跨文件未解析)")


# ── 样本 4：Legacy Font + TextMesh ───────────────────────────────
def sample4_consumer() -> FontConsumer:
    return FontConsumer(
        consumer_id="legacy_textmesh", kind="textmesh",
        static_replaced=True, font_scalars=cjk_font(),
        ref="m_FontData TTF 已替换为 Source Han Sans SC")


# ── 样本 5：Mono 动态 TMP——pending → attested ───────────────────
def sample5_pending() -> FontConsumer:
    return FontConsumer(
        consumer_id="mono_dynamic_pending", kind="dynamic_tmp",
        runtime_provider_available=True, runtime_attested=False,
        ref="BepInEx 插件已部署，尚未启动验证")


def sample5_attested() -> FontConsumer:
    return FontConsumer(
        consumer_id="mono_dynamic_attested", kind="dynamic_tmp",
        runtime_provider_available=True, runtime_attested=True,
        ref="插件启动后逐字符 attestation 完成")


# ── 样本 6：IL2CPP 动态 TMP 无 provider ──────────────────────────
def sample6_consumer() -> FontConsumer:
    return FontConsumer(
        consumer_id="il2cpp_dynamic", kind="dynamic_tmp",
        runtime_provider_available=False,
        ref="IL2CPP 无运行时 fallback provider")


# ── 样本 7：NGUI / BMFont 证据 ───────────────────────────────────
def sample7_consumer() -> FontConsumer:
    return FontConsumer(
        consumer_id="ngui_bitmap", kind="ngui_bitmap",
        static_replaced=False,
        ref="NGUI BMFont（mFont/mBMFont 指纹证据）→ Phase 5 专用 provider")


# ── 样本 8：数据层方框码点已写入 ─────────────────────────────────
CORRUPTED_TEXT = "□□□□"  # U+25A1 ×4——上游文本已丢失


# ── 样本 9：非 BMP 字符（😀 = U+1F600，单 scalar） ───────────────
NON_BMP_TEXT = "继续😀"

#: surrogate 半码点（UTF-16 视角会拆出来的两个）——需求集不得包含
NON_BMP_SURROGATES = {0xD83D, 0xDE00}


# ── 样本 10：<sprite> 图标引用 ───────────────────────────────────
SPRITE_TEXT = "<sprite=2> <sprite=5> 继续游戏"
SPRITE_ONLY_TEXT = "<sprite=2><sprite=5>"


def sample10_consumer() -> FontConsumer:
    return FontConsumer(
        consumer_id="sprite_icon_font", kind="tmp_font",
        sprite_icon=True, unity_version=UNITY_VERSION,
        ref="图标字体——非 CJK 替换目标")
