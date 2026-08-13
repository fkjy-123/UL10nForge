# -*- coding: utf-8 -*-
"""#43 阶段 A：知识置信度/生命周期/冲突检测/来源可追溯。

重构指令 §7（置信度）、§8（来源）、§9（冲突检测）、§17-18（生命周期）、
§19（可观测性）在 KnowledgeStore / GlossaryStore 的增量落地验证。
"""
from __future__ import annotations

import pytest

from hanhua.core.glossary import GlossaryStore
from hanhua.core.knowledge import KnowledgeBase, KnowledgeStore


@pytest.fixture()
def kb(tmp_path):
    return KnowledgeBase(tmp_path / "kb.db")


@pytest.fixture()
def gs(tmp_path):
    store = GlossaryStore(tmp_path / "glossary.db")
    store.init_schema()
    return store


# ── §7 置信度 + 加列默认值（零迁移兼容） ─────────────────────

def test_new_columns_exist_with_defaults(kb):
    """旧库升级语义：新列带 DEFAULT，旧行自动获得保守值（AI 0.6）。"""
    assert kb.store.upsert("text", "spaced_action", "H E L L O",
                           action="translate", source="auto")
    row = kb.store.list_by_domain("text")[0]
    assert row["confidence"] == 0.6          # AI 自动生成保守值
    assert row["status"] == "verified"       # 生命周期默认
    assert row["priority"] == 0
    assert row["source_ref"] == ""


def test_upsert_with_full_metadata(kb):
    """人工确认路径：confidence=1.0 + source_ref 溯源。"""
    kb.store.upsert(
        "text", "uppercase_action", "PRESS START", action="translate",
        map_to="按开始", source="human_corrected", game="g1",
        confidence=1.0, priority=10, source_ref="gui:manual-fix 2026-08-14")
    row = kb.store.list_by_domain("text")[0]
    assert row["confidence"] == 1.0
    assert row["priority"] == 10
    assert row["source_ref"] == "gui:manual-fix 2026-08-14"
    assert row["source"] == "human_corrected"


def test_invalid_status_and_source_fall_back(kb):
    """未知状态/来源不静默写坏库（回退到合法保守值）。"""
    kb.store.upsert("text", "uppercase_action", "GO", action="translate",
                    source="bogus", status="nonsense")
    row = kb.store.list_by_domain("text")[0]
    assert row["status"] == "verified"
    assert row["source"] == "auto"


# ── §17-18 生命周期 ───────────────────────────────────────────

def test_set_status_lifecycle(kb):
    """candidate → verified → locked → deprecated，deprecated 保留历史。"""
    kb.store.upsert("text", "uppercase_action", "QUIT", action="translate",
                    status="candidate", confidence=0.6)
    assert kb.store.set_status("text", "uppercase_action", "QUIT",
                               "verified")
    assert kb.store.set_status("text", "uppercase_action", "QUIT", "locked")
    assert kb.store.set_status("text", "uppercase_action", "QUIT",
                               "deprecated")
    rows = kb.store.list_by_domain("text")
    assert len(rows) == 1                       # 不删除，保留历史
    assert rows[0]["status"] == "deprecated"
    assert kb.store.set_status("text", "uppercase_action", "QUIT",
                               "bogus") is False


def test_deprecated_excluded_from_retrieval(kb):
    """退役知识不参与 match_text / format_for_prompt（但数据保留）。"""
    kb.store.upsert("text", "exact", r"^\bOPEN\b$", action="translate",
                    map_to="打开", source="auto")
    assert kb.store.set_status("text", "exact", r"^\bOPEN\b$",
                               "deprecated")
    assert kb.match_text("OPEN") == []          # 不再命中
    assert "打开" not in kb.format_for_prompt()  # 不再注入 prompt
    assert len(kb.store.list_by_domain("text")) == 1  # 历史保留


# ── §9 冲突检测（规则域，术语域已有 Phase B-3 detect_conflicts） ─

def test_detect_conflicts_same_pattern_diff_action(kb):
    """同 pattern 不同 action = 规则冲突，必须检出而非静默共存。"""
    kb.store.upsert("text", "exact", "START", action="translate")
    conflicts = kb.store.detect_conflicts("text", "exact", "START",
                                          "skip")
    assert len(conflicts) == 1
    assert conflicts[0]["action"] == "translate"
    assert kb.store.detect_conflicts("text", "exact", "START",
                                     "translate") == []  # 同处置无冲突


# ── §19 可观测性：使用计数 ───────────────────────────────────

def test_mark_used_counts(kb):
    kb.store.upsert("text", "exact", "RESUME", action="translate",
                    map_to="继续")
    kb.store.mark_used("text", "exact", "RESUME", success=True)
    kb.store.mark_used("text", "exact", "RESUME", success=True)
    kb.store.mark_used("text", "exact", "RESUME", success=False)
    row = kb.store.list_by_domain("text")[0]
    assert row["usage_count"] == 3
    assert row["success_count"] == 2


# ── §7 术语置信度（glossary） ─────────────────────────────────

def test_glossary_confidence_by_path(gs):
    """人工 add = 1.0（DEFAULT）；审核沉淀新词 = 0.85；跨游戏激活 = 0.95。"""
    gs.add("Soul Shard", "灵魂碎片")  # 人工
    assert gs.list_all()[0]["confidence"] == 1.0

    r1 = gs.add_reviewed("Mana", "法力", context="Combat", game="g1")
    assert r1.status == "CANDIDATE"
    assert gs.list_all()[-1]["confidence"] == 0.85

    r2 = gs.add_reviewed("Mana", "法力", context="Combat", game="g2")
    assert r2.status == "ACTIVATED"               # 两独立游戏同译法激活
    mana = [r for r in gs.list_all() if r["term"] == "Mana"][0]
    assert mana["confidence"] == 0.95          # 激活升级


def test_glossary_conflict_not_overwritten(gs):
    """同源异译（指令 Case 6）：不覆盖、不升级，留档供人工复核。"""
    gs.add_reviewed("Mana", "法力", context="Combat", game="g1")
    r = gs.add_reviewed("Mana", "魔力", context="Combat", game="g1")
    assert r.status == "CONFLICT"
    mana = [row for row in gs.list_all() if row["term"] == "Mana"][0]
    assert mana["translation"] == "法力"       # 原译法未被覆盖
    assert "冲突例句" in mana["note"]          # 冲突证据留档
