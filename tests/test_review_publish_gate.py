# -*- coding: utf-8 -*-
"""Phase A 发布门端到端测试（审计 §14 Phase A：ReviewOutcome → Atomic
Persistence → PublishGate）。

覆盖审计最高优先级 P0-1/P0-5/P0-6/P0-7 的落地闭环：
  1. CRITICAL 判定 → NEEDS_REVISION 终态 → 持久化 → 写回门拒绝；
  2. 重译失败 → BLOCKED 完整领域状态（status=blocked / 译文清空 /
     rejected_candidate 保留）→ 持久化 → 重启后写回门仍拒绝；
  3. 审核错误（TRANSPORT_ERROR）→ REVIEW_ERROR 终态，不伪装成 pass；
  4. APPROVED 正常路径可发布 → 计入写回就绪统计；
  5. 混合 store：blocked 条目被写回预检排除（_count_write_ready_translations）；
  6. is_write_ready / review_publishable 发布矩阵单测。
"""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from hanhua.core.memory import ProjectStore
from hanhua.core.models import STATUS_BLOCKED, TextEntry
from hanhua.core.project import _count_write_ready_translations
from hanhua.core.quality import is_write_ready
from hanhua.core.review_outcome import (
    APPROVED, APPROVED_MINOR, BLOCKED, CANCELLED, NEEDS_REVISION,
    PARSE_ERROR, REVIEW_ERROR, TRANSPORT_ERROR, review_publishable,
)
from hanhua.core.reviewer import ReviewResult, review_entries


# ── 替身 ───────────────────────────────────────────────────────────

class _FakeGlossary:
    """空术语库替身（本文件不测沉淀）。"""

    def __init__(self):
        self.calls = []

    def add_reviewed(self, term, trans, context="", game=""):
        from hanhua.core.glossary import CANDIDATE, DepositResult
        self.calls.append((term, trans, context, game))
        return DepositResult(CANDIDATE, term=term)


class _FakeTranslator:
    """重译替身：按调用次数返回 (ok, translation)。"""

    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.calls = 0
        self.feedbacks: list[str] = []

    def retranslate_with_feedback(self, entry, feedback, round_no=1):
        self.calls += 1
        self.feedbacks.append(feedback)
        return self.rounds[min(self.calls - 1, len(self.rounds) - 1)]


def _fake_review(monkeypatch, results: dict[str, ReviewResult]):
    """把 SemanticReviewer 换成替身：usable + review_batch 返回 (results, 0)。"""
    monkeypatch.setattr(
        "hanhua.core.reviewer.SemanticReviewer.usable",
        property(lambda self: True))
    monkeypatch.setattr(
        "hanhua.core.reviewer.SemanticReviewer.review_batch",
        lambda self, items, timeout=None, **kwargs: (results, 0))
    # 4B 重译通道禁用（2026-08-14 起 _retranslate_with_feedback 4B 优先
    # 且 reviewer 已 usable——本文件验证发布门语义，必须走 translator
    # fake 确定性路径；否则本地 4B 模型运行时会真实重译，断言不稳）
    monkeypatch.setattr(
        "hanhua.core.reviewer.SemanticReviewer.retranslate_with_feedback",
        lambda self, original, translation, feedback, **kwargs: "")


def _entry(original="Press Resume to continue", translation="按下继续继续游戏",
           status="translated", meta=None, key_path="k1") -> TextEntry:
    return TextEntry(
        "f", key_path, original, translation=translation, status=status,
        meta=meta or {"role": "display", "disposition": "translate",
                      "confidence": "high"})


def _store(tmp_path, entries: list[TextEntry]) -> ProjectStore:
    store = ProjectStore(tmp_path / "m.db")
    store.init_schema()
    store.add_file("f", "x.txt", "plain", "utf-8", "lf")
    store.upsert_entries([{
        "file_id": e.file_id, "key_path": e.key_path,
        "original": e.original, "status": e.status,
        "translation": e.translation, "meta": e.meta,
    } for e in entries])
    return store


def _load(store: ProjectStore) -> dict:
    row = store.get_entries()[0]
    row["meta"] = json.loads(row["meta"] or "{}")
    return row


# ── 1. CRITICAL → NEEDS_REVISION → 持久化 → 写回门拒绝 ─────────────

def test_critical_becomes_needs_revision_and_blocks_writeback(monkeypatch,
                                                              tmp_path):
    """CRITICAL 判定、无 translator → NEEDS_REVISION 终态原子持久化，
    写回门（is_write_ready）拒绝。"""
    entry = _entry()
    store = _store(tmp_path, [entry])
    _fake_review(monkeypatch, {
        "e0": ReviewResult("e0", level="CRITICAL", reason="否定颠倒"),
    })
    summary = review_entries([entry], _FakeGlossary(), store=store,
                             game_name="G", max_send_rate=1.0)
    assert summary["used"] is True
    assert summary["flagged"][0].level == "CRITICAL"
    # 终态 + 原子持久化
    assert entry.meta["review_outcome"] == NEEDS_REVISION
    assert entry.meta["review_level"] == "CRITICAL"
    assert entry.meta["need_retranslate"] is True
    assert entry.meta["quality_passed"] is False
    assert entry.status == "translated"   # NEEDS_REVISION 保留译文供审校
    row = _load(store)
    assert row["meta"]["review_outcome"] == NEEDS_REVISION
    assert row["meta"]["quality_passed"] is False
    # 写回门拒绝
    assert is_write_ready("translated", "按下继续继续游戏", row["meta"]) is False


# ── 2. CRITICAL → 重译失败 → BLOCKED 恢复安全状态 ───────────────────

def test_retranslate_failure_becomes_blocked_safe_state(monkeypatch,
                                                        tmp_path):
    """CRITICAL 重译失败 → BLOCKED：status=blocked、译文清空、
    rejected_candidate 保留坏译文供人工复核；持久化后重启写回门仍拒绝。"""
    entry = _entry(translation="旧坏译文")
    store = _store(tmp_path, [entry])
    _fake_review(monkeypatch, {
        "e0": ReviewResult("e0", level="CRITICAL", reason="否定颠倒",
                           suggestion="不要打开门"),
    })
    summary = review_entries([entry], _FakeGlossary(), store=store,
                             translator=_FakeTranslator([(False, "")]),
                             game_name="G", max_send_rate=1.0)
    assert summary["blocked"] == 1
    # 完整领域状态
    assert entry.status == STATUS_BLOCKED
    assert entry.meta["review_outcome"] == BLOCKED
    assert entry.meta["review_blocked"] is True
    assert entry.meta["quality_passed"] is False
    assert entry.translation == ""                 # 发布槽位清空
    assert entry.meta["rejected_candidate"] == "旧坏译文"  # 坏译文保留复核
    # 持久化 + 重启（重新打开同一 db 文件）后状态仍正确
    row = _load(store)
    assert row["status"] == STATUS_BLOCKED
    assert row["meta"]["review_outcome"] == BLOCKED
    assert row["meta"]["rejected_candidate"] == "旧坏译文"
    reloaded = ProjectStore(tmp_path / "m.db")
    reloaded.init_schema()
    r2 = _load(reloaded)
    assert r2["status"] == STATUS_BLOCKED
    assert is_write_ready(r2["status"], r2["translation"], r2["meta"]) is False
    assert r2["translation"] == ""


def test_blocked_after_two_unconverged_rounds(monkeypatch, tmp_path):
    """CRITICAL 重译两轮仍 CRITICAL → BLOCKED（上限 2 轮即停）。"""
    entry = _entry(translation="旧译文")
    store = _store(tmp_path, [entry])

    def fake_review(entry, reviewer=None, app_dir=None, term_hint="",
                context_hint="", game_context_hint=""):
        return ReviewResult("re", level="CRITICAL", reason="仍错译")

    monkeypatch.setattr("hanhua.core.reviewer._re_review", fake_review)
    _fake_review(monkeypatch, {
        "e0": ReviewResult("e0", level="CRITICAL", reason="错译"),
    })
    tr = _FakeTranslator([(True, "译1"), (True, "译2")])
    summary = review_entries([entry], _FakeGlossary(), store=store,
                             translator=tr, game_name="G", max_send_rate=1.0)
    assert tr.calls == 2
    assert summary["blocked"] == 1
    assert entry.status == STATUS_BLOCKED
    assert entry.meta["review_outcome"] == BLOCKED
    assert entry.meta["review_blocked_rounds"] == 2
    assert entry.translation == ""
    assert entry.meta["rejected_candidate"] == "译2"


# ── 3. 审核错误 → REVIEW_ERROR，不伪装 pass ─────────────────────────

def test_review_error_becomes_review_error_and_blocks(monkeypatch, tmp_path):
    """审核传输错误 → REVIEW_ERROR 终态持久化（fail-closed，不得转 PASS）。"""
    entry = _entry()
    store = _store(tmp_path, [entry])
    _fake_review(monkeypatch, {
        "e0": ReviewResult("e0", reason="审核请求失败", reviewed=False,
                           error=TRANSPORT_ERROR),
    })
    summary = review_entries([entry], _FakeGlossary(), store=store,
                             game_name="G", max_send_rate=1.0)
    assert summary["errors"] == 1
    assert entry.meta["review_outcome"] == REVIEW_ERROR
    assert entry.meta["review_error_kind"] == TRANSPORT_ERROR
    assert entry.meta["quality_passed"] is False
    assert is_write_ready(entry.status, entry.translation, entry.meta) is False
    row = _load(store)
    assert row["meta"]["review_outcome"] == REVIEW_ERROR
    # 错误不沉淀术语词对
    assert summary["pairs_added"] == 0


# ── 4. APPROVED 正常路径可发布 ─────────────────────────────────────

def test_approved_persists_and_is_write_ready(monkeypatch, tmp_path):
    entry = _entry()
    store = _store(tmp_path, [entry])
    _fake_review(monkeypatch, {
        "e0": ReviewResult("e0", level="PASS", reason="正确"),
    })
    summary = review_entries([entry], _FakeGlossary(), store=store,
                             game_name="G", max_send_rate=1.0)
    assert summary["outcomes"].get(APPROVED) == 1
    assert entry.meta["review_outcome"] == APPROVED
    assert entry.meta["quality_passed"] is True
    assert is_write_ready(entry.status, entry.translation, entry.meta) is True
    row = _load(store)
    assert row["meta"]["review_outcome"] == APPROVED
    assert is_write_ready(row["status"], row["translation"], row["meta"]) is True


# ── 5. 混合 store：写回预检排除非发布条目 ───────────────────────────

def test_write_ready_count_excludes_blocked(monkeypatch, tmp_path):
    """写回预检 _count_write_ready_translations：blocked 条目不计数，
    只 APPROVED 可发布（写回端按此单点做第一道预检）。"""
    good = _entry(original="Press Resume to continue", translation="按下继续")
    bad = _entry(original="Don't open the door", translation="不要开门",
                 key_path="k2")
    store = _store(tmp_path, [good, bad])
    _fake_review(monkeypatch, {
        "e0": ReviewResult("e0", level="PASS", reason="正确"),
        "e1": ReviewResult("e1", level="CRITICAL", reason="否定颠倒"),
    })
    # 两条一起进审核：good → APPROVED，bad → NEEDS_REVISION（无 translator）
    review_entries([good, bad], _FakeGlossary(), store=store,
                   game_name="G", max_send_rate=1.0)
    count = _count_write_ready_translations(store)
    assert count == 1
    # 直接构造 BLOCKED 条目（status=blocked 是终态）同样被排除
    blocked_entry = _entry(original="Open the chest", translation="",
                           status=STATUS_BLOCKED,
                           key_path="k3")
    store.upsert_entries([{
        "file_id": "f", "key_path": "k3", "original": "Open the chest",
        "status": STATUS_BLOCKED, "translation": "",
        "meta": {"quality_passed": False, "review_outcome": BLOCKED,
                 "review_blocked": True},
    }])
    assert _count_write_ready_translations(store) == 1


# ── 6. is_write_ready / review_publishable 发布矩阵单测 ─────────────

def test_is_write_ready_publishable_matrix():
    base = {"quality_passed": True, "confidence": "high"}
    assert is_write_ready("translated", "译文", base) is True
    assert is_write_ready("translated", "译文",
                          {**base, "review_outcome": APPROVED}) is True
    assert is_write_ready("translated", "译文",
                          {**base, "review_outcome": APPROVED_MINOR}) is True
    # 非发布终态一律拒绝
    for state in (NEEDS_REVISION, BLOCKED, REVIEW_ERROR, CANCELLED):
        assert is_write_ready(
            "translated", "译文",
            {**base, "review_outcome": state}) is False, state
    # 状态不是 translated（blocked 终态）直接拒绝
    assert is_write_ready(STATUS_BLOCKED, "译文", base) is False
    # 旧字段坏状态兼容拒绝
    assert is_write_ready("translated", "译文",
                          {**base, "review_blocked": True}) is False
    assert is_write_ready("translated", "译文",
                          {**base, "need_retranslate": True}) is False
    assert is_write_ready("translated", "译文",
                          {**base, "review_level": "MAJOR"}) is False


# ── 7. P0-4：failed 条目（quality_failed 强制通道）真正可达 ──────────

def _failed_entry(original="Press Resume to continue",
                  translation="坏译文", quality_reason="untranslated_text",
                  key_path="kf") -> TextEntry:
    return TextEntry(
        "f", key_path, original, translation=translation, status="failed",
        meta={"role": "display", "disposition": "translate",
              "confidence": "high", "quality_passed": False,
              "quality_reasons": [quality_reason]},
        quality_reasons=(quality_reason,))


def test_failed_entry_with_candidate_enters_mandatory_review(monkeypatch,
                                                             tmp_path):
    """审计 §11 矩阵「mechanical failed 有 candidate → 真正进入 mandatory
    审核」：status=failed 条目即使 max_send_rate=0（discretionary 关闭）
    也走 mandatory 通道送审；CRITICAL → 重译 → 再审 PASS → APPROVED，
    状态恢复 translated，可发布。"""
    entry = _failed_entry()
    store = _store(tmp_path, [entry])

    def fake_re_review(entry, reviewer=None, app_dir=None, term_hint="",
                    context_hint="", game_context_hint=""):
        return ReviewResult("re", level="PASS", reason="修正后正确")

    monkeypatch.setattr("hanhua.core.reviewer._re_review", fake_re_review)
    _fake_review(monkeypatch, {
        "e0": ReviewResult("e0", level="CRITICAL", reason="否定颠倒"),
    })
    tr = _FakeTranslator([(True, "修正后译文")])
    summary = review_entries([entry], _FakeGlossary(), store=store,
                             translator=tr, game_name="G", max_send_rate=0.0)
    # mandatory 通道不受 15% 预算：rate=0 仍送审
    assert summary["used"] is True
    assert summary["mandatory"] == 1
    assert summary["sent"] == 1
    # CRITICAL → 重译收敛 → APPROVED，恢复 translated 可发布
    assert tr.calls == 1
    assert summary["converged"] == 1
    assert entry.status == "translated"
    assert entry.meta["review_outcome"] == APPROVED
    assert entry.meta["quality_passed"] is True
    assert is_write_ready(entry.status, entry.translation, entry.meta) is True
    row = _load(store)
    assert row["status"] == "translated"
    assert row["meta"]["review_outcome"] == APPROVED
    assert is_write_ready(row["status"], row["translation"], row["meta"]) is True


def test_failed_entry_pass_verdict_never_approves_rejected_candidate(
        monkeypatch, tmp_path):
    """4B 判 PASS 但机械门已拒绝：机械证据优先，强制重译——坏候选
    绝不能因语义 PASS 直接发布；收敛只接受重译输出（已过机械门）。"""
    entry = _failed_entry(translation="残留英文的坏译文")
    store = _store(tmp_path, [entry])

    def fake_re_review(entry, reviewer=None, app_dir=None, term_hint="",
                    context_hint="", game_context_hint=""):
        return ReviewResult("re", level="PASS", reason="重译正确")

    monkeypatch.setattr("hanhua.core.reviewer._re_review", fake_re_review)
    _fake_review(monkeypatch, {
        "e0": ReviewResult("e0", level="PASS", reason="语义正确"),
    })
    tr = _FakeTranslator([(True, "合格的新译文")])
    summary = review_entries([entry], _FakeGlossary(), store=store,
                             translator=tr, game_name="G", max_send_rate=1.0)
    assert tr.calls == 1                      # PASS 也强制走重译
    assert "机械质量门最终失败" in tr.feedbacks[0]  # 附加机械失败原因
    assert summary["converged"] == 1
    assert entry.translation == "合格的新译文"      # 坏候选未进发布槽
    assert entry.meta["review_outcome"] == APPROVED
    assert is_write_ready(entry.status, entry.translation, entry.meta) is True


def test_failed_entry_without_candidate_blocked_not_reviewed(monkeypatch,
                                                             tmp_path):
    """无候选（空译文、无 raw_output）的 failed 条目：不占审核请求、
    不伪装成已审核，直接 BLOCKED 原子持久化。"""
    entry = _failed_entry(translation="", key_path="kn")
    store = _store(tmp_path, [entry])
    called = {"n": 0}

    def fake_review_batch(self, items, timeout=None, **kwargs):
        called["n"] += len(items)
        return {}, 0

    monkeypatch.setattr(
        "hanhua.core.reviewer.SemanticReviewer.usable",
        property(lambda self: True))
    monkeypatch.setattr(
        "hanhua.core.reviewer.SemanticReviewer.review_batch",
        fake_review_batch)
    summary = review_entries([entry], _FakeGlossary(), store=store,
                             game_name="G", max_send_rate=1.0)
    assert called["n"] == 0                    # 未送审
    assert summary["used"] is False
    assert summary["failed_no_candidate"] == 1
    assert summary["blocked"] == 1
    assert entry.meta["review_outcome"] == BLOCKED
    assert entry.status == STATUS_BLOCKED
    assert is_write_ready(entry.status, entry.translation, entry.meta) is False
    row = _load(store)
    assert row["status"] == STATUS_BLOCKED
    assert row["meta"]["review_outcome"] == BLOCKED


def test_failed_entry_no_translator_blocks_with_candidate_preserved(
        monkeypatch, tmp_path):
    """failed 条目无重译通道（translator=None）：fail-closed → BLOCKED，
    坏候选存入 rejected_candidate，发布槽位清空。"""
    entry = _failed_entry(translation="坏候选译文")
    store = _store(tmp_path, [entry])
    _fake_review(monkeypatch, {
        "e0": ReviewResult("e0", level="CRITICAL", reason="否定颠倒"),
    })
    summary = review_entries([entry], _FakeGlossary(), store=store,
                             game_name="G", max_send_rate=1.0)
    assert summary["blocked"] == 1
    assert entry.status == STATUS_BLOCKED
    assert entry.meta["review_outcome"] == BLOCKED
    assert entry.translation == ""
    assert entry.meta["rejected_candidate"] == "坏候选译文"
    row = _load(store)
    assert row["status"] == STATUS_BLOCKED
    assert is_write_ready(row["status"], row["translation"], row["meta"]) is False


def test_review_publishable_matrix():
    assert review_publishable({}) is True            # 缺省：机械门是第一道
    assert review_publishable({"quality_passed": True}) is True
    assert review_publishable({"review_outcome": APPROVED}) is True
    assert review_publishable({"review_outcome": APPROVED_MINOR}) is True
    assert review_publishable({"review_outcome": NEEDS_REVISION}) is False
    assert review_publishable({"review_outcome": BLOCKED}) is False
    assert review_publishable({"review_outcome": REVIEW_ERROR}) is False
    assert review_publishable({"review_outcome": CANCELLED}) is False
    assert review_publishable({"review_outcome": "PENDING"}) is False
    assert review_publishable({"review_blocked": True}) is False
    assert review_publishable({"review_error": True}) is False
    assert review_publishable({"need_revision": True}) is False
    assert review_publishable({"need_retranslate": True}) is False
    assert review_publishable({"review_level": "CRITICAL"}) is False
    assert review_publishable({"review_level": "MAJOR"}) is False
    # 显式终态覆盖旧字段（非 approved 终态优先拒绝）
    assert review_publishable(
        {"review_outcome": APPROVED, "review_blocked": True}) is True
