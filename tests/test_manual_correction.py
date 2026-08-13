"""Phase B-2：人工修正统一回流（审计 §6 P1-6）。

set_manual 过去只改 translation/status——审核终态残留（发布门误判）、
坏记忆留存（被改正的译文继续命中）、经验记忆/审计/矢量索引缺失。
本组测试覆盖 manual_correction 统一回流：清旧审核状态 + 写人工终态
+ 记忆提交/撤销 + 经验记忆最高权重写入 + 审计日志 + 矢量 outbox。
#9：失败/阻断文本自处理——reset_to_pending 清审核终态后重译成功可写回。
"""

import json
import sqlite3
import tempfile
from pathlib import Path

from hanhua.core.agent_memory import AgentMemory
from hanhua.core.batch_translator import _clear_review_state
from hanhua.core.manual_correction import manual_correction
from hanhua.core.memory import ProjectStore
from hanhua.core.quality import is_write_ready
from hanhua.core.review_outcome import review_publishable


def _store():
    store = ProjectStore(Path(tempfile.mkdtemp()) / "p.db")
    store.init_schema()
    return store


def _entry(store, original="Hello world", *, status="pending",
           translation="", meta=None):
    store.upsert_entries([{
        "file_id": "f1", "key_path": "k1", "original": original,
        "status": status, "meta": meta or {},
    }])
    if translation:
        store.conn.execute(
            "UPDATE entries SET translation=? WHERE file_id='f1' AND key_path='k1'",
            (translation,))
        store.conn.commit()
    return store.get_entries()[0]


def _agent(tmp_path):
    agent = AgentMemory(tmp_path / "agent_memory.db")
    agent.init_schema()
    return agent


def _read_meta(row) -> dict:
    return json.loads(row["meta"] or "{}")


def test_blocked_entry_manual_fix_becomes_publishable():
    store = _store()
    _entry(store, status="blocked", meta={
        "review_outcome": "BLOCKED", "review_blocked": True,
        "quality_passed": False, "rejected_candidate": "坏译文",
        "review_level": "CRITICAL", "review_reason": "错误",
        "need_revision": True,
    })

    result = manual_correction(store, "f1", "k1", " 你好，世界 ",
                               model="m", lang="en→zh-CN")

    assert result["applied"] is True
    assert result["translation"] == "你好，世界"
    assert result["status"] == "translated"
    row = store.get_entries()[0]
    assert row["translation"] == "你好，世界"
    assert row["status"] == "translated"
    meta = _read_meta(row)
    # 人工终态：可发布
    assert meta["review_outcome"] == "APPROVED"
    assert meta["review_level"] == "MANUAL"
    assert meta["quality_passed"] is True
    assert is_write_ready(row["status"], row["translation"], meta) is True
    # 旧审核状态全部清除（review_level 由人工终态覆盖为 MANUAL）
    for field in ("review_blocked", "review_error", "need_revision",
                  "need_retranslate", "review_reason",
                  "review_suggestion", "review_error_kind",
                  "review_blocked_rounds", "rejected_candidate",
                  "quality_reasons"):
        assert field not in meta, field
    # 人工修正留痕
    assert meta["manual_corrected"]["before"] == ""


def test_manual_fix_replaces_bad_memory_and_is_immediately_visible():
    store = _store()
    _entry(store, status="blocked", meta={"review_outcome": "BLOCKED"})
    # 旧坏记忆已提交（可命中）
    store.add_memory("Hello world", "坏译文", "m", "en→zh-CN")

    manual_correction(store, "f1", "k1", "你好，世界",
                      model="m", lang="en→zh-CN")

    hits = store.get_memory_hits(["Hello world"], "m", "en→zh-CN")
    assert hits == {"Hello world": "你好，世界"}


def test_stale_approved_state_replaced_by_manual_correction():
    store = _store()
    _entry(store, status="translated", translation="旧译文", meta={
        "review_outcome": "APPROVED", "review_level": "MINOR",
        "review_reason": "旧判定", "quality_passed": True,
    })

    manual_correction(store, "f1", "k1", "新译文",
                      model="m", lang="en→zh-CN")

    meta = _read_meta(store.get_entries()[0])
    assert meta["review_outcome"] == "APPROVED"
    assert meta["review_level"] == "MANUAL"
    assert "review_reason" not in meta
    assert meta["manual_corrected"]["before"] == "旧译文"


def test_clear_translation_resets_to_pending_and_revokes_memory():
    store = _store()
    _entry(store, status="blocked", translation="坏译文", meta={
        "review_outcome": "BLOCKED", "quality_passed": False,
        "manual_corrected": {"at": "2026-08-13", "before": "更坏"},
    })
    store.add_memory("Hello world", "坏译文", "m", "en→zh-CN")
    store.add_memory("Hello world", "坏译文", "m2", "ja→zh-CN")

    result = manual_correction(store, "f1", "k1", "   ",
                               model="m", lang="en→zh-CN")

    assert result["translation"] == ""
    assert result["status"] == "pending"
    row = store.get_entries()[0]
    assert row["status"] == "pending"
    assert row["translation"] == ""
    meta = _read_meta(row)
    assert "review_outcome" not in meta
    assert "manual_corrected" not in meta
    assert meta["quality_passed"] is False
    assert is_write_ready(row["status"], row["translation"], meta) is False
    # 全部 model/lang 组合下的旧记忆都被撤销
    assert store.get_memory_hits(["Hello world"], "m", "en→zh-CN") == {}
    assert store.get_memory_hits(["Hello world"], "m2", "ja→zh-CN") == {}
    assert store.count_pending_memory() == 0


def test_audit_log_and_vector_outbox_written():
    store = _store()
    _entry(store, status="blocked", translation="坏译文",
           meta={"review_outcome": "BLOCKED"})

    manual_correction(store, "f1", "k1", "好译文",
                      model="m", lang="en→zh-CN")

    with store.conn:
        audit = store.conn.execute(
            "SELECT * FROM audit_log").fetchall()
        outbox = store.conn.execute(
            "SELECT * FROM vector_outbox").fetchall()
    assert len(audit) == 1
    assert audit[0]["kind"] == "manual"
    assert audit[0]["file_id"] == "f1"
    assert audit[0]["key_path"] == "k1"
    assert audit[0]["before_translation"] == "坏译文"
    assert audit[0]["after_translation"] == "好译文"
    assert audit[0]["model"] == "m"
    assert audit[0]["lang"] == "en→zh-CN"
    assert len(outbox) == 1
    assert outbox[0]["kind"] == "manual"
    assert outbox[0]["translation"] == "好译文"


def test_clear_writes_outbox_removal_signal_and_audit():
    store = _store()
    _entry(store, status="translated", translation="旧译文",
           meta={"review_outcome": "APPROVED"})

    manual_correction(store, "f1", "k1", "", model="m", lang="en→zh-CN")

    with store.conn:
        audit = store.conn.execute("SELECT * FROM audit_log").fetchall()
        outbox = store.conn.execute("SELECT * FROM vector_outbox").fetchall()
    assert audit[0]["after_translation"] == ""
    assert "清空" in audit[0]["note"]
    # 空译文 = 消费端删除指令
    assert outbox[0]["translation"] == ""


def test_missing_entry_returns_applied_false():
    store = _store()
    result = manual_correction(store, "nope", "nope", "译文",
                               model="m", lang="en→zh-CN")
    assert result["applied"] is False
    with store.conn:
        assert store.conn.execute("SELECT COUNT(*) n FROM audit_log").fetchone()["n"] == 0


def test_agent_memory_upsert_manual_overrides_conflicts_and_retired(tmp_path):
    agent = _agent(tmp_path)
    agent.init_schema()
    # 既有冲突/退休记忆（同 key 同语境）
    agent.propose("Hello world", "旧译文A", "game1")
    agent.propose("Hello world", "旧译文A", "game1")
    agent.propose("Hello world", "旧译文B", "game1")  # conflicts+1
    agent.apply_feedback("Hello world", "", accepted=False)
    agent.apply_feedback("Hello world", "", accepted=False)  # retired

    agent.upsert_manual("Hello world", "人工译文", "game2")

    row = agent.conn.execute(
        "SELECT * FROM memories WHERE key='Hello world'").fetchone()
    assert row["value"] == "人工译文"
    assert row["status"] == "active"
    assert row["evidence_count"] == 3
    assert row["rejects"] == 0
    assert row["conflicts"] == 0
    assert row["source"] == "manual"
    # 人工证据：单游戏即直接应用
    hits = agent.direct_applications(["Hello world"])
    assert hits == {"Hello world": "人工译文"}
    # 会话统计可见
    report = agent.session_report("game2")
    assert report["session"]["manual_applied"] == 1


def test_agent_memory_upsert_manual_merges_games(tmp_path):
    agent = _agent(tmp_path)
    agent.init_schema()
    agent.propose("Use the force", "原译文", "game1")
    agent.propose("Use the force", "原译文", "game1")

    agent.upsert_manual("Use the force", "使用原力", "game2")

    row = agent.conn.execute(
        "SELECT * FROM memories WHERE key='Use the force'").fetchone()
    assert json.loads(row["games"]) == ["game1", "game2"]


def test_set_manual_legacy_api_delegates_to_unified_flow():
    store = _store()
    _entry(store, status="blocked", meta={"review_outcome": "BLOCKED"})

    result = store.set_manual("f1", "k1", "人工译文")

    assert result["applied"] is True
    meta = _read_meta(store.get_entries()[0])
    assert meta["review_outcome"] == "APPROVED"
    assert meta["review_level"] == "MANUAL"


def test_manual_fix_of_low_confidence_entry_is_write_ready():
    store = _store()
    _entry(store, status="pending", translation="低置信译文", meta={
        "confidence": "low", "quality_passed": False,
        "quality_reasons": ["length_over_budget"],
    })

    manual_correction(store, "f1", "k1", "人工定稿", model="m", lang="en→zh-CN")

    row = store.get_entries()[0]
    meta = _read_meta(row)
    # 人工提升：低置信不再挡发布门
    assert is_write_ready(row["status"], row["translation"], meta) is True


def test_new_tables_exist_after_init_schema(tmp_path):
    store = ProjectStore(tmp_path / "p.db")
    store.init_schema()
    with store.conn:
        names = {r[0] for r in store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"audit_log", "vector_outbox"} <= names


def test_old_schema_migration_adds_tables(tmp_path):
    # 旧库（Phase A 前结构）：无 audit_log/vector_outbox/pending
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE files(id TEXT PRIMARY KEY, rel_path TEXT, format TEXT,
            encoding TEXT, eol TEXT, meta TEXT);
        CREATE TABLE entries(id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT, key_path TEXT, original TEXT,
            translation TEXT DEFAULT '', status TEXT DEFAULT 'pending',
            locked INTEGER DEFAULT 0, meta TEXT DEFAULT '{}',
            UNIQUE(file_id, key_path));
        CREATE TABLE memory(src_hash TEXT PRIMARY KEY, original TEXT,
            translation TEXT, model TEXT, lang TEXT,
            created_at TEXT DEFAULT (datetime('now')));
        CREATE TABLE profile(key TEXT PRIMARY KEY, value TEXT);
    """)
    conn.commit()
    conn.close()

    store = ProjectStore(db)
    store.init_schema()

    with store.conn:
        names = {r[0] for r in store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"audit_log", "vector_outbox"} <= names
        cols = {r[1] for r in store.conn.execute("PRAGMA table_info(memory)")}
        assert "pending" in cols
        # 旧记忆保留且视为已提交
        store.conn.execute(
            "INSERT INTO memory(src_hash, original, translation, model, lang)"
            " VALUES ('h1','x','y','m','l')")
        store.conn.commit()
    assert store.count_pending_memory() == 0


# ── #9：失败/阻断文本自处理（重译 = 清终态的新开始） ─────────

def test_reset_to_pending_clears_blocked_review_state():
    """审核阻断条目 → 标记重译：BLOCKED 终态全部清除，可重新翻译。"""
    store = _store()
    row = _entry(store, status="blocked", meta={
        "review_outcome": "BLOCKED", "review_blocked": True,
        "quality_passed": False, "rejected_candidate": "坏译文",
        "review_level": "CRITICAL", "review_reason": "错误",
        "review_blocked_rounds": 3, "review_issue": "需修正",
        "quality_reasons": ["semantic_error"],
    })
    assert is_write_ready(row["status"], row["translation"], row["meta"]) is False

    store.reset_to_pending("f1", "k1")
    row = store.get_entries()[0]
    meta = _read_meta(row)
    assert row["status"] == "pending"
    for field in ("review_outcome", "review_blocked", "rejected_candidate",
                  "review_level", "review_reason", "review_blocked_rounds",
                  "review_issue", "quality_reasons"):
        assert field not in meta
    # 清终态后发布门恢复（重译成功后由 translator 重写 quality 字段）
    assert review_publishable(meta) is True


def test_retranslate_success_clears_stale_review_outcome():
    """重译成功写入路径（_clear_review_state）：残留终态不再拒绝新译文。

    修复前：审校标记重译只 set_status → review_outcome=BLOCKED 残留 →
    重译成功 meta 重写 quality_passed 但不碰终态 → 发布门 fail-closed
    拒绝 → 失败文本无法通过重译自己处理（只能人工改）。
    """
    meta = {
        "review_outcome": "BLOCKED", "review_blocked": True,
        "quality_passed": False, "rejected_candidate": "坏译文",
        "review_level": "MAJOR", "review_reason": "术语错误",
        "review_blocked_rounds": 2,
    }
    _clear_review_state(meta)
    assert "review_outcome" not in meta
    assert "review_blocked" not in meta
    assert "rejected_candidate" not in meta
    # 重译成功：translator 随后重写质量门
    meta["quality_passed"] = True
    assert review_publishable(meta) is True


def test_reset_to_pending_keeps_other_meta():
    """标记重译只清审核/质量终态，场景/术语等业务 meta 保留。"""
    store = _store()
    _entry(store, status="blocked", meta={
        "review_outcome": "BLOCKED", "review_blocked": True,
        "scene": "menu", "role": "display", "ctx_before": "玩家",
    })
    store.reset_to_pending("f1", "k1")
    meta = _read_meta(store.get_entries()[0])
    assert meta["scene"] == "menu"
    assert meta["role"] == "display"
    assert meta["ctx_before"] == "玩家"
    assert "review_outcome" not in meta
