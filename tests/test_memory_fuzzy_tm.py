# -*- coding: utf-8 -*-
"""#43 阶段 C：TM 模糊匹配（重构指令 §三-2 / §6 第 6 路召回）。

验证：归一化命中（大小写/空白/标点无关，0.95）、token 相似命中
（0.7×重叠率）、阈值过滤、pending 待审记忆不参与、TM 与术语分层
（查询层不动表结构，零迁移）。
"""
from __future__ import annotations

import pytest

from hanhua.core.project import ProjectStore


@pytest.fixture()
def store(tmp_path):
    s = ProjectStore(tmp_path / "p.db")
    s.init_schema()
    return s


def _seed(store, rows, pending=False):
    for original, translation in rows:
        if pending:
            store.batch_add_memory([(original, translation, "m1", "en→zh")])
        else:
            store.add_memory(original, translation, "m1", "en→zh")


# ── 归一化命中（normalized，0.95） ───────────────────────────

def test_normalized_match_ignores_case_space_punct(store):
    _seed(store, [("Mana Cost", "法力消耗")])
    hits = store.get_memory_similar("mana cost", "m1", "en→zh")
    assert len(hits) == 1
    assert hits[0]["kind"] == "normalized"
    assert hits[0]["confidence"] == 0.95
    # 标点/空格变体同样命中
    assert store.get_memory_similar("Mana-Cost!", "m1", "en→zh")[0][
        "kind"] == "normalized"


def test_exact_match_is_covered_by_normalized(store):
    _seed(store, [("Press Start", "按开始")])
    hits = store.get_memory_similar("Press Start", "m1", "en→zh")
    assert hits[0]["kind"] == "normalized"
    assert hits[0]["translation"] == "按开始"


# ── token 相似命中（similar，0.7×重叠） ──────────────────────

def test_token_similar_match(store):
    _seed(store, [("Pick up the Iron Key", "拾起铁钥匙")])
    hits = store.get_memory_similar("Pick up the key", "m1", "en→zh")
    assert len(hits) == 1
    assert hits[0]["kind"] == "similar"
    assert 0.7 * 0.5 <= hits[0]["confidence"] <= 0.7   # 3/6 重叠 ≈ 0.35
    assert hits[0]["translation"] == "拾起铁钥匙"


def test_cjk_token_similar(store):
    """CJK 按单字分词：日文汉字共性可召回（重叠 4/6 ≈ 0.67 > 0.6）。"""
    _seed(store, [("開始の選択肢", "开始的选择")])
    hits = store.get_memory_similar("開始の選択", "m1", "en→zh")
    assert len(hits) == 1
    assert hits[0]["kind"] == "similar"


def test_below_threshold_not_returned(store):
    _seed(store, [("Open the wooden door", "打开木门")])
    hits = store.get_memory_similar("Press X to jump", "m1", "en→zh",
                                    min_similarity=0.6)
    assert hits == []                              # 0 重叠 < 0.6


def test_sorted_by_confidence(store):
    _seed(store, [("Soul Shard", "灵魂碎片"), ("Soul Stone", "灵魂石")])
    hits = store.get_memory_similar("Soul shard", "m1", "en→zh")
    assert hits[0]["kind"] == "normalized"          # 精确归一化在最前
    assert hits[0]["translation"] == "灵魂碎片"


# ── Phase B 语义延续：pending 待审不参与 ─────────────────────

def test_pending_memory_excluded(store):
    _seed(store, [("Mana Cost", "法力消耗(未审)")], pending=True)
    assert store.get_memory_similar("mana cost", "m1", "en→zh") == []
    # 提交后立即可命中（promote 语义）
    store.promote_memory([("Mana Cost", "法力消耗(未审)", "m1", "en→zh")])
    assert len(store.get_memory_similar("mana cost", "m1", "en→zh")) == 1


def test_empty_and_model_scope(store):
    _seed(store, [("Mana", "法力")])
    assert store.get_memory_similar("", "m1", "en→zh") == []
    assert store.get_memory_similar("Mana", "other-model", "en→zh") == []
    assert store.get_memory_similar("Mana", "m1", "ja→zh") == []
