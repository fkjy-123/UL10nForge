# -*- coding: utf-8 -*-
"""Phase 0：方框字症状分类 + RequiredGlyphSet 基础语义测试。

审计 §9 Phase 0 完成标准：测试输出能明确区分四大主要症状（字体缺字/
编码损坏/图集缺失/未覆盖消费者），不再统一报「字体失败」；非 BMP
字符不能拆成两个 surrogate；<sprite> 不得当 CJK 替换目标。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from hanhua.core.font.diagnostics import (
    ATLAS_MISSING, DATA_CORRUPTION, MISSING_GLYPH, OK, SPRITE_ONLY,
    UNCOVERED_CONSUMER, FontSymptom, classify_data, diagnose_render,
)
from hanhua.core.font.glyph_set import (RequiredGlyphSet,
                                        build_required_glyph_set,
                                        strip_rich_text, text_codepoints)
from tests.fixtures.font_games import fixtures as fx


# ── RequiredGlyphSet：字符集语义 ─────────────────────────────────

def test_build_required_glyph_set_from_translations():
    entries = fx.make_entries(["继续游戏", "开始"])
    required = build_required_glyph_set(entries)
    assert ord("继") in required and ord("开") in required
    assert len(required) == 6          # 继续游戏 4 + 开始 2


def test_rich_text_tags_do_not_produce_glyphs():
    """<b>/<size>/<color> 等 TMP 标签不产生字形需求。"""
    required = build_required_glyph_set(
        fx.make_entries(["<b>继续</b><size=24>游</size>"]))
    assert required.scalars == text_codepoints("继续游")
    assert ord("b") not in required and ord("s") not in required


def test_sprite_tags_excluded_from_requirements():
    """样本 10：<sprite> 图标引用不产生字形需求。"""
    required = build_required_glyph_set(fx.make_entries([fx.SPRITE_TEXT]))
    assert required.scalars == text_codepoints("继续游戏")


def test_sprite_only_string_yields_empty_set():
    """整串都是 <sprite> → 无字形需求（不是 CJK 替换目标）。"""
    required = build_required_glyph_set(fx.make_entries([fx.SPRITE_ONLY_TEXT]))
    assert len(required) == 0
    assert required.sprite_only() is True


def test_non_bmp_is_single_scalar():
    """样本 9：非 BMP 字符是单个 scalar，绝不拆成两个 surrogate。"""
    required = build_required_glyph_set(fx.make_entries([fx.NON_BMP_TEXT]))
    assert 0x1F600 in required.scalars              # 😀 整体一个
    assert 0x1F600 in required
    assert not (fx.NON_BMP_SURROGATES & required.scalars)  # 半码点不存在
    assert len(required) == 3                       # 继续 + 😀


def test_missing_from_returns_absent_scalars():
    required = RequiredGlyphSet(text_codepoints("继续游戏"))
    missing = required.missing_from(text_codepoints("继续"))
    assert missing == {ord("游"), ord("戏")}


def test_locators_trace_missing_char_to_translation():
    """Phase 1 完成标准提前锁定：任意缺字可回溯到译文 locator。"""
    entries = fx.make_entries([f"继续{fx.RARE_CHAR}"])   # k0
    required = build_required_glyph_set(entries)
    missing = required.missing_from(fx.cjk_font())
    assert fx.RARE_CP in missing
    assert "f:k0" in required.sources_of(fx.RARE_CP)


def test_empty_translation_falls_back_to_original():
    """未翻译条目原样写回仍被渲染——需求集应含原文。"""
    from hanhua.core.models import TextEntry
    entry = TextEntry("f", "k1", "Press Start", translation="",
                      status="pending")
    required = build_required_glyph_set([entry])
    assert ord("P") in required and ord("t") in required


def test_strip_rich_text_keeps_literal_text():
    assert strip_rich_text("<color=#ffcc00>继续</color>") == "继续"
    assert strip_rich_text("a < b") == "a < b"    # 非标签尖括号保留


# ── 症状分类：四大症状可区分 ─────────────────────────────────────

def test_classify_data_detects_tofu_codepoints():
    """样本 8：文本字节本身是 □□□□ → DATA_CORRUPTION（数据问题，
    不是字体缺字——归因字体是误诊）。"""
    assert classify_data(fx.CORRUPTED_TEXT) == DATA_CORRUPTION
    assert classify_data("缺�字") == DATA_CORRUPTION   # � 替换符


def test_classify_data_keeps_legit_ko_unflagged():
    """口（U+53E3）是合法汉字——不得自动判损坏（避免误报拟声/歌词）。"""
    assert classify_data("口口相传") is None
    assert classify_data("おいしい口調") is None


def test_classify_data_sprite_only():
    assert classify_data(fx.SPRITE_ONLY_TEXT) == SPRITE_ONLY
    assert classify_data("继续游戏") is None


def test_diagnose_missing_glyph():
    """MISSING_GLYPH：Unicode 正确但字体字形表缺需求码点。"""
    diag = diagnose_render("继续游戏", font_scalars=text_codepoints("继续"))
    assert diag.symptom == MISSING_GLYPH
    assert {ord("游"), ord("戏")} == diag.missing_scalars
    assert "码点" in diag.detail


def test_diagnose_atlas_missing():
    diag = diagnose_render("继续游戏", font_scalars=text_codepoints("继续游戏"),
                           atlas_resolved=False)
    assert diag.symptom == ATLAS_MISSING


def test_diagnose_uncovered_unknown_renderer():
    """样本 7：NGUI/BMFont/自定义渲染栈 → UNCOVERED_CONSUMER。"""
    diag = diagnose_render("继续游戏", font_scalars=frozenset(),
                           consumer_known=False)
    assert diag.symptom == UNCOVERED_CONSUMER


def test_diagnose_uncovered_dynamic_no_provider():
    """样本 6：动态字体且无运行时 provider → UNCOVERED_CONSUMER。"""
    diag = diagnose_render("继续游戏", font_scalars=frozenset(),
                           dynamic=True, provider_available=False)
    assert diag.symptom == UNCOVERED_CONSUMER


def test_diagnose_ok():
    diag = diagnose_render("继续游戏", font_scalars=text_codepoints("继续游戏"))
    assert diag.symptom == OK


def test_data_corruption_wins_over_missing_glyph():
    """数据损坏优先于字体缺字——方框码点已写入时不归因字体。"""
    diag = diagnose_render(fx.CORRUPTED_TEXT,
                           font_scalars=text_codepoints("继续"))
    assert diag.symptom == DATA_CORRUPTION


def test_four_main_symptoms_are_distinct():
    """完成标准：四种主要症状互不相同，不再统一报「字体失败」。"""
    symptoms = {
        diagnose_render("继续", font_scalars=frozenset()).symptom,
        diagnose_render(fx.CORRUPTED_TEXT,
                        font_scalars=frozenset()).symptom,
        diagnose_render("继续", font_scalars=text_codepoints("继续"),
                        atlas_resolved=False).symptom,
        diagnose_render("继续", font_scalars=frozenset(),
                        consumer_known=False).symptom,
    }
    assert symptoms == {MISSING_GLYPH, DATA_CORRUPTION,
                        ATLAS_MISSING, UNCOVERED_CONSUMER}
    assert len(symptoms) == 4
