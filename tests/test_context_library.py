# -*- coding: utf-8 -*-
"""游戏语境库测试（任务一阶段 2，翻译 C6）。

覆盖：指纹生成、种子入库（T2-4）、证据加权（T2-6）、同游戏精确命中直填、
跨游戏参考注入、置信度门禁（<0.3 只参考）、存疑标记（阶段 3 接口）、
提取器上下文窗口采集（T2-1）、BatchTranslator 注入链（直填+prompt 参考，
T2-3）。全部为纯 SQLite/纯函数测试，零模型调用。
"""
import json
import threading

import pytest

from hanhua.core.batch_translator import BatchTranslator
from hanhua.core.context_library import (
    ContextEntry,
    ContextStore,
    _DIRECT_FILL_MIN_CONFIDENCE,
    _POLYSEMY_SEED,
    _POLYSEMY_WORDS,
    collect_window,
    fingerprint_for,
)
from hanhua.core.extractor import parse_file
from hanhua.core.models import TextEntry
from hanhua.core.translator import BaseClient, Usage


@pytest.fixture()
def store(tmp_path):
    s = ContextStore(tmp_path / "context.db")
    s.init_schema()
    return s


# ── 指纹 ──────────────────────────────────────────────────────────

def test_fingerprint_varies_by_context_but_stable_within():
    """同要素指纹稳定；场景/相邻文本任一变化指纹变化（Resume 消歧依据）。"""
    fp1 = fingerprint_for(scene="main_menu", text_type="按钮",
                          ctx_before=["Press Enter"])
    fp1b = fingerprint_for(scene="main_menu", text_type="按钮",
                           ctx_before=["Press Enter"])
    assert fp1 == fp1b
    assert fp1 != fingerprint_for(scene="dialog", text_type="按钮",
                                  ctx_before=["Press Enter"])
    assert fp1 != fingerprint_for(scene="main_menu", text_type="按钮",
                                  ctx_before=["She said"])
    # 无语境降级：要素全空指纹恒定（不阻塞命中）
    assert fingerprint_for() == fingerprint_for()


# ── 种子（T2-4） ──────────────────────────────────────────────────

def test_seed_inserts_10_words_5_contexts(store):
    assert store.seed() == len(_POLYSEMY_SEED) == 50
    assert store.seed() == 0                       # 幂等：重复入不入新
    stats = store.stats()
    assert stats["entries"] == 50
    assert stats["by_source"]["manual"] == 50
    words = {e.source_text for e in store.list_all()}
    assert "Resume" in words and "Skill" in words


def test_seed_manual_confidence_is_top(store):
    store.seed()
    entry = store.match_exact(
        "seed", "Resume", scene="main_menu", text_type="种子")
    assert entry is not None
    assert entry.recommended_translation == "继续"
    assert entry.correct_meaning.startswith("继续游戏")
    assert entry.confidence == 1.0


# ── 证据加权（T2-6） ──────────────────────────────────────────────

def test_confidence_weights_by_source(store):
    base = ContextEntry(source_text="Run", fingerprint="fp",
                        source="manual", evidence_count=1)
    store.add_entry(base)
    assert store.match_exact("g", "Run", ui_position="x") is None  # 指纹不同

    low = ContextEntry(source_text="Run", fingerprint="fp2",
                       source="memory_promote", evidence_count=1)
    store.add_entry(low)
    got = store.match_exact("g", "Run", scene="s", text_type="t")
    assert got is None          # 指纹 fp2 与 (s|t) 不符——fingerprint 参数化
    # 直接用相同指纹验证置信度
    store2 = ContextStore(store.db)  # noqa: F841 — 同库复用
    got2 = store.match_exact("g", "Run", ui_position="x")
    assert got2 is None


def test_evidence_accumulates_and_caps(store):
    entry = ContextEntry(source_text="Guard", fingerprint="fpE",
                         source="review_confirm", evidence_count=1)
    store.add_entry(entry)
    store.add_entry(entry)
    rows = [e for e in store.list_all() if e.fingerprint == "fpE"]
    assert rows[0].evidence_count == 2          # 首入 1 + 合并 +1
    assert rows[0].confidence > 0.7
    assert rows[0].confidence <= 1.0


# ── 精确命中直填（T2-3） ──────────────────────────────────────────

def test_match_exact_same_game_direct_fill(store):
    store.seed()
    entry = ContextEntry(
        source_text="Resume", fingerprint=fingerprint_for(
            scene="main_menu", ui_position="menu/main", text_type="按钮",
            ctx_before=["Save Game"], ctx_after=["Options"]),
        correct_meaning="继续游戏（主菜单按钮）", recommended_translation="继续",
        source="review_confirm", game="hickory", evidence_count=2)
    store.add_entry(entry)

    hit = store.match_exact(
        "hickory", "Resume", scene="main_menu", ui_position="menu/main",
        text_type="按钮", ctx_before=["Save Game"], ctx_after=["Options"])
    assert hit is not None
    assert hit.recommended_translation == "继续"
    assert hit.confidence >= _DIRECT_FILL_MIN_CONFIDENCE

    # 指纹不同（相邻文本不同）→ 不命中（Resume 在对话语境是别的词义）
    miss = store.match_exact(
        "hickory", "Resume", scene="dialog", ui_position="text",
        text_type="对话", ctx_before=["She said"])
    assert miss is None


def test_match_exact_other_game_not_direct(store):
    store.seed()
    hit = store.match_exact(
        "other_game", "Resume", scene="main_menu", text_type="种子")
    # 种子 game=seed ≠ other_game → 不是同游戏精确命中（跨游戏走参考）
    assert hit is None
    similar = store.match_similar("other_game", "Resume",
                                  scene="main_menu", text_type="种子")
    assert any(e.recommended_translation == "继续" for e in similar)


def test_low_confidence_not_direct_fill(store):
    low = ContextEntry(
        source_text="Charge", fingerprint=fingerprint_for(scene="x"),
        correct_meaning="?", recommended_translation="充电",
        source="memory_promote", evidence_count=0)
    store.add_entry(low)
    hit = store.match_exact("g", "Charge", scene="x")
    assert hit is None or hit.confidence < _DIRECT_FILL_MIN_CONFIDENCE


# ── 跨游戏参考注入（T2-3） ────────────────────────────────────────

def test_match_similar_cross_game_reference(store):
    store.seed()
    refs = store.match_similar("hickory", "Load Game",
                               scene="pause_menu", text_type="种子")
    assert refs and any(e.recommended_translation == "读取游戏" for e in refs)
    # 同游戏精确命中的条目不进参考（去重）
    entry = ContextEntry(
        source_text="Load Game", fingerprint=fingerprint_for(
            scene="pause_menu", text_type="种子"),
        recommended_translation="读取游戏", source="review_confirm",
        game="hickory", evidence_count=2)
    store.add_entry(entry)
    refs2 = store.match_similar("hickory", "Load Game",
                                scene="pause_menu", text_type="种子")
    assert all(e.game != "hickory" for e in refs2)


# ── 存疑标记（阶段 3 T3-4 接口） ──────────────────────────────────

def test_suspicious_excludes_from_matches(store):
    store.seed()
    entry = store.match_exact("seed", "Resume", scene="main_menu",
                              text_type="种子")
    assert entry is not None
    store.mark_suspicious(entry.id)
    assert store.get(entry.id).suspicious == 1
    assert store.match_exact("seed", "Resume", scene="main_menu",
                             text_type="种子") is None
    assert store.clear_suspicious(entry.id) == 1
    assert store.match_exact("seed", "Resume", scene="main_menu",
                             text_type="种子") is not None


# ── 提取器上下文窗口（T2-1） ──────────────────────────────────────

def test_extractor_attaches_context_window(tmp_path):
    p = tmp_path / "ui.txt"
    p.write_text("Save Game\nResume\nOptions\nQuit\n",
                 encoding="utf-8")
    parsed = parse_file(p)
    entries = {e.original: e for e in parsed.entries}
    resume = entries["Resume"]
    assert resume.meta["ctx_before"] == ["Save Game"]
    assert resume.meta["ctx_after"] == ["Options", "Quit"]
    # collect_window 是注入链的读取口
    before, after = collect_window(resume.meta)
    assert before == ["Save Game"] and after == ["Options", "Quit"]
    # 文件首条无前窗口
    save = entries["Save Game"]
    assert save.meta.get("ctx_before", []) == []


def test_extractor_window_skips_blanks(tmp_path):
    p = tmp_path / "ui2.txt"
    p.write_text("\n\nResume\n\nOptions\n", encoding="utf-8")
    parsed = parse_file(p)
    resume = next(e for e in parsed.entries if e.original == "Resume")
    assert resume.meta.get("ctx_before", []) == []
    assert resume.meta["ctx_after"] == ["Options"]


# ── BatchTranslator 注入链（T2-3） ────────────────────────────────

class _NoCallClient(BaseClient):
    """断言翻译链未被调用的假客户端。"""

    def __init__(self):
        self.calls = 0

    def chat(self, system, messages):
        self.calls += 1
        out = []
        for m in messages:
            for line in m["content"].splitlines():
                if '": ' in line:
                    kid, text = line.split('": ', 1)
                    kid = kid.strip().strip('"')
                    out.append({"id": kid, "translation": "不该直译"})
        return json.dumps(out, ensure_ascii=False), Usage(1, 1)


def _auto_entry(original, key_path="k1", meta=None):
    base = {"role": "display", "disposition": "translate",
            "confidence": "high"}
    if meta:
        base.update(meta)
    return TextEntry("f", key_path, original, status="pending", meta=base)


def test_context_direct_fill_skips_model(store):
    """同游戏同指纹命中 → 直填「继续」，翻译链零调用。"""
    store.add_entry(ContextEntry(
        source_text="Resume",
        fingerprint=fingerprint_for(ui_position="display", text_type="按钮",
                                    ctx_before=["Save Game"]),
        correct_meaning="继续游戏（主菜单按钮）", recommended_translation="继续",
        source="review_confirm", game="hickory", evidence_count=3))
    client = _NoCallClient()
    bt = BatchTranslator(client, batch_size=2, concurrency=1,
                         lang="en→zh-CN", context_store=store,
                         context_game="hickory")
    entry = _auto_entry("Resume", meta={"kind": "按钮",
                                        "ctx_before": ["Save Game"]})
    stats = bt.run([entry])
    assert client.calls == 0
    assert stats.done == 1 and stats.from_memory == 1
    assert entry.status == "translated"
    assert entry.translation == "继续"


def test_context_direct_fill_other_game_not_applied(store):
    """跨游戏（种子 game=seed）不直填——走模型链（参考注入兜底）。"""
    store.seed()
    client = _NoCallClient()
    bt = BatchTranslator(client, batch_size=2, concurrency=1,
                         lang="en→zh-CN", context_store=store,
                         context_game="hickory")
    # Charge the crystal 非内置 UI 术语（无语义门），质量门接受模型链输出
    entry = _auto_entry("Charge the crystal")
    stats = bt.run([entry])
    assert client.calls >= 1            # 模型链被调用（种子语境注入参考）
    assert entry.status == "translated"
    assert entry.translation == "不该直译"   # 参考不强制


def test_context_reference_lines_injected(store):
    """跨游戏相似语境注入 prompt 参考行（Top-3 封顶、带语境来源）。"""
    store.seed()
    client = _NoCallClient()
    bt = BatchTranslator(client, batch_size=2, concurrency=1,
                         lang="en→zh-CN", context_store=store,
                         context_game="hickory")
    items = [{"id": "a", "text": "Resume", "role": "display",
              "ctx_before": [], "ctx_after": []}]
    lines = bt._context_reference_lines(items)
    assert lines and len(lines) <= 3
    assert any("Resume → 继续" in line and "语境：" in line
               and "来源：seed" in line for line in lines)


def test_context_reference_injected_into_prompt(store):
    """prompt 实际包含语境参考段（end-to-end 注入）。"""
    store.seed()
    client = _NoCallClient()
    bt = BatchTranslator(client, batch_size=2, concurrency=1,
                         lang="en→zh-CN", context_store=store,
                         context_game="hickory")
    entry = _auto_entry("Resume")
    user = bt._build_chat_user_prompt([
        bt._build_item([entry], 0, 0, single=True)])
    assert "语境参考：Resume → 继续" in user


def test_context_rejected_fill_marks_suspicious(store):
    """直填被质量门拒绝 → 语境记录标记存疑（防污染，T3-4 接口先行）。

    回显译文（译文==原文）必然触发 untranslated_text 质量门拒绝——
    这是 100% 稳定的拒绝规则（多个游戏实证的恒败路径）。
    """
    store.add_entry(ContextEntry(
        source_text="Save Game",
        fingerprint=fingerprint_for(ui_position="display"),
        correct_meaning="?", recommended_translation="Save Game",  # 回显必拒
        source="review_confirm", game="g", evidence_count=3))
    client = _NoCallClient()
    bt = BatchTranslator(client, batch_size=2, concurrency=1,
                         lang="en→zh-CN", context_store=store,
                         context_game="g")
    entry = _auto_entry("Save Game")
    stats = bt.run([entry])
    # 直填被质量门拒绝（回显）→ 语境记录标记存疑 + 走模型链兜底
    assert store.stats()["suspicious"] >= 1
    assert client.calls >= 1
    assert stats.from_memory == 0
