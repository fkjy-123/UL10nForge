# -*- coding: utf-8 -*-
"""#43 阶段 D：risk_gate 评分化（重构指令 §13 风险评分 / §14 自动分流）。

验证：信号分值求和、等级映射（LOW/MEDIUM/HIGH/CRITICAL）、错误模式
命中信号（Case 5）、语境消歧减分（多义词支持 → 不计分）、quality_failed
强制 HIGH 基线、gate_entries 风险统计透出、旧调用零破坏（默认参数）。
"""
from __future__ import annotations

import pytest

from hanhua.core.models import TextEntry
from hanhua.core.risk_gate import (
    RISK_CRITICAL, RISK_HIGH, RISK_MEDIUM, evaluate_entry, gate_entries,
    risk_level_for,
)


def _entry(original="Hello {0}", translation="你好 {0}", status="translated",
           **meta):
    return TextEntry(file_id="f", key_path="0", original=original,
                     translation=translation, status=status, meta=meta)


# ── §13 评分与等级映射 ───────────────────────────────────────

def test_level_mapping():
    assert risk_level_for(0) == "LOW"
    assert risk_level_for(34) == "LOW"
    assert risk_level_for(35) == "MEDIUM"
    assert risk_level_for(59) == "MEDIUM"
    assert risk_level_for(60) == "HIGH"
    assert risk_level_for(84) == "HIGH"
    assert risk_level_for(85) == "CRITICAL"


def test_polysemy_scores_medium():
    """Resume 多义词（无语境）→ 35 分 = MEDIUM 阈值（本地模型二次审）。"""
    sig = evaluate_entry(_entry("Resume"))
    assert "polysemy" in sig.signals
    assert sig.risk_score == 35
    assert sig.risk_level == "MEDIUM"


def test_quality_failed_floor_high():
    """quality_failed 55 分 → 强制 HIGH 基线（60，不因分数截断降级）。"""
    sig = evaluate_entry(_entry(status="failed"))
    assert sig.risk_score == 60
    assert sig.risk_level == "HIGH"


def test_glossary_conflict_score():
    """术语冲突 40 分 → HIGH 区间（≥60 需叠加，40 → MEDIUM）。"""
    sig = evaluate_entry(
        _entry("Mana", "蓝量"),
        glossary_pairs=[("Mana", "法力")])
    assert "glossary_conflict" in sig.signals
    assert sig.risk_score == 40
    assert sig.risk_level == "MEDIUM"


def test_multiple_signals_sum():
    """多信号叠加：polysemy(30) + negation(15) + character(10) = 55。"""
    sig = evaluate_entry(_entry("Save or not", "保存或否",
                                role="dialogue"))
    assert sig.risk_score == 60
    assert sig.risk_level == "HIGH"


def test_capped_at_100():
    """超 100 截断（硬错 60 + 术语 40 + 多义 30 = 130 → 100 CRITICAL）。"""
    sig = evaluate_entry(
        _entry("Resume", "简历", status="failed"),
        glossary_pairs=[("Resume", "继续")])
    assert sig.risk_score == 100
    assert sig.risk_level == "CRITICAL"


# ── Case 5：历史错误模式命中 ─────────────────────────────────

def test_error_pattern_hit_raises_score():
    """Charge 曾被纠正为「蓄力」→ 命中即警示（25 × 0.95 ≈ 23 分）。"""
    hits = [{"original": "Charge", "correct": "蓄力", "wrong": "收费",
             "confidence": 0.95, "status": "verified"}]
    sig = evaluate_entry(_entry("mana potion"), error_patterns=hits)
    assert "error_pattern_hit" in sig.signals
    assert sig.risk_score == 23
    assert sig.risk_level == "LOW"          # 单信号低分不强行送审


def test_error_pattern_no_meta_dict_ok():
    """鸭子类型：dict 与 PatternHit 均可（纯函数不绑定库）。"""
    from hanhua.core.error_patterns import hits_to_patterns
    from hanhua.core.error_patterns import ErrorPatternStore
    import tempfile
    from pathlib import Path
    ep = ErrorPatternStore(Path(tempfile.mkdtemp()) / "ep.db")
    ep.record("Charge", "蓄力", wrong="收费", source="human_corrected")
    hits = hits_to_patterns(ep.search("Charge"))
    sig = evaluate_entry(_entry("mana potion"), error_patterns=hits)
    assert sig.risk_score == 23


# ── 语境消歧：多义词支持 → 移除信号不计分 ───────────────────

def test_context_supported_removes_polysemy_score():
    """Pause Menu 语境高置信支持「继续」→ polysemy 移除，0 分直放。"""
    evidence = [{"kind": "context_exact", "translation": "继续",
                 "confidence": 0.9}]
    sig = evaluate_entry(
        _entry("Resume", "继续"), context_evidence=evidence)
    assert sig.context == "supported"
    assert sig.signals == ()
    assert sig.risk_score == 0
    assert sig.risk_level == "LOW"


def test_context_conflict_adds_score():
    """语境证据全部反对候选 → context_conflict（30）+ 原多义词（35）= 65。"""
    evidence = [{"kind": "context_exact", "translation": "继续",
                 "confidence": 0.9}]
    sig = evaluate_entry(
        _entry("Resume", "简历"), context_evidence=evidence)
    assert sig.context == "conflict"
    assert sig.risk_score == 65
    assert sig.risk_level == "HIGH"         # 歧义未决 → 人工确认


# ── §14 分流统计透出 + 兼容 ───────────────────────────────────

def test_gate_entries_risk_stats():
    """gate_entries stats 透出 risk 分数与等级分布（旧字段不变）。"""
    entries = [
        _entry("Resume"),                       # polysemy 35 MEDIUM
        _entry("open door", "打开门"),           # 无信号 LOW（小写避开专名）
        _entry("Save or not", "保存或否", role="dialogue"),  # 60 HIGH
    ]
    to_review, passed, deferred, stats = gate_entries(
        entries, max_send_rate=0.5)
    assert stats["total"] == 3
    assert stats["risk_levels"]["MEDIUM"] == 1
    assert stats["risk_levels"]["LOW"] == 1
    assert stats["risk_levels"]["HIGH"] == 1
    assert set(stats["risk"].values()) <= {0, 35, 60}
    # 预算截断：2 条 discretionary，预算 max(1, 2×0.5)=1 → 1 送审 1 deferred
    assert len(to_review) == 1
    assert len(deferred) == 1
    assert len(passed) == 1
    # 旧字段兼容
    for key in ("sent", "mandatory", "discretionary", "rate",
                "deferred_due_to_budget", "signals"):
        assert key in stats


def test_gate_entries_error_patterns_wiring():
    """error_patterns_by_id 接线：命中错误模式的条目送审。"""
    e1 = _entry("mana potion")
    e1.id = 1
    e2 = _entry("Hello")
    to_review, passed, deferred, stats = gate_entries(
        [e1, e2],
        error_patterns_by_id={1: [{"confidence": 0.95}]},
        max_send_rate=0.5)
    assert e1 in to_review
    assert e2 in passed
    assert stats["signals"].get("error_pattern_hit") == 1


def test_gate_entries_context_support_passes():
    """语境证据支持候选（多义词已消歧）→ 整批直放，不占送审预算。"""
    e1 = _entry("Resume", "继续")     # polysemy 35，但语境支持「继续」
    e1.id = 1
    e2 = _entry("Hello", "你好")
    e2.id = 2
    to_review, passed, deferred, stats = gate_entries(
        [e1, e2],
        context_evidence_by_id={1: [
            {"kind": "context_exact", "translation": "继续",
             "confidence": 0.9}]},
        max_send_rate=0.5)
    assert e1 in passed               # 已消歧 → 直放
    assert e2 in passed
    assert to_review == []
    assert "polysemy" not in stats["signals"]
    assert stats["risk"][1] == 0


def test_gate_entries_context_conflict_sends():
    """语境证据反对候选（歧义未决）→ context_conflict 高分送审。"""
    e1 = _entry("Resume", "简历")     # 语境证据是「继续」→ 冲突
    e1.id = 1
    to_review, passed, deferred, stats = gate_entries(
        [e1],
        context_evidence_by_id={1: [
            {"kind": "context_exact", "translation": "继续",
             "confidence": 0.9}]},
        max_send_rate=0.5)
    assert e1 in to_review
    assert stats["signals"].get("context_conflict") == 1
    assert stats["risk"][1] == 65    # 30 冲突 + 35 多义词 → HIGH 人工确认


def test_gate_entries_key_fallback_file_keypath():
    """无 id 条目（reviewer 场景）用 file_id:key_path 做键。"""
    e1 = _entry("mana potion")
    to_review, passed, deferred, stats = gate_entries(
        [e1],
        error_patterns_by_id={"f:0": [{"confidence": 0.95}]},
        max_send_rate=0.5)
    assert e1 in to_review
    assert stats["signals"].get("error_pattern_hit") == 1
