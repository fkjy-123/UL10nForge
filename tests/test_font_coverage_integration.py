# -*- coding: utf-8 -*-
"""Phase 0：消费者—字体—字符覆盖组合测试（审计 §9 样本 1-10）。

核心：任何消费者未完全覆盖 → 整体 CANDIDATE_ONLY/BLOCKED——「替换一个
对象却全局 PASS」的缺陷被逐消费者语义锁死（样本 1）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from hanhua.core.font import (
    ATLAS_REFERENCE_UNRESOLVED, BITMAP_FONT_INJECTION_REQUIRED, BLOCKED,
    CANDIDATE_ONLY, COVERED, MISSING_CODEPOINT, NOT_A_CJK_TARGET,
    PENDING_RUNTIME_ATTESTATION, RUNTIME_PROVIDER_UNAVAILABLE,
    TMP_LAYOUT_MISMATCH, UNSUPPORTED_RENDERER,
    FontConsumer, compute_coverage,
)
from hanhua.core.font.diagnostics import (DATA_CORRUPTION,
                                          diagnose_render)
from hanhua.core.font.glyph_set import (build_required_glyph_set,
                                        text_codepoints)
from tests.fixtures.font_games import fixtures as fx


def _required(translations):
    return build_required_glyph_set(fx.make_entries(translations))


def _single(consumer) -> tuple:
    outcome = compute_coverage([consumer], _required(["继续游戏"]))
    return outcome.overall, outcome.consumers[0]


# ── 样本 1：部分命中不得全局 PASS（核心缺陷锁） ─────────────────

def test_sample1_partial_hit_is_incomplete_not_pass():
    """一个 TMP 可替换、一个 dynamic 0 glyph（无 provider）：整体 BLOCKED。

    旧逻辑（project.py 只看 static.replaced > 0 标 runtime_verified=True）
    在此场景全局 PASS——本测试锁定新语义：可替换消费者 COVERED 不能
    抵消未覆盖消费者（最差消费者定整体）。"""
    outcome = compute_coverage(fx.sample1_consumers(),
                               _required(["继续游戏"]))
    assert outcome.consumers[0].state == COVERED       # 可替换的确实覆盖
    assert outcome.consumers[1].state == BLOCKED       # dynamic 0 glyph 无路径
    assert outcome.overall == BLOCKED                  # 但整体最差态
    assert outcome.blocks_publish() is True
    assert "1 个未覆盖" in outcome.summary_text()


def test_sample1_dynamic_zero_glyph_reason():
    outcome = compute_coverage([fx.sample1_consumers()[1]],
                               _required(["继续游戏"]))
    assert outcome.consumers[0].reason == RUNTIME_PROVIDER_UNAVAILABLE


# ── 样本 2：字形总数大但缺生僻字 ────────────────────────────────

def test_sample2_big_table_missing_rare_char():
    outcome = compute_coverage([fx.sample2_consumer()],
                               _required([f"继续{fx.RARE_CHAR}"]))
    per = outcome.consumers[0]
    assert per.state == CANDIDATE_ONLY
    assert per.reason == MISSING_CODEPOINT
    assert fx.RARE_CP in per.missing_scalars          # 缺的是生僻字
    assert outcome.blocks_publish() is True


# ── 样本 3：atlas 跨文件引用 ────────────────────────────────────

def test_sample3_cross_file_atlas_unresolved():
    overall, per = _single(fx.sample3_consumer())
    assert overall == CANDIDATE_ONLY
    assert per.reason == ATLAS_REFERENCE_UNRESOLVED
    assert per.consumer.ref  # 引用描述可审计


# ── 样本 4：Legacy Font + TextMesh ──────────────────────────────

def test_sample4_legacy_textmesh_covered():
    overall, per = _single(fx.sample4_consumer())
    assert overall == COVERED
    assert per.state == COVERED
    assert _single(fx.sample4_consumer())[0] == COVERED


# ── 样本 5：Mono 动态 TMP pending → attested ────────────────────

def test_sample5_pending_before_runtime_verification():
    outcome = compute_coverage([fx.sample5_pending()],
                               _required(["继续游戏"]))
    assert outcome.overall == PENDING_RUNTIME_ATTESTATION
    assert outcome.consumers[0].reason == "DYNAMIC_FONT_REQUIRES_RUNTIME"
    # 已部署未验证：不阻断测试候选（§8.2），但禁止称正式完成
    assert outcome.blocks_publish() is False
    assert outcome.pending_runtime() is True


def test_sample5_attested_after_runtime_verification():
    overall, per = _single(fx.sample5_attested())
    assert overall == COVERED
    assert per.reason == "RUNTIME_ATTESTED"


# ── 样本 6：IL2CPP 动态 TMP 无 provider ─────────────────────────

def test_sample6_il2cpp_no_provider_blocks():
    outcome = compute_coverage([fx.sample6_consumer()],
                               _required(["继续游戏"]))
    assert outcome.overall == BLOCKED
    assert outcome.consumers[0].reason == RUNTIME_PROVIDER_UNAVAILABLE
    assert outcome.blocks_publish() is True


# ── 样本 7：NGUI/BMFont 证据 ────────────────────────────────────

def test_sample7_ngui_bitmap_needs_injection():
    """NGUI/BMFont 位图字体：Phase 1 起有专用 reason（Phase 5 注入
    provider 前即未覆盖）——不再是泛化 UNSUPPORTED_RENDERER。"""
    outcome = compute_coverage([fx.sample7_consumer()],
                               _required(["继续游戏"]))
    assert outcome.overall == CANDIDATE_ONLY
    assert outcome.consumers[0].reason == BITMAP_FONT_INJECTION_REQUIRED
    assert outcome.blocks_publish() is True


def test_sample7_true_unknown_renderer_still_unsupported():
    """真正未识别的渲染栈仍走 UNSUPPORTED_RENDERER（不静默消失）。"""
    unknown = FontConsumer("mystery", "unknown", ref="未知渲染栈")
    outcome = compute_coverage([unknown], _required(["继续游戏"]))
    assert outcome.overall == CANDIDATE_ONLY
    assert outcome.consumers[0].reason == UNSUPPORTED_RENDERER
    assert outcome.blocks_publish() is True


# ── 样本 8：数据层方框码点 → data corruption ────────────────────

def test_sample8_corrupted_data_is_not_missing_glyph():
    """□□□□ 必须归为 data corruption，不得归因字体缺字。"""
    diag = diagnose_render(fx.CORRUPTED_TEXT,
                           font_scalars=text_codepoints("继续游戏"))
    assert diag.symptom == DATA_CORRUPTION


# ── 样本 9：非 BMP 单 scalar 覆盖 ───────────────────────────────

def test_sample9_non_bmp_single_scalar_coverage():
    required = _required([fx.NON_BMP_TEXT])
    # 字体含 😀 → 覆盖完整
    good_font = FontConsumer("good", "tmp_font", static_replaced=True,
                             font_scalars=text_codepoints(fx.NON_BMP_TEXT),
                             unity_version=fx.UNITY_VERSION)
    assert compute_coverage([good_font], required).overall == COVERED
    # 字体只有 surrogate 半码点（UTF-16 拆分视角）→ 仍缺 😀
    half_font = FontConsumer("half", "tmp_font", static_replaced=True,
                             font_scalars=fx.NON_BMP_SURROGATES
                             | text_codepoints("继续"),
                             unity_version=fx.UNITY_VERSION)
    per = compute_coverage([half_font], required).consumers[0]
    assert per.state == CANDIDATE_ONLY
    assert 0x1F600 in per.missing_scalars
    assert not (per.missing_scalars & fx.NON_BMP_SURROGATES)


# ── 样本 10：<sprite> 图标字体不得当 CJK 替换目标 ───────────────

def test_sample10_sprite_icon_excluded_from_replacement():
    outcome = compute_coverage([fx.sample10_consumer()],
                               _required(["继续游戏"]))
    assert outcome.consumers[0].state == COVERED
    assert outcome.consumers[0].reason == NOT_A_CJK_TARGET
    assert outcome.blocks_publish() is False          # 图标字体不阻断
    # 纯 sprite 串需求集为空——不进替换目标
    assert len(_required([fx.SPRITE_ONLY_TEXT])) == 0


# ── 聚合语义 ─────────────────────────────────────────────────────

def test_overall_takes_worst_consumer_state():
    outcome = compute_coverage(
        [fx.sample4_consumer(), fx.sample6_consumer()],
        _required(["继续游戏"]))
    assert outcome.overall == BLOCKED                 # 最差者定整体


def test_layout_mismatch_is_consumer_failure():
    bad = FontConsumer("mismatch", "tmp_font", static_replaced=True,
                       font_scalars=text_codepoints("继续游戏"),
                       layout_ok=False, unity_version=fx.UNITY_VERSION)
    overall, per = _single(bad)
    assert overall == CANDIDATE_ONLY
    assert per.reason == TMP_LAYOUT_MISMATCH


def test_summary_text_counts():
    outcome = compute_coverage(fx.sample1_consumers(),
                               _required(["继续游戏"]))
    text = outcome.summary_text()
    assert outcome.overall.name in text and "1 个未覆盖" in text


def test_static_not_replaced_is_consumer_failure():
    untouched = FontConsumer("untouched", "tmp_font",
                             static_replaced=False,
                             font_scalars=text_codepoints("继续游戏"),
                             unity_version=fx.UNITY_VERSION)
    overall, per = _single(untouched)
    assert overall == CANDIDATE_ONLY
    assert _single(untouched)[0] == CANDIDATE_ONLY
