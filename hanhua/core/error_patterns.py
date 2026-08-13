# -*- coding: utf-8 -*-
"""翻译错误模式库（重构指令 §8/§16/§17——#43 阶段 B）。

记录模型过去经常犯的错误，让后续翻译提前规避、审校提高风险识别：

    Original: Charge          Wrong: 收费          Correct: 蓄力
    Context:  Combat          Game:   xxx

写入门禁（§17 不污染原则，AI 翻译不得自动进库）：
  - 人工纠正（manual_correction 链路）：before→after 终局证据，
    confidence=0.95，直接 verified；
  - 审校确认（review_confirmed）：模型错误被审核修正，confidence=0.85；
  - 模型自生成：只进 candidate（参考不强制），需人工/审核确认才升级。

检索：按 original（精确/大小写归一）+ context 命中；只返回 verified/
candidate 中的 verified 优先（§4 知识优先级：Error Pattern 在 TM 之后、
通用规则之前）。命中即触发风险信号（阶段 D 评分接线）。

生命周期：candidate / verified / deprecated（退役保留历史，不删除）。
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

_NAMESPACE_CLEAN = __import__("re").compile(r"[^0-9a-z一-鿿]+")


def _norm_key(text: str) -> str:
    """归一化检索键：大小写/空白/标点无关（与 glossary term_norm 同语义）。"""
    return _NAMESPACE_CLEAN.sub("", text.casefold())


@dataclass(frozen=True)
class PatternHit:
    """检索命中：证据 + 置信（供 risk 评分/提示词注入）。"""

    original: str
    correct: str
    wrong: str = ""
    context: str = ""
    game: str = ""
    confidence: float = 0.85
    status: str = "verified"


class ErrorPatternStore:
    """错误模式库（SQLite，跨项目共享，与术语库同目录族）。"""

    def __init__(self, db_path: str | Path):
        self.db = Path(db_path)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.db), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self):
        with self._lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS error_patterns(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original TEXT NOT NULL,
                norm TEXT NOT NULL,
                wrong TEXT NOT NULL DEFAULT '',
                correct TEXT NOT NULL DEFAULT '',
                context TEXT NOT NULL DEFAULT '',
                game TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.6,
                status TEXT NOT NULL DEFAULT 'candidate',
                usage_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                UNIQUE(norm, wrong, correct, context)
            );""")
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ep_norm_status"
                " ON error_patterns(norm, status)")
            self.conn.commit()

    @staticmethod
    def _now() -> str:
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 写入（带门禁：来源决定初始状态与置信） ──

    def record(self, original: str, correct: str, *,
               wrong: str = "", context: str = "", game: str = "",
               source: str = "ai") -> str:
        """记录一个错误模式。返回落库状态（verified/candidate）。

        source 决定初始状态（§17 不污染原则）：
          human_corrected → verified + 0.95（人工纠正终局证据）
          review_confirmed → verified + 0.85（审核修正）
          ai（默认）→ candidate + 0.6（模型自生成，参考不强制）
        已存在同模式（norm+wrong+correct+context 唯一）→ 计数 +1。
        """
        original = str(original).strip()
        correct = str(correct).strip()
        if not original or not correct:
            return "rejected"
        if source == "human_corrected":
            status, confidence = "verified", 0.95
        elif source == "review_confirmed":
            status, confidence = "verified", 0.85
        else:
            status, confidence = "candidate", 0.6
        now = self._now()
        with self._lock:
            row = self.conn.execute(
                "SELECT id FROM error_patterns"
                " WHERE norm=? AND wrong=? AND correct=? AND context=?",
                (_norm_key(original), wrong, correct, context)).fetchone()
            if row is None:
                self.conn.execute(
                    "INSERT INTO error_patterns"
                    "(original, norm, wrong, correct, context, game,"
                    " confidence, status, created_at, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (original, _norm_key(original), wrong, correct, context,
                     game, confidence, status, now, now))
            else:
                # 升级路径：candidate 被人工/审核确认 → 升 verified；
                # 已 verified 的旧模式被更高置信来源再确认 → 置信取大
                self.conn.execute(
                    "UPDATE error_patterns SET confidence=MAX(confidence, ?),"
                    " status=CASE WHEN ?='verified' THEN 'verified'"
                    "              ELSE status END,"
                    " game=CASE WHEN ?!='' THEN ? ELSE game END,"
                    " updated_at=? WHERE id=?",
                    (confidence, status, game, game, now, row["id"]))
            self.conn.commit()
            return status

    def promote(self, original: str, correct: str, *, context: str = "",
                status: str = "verified") -> bool:
        """生命周期流转（candidate→verified→deprecated）。"""
        if status not in {"verified", "deprecated"}:
            return False
        with self._lock:
            cur = self.conn.execute(
                "UPDATE error_patterns SET status=?, updated_at=?"
                " WHERE norm=? AND correct=? AND context=?",
                (status, self._now(), _norm_key(original), correct, context))
            self.conn.commit()
            return cur.rowcount > 0

    # ── 检索 ──

    def search(self, original: str, context: str = "",
               status: str | None = "verified") -> list[dict]:
        """按原文（归一化）+ 可选语境命中。verified 优先（有序返回）。

        命中记录供风险评分（历史错误模式信号）与提示词注入
        （"Resume" 曾经被误译为「简历」，正确译法「继续」）。
        """
        norm = _norm_key(original)
        if not norm:
            return []
        with self._lock:
            sql = ("SELECT * FROM error_patterns WHERE norm=?"
                   " AND status!='deprecated'")
            args: list = [norm]
            if context:
                sql += " AND context=?"
                args.append(context)
            rows = self.conn.execute(
                sql + " ORDER BY (status='verified') DESC, confidence DESC,"
                      " usage_count DESC", tuple(args)).fetchall()
            return [dict(r) for r in rows]

    def mark_used(self, original: str, correct: str, *,
                  context: str = "") -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE error_patterns SET usage_count=usage_count+1"
                " WHERE norm=? AND correct=? AND context=?",
                (_norm_key(original), correct, context))
            self.conn.commit()

    def list_all(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(
                "SELECT * FROM error_patterns"
                " ORDER BY status, confidence DESC, id")]

    def close(self):
        with self._lock:
            self.conn.close()


def hits_to_patterns(hits: list[dict]) -> list[PatternHit]:
    """检索结果 → 结构化命中（供 risk_gate/提示词消费，隔离 dict 细节）。"""
    return [PatternHit(
        original=str(h["original"]), correct=str(h["correct"]),
        wrong=str(h.get("wrong") or ""), context=str(h.get("context") or ""),
        game=str(h.get("game") or ""), confidence=float(h["confidence"]),
        status=str(h["status"])) for h in hits]
