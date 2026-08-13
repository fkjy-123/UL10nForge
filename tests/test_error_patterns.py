# -*- coding: utf-8 -*-
"""#43 阶段 B：翻译错误模式库（重构指令 §8/§16/§17）。

验证：写入门禁（人工纠正 verified/0.95、AI candidate/0.6）、检索
（归一化 + 语境）、生命周期（deprecated 保留历史）、manual_correction
接线（AI 坏译文被人工纠正 → 自动沉淀错误模式）。
"""
from __future__ import annotations

import pytest

from hanhua.core.error_patterns import ErrorPatternStore, hits_to_patterns
from hanhua.core.manual_correction import manual_correction
from hanhua.core.project import ProjectStore


@pytest.fixture()
def ep(tmp_path):
    return ErrorPatternStore(tmp_path / "ep.db")


def _project(tmp_path):
    store = ProjectStore(tmp_path / "p.db")
    store.init_schema()
    return store


# ── §17 写入门禁：来源决定初始状态与置信 ─────────────────────

def test_human_corrected_verified_095(ep):
    """人工纠正：终局证据 → verified + 0.95。"""
    status = ep.record("Resume", "继续", wrong="简历",
                       source="human_corrected")
    assert status == "verified"
    row = ep.list_all()[0]
    assert row["confidence"] == 0.95
    assert row["wrong"] == "简历"
    assert row["status"] == "verified"


def test_ai_generated_stays_candidate(ep):
    """模型自生成：只进 candidate（参考不强制，不污染）。"""
    status = ep.record("Charge", "蓄力", wrong="收费", source="ai")
    assert status == "candidate"
    assert ep.list_all()[0]["confidence"] == 0.6


def test_candidate_promoted_by_human_confirmation(ep):
    """candidate 被人工确认 → 升级 verified + 置信取大。"""
    ep.record("Charge", "蓄力", wrong="收费", source="ai")
    ep.record("Charge", "蓄力", wrong="收费", source="human_corrected")
    row = ep.list_all()[0]
    assert row["status"] == "verified"
    assert row["confidence"] == 0.95


def test_empty_rejected(ep):
    assert ep.record("", "继续", source="human_corrected") == "rejected"
    assert ep.record("Charge", "", source="human_corrected") == "rejected"
    assert ep.list_all() == []


# ── 检索（§4 优先级：verified 优先） ─────────────────────────

def test_search_normalized_case_insensitive(ep):
    """大小写/空白无关命中（Charge/charge 同模式）。"""
    ep.record("Charge", "蓄力", wrong="收费", source="human_corrected")
    hits = ep.search("charge")
    assert len(hits) == 1
    assert hits[0]["correct"] == "蓄力"
    assert hits_to_patterns(hits)[0].confidence == 0.95


def test_search_prefers_verified_over_candidate(ep):
    ep.record("Resume", "继续", wrong="简历", source="human_corrected")
    ep.record("Resume", "简历", wrong="恢复", source="ai")
    hits = ep.search("Resume")
    assert hits[0]["correct"] == "继续"   # verified 在前
    assert hits[0]["status"] == "verified"


def test_search_context_filter(ep):
    ep.record("Charge", "蓄力", wrong="收费", context="Combat",
              source="human_corrected")
    assert len(ep.search("Charge", context="Combat")) == 1
    assert len(ep.search("Charge", context="Shop")) == 0


def test_deprecated_kept_but_not_returned(ep):
    """退役保留历史（§18 不删除），但不再参与检索。"""
    ep.record("Rank", "等级", wrong="军衔", source="human_corrected")
    assert ep.promote("Rank", "等级", status="deprecated")
    assert ep.promote("Rank", "等级", status="bogus") is False
    assert ep.search("Rank") == []
    assert len(ep.list_all()) == 1          # 历史保留


def test_usage_counting(ep):
    ep.record("Resume", "继续", wrong="简历", source="human_corrected")
    ep.mark_used("Resume", "继续")
    ep.mark_used("resume", "继续")
    assert ep.list_all()[0]["usage_count"] == 2


# ── §16 反馈系统接线：manual_correction 自动沉淀 ─────────────

def test_manual_correction_records_error_pattern(tmp_path):
    """AI 译文被人工纠正 → 错误模式自动沉淀（verified）。"""
    store = _project(tmp_path)
    store.add_file("f1", "f1.txt", "txt", "utf-8", "lf")
    store.upsert_entries([{
        "file_id": "f1", "key_path": "0", "original": "Resume",
        "status": "translated", "meta": {"role": "display"},
    }])
    store.update_translation("f1", "0", "简历")   # AI 坏译文
    ep = ErrorPatternStore(tmp_path / "ep.db")
    result = manual_correction(store, "f1", "0", "继续",
                               error_patterns=ep)
    assert result["applied"]
    assert result["error_pattern"] == "verified"
    hits = ep.search("Resume")
    assert hits[0]["wrong"] == "简历"
    assert hits[0]["correct"] == "继续"


def test_manual_correction_no_pattern_when_same(tmp_path):
    """人工译文与 AI 相同（未改正）→ 不沉淀错误模式。"""
    store = _project(tmp_path)
    store.add_file("f1", "f1.txt", "txt", "utf-8", "lf")
    store.upsert_entries([{
        "file_id": "f1", "key_path": "0", "original": "Resume",
        "status": "translated", "meta": {"role": "display"},
    }])
    store.update_translation("f1", "0", "继续")   # AI 已正确
    ep = ErrorPatternStore(tmp_path / "ep.db")
    result = manual_correction(store, "f1", "0", "继续",
                               error_patterns=ep)
    assert "error_pattern" not in result
    assert ep.list_all() == []
