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
            self.conn.commit()

    def add(self, term, translation, category="术语", note=""):
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO glossary(term, translation, category, note) VALUES (?,?,?,?)",
                (term, translation, category, note))
            self.conn.commit()

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
        if limit > 0:
            # 全局术语库跨游戏持续积累后可能很大；注入 prompt 只取最新 limit 条
            # （ID 单调递增，最新学习的最贴近当前需求）。
            rows = rows[-limit:]
        return "\n".join(f"{r['term']} → {r['translation']}（{r['category']}）" for r in rows)

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
