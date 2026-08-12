from __future__ import annotations
import re
import sqlite3
import threading

from hanhua.core.knowledge import _UPPERCASE_ACTION_VERBS
from pathlib import Path

# 归一化冲突键：大小写 + 空白压缩 + 去标点。用于检测「同源不同译」：
# "moon key" 与 "Moon Key" 是同一术语，若译名不同则模型会无所适从
# （同一原文在 prompt 里出现两个译法 → 一致性破坏）。
_CONFLICT_NORM = re.compile(r"[^a-z0-9一-鿿]+")

# 翻译 C5：高频普通词单 token 黑名单——这些词在游戏文本里动词/名词/
# 方向/介词用法混杂（miss=未命中/想念/错过、right=右边/正确/右拨片），
# 审核沉淀若无语境强制全局，后续游戏同一词的其他语境会被改写（F22-4
# 三连杀实证：miss/encore/Right 各自杀死 100+ 条正常翻译）。
_HIGH_FREQUENCY_WORD_PAIRS = frozenset(
    "miss right left up down play stop save load charge exit enter open "
    "close start end back next ok yes no on off run jump attack hit "
    "throw use talk buy sell pick drop eat drink rest savegame resume "
    "health unit damage speed power".split()
    # health 2026-08-13 实证：force-reboot 沉淀 HEALTH→健康 active，
    # incremental-rts 'Increase unit HP by {health}' 译文「生命值」被
    # 误杀——health 在游戏语境变体多（健康/生命值/血量），单 token
    # 全局强制必误杀。unit/damage/speed/power 同族高频游戏词一并列入
)


class GlossaryStore:
    """全局术语表（SQLite，跨项目共享）。"""

    def __init__(self, db_path: str | Path):
        self.db = Path(db_path)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.db), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self):
        with self._lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS glossary(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT UNIQUE, translation TEXT, category TEXT DEFAULT '术语',
                note TEXT DEFAULT ''
            );""")
            # 翻译 C5：审核沉淀语境保护——候选桶（candidate 只参考不强制）、
            # 沉淀游戏列表（跨游戏复现升级）、原文例句（语境留档）。
            # 翻译 C6（阶段 2 术语库升级）：forbidden_translation（禁止
            # 译法——审核检出错误译法）、part_of_speech（词性）、
            # game_specific_meaning（游戏特指义）、usage_example（用法例句，
            # format_for_prompt 附带语境提示）。
            # 老库迁移：缺列则 ALTER TABLE 补上。
            columns = {row["name"] for row in self.conn.execute(
                "PRAGMA table_info(glossary)")}
            for column, ddl in (
                    ("status", "TEXT DEFAULT 'active'"),
                    ("games", "TEXT DEFAULT ''"),
                    ("context", "TEXT DEFAULT ''"),
                    ("forbidden_translation", "TEXT DEFAULT ''"),
                    ("part_of_speech", "TEXT DEFAULT ''"),
                    ("game_specific_meaning", "TEXT DEFAULT ''"),
                    ("usage_example", "TEXT DEFAULT ''")):
                if column not in columns:
                    self.conn.execute(
                        f"ALTER TABLE glossary ADD COLUMN {column} {ddl}")
            self.conn.commit()

    def add(self, term, translation, category="术语", note="",
            forbidden_translation="", part_of_speech="",
            game_specific_meaning="", usage_example=""):
        """入库（翻译 C6 字段升级）：扩展字段可空，向后兼容旧调用。"""
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO glossary"
                "(term, translation, category, note, forbidden_translation,"
                " part_of_speech, game_specific_meaning, usage_example)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (term, translation, category, note, forbidden_translation,
                 part_of_speech, game_specific_meaning, usage_example))
            self.conn.commit()

    def add_reviewed(self, term, translation, context: str = "",
                     game: str = "", forbidden_translation: str = ""
                     ) -> str:
        """审核沉淀专用门禁（翻译 C5）：带语境保护的词对沉淀。

        F22-4 三连杀实证：审核沉淀 (miss,未命中)/(encore,安可)/(Right,右拨片)
        无门禁直写全局术语库，后续游戏强制约束把正常动词用法/外语语境
        全部改写（deadbeat 杀 doubleshake 动词用法 → 杀 faerie miss=想念；
        encore 杀法语；Right 杀 'pick the right door' 2083 条失败）——
        事后靠 quality.py 豁免补丁而非沉淀端预防。

        门禁规则（只作用于审核沉淀路径，人工/专名路径不受影响）：
        - 高频普通词单 token 词对（miss/right/play/…）：拒绝全局强制，
          返回拒绝原因（污染源——无语境可区分动词/名词/方向用法）；
        - 其他单 token 词对：进 candidate 桶（参考不强制），跨游戏复现
          （第二次审核沉淀）才升级 active；
        - 组合词对（含空格）：语境充分，直接 active；
        - 全部条目 note 载入语境（原文例句+来源游戏+分类），不再只写
          「来源 X」。

        返回 "" 表示已沉淀/激活，否则为拒绝原因（调用方记入报告）。
        """
        term_s = str(term).strip()
        trans_s = str(translation).strip()
        if not term_s or not trans_s:
            return "空词对"
        if (" " not in term_s
                and term_s.casefold() in _HIGH_FREQUENCY_WORD_PAIRS):
            return (f"拒绝沉淀：{term_s!r} 是高频普通词单 token 词对"
                    f"（无语境可区分动词/名词/方向用法，全局强制会误杀"
                    f"其他语境——F22-4 三连杀实证）")
        games = [g for g in re.split(r"[,，]", game or "") if g]
        is_combo = " " in term_s
        note = f"来源 {game or '?'}"
        if context:
            note += f" · 例句: {context[:120]}"
        with self._lock:
            row = self.conn.execute(
                "SELECT id, translation, status, games FROM glossary"
                " WHERE term=?", (term_s,)).fetchone()
            if row is not None:
                existing_games = [g for g in re.split(r"[,，]", row["games"] or "")
                                  if g]
                merged = list(dict.fromkeys(existing_games + games))
                status = row["status"] or "active"
                if status != "active" and (is_combo or len(merged) >= 2):
                    status = "active"
                # forbidden_translation 只在传入时刷新（空值不抹已有禁止译法）
                if forbidden_translation:
                    self.conn.execute(
                        "UPDATE glossary SET translation=?, note=?, games=?,"
                        " status=?, context=?, forbidden_translation=?"
                        " WHERE id=?",
                        (trans_s, note, ",".join(merged), status, context,
                         forbidden_translation, row["id"]))
                else:
                    self.conn.execute(
                        "UPDATE glossary SET translation=?, note=?, games=?,"
                        " status=?, context=? WHERE id=?",
                        (trans_s, note, ",".join(merged), status, context,
                         row["id"]))
                self.conn.commit()
                return "" if status == "active" else ""
            status = "active" if is_combo else "candidate"
            self.conn.execute(
                "INSERT OR REPLACE INTO glossary"
                "(term, translation, category, note, status, games, context,"
                " forbidden_translation)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (term_s, trans_s, "审核术语", note, status,
                 ",".join(games), context, forbidden_translation))
            self.conn.commit()
            return ""

    def update(self, term, translation, category, note=""):
        with self._lock:
            self.conn.execute("UPDATE glossary SET translation=?, category=?, note=? WHERE term=?",
                              (translation, category, note, term))
            self.conn.commit()

    def delete(self, term):
        with self._lock:
            self.conn.execute("DELETE FROM glossary WHERE term=?", (term,))
            self.conn.commit()

    def list_all(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM glossary ORDER BY id")]

    def by_category(self, category: str) -> list[str]:
        with self._lock:
            return [r["term"] for r in self.conn.execute(
                "SELECT term FROM glossary WHERE category=?", (category,))]

    def format_for_prompt(self, limit: int = 0) -> str:
        rows = self.list_all()
        if not rows:
            return ""
        # 翻译 C5：只注入 active 条目——candidate 桶（审核沉淀未跨游戏
        # 复现的词对）仅参考不强制：候选可能在当前游戏恰好是错误语境
        # （如 miss=未命中 沉淀自音游，却在剧情游戏里是 想念），注入为
        # 强制约束会误杀；active 条目已跨游戏复现或为组合词对，语境充分。
        rows = [r for r in rows if r.get("status", "active") == "active"]
        if limit > 0:
            # 全局术语库跨游戏持续积累后可能很大；注入 prompt 只取最新 limit 条
            # （ID 单调递增，最新学习的最贴近当前需求）。
            rows = rows[-limit:]
        # 翻译 C6：usage_example 存在时附带用法例句（消歧提示，仅提示不
        # 强制——model 参考词义而非复制句子）。
        lines = []
        for r in rows:
            line = f"{r['term']} → {r['translation']}（{r['category']}）"
            if r.get("usage_example"):
                line += f" 例：{r['usage_example'][:60]}"
            lines.append(line)
        return "\n".join(lines)

    def known_names_for(self, collected: list[str] | None = None) -> list[str]:
        """专名注入清单：当前游戏收集的专名优先，全局术语库专名兜底。

        术语库的专名条目（category='专名'）跨游戏积累——后续游戏遇到
        同名专名时，即使当前池子未收集到，也能保持译名一致。
        """
        names: list[str] = []
        seen: set[str] = set()
        for n in (collected or []):
            if n not in seen:
                names.append(n)
                seen.add(n)
        for row in self.list_all():
            if row["category"] == "专名" and row["term"] not in seen:
                names.append(row["term"])
                seen.add(row["term"])
        return names[:50]

    def learn_proper_names(self, entries, names: list[str],
                           source_game: str) -> int:
        """从已确认翻译中学习专名（保留型）写入全局术语库。

        输入：全部条目 + 疑似专名清单。仅使用质量门通过的 translated 条目
        作为证据：专名在其原文中多次出现、且译文保留了原文形态（未误译、
        未丢失），则记「term → 原文」保留映射——后续游戏命中该词时，
        [术语命中] 强制该词保留原文，防止 HY-MT2 丢失/意译专名。

        音译型（译文为中文）无法可靠定位对应片段，不自动提取（人工可在
        术语库补充）。返回新学习条数。
        """
        evidence: dict[str, dict] = {}
        for e in entries:
            if e.status != "translated" or not e.translation:
                continue
            if not e.meta.get("quality_passed"):
                continue
            for n in names:
                # 动作动词不是专名：TOSS TRASH 的 TOSS 是动作指令文本的词，
                # 学成专名后「TOSS → TOSS」保留映射会与知识库译例
                # 「TOSS TRASH → 丢垃圾」在 references 里冲突，模型采纳
                # 专名保留 → 输出半翻译 TOSS 垃圾（taxes 实证）
                if n.casefold() in _UPPERCASE_ACTION_VERBS:
                    continue
                if n in e.original:
                    ev = evidence.setdefault(n, {"total": 0, "kept": 0})
                    ev["total"] += 1
                    # 保留检测大小写不敏感（模型可能保留为 Glislya 变体）
                    if n.casefold() in e.translation.casefold():
                        ev["kept"] += 1
        learned = 0
        for n, ev in evidence.items():
            if ev["total"] >= 1 and ev["kept"] >= ev["total"] * 0.5:
                with self._lock:
                    row = self.conn.execute(
                        "SELECT id, translation FROM glossary WHERE term=?",
                        (n,)).fetchone()
                    if row is not None:
                        # 已存在：仅当旧条目无译名证据时刷新来源备注
                        if not row["translation"]:
                            self.conn.execute(
                                "UPDATE glossary SET note=? WHERE id=?",
                                (f"auto:{source_game}:保留", row["id"]))
                    else:
                        self.conn.execute(
                            "INSERT OR REPLACE INTO glossary"
                            "(term, translation, category, note)"
                            " VALUES (?,?,?,?)",
                            (n, n, "专名", f"auto:{source_game}:保留"))
                        learned += 1
        self.conn.commit()
        return learned

    @staticmethod
    def _conflict_key(term: str) -> str:
        return _CONFLICT_NORM.sub("", term.strip().casefold())

    def detect_conflicts(self) -> list[dict]:
        """同源异译冲突检测（P2）：大小写/空白/标点变体视为同源，
        同源但译名不同的条目返回冲突组（供人工合并修订）。

        返回: [{"key": 归一化键, "rows": [同源条目 dict, ...]}, ...]
        每组至少 2 个不同译名才上报。
        """
        buckets: dict[str, list[dict]] = {}
        for row in self.list_all():
            key = self._conflict_key(row["term"])
            if key:
                buckets.setdefault(key, []).append(row)
        return [
            {"key": key, "rows": rows}
            for key, rows in buckets.items()
            if len({r["translation"] for r in rows}) > 1
        ]

    def close(self):
        with self._lock:
            self.conn.close()
