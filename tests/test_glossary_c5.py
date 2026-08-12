"""翻译 C5：审核术语沉淀语境保护门禁回归（2026-08-12）。

背景：F22-4 三连杀实证——审核沉淀 (miss,未命中)/(encore,安可)/
(Right,右拨片) 无门禁直写全局术语库，后续游戏强制约束把正常动词
用法/外语语境全部改写（deadbeat 杀 doubleshake 动词用法 → 杀 faerie
miss=想念；encore 杀法语；Right 杀 'pick the right door' 2083 条
失败）。事后靠 quality.py 豁免补丁而非沉淀端预防。

C5 门禁（只作用于审核沉淀路径 add_reviewed）：
- 高频普通词单 token（miss/right/play/…）→ 拒绝全局强制，返回原因
- 其他单 token 词对 → candidate 桶（format_for_prompt 不注入），
  跨游戏复现（第二次审核沉淀）才升级 active
- 组合词对（含空格）→ 语境充分，直接 active
- note 载入语境（例句+来源游戏）
"""
import sqlite3

import pytest

from hanhua.core.glossary import GlossaryStore


def _store(tmp_path, legacy=False):
    db = tmp_path / "glossary.db"
    if legacy:
        # 老库：只有 term/translation/category/note 四列（C5 迁移前形态）
        conn = sqlite3.connect(str(db))
        conn.executescript("""
        CREATE TABLE glossary(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT UNIQUE, translation TEXT,
            category TEXT DEFAULT '术语', note TEXT DEFAULT ''
        );""")
        conn.commit()
        conn.close()
    store = GlossaryStore(db)
    store.init_schema()
    return store


# ── 迁移 ────────────────────────────────────────────────────────────

def test_init_schema_migrates_legacy_table(tmp_path):
    """老库（无 status/games/context 列）init_schema 后自动补列。"""
    store = _store(tmp_path, legacy=True)
    columns = {row[1] for row in store.conn.execute(
        "PRAGMA table_info(glossary)")}
    assert {"status", "games", "context"} <= columns
    # 老数据默认 status='active'（人工/专名路径不受门禁影响）
    store.add("foo", "酒吧", category="专名")
    row = store.conn.execute(
        "SELECT status FROM glossary WHERE term='foo'").fetchone()
    assert row["status"] == "active"


# ── 拒绝：高频普通词单 token ────────────────────────────────────────

def test_high_frequency_word_rejected(tmp_path):
    """(miss, 未命中) 音游语境沉淀 → 拒绝，不写入全局库。"""
    store = _store(tmp_path)
    reason = store.add_reviewed("miss", "未命中", context="Miss Combo x3",
                                game="deadbeat")
    assert reason
    assert "拒绝沉淀" in reason
    assert store.list_all() == []


@pytest.mark.parametrize("term", ["miss", "right", "play", "save",
                                  "charge", "start", "on", "yes"])
def test_high_frequency_word_blacklist(tmp_path, term):
    """黑名单单 token 全部拒绝（动词/名词/方向用法无语境区分）。"""
    store = _store(tmp_path)
    reason = store.add_reviewed(term, "测试译名", context=f"{term} xxx",
                                game="g")
    assert reason
    assert store.list_all() == []


def test_blacklist_ignores_case(tmp_path):
    """大写形态同样拒绝（审核建议常大写原文词）。"""
    store = _store(tmp_path)
    reason = store.add_reviewed("RIGHT", "右拨片", context="Hat RIGHT",
                                game="ffs")
    assert reason


# ── candidate 桶：非黑名单单 token ──────────────────────────────────

def test_single_token_goes_candidate(tmp_path):
    """非黑名单单 token（encore 等专有/术语形态）→ candidate 桶。"""
    store = _store(tmp_path)
    assert store.add_reviewed("encore", "安可", context="Encore!",
                              game="faerie") == ""
    row = store.conn.execute(
        "SELECT status, games FROM glossary WHERE term='encore'").fetchone()
    assert row["status"] == "candidate"
    assert "faerie" in row["games"]


def test_candidate_not_injected_into_prompt(tmp_path):
    """format_for_prompt 只注入 active——candidate 仅参考不强制。"""
    store = _store(tmp_path)
    store.add_reviewed("encore", "安可", context="Encore!", game="g1")
    store.add_reviewed("Left Paddle", "左拨片", context="Left Paddle",
                       game="g1")
    prompt = store.format_for_prompt()
    assert "encore" not in prompt
    assert "Left Paddle" in prompt


def test_candidate_promotes_on_cross_game_repeat(tmp_path):
    """candidate 跨游戏复现（第二次审核沉淀）→ 升级 active。"""
    store = _store(tmp_path)
    store.add_reviewed("encore", "安可", context="Encore!", game="faerie")
    assert store.add_reviewed("encore", "安可", context="Encore!",
                              game="ffs") == ""
    row = store.conn.execute(
        "SELECT status, games FROM glossary WHERE term='encore'").fetchone()
    assert row["status"] == "active"
    assert row["games"] == "faerie,ffs"
    assert "encore" in store.format_for_prompt()


# ── 组合词对直接 active ─────────────────────────────────────────────

def test_combo_pair_active_directly(tmp_path):
    """组合词对（含空格）语境充分 → 直接 active 并注入 prompt。"""
    store = _store(tmp_path)
    assert store.add_reviewed("Left Paddle", "左拨片",
                              context="Left Paddle: 左拨片", game="ffs") == ""
    row = store.conn.execute(
        "SELECT status, context FROM glossary WHERE term='Left Paddle'"
    ).fetchone()
    assert row["status"] == "active"
    assert "Left Paddle" in store.format_for_prompt()


# ── 语境留档 ────────────────────────────────────────────────────────

def test_note_carries_example_and_game(tmp_path):
    """note 载入原文例句+来源游戏，不再只写「来源 X」。"""
    store = _store(tmp_path)
    store.add_reviewed("Left Paddle", "左拨片",
                       context="Left Paddle to open menu", game="ffs")
    row = store.conn.execute(
        "SELECT note FROM glossary WHERE term='Left Paddle'").fetchone()
    assert "来源 ffs" in row["note"]
    assert "Left Paddle to open menu" in row["note"]


def test_existing_active_pair_keeps_active(tmp_path):
    """已 active 条目再次沉淀 → 保持 active、games 去重合并。"""
    store = _store(tmp_path)
    store.add_reviewed("Left Paddle", "左拨片", context="c1", game="ffs")
    store.add_reviewed("Left Paddle", "左拨片", context="c2", game="ffs")
    row = store.conn.execute(
        "SELECT status, games FROM glossary WHERE term='Left Paddle'"
    ).fetchone()
    assert row["status"] == "active"
    assert row["games"] == "ffs"


def test_empty_pair_rejected(tmp_path):
    """空词对不沉淀。"""
    store = _store(tmp_path)
    assert store.add_reviewed("", "译名", context="c", game="g")
    assert store.add_reviewed("term", "", context="c", game="g")
    assert store.list_all() == []
