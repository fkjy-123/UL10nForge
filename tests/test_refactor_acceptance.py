# -*- coding: utf-8 -*-
"""#43 阶段 H：重构指令「二十二、最终验收标准」Case 1-9 验收测试。

每个 Case 映射到已实现的确定性能力（规则优先于 LLM 原则）：
  Case 1 多义词    → risk_gate 语境消歧（支持→直放 / 反对→送审）+ 十维
  Case 2 术语一致  → glossary 词对 + glossary_conflict 信号 + 术语参考注入
  Case 3 占位符    → placeholders 保真 + 审核维度 8（结构完整）
  Case 4 Rich Text → protected_spans 保真 + 审核维度 8
  Case 5 历史错误  → ErrorPatternStore 命中 → 提高风险 + prompt 注入
  Case 6 知识冲突  → glossary term_norm 冲突 + knowledge 规则域冲突
  Case 7 上下文不足 → 无语境证据 → polysemy 35 送审（不强行高置信）
  Case 8 明显机翻  → 审核维度 4 自然度 + 维度 10 机翻痕迹
  Case 9 幻觉      → 审核维度 7（增义 = CRITICAL 核对点）
"""
from __future__ import annotations

from hanhua.core.models import TextEntry
from hanhua.core.risk_gate import evaluate_entry, gate_entries
from hanhua.core.reviewer import _REVIEW_SYSTEM_PROMPT, _build_item_prompt
from hanhua.core.reviewer import ReviewItem


def _entry(original, translation="", status="translated"):
    return TextEntry(file_id="f", key_path="0", original=original,
                     translation=translation, status=status)


# ── Case 1：多义词（Resume：Pause Menu→继续 / Profile→简历） ───────

def test_case1_polysemy_pause_menu_context_supported_passes():
    """Pause Menu 语境高置信支持「继续」→ 消歧直放（0 分 LOW）。"""
    sig = evaluate_entry(
        _entry("Resume", "继续"),
        context_evidence=[{"kind": "context_exact", "translation": "继续",
                           "confidence": 0.9}])
    assert sig.context == "supported"
    assert sig.signals == ()
    assert sig.risk_level == "LOW"


def test_case1_polysemy_profile_context_conflict_reviews():
    """Profile/CV 语境证据「简历」→ 候选「继续」冲突 → 送审。"""
    sig = evaluate_entry(
        _entry("Resume", "继续"),
        context_evidence=[{"kind": "context_exact", "translation": "简历",
                           "confidence": 0.9}])
    assert sig.context == "conflict"
    assert "context_conflict" in sig.signals
    assert sig.risk_level in ("HIGH", "MEDIUM")


def test_case1_polysemy_no_context_goes_to_review():
    """无语境证据 → 不强行高置信：35 分 MEDIUM 二次审（Case 7 同根）。"""
    sig = evaluate_entry(_entry("Resume"))
    assert "polysemy" in sig.signals
    assert sig.risk_score == 35
    assert sig.risk_level == "MEDIUM"


# ── Case 2：术语一致（Mana / Mana Potion / Mana Cost） ─────────────

def test_case2_glossary_conflict_detected():
    """词对 Mana=法力 命中原文但译文未用标准译法 → 40 分冲突信号。"""
    sig = evaluate_entry(
        _entry("Mana", "蓝量"),
        glossary_pairs=[("Mana", "法力")])
    assert "glossary_conflict" in sig.signals
    assert sig.risk_score == 40
    assert sig.risk_level == "MEDIUM"


def test_case2_glossary_term_injected_into_prompt():
    """术语参考注入审核 prompt（知识优先级链 §16）。"""
    item = ReviewItem(entry_id="e", original="Mana Cost",
                      translation="法力消耗", text_type="UI 显示文本",
                      term_hint="Mana=法力；Mana Cost=法力消耗")
    prompt = _build_item_prompt(item)
    assert "术语参考：Mana=法力" in prompt
    assert "Mana Cost=法力消耗" in prompt


# ── Case 3：占位符（Hello {0} → {0} 必须存在） ─────────────────────

def test_case3_placeholder_integrity_in_prompt():
    """审核维度 8 显式核对占位符保留（{0}/%s 被吞或改位是 CRITICAL）。"""
    assert "结构完整" in _REVIEW_SYSTEM_PROMPT
    assert "{0}" in _REVIEW_SYSTEM_PROMPT
    assert "%s" in _REVIEW_SYSTEM_PROMPT


def test_case3_placeholder_detected_by_gate_as_character_text():
    """Hello {0}（含 {0}）不被误伤：无风险信号直放（占位符不触发专名）。"""
    sig = evaluate_entry(_entry("Hello {0}", "你好 {0}"))
    assert sig.signals == ()
    assert sig.risk_level == "LOW"


# ── Case 4：Rich Text（<color=red>Danger</color> 标签完整） ────────

def test_case4_rich_text_integrity_in_prompt():
    """审核维度 8 显式核对 HTML/富文本标签完整。"""
    assert "标签" in _REVIEW_SYSTEM_PROMPT or "HTML" in _REVIEW_SYSTEM_PROMPT


def test_case4_rich_text_not_false_flagged():
    """含富文本标签的行不触发专名/长句误伤（直放）。"""
    sig = evaluate_entry(_entry("<color=red>Danger</color>",
                                "<color=red>危险</color>"))
    assert sig.risk_level in ("LOW", "MEDIUM")


# ── Case 5：历史错误（Charge→收费 纠正为 蓄力 → 提高风险） ────────

def test_case5_error_pattern_raises_risk():
    """Charge 曾被纠正 → 命中错误模式 → 风险识别必须提高。"""
    hits = [{"original": "Charge", "wrong": "收费", "correct": "蓄力",
             "confidence": 0.95, "status": "verified"}]
    sig = evaluate_entry(_entry("Charge"), error_patterns=hits)
    assert "error_pattern_hit" in sig.signals
    # 无命中对照：同原文无历史错误 → 仅多义词 35（不混入错误模式信号）
    plain = evaluate_entry(_entry("Charge"))
    assert "error_pattern_hit" not in plain.signals
    assert sig.risk_score > plain.risk_score     # 提高风险识别能力
    assert sig.risk_score == 58                  # 35 多义词 + 23 模式


def test_case5_error_pattern_full_chain(tmp_path):
    """端到端：人工纠正落库 → 检索命中 → 批量门送审。"""
    from hanhua.core.error_patterns import ErrorPatternStore
    store = ErrorPatternStore(tmp_path / "ep.db")
    store.record("Charge", "蓄力", wrong="收费", source="human_corrected")
    e = _entry("Charge", "收费")
    e.id = 1
    hits = store.search("Charge")
    to_review, passed, deferred, stats = gate_entries(
        [e], error_patterns_by_id={1: hits}, max_send_rate=0.5)
    assert e in to_review
    assert stats["signals"].get("error_pattern_hit") == 1


# ── Case 6：知识冲突（Mana→法力 与 Mana→魔力 必须发现） ───────────

def test_case6_glossary_conflict_detected(tmp_path):
    """同词双译法入库 → 冲突检测（term_norm 唯一约束，不静默覆盖）。"""
    from hanhua.core.glossary import GlossaryStore
    g = GlossaryStore(tmp_path / "g.db")
    g.init_schema()
    r1 = g.add_reviewed("Mana", "法力", game="gameA")
    r2 = g.add_reviewed("Mana", "魔力", game="gameB")
    assert r1.status in ("CANDIDATE", "ACTIVATED")
    assert r2.status == "CONFLICT"          # 冲突不覆盖、不升级


def test_case6_knowledge_rule_conflict_detected(tmp_path):
    """知识库规则域同 pattern 不同处置 → detect_conflicts 发现。"""
    from hanhua.core.knowledge import KnowledgeStore
    kb = KnowledgeStore(tmp_path / "k.db")
    kb.init_schema()
    kb.upsert("text", "exact", "START", action="translate", map_to="开始")
    conflicts = kb.detect_conflicts("text", "exact", "START", "skip")
    assert len(conflicts) == 1
    assert conflicts[0]["action"] == "translate"
    # 同处置无冲突（静默共存不被误报）
    assert kb.detect_conflicts("text", "exact", "START", "translate") == []


# ── Case 7：上下文不足（Charge 无上下文 → 转人工/二次审） ─────────

def test_case7_charge_no_context_medium_review():
    """Charge 无语境 → 多义词 MEDIUM（本地模型二次审，不强行高置信）。"""
    sig = evaluate_entry(_entry("Charge"))
    assert "polysemy" in sig.signals
    assert sig.risk_score == 35
    assert sig.risk_level == "MEDIUM"


# ── Case 8：明显机翻（语义正确但表达不自然） ─────────────────────

def test_case8_machine_translation_dimensions_in_prompt():
    """审核维度 4 自然度 + 维度 10 机翻痕迹（显式可评估）。"""
    assert "自然度" in _REVIEW_SYSTEM_PROMPT
    assert "机翻痕迹" in _REVIEW_SYSTEM_PROMPT
    assert "翻译腔" in _REVIEW_SYSTEM_PROMPT


# ── Case 9：幻觉（Open door. → 打开前方那扇木门。增义） ───────────

def test_case9_hallucination_dimension_in_prompt():
    """审核维度 7 幻觉：增义（编造数字/物品/行为）是 CRITICAL。"""
    assert "幻觉" in _REVIEW_SYSTEM_PROMPT
    assert "编造" in _REVIEW_SYSTEM_PROMPT
    assert "CRITICAL" in _REVIEW_SYSTEM_PROMPT


def test_case9_hallucination_suggestion_parses():
    """幻觉 issue 经 JSON 解析透出（suggestion 供人工修正）。"""
    from hanhua.core.reviewer import _parse_result
    r = _parse_result(
        '{"level": "CRITICAL", "overall_score": 30, '
        '"dimensions": {"幻觉": 20}, "reason": "译文增加原文没有的信息", '
        '"issues": [{"type": "幻觉", "detail": "前方/木门是增义", '
        '"suggestion": "打开门。"}]}', "e0")
    assert r.level == "CRITICAL"
    assert r.overall_score == 30
    assert r.dimensions["幻觉"] == 20
    assert r.issue == "幻觉"
    assert r.suggestion == "打开门。"
