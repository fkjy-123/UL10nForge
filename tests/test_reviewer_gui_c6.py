# -*- coding: utf-8 -*-
"""翻译 C6：GUI 主路径接入语义审核与 C5 门禁沉淀。

- review_entries：runner 与 GUI 共用的审核核心——条目筛选（translated
  非回显）、五维审核、术语词对 C5 门禁沉淀；无凭据/无条目 → used=False
  不阻断调用方。
- text_type_for：runner 本地函数迁移为 reviewer 公共函数（两入口同源）。
- ProjectStore.update_entry_metas：审核结论批量落 store meta（审校页
  「需要优化」筛选依据），保留既有字段。
- ReviewPage：状态筛选下拉含「需要优化」，按 meta.review_issue 过滤。
"""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from hanhua.core.glossary import GlossaryStore
from hanhua.core.memory import ProjectStore
from hanhua.core.models import TextEntry
from hanhua.core.reviewer import (
    ReviewResult,
    review_entries,
    text_type_for,
)
from hanhua.ui.app_state import AppState
from hanhua.ui.pages.review_page import ReviewPage
from hanhua.core.settings import SettingsStore


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Window:
    def navigate(self, _page):
        pass


def _state(tmp_path) -> AppState:
    settings = SettingsStore(tmp_path / "settings.json")
    settings.load()
    return AppState(tmp_path, settings)


class _FakeGlossary:
    """记录 add_reviewed 调用的替身（C5 门禁本身由 test_glossary_c5 覆盖）。"""

    def __init__(self, reject: set[str]):
        self.reject = reject
        self.calls: list[tuple] = []

    def add_reviewed(self, term, trans, context="", game=""):
        self.calls.append((term, trans, context, game))
        if term in self.reject:
            return f"单 token 高频普通词拒绝：{term}"
        return ""


def _entries() -> list[TextEntry]:
    return [
        TextEntry(file_id="a", key_path="k1", original="Resume",
                  translation="简历", status="translated",
                  meta={"kind": "us"}),
        TextEntry(file_id="a", key_path="k2", original="Quit",
                  translation="退出", status="translated"),
        TextEntry(file_id="a", key_path="k3", original="Hello",
                  translation="Hello", status="translated"),   # 回显跳过
        TextEntry(file_id="a", key_path="k4", original="x",
                  translation="", status="translated"),        # 空译文跳过
        TextEntry(file_id="a", key_path="k5", original="y",
                  translation="y2", status="pending"),         # 非 translated
        TextEntry(file_id="a", key_path="k6", original="Left Paddle",
                  translation="左拨片", status="translated",
                  meta={"kind": "plain"}),
    ]


def _fake_batch(monkeypatch, results: dict[str, ReviewResult]):
    monkeypatch.setattr(
        "hanhua.core.reviewer.SemanticReviewer.usable",
        property(lambda self: True))
    monkeypatch.setattr(
        "hanhua.core.reviewer.SemanticReviewer.review_batch",
        lambda self, items, timeout=None: results)


# ── review_entries：条目筛选与全过不沉淀 ──────────────────────────

def test_review_entries_skips_echo_and_non_translated():
    """回显/空译文/非 translated 不进审核；items 只含真译文。"""
    fake = _FakeGlossary(reject=set())
    seen: list[str] = []

    def capture(self, items, timeout=None):
        seen.extend(it.entry_id for it in items)
        return {}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "hanhua.core.reviewer.SemanticReviewer.usable",
        property(lambda self: True))
    monkeypatch.setattr(
        "hanhua.core.reviewer.SemanticReviewer.review_batch", capture)
    summary = review_entries(_entries(), fake, game_name="G")
    monkeypatch.undo()

    assert summary["used"] is True
    assert sorted(seen) == ["e0", "e1", "e2"]        # 3 条真译文
    assert summary["reviewed"] == 0
    assert summary["flagged"] == []
    assert fake.calls == []                           # 无 flag 不沉淀
    assert summary["pairs_added"] == 0


def test_review_entries_all_pass_no_pairs():
    fake = _FakeGlossary(reject=set())
    monkeypatch = pytest.MonkeyPatch()
    _fake_batch(monkeypatch, {
        "e0": ReviewResult("e0", verdict="pass"),
        "e1": ReviewResult("e1", verdict="pass"),
        "e2": ReviewResult("e2", verdict="pass"),
    })
    summary = review_entries(_entries(), fake, game_name="G")
    monkeypatch.undo()

    assert summary["reviewed"] == 3
    assert summary["flagged"] == []
    assert fake.calls == []


def test_review_entries_no_entries_returns_unused():
    fake = _FakeGlossary(reject=set())
    notes: list[str] = []
    summary = review_entries([], fake, game_name="G", on_note=notes.append)
    assert summary["used"] is False
    assert notes == []


def test_review_entries_without_credentials_warns():
    """无审核凭据 → used=False + on_note 告警，不阻断调用方。"""
    fake = _FakeGlossary(reject=set())
    notes: list[str] = []
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "hanhua.core.reviewer.SemanticReviewer.usable",
        property(lambda self: False))
    summary = review_entries(
        _entries(), fake, game_name="G", on_note=notes.append)
    monkeypatch.undo()

    assert summary["used"] is False
    assert any("审核" in n for n in notes)


# ── review_entries：词对提取 + C5 门禁沉淀 ─────────────────────────

def test_review_entries_sediments_pairs_through_gate():
    """flag 条目的术语词对经 add_reviewed 沉淀：黑名单拒绝、组合词对
    入库，context 取首次含 term 的原文例句。"""
    fake = _FakeGlossary(reject={"Resume"})
    monkeypatch = pytest.MonkeyPatch()
    _fake_batch(monkeypatch, {
        "e0": ReviewResult("e0", verdict="flag", issue="术语错误",
                           reason="Resume 应译为继续",
                           suggestion="Resume→继续"),
        "e1": ReviewResult("e1", verdict="pass"),
        "e2": ReviewResult("e2", verdict="flag", issue="专名误译",
                           reason="Left Paddle 是设备名",
                           suggestion="Left Paddle→左拨片"),
    })
    notes: list[str] = []
    summary = review_entries(
        _entries(), fake, game_name="G", on_note=notes.append)
    monkeypatch.undo()

    assert summary["used"] is True
    assert len(summary["flagged"]) == 2
    assert summary["pairs_added"] == 1
    assert list(summary["pairs_rejected"]) == ["Resume"]
    # (Resume, 继续) 被 C5 门禁拒绝（单 token 高频普通词）
    assert fake.calls[0][:2] == ("Resume", "继续")
    # (Left Paddle, 左拨片) 入库：context = 首次含该词的原文例句
    assert fake.calls[1][:2] == ("Left Paddle", "左拨片")
    assert fake.calls[1][2] == "Left Paddle"
    assert fake.calls[1][3] == "G"
    # 审核开始日志（GUI 与 runner 同源）
    assert any("开始语义审核 3 条" in n for n in notes)


def test_review_entries_pairs_survive_pure_chinese_suggestion():
    """建议为纯中文（无「英文→中文」分隔符）时按「短原文→建议」沉淀
    （runner 既有形态 2：'Resume' 建议 '继续'）。"""
    fake = _FakeGlossary(reject=set())
    monkeypatch = pytest.MonkeyPatch()
    _fake_batch(monkeypatch, {
        "e0": ReviewResult("e0", verdict="flag", issue="术语错误",
                           reason="按钮语境",
                           suggestion="建议译为 继续"),
    })
    summary = review_entries(_entries(), fake, game_name="G")
    monkeypatch.undo()
    assert summary["pairs_added"] == 1
    assert fake.calls[0][:2] == ("Resume", "继续")


# ── text_type_for（runner 本地函数迁移为公共函数） ─────────────────

def test_text_type_for_kinds():
    assert text_type_for({"kind": "us"}) == "DLL 字符串"
    assert text_type_for({"kind": "il2cpp"}) == "IL2CPP 字符串"
    assert text_type_for({"kind": "textasset"}) == "文本脚本"
    assert text_type_for({"kind": "plain"}) == "纯文本"
    assert text_type_for({"role": "button"}) == "UI 显示文本"
    assert text_type_for({"role": "log"}) == "调试日志"
    assert text_type_for({}) == "游戏文本"


# ── ProjectStore.update_entry_metas：审核结论落 store ──────────────

def test_update_entry_metas_merges_fields(tmp_path):
    store = ProjectStore(tmp_path / "m.db")
    store.init_schema()
    store.add_file("f", "x.txt", "plain", "utf-8", "lf")
    store.upsert_entries([{
        "file_id": "f", "key_path": "l/1", "original": "Resume",
        "status": "pending", "meta": {"source": "scan"},
    }])
    updated = store.update_entry_metas([
        ("f", "l/1", {"review_issue": "术语错误",
                      "review_reason": "Resume 应译为继续",
                      "review_suggestion": "继续"}),
        ("f", "missing", {"review_issue": "术语错误"}),   # 不存在跳过
    ])
    assert updated == 1
    rows = store.get_entries()
    assert len(rows) == 1
    meta = json.loads(rows[0]["meta"])
    assert meta["review_issue"] == "术语错误"
    assert meta["review_suggestion"] == "继续"
    assert meta["source"] == "scan"                       # 既有字段保留
    assert rows[0]["status"] == "pending"                 # 状态不动


def test_update_entry_metas_empty_noop(tmp_path):
    store = ProjectStore(tmp_path / "m.db")
    store.init_schema()
    assert store.update_entry_metas([]) == 0


# ── ReviewPage：需要优化筛选 ───────────────────────────────────────

def test_review_page_has_needs_review_filter(qapp, tmp_path):
    page = ReviewPage(_state(tmp_path), _Window())
    assert page.status_combo.findText("需要优化") >= 0


def test_review_page_needs_review_filters_by_meta(qapp, tmp_path):
    page = ReviewPage(_state(tmp_path), _Window())
    page.model.setEntries([
        {"id": 1, "file_id": "f", "key_path": "a", "original": "Resume",
         "translation": "简历", "status": "translated", "locked": False,
         "meta": {"review_issue": "术语错误"}},
        {"id": 2, "file_id": "f", "key_path": "b", "original": "Quit",
         "translation": "退出", "status": "translated", "locked": False,
         "meta": {}},
    ])
    page.status_combo.setCurrentText("需要优化")
    visible = [
        page.proxy.mapToSource(page.proxy.index(i, 0)).row()
        for i in range(page.proxy.rowCount())
    ]
    assert visible == [0]
    # 普通状态筛选不受影响
    page.status_combo.setCurrentText("已翻译")
    visible2 = [
        page.proxy.mapToSource(page.proxy.index(i, 0)).row()
        for i in range(page.proxy.rowCount())
    ]
    assert sorted(visible2) == [0, 1]
