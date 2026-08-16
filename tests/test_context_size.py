"""智能上下文计算测试（2026-08-16 用户指令）。

规则：原文字数 → 预估译文 token（×1.5 保守）→ 单条需求（最长原文
兜底，切换批量不影响）与批量需求 → max × 安全余量 → [2048, 16384]。
"""
from hanhua.core.context_size import (estimate_tokens, smart_context_size)


def test_estimate_tokens_mixed():
    assert estimate_tokens("Hello world") > 0
    # 中文 token 密度高于英文
    assert estimate_tokens("这是一段中文文本") > estimate_tokens("abc")
    assert estimate_tokens("") == 1


def test_small_texts_min_ctx():
    """小文本（短菜单/提示）→ 下限 2048，不冗余。"""
    small = ["Options", "Start Game", "Are you sure you want to quit?"]
    assert smart_context_size(small) == 2048


def test_large_texts_scaled():
    """大文本（drova 风格长描述）→ ctx 按文本规模放大。"""
    big = ["A" * 3000] * 100
    ctx = smart_context_size(big, batch_size=8)
    assert 2048 < ctx <= 16384
    # 更长文本 → 更大 ctx
    bigger = ["A" * 6000] * 100
    assert smart_context_size(bigger) > ctx


def test_batch_switch_does_not_break_single():
    """切换条数不影响单条兜底：任何批量下 ctx 都能容纳最长单条
    （单条需求独立于批量大小）。"""
    big = ["The monster is approaching from the dark forest, " * 60] * 20
    c1 = smart_context_size(big, batch_size=1)
    c64 = smart_context_size(big, batch_size=64)
    # 单条需求 = 最长原文×1.5 + 开销，小于 min(c1, c64) 即可
    single_need = estimate_tokens(big[0]) * 1.5 + 900
    assert min(c1, c64) >= single_need


def test_empty_default():
    assert smart_context_size([]) == 8192


def test_clamped_upper():
    """超长文本封顶 16384（防 KV 超显存）。"""
    huge = ["Z" * 50000] * 500
    assert smart_context_size(huge, batch_size=32) <= 16384
