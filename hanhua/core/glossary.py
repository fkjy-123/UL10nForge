from __future__ import annotations
import re
import sqlite3
import threading
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

    def format_for_prompt(self) -> str:
        rows = self.list_all()
        if not rows:
            return ""
        return "\n".join(f"{r['term']} → {r['translation']}（{r['category']}）" for r in rows)

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
