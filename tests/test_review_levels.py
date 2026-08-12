"""任务一阶段 1 测试（T1-8）：四级审核闭环全链路。

覆盖：四级判定解析、ReviewResult 扩展与 apply_verdict 分发、
风险分流决策表全分支、反馈重译注入、记忆门禁、再审收敛上限、
审核日志生成。
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from hanhua.core.batch_translator import BatchTranslator
from hanhua.core.models import TextEntry
from hanhua.core.reviewer import (
    ReviewResult,
    _memory_apply,
    _parse_level,
    _parse_result,
    _retranslate_with_feedback,
    write_review_report,
)
from hanhua.core.risk_gate import RiskSignals, evaluate_entry, gate_entries


def _entry(original="Save the game", translation="保存游戏",
           status="translated", meta=None) -> TextEntry:
    return TextEntry(
        "f", "k1", original, translation=translation, status=status,
        meta=meta or {"role": "display", "disposition": "translate",
                      "confidence": "high"})


# ── 四级判定解析（T1-1） ───────────────────────────────────────────
@pytest.mark.parametrize(
    ("raw", "expected"),
    (("PASS", "PASS"), ("pass", "PASS"), ("Pass", "PASS"),
     ("MINOR", "MINOR"), ("minor", "MINOR"),
     ("MAJOR", "MAJOR"), ("major", "MAJOR"),
     ("CRITICAL", "CRITICAL"), ("critical", "CRITICAL"),
     ("CRITICAL: 语义完全错误", "CRITICAL"),        # 前缀
     ("(MAJOR) 术语误用", "MAJOR"),                # 括号子串
     ("[MINOR] 语序", "MINOR"),                    # 方括号子串
     ("incorrect", "MAJOR"), ("flag", "MAJOR"),    # 旧词形兼容
     ("不合格", "MAJOR"), ("需要优化", "MAJOR"),
     ("", "PASS"), (None, "PASS"), ("？？？", "PASS"),  # 兜底
     ("PASS 完全正确", "PASS"), ("MINOR only", "MINOR")))
def test_parse_level(raw, expected):
    assert _parse_level(raw) == expected


def test_parse_result_valid_json():
    r = _parse_result(
        '{"level": "CRITICAL", "reason": "否定颠倒", '
        '"issues": [{"type": "否定", "detail": "don\'t 被漏译", '
        '"suggestion": "不要打开门"}]}', "e0")
    assert r is not None
    assert r.level == "CRITICAL"
    assert r.reason == "否定颠倒"
    assert r.issues[0]["type"] == "否定"
    assert r.issue == "否定"
    assert r.suggestion == "不要打开门"
    assert r.needs_optimization


def test_parse_result_fence_stripped():
    r = _parse_result('```json\n{"level": "MAJOR"}\n```', "e1")
    assert r is not None and r.level == "MAJOR"


def test_parse_result_non_json_fallback():
    r = _parse_result("这句话译得不对，Resume 应该是继续。", "e2")
    assert r is not None
    assert r.level == "PASS"           # 非 JSON 无四级标记词 → 保守 PASS
    assert r.reviewed is False
    assert "Resume" in r.reason        # 原文保留为 reason 供人工核查


def test_parse_result_non_json_plain_pass():
    r = _parse_result("翻译质量可以。", "e3")
    assert r is not None and r.level == "PASS"


# ── ReviewResult 扩展与分发（T1-2） ────────────────────────────────
@pytest.mark.parametrize(
    ("level", "optimization"),
    (("PASS", False), ("MINOR", False), ("MAJOR", True),
     ("CRITICAL", True)))
def test_needs_optimization_by_level(level, optimization):
    assert ReviewResult("e0", level=level).needs_optimization is optimization


def test_apply_verdict_pass_writes():
    entry = _entry()
    assert ReviewResult("e0", level="PASS").apply_verdict(entry) == "write"
    assert entry.meta["review_level"] == "PASS"
    assert "need_revision" not in entry.meta
    assert "need_retranslate" not in entry.meta


def test_apply_verdict_minor_records_and_passes():
    entry = _entry()
    r = ReviewResult("e0", level="MINOR", reason="语序略生硬")
    assert r.apply_verdict(entry) == "pass_minor"
    assert entry.meta["review_level"] == "MINOR"
    assert entry.meta["review_reason"] == "语序略生硬"
    assert "need_revision" not in entry.meta


def test_apply_verdict_major_revise():
    entry = _entry()
    r = ReviewResult("e0", level="MAJOR", reason="术语误用",
                     issues=({
                         "type": "术语错误", "detail": "Resume 应为继续",
                         "suggestion": "继续游戏"},))
    assert r.apply_verdict(entry) == "revise"
    assert entry.meta["review_level"] == "MAJOR"
    assert entry.meta["need_revision"] is True
    assert entry.meta["review_suggestion"] == "继续游戏"


def test_apply_verdict_critical_retranslate():
    entry = _entry()
    r = ReviewResult("e0", level="CRITICAL", reason="否定颠倒")
    assert r.apply_verdict(entry) == "retranslate"
    assert entry.meta["need_retranslate"] is True
    assert entry.meta["review_reason"] == "否定颠倒"


# ── 风险分流决策表全分支（T1-3） ───────────────────────────────────
def test_gate_quality_failed_forced():
    entry = _entry(status="failed")
    sig = evaluate_entry(entry)
    assert sig.risky
    assert "quality_failed" in sig.signals
    assert sig.priority == 6


def test_gate_glossary_conflict():
    entry = _entry(original="Press START to begin", translation="按开始键开始")
    sig = evaluate_entry(entry, [("START", "开始")])
    # START 命中词对且译文含标准译法「开始」→ 无冲突
    assert "glossary_conflict" not in sig.signals
    entry2 = _entry(original="Press START to begin", translation="按播放键")
    sig2 = evaluate_entry(entry2, [("START", "开始")])
    # 词对命中但译文未用标准译法 → 冲突送审
    assert "glossary_conflict" in sig2.signals


def test_gate_polysemy_wordlist():
    for word in ("Resume", "save", "CHARGE", "Load", "Quit"):
        sig = evaluate_entry(_entry(original=f"Press {word} now"))
        assert "polysemy" in sig.signals
    sig = evaluate_entry(_entry(original="Hello world"))
    assert "polysemy" not in sig.signals


def test_gate_long_text():
    long_text = " ".join(f"word{i}" for i in range(70))
    sig = evaluate_entry(_entry(original=long_text))
    assert "long_text" in sig.signals
    sig2 = evaluate_entry(_entry(original="short text"))
    assert "long_text" not in sig2.signals


@pytest.mark.parametrize("word", ["not", "no", "never", "if", "unless",
                                  "only", "more", "than", "but"])
def test_gate_negation_conditional(word):
    sig = evaluate_entry(_entry(original=f"You {word} open the door"))
    assert "negation_conditional" in sig.signals


def test_gate_character_text_dialogue_role():
    entry = _entry(meta={"role": "dialogue", "disposition": "translate",
                         "confidence": "high"})
    sig = evaluate_entry(entry)
    assert "character_text" in sig.signals


def test_gate_plain_passes_through():
    entry = _entry(original="Open the door", translation="打开门")
    sig = evaluate_entry(entry)
    assert not sig.risky
    assert sig.priority == 0


def test_gate_priority_ordering():
    # 同时命中 quality_failed + long_text → 最高优先级 6
    long_text = " ".join(f"word{i}" for i in range(70))
    sig = evaluate_entry(_entry(original=long_text, status="failed"))
    assert sig.priority == 6
    assert sig.signals[0] == "quality_failed"


def test_gate_entries_budget_truncation():
    # 100 条全可疑（15% 预算 = 15 条）→ 高优先级先保，低优先级截断
    entries = [_entry(original=f"Press Resume word{i}") for i in range(100)]
    to_review, passed, stats = gate_entries(entries, max_send_rate=0.15)
    assert stats["sent"] == 15
    assert stats["truncated"] == 85
    assert len(to_review) == 15
    assert len(passed) == 85
    # 全部同信号 → 信号数排序稳定，无崩溃
    assert all(e.original for e in to_review)


def test_gate_entries_priority_preserved():
    # failed 条目（优先级 6）必须入选，即使排在列表尾部
    entries = [_entry(original=f"Press Resume word{i}") for i in range(99)]
    entries.append(_entry(original="Press Resume fail", status="failed"))
    to_review, _passed, stats = gate_entries(entries, max_send_rate=0.15)
    assert stats["sent"] == 15
    # failed 优先级最高 → 排序最前（截断从低优先级开始，failed 必保）
    assert to_review[0].status == "failed"


def test_gate_entries_empty():
    to_review, passed, stats = gate_entries([])
    assert to_review == [] and passed == []
    assert stats["total"] == 0


def test_gate_entries_rate_zero_means_nothing_sent():
    entries = [_entry(original="Resume game") for _ in range(10)]
    to_review, _passed, stats = gate_entries(entries, max_send_rate=0.0)
    assert to_review == []
    assert stats["sent"] == 0
    assert stats["rate"] == 0.0


# ── 反馈重译注入（T1-4） ───────────────────────────────────────────
class _FakeChatClient:
    """按调用序号返回译文的假客户端（首坏后好）。"""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []
        self.config = None

    def chat(self, system, messages):
        content = "".join(m["content"] for m in messages
                          if m["role"] == "user")
        self.calls.append(content)
        out = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        return out, type("Usage", (), {"prompt_tokens": 5,
                                       "completion_tokens": 5})()


def test_retranslate_injects_feedback_prompt():
    client = _FakeChatClient(["保存游戏"])
    bt = BatchTranslator(client, batch_size=1, concurrency=1,
                         lang="en→zh-CN")
    entry = _entry(translation="存档游戏")
    ok, out = bt.retranslate_with_feedback(entry, "术语误用：Save 应译为保存")
    assert ok and out == "保存游戏"
    assert entry.translation == "保存游戏"
    assert "[审核反馈]" in client.calls[0]
    assert "术语误用：Save 应译为保存" in client.calls[0]
    assert entry.meta["review_round"] == 1


def test_retranslate_quality_gate_rejects_echo():
    # 回显原文 = 质量门失败 → 重译失败，attempt 记账
    client = _FakeChatClient(["Save the game"])
    bt = BatchTranslator(client, batch_size=1, concurrency=1,
                         lang="en→zh-CN")
    entry = _entry(translation="存档")
    ok, out = bt.retranslate_with_feedback(entry, "译文未翻译")
    assert ok is False
    assert int(entry.meta.get("attempt_count", 0)) >= 1


def test_retranslate_request_failure_returns_false():
    class _BrokenClient:
        config = None

        def chat(self, system, messages):
            raise RuntimeError("服务不可用")

    bt = BatchTranslator(_BrokenClient(), batch_size=1, concurrency=1)
    entry = _entry()
    ok, out = bt.retranslate_with_feedback(entry, "问题")
    assert ok is False and out == ""


# ── 记忆门禁（T1-6） ───────────────────────────────────────────────
class _FakeMemory:
    def __init__(self):
        self.added = []
        self.removed = []

    def add_memory(self, original, translation, model, lang):
        self.added.append((original, translation, model, lang))

    def remove_memory(self, original, model, lang):
        self.removed.append((original, model, lang))


def test_memory_gate_blocks_major_critical():
    mem = _FakeMemory()
    for level in ("MAJOR", "CRITICAL"):
        entry = _entry()
        _memory_apply(mem, entry, level, "model", "zh-CN")
        assert mem.removed, f"{level} 应移除坏记忆"
        assert mem.added == []
    mem2 = _FakeMemory()
    _memory_apply(mem2, _entry(), "CRITICAL", "m", "zh-CN")
    assert mem2.removed == [("Save the game", "m", "zh-CN")]


def test_memory_gate_pass_minor_enters_memory():
    mem = _FakeMemory()
    for level in ("PASS", "MINOR"):
        _memory_apply(mem, _entry(), level, "m", "zh-CN")
    assert len(mem.added) == 2
    assert mem.removed == []


def test_memory_gate_none_memory_is_noop():
    _memory_apply(None, _entry(), "CRITICAL", "m", "zh-CN")  # 不抛


# ── 再审收敛上限（T1-5） ───────────────────────────────────────────
@dataclass
class _FakeTranslator:
    rounds_ok: list[tuple[bool, str]]   # 每轮 (ok, translation)
    calls: int = 0

    def retranslate_with_feedback(self, entry, feedback, round_no=1):
        self.calls += 1
        return self.rounds_ok[min(self.calls - 1, len(self.rounds_ok) - 1)]


def test_convergence_after_one_round(monkeypatch):
    def fake_review(entry, reviewer=None, app_dir=None):
        return ReviewResult("re", level="PASS")

    monkeypatch.setattr("hanhua.core.reviewer._re_review", fake_review)
    tr = _FakeTranslator([(True, "继续游戏")])
    entry = _entry()
    result = _retranslate_with_feedback(
        tr, entry, ReviewResult("e0", level="CRITICAL", reason="错译"), None)
    assert result == "converged"
    assert tr.calls == 1
    assert entry.meta["review_level"] == "PASS"
    assert "review_blocked" not in entry.meta


def test_convergence_minor_after_retranslate(monkeypatch):
    def fake_review(entry, reviewer=None, app_dir=None):
        return ReviewResult("re", level="MINOR", reason="语序略生硬")

    monkeypatch.setattr("hanhua.core.reviewer._re_review", fake_review)
    tr = _FakeTranslator([(True, "继续游戏")])
    entry = _entry()
    result = _retranslate_with_feedback(
        tr, entry, ReviewResult("e0", level="MAJOR", reason="术语误用"), None)
    assert result == "converged"
    assert entry.meta["review_level"] == "MINOR"


def test_blocked_after_two_rounds(monkeypatch):
    def fake_review(entry, reviewer=None, app_dir=None):
        return ReviewResult("re", level="CRITICAL", reason="仍错译")

    monkeypatch.setattr("hanhua.core.reviewer._re_review", fake_review)
    tr = _FakeTranslator([(True, "译1"), (True, "译2")])
    entry = _entry()
    result = _retranslate_with_feedback(
        tr, entry, ReviewResult("e0", level="CRITICAL", reason="错译"), None)
    assert result == "blocked"
    assert tr.calls == 2                    # 上限 2 轮即停
    assert entry.meta["review_blocked"] is True
    assert entry.meta["review_blocked_rounds"] == 2


def test_blocked_when_retranslate_fails(monkeypatch):
    tr = _FakeTranslator([(False, "")])
    entry = _entry()
    result = _retranslate_with_feedback(
        tr, entry, ReviewResult("e0", level="CRITICAL", reason="错译"), None)
    assert result == "blocked"
    assert tr.calls == 1
    assert entry.meta["review_blocked"] is True


def test_review_never_reviews_failed_translation():
    # 回显译文不进送审池（review_entries 过滤——经 _entry_for 语义）
    entry = _entry(original="Save the game", translation="Save the game")
    from hanhua.core.reviewer import review_entries
    summary = review_entries([entry], None, app_dir=".")
    assert summary["used"] is False
    assert summary["sent"] == 0


# ── 审核日志（T1-7） ───────────────────────────────────────────────
def test_write_review_report(tmp_path):
    summary = {
        "sent": 40, "rate": 0.12, "reviewed": 40,
        "levels": {"PASS": 30, "MINOR": 5, "MAJOR": 3, "CRITICAL": 2,
                   "PARSE_FAIL": 0},
        "retranslated": 4, "converged": 3, "blocked": 1,
        "pairs_added": 1, "pairs_rejected": {"miss": "拒绝"},
        "flagged": [
            ReviewResult("e1", level="CRITICAL", reason="PRESS 译成媒体",
                         issues=({"type": "术语错误",
                                  "suggestion": "按开始键开始"},)),
            ReviewResult("e2", level="CRITICAL", reason="否定颠倒",
                         issues=()),
        ],
        "originals": {"e1": "PRESS TO START", "e2": "Don't open it"},
        "locators": {"e1": "f:k1", "e2": "f:k2"},
    }
    path = write_review_report(summary, tmp_path / "review_report.md",
                               game_name="hickory")
    text = path.read_text(encoding="utf-8")
    assert "hickory" in text
    assert "送审：40 条" in text
    assert "CRITICAL 2" in text
    assert "收敛 3" in text
    assert "PRESS TO START" in text
    assert "按开始键开始" in text
    assert "f:k1" in text


def test_write_review_report_no_critical(tmp_path):
    summary = {"sent": 1, "rate": 0.01, "reviewed": 1,
               "levels": {"PASS": 1, "MINOR": 0, "MAJOR": 0,
                          "CRITICAL": 0, "PARSE_FAIL": 0},
               "retranslated": 0, "converged": 0, "blocked": 0,
               "pairs_added": 0, "pairs_rejected": {}, "flagged": [],
               "originals": {}, "locators": {}}
    path = write_review_report(summary, tmp_path / "r.md")
    assert "无（本轮无 CRITICAL 级错译）" in path.read_text(encoding="utf-8")
