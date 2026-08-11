from __future__ import annotations
import hashlib
import json
import sqlite3
import threading
from pathlib import Path

from hanhua.core.models import GameProfile


class ProjectStore:
    """单项目 SQLite：条目状态 + 翻译记忆 + 断点续传。所有方法线程安全。"""

    def __init__(self, db_path: str | Path, timeout: float = 5.0):
        self.db = Path(db_path)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        connection = sqlite3.connect(
            str(self.db), check_same_thread=False, timeout=timeout,
        )
        try:
            connection.row_factory = sqlite3.Row
            self.conn = connection
        except Exception:
            connection.close()
            raise

    def init_schema(self):
        with self._lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS files(
                id TEXT PRIMARY KEY, rel_path TEXT, format TEXT,
                encoding TEXT, eol TEXT, meta TEXT
            );
            CREATE TABLE IF NOT EXISTS entries(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT, key_path TEXT, original TEXT,
                translation TEXT DEFAULT '', status TEXT DEFAULT 'pending',
                locked INTEGER DEFAULT 0, meta TEXT DEFAULT '{}',
                UNIQUE(file_id, key_path)
            );
            CREATE TABLE IF NOT EXISTS memory(
                src_hash TEXT PRIMARY KEY, original TEXT, translation TEXT,
                model TEXT, lang TEXT, created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_entries_status ON entries(status);
            CREATE TABLE IF NOT EXISTS profile(
                key TEXT PRIMARY KEY, value TEXT
            );
            """)
            self.conn.commit()

    def schema_tables(self) -> frozenset[str]:
        """Return existing table names without creating or migrating schema."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'",
            ).fetchall()
        return frozenset(row["name"] for row in rows)

    def add_file(self, file_id, rel_path, fmt, encoding, eol, meta=None):
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?)",
                (file_id, rel_path, fmt, encoding, eol, json.dumps(meta or {})))
            self.conn.commit()

    def upsert_entries(self, rows: list[dict]):
        """插入/更新条目。状态合并规则：
        - skipped 强制覆盖（键位置等不该翻译的条目，即使旧状态是 translated 也降级）
        - pending 不覆盖已翻译（译文继承，断点续传）
        """
        quality_keys = {
            "quality_passed", "quality_reasons", "quality_source",
            "confidence_promoted",
        }

        def decoded_meta(raw) -> dict:
            try:
                value = json.loads(raw or "{}") if isinstance(raw, str) else dict(raw or {})
            except (json.JSONDecodeError, TypeError, ValueError):
                return {}
            return value if isinstance(value, dict) else {}

        def with_quality(incoming, existing_meta) -> dict:
            merged = decoded_meta(incoming)
            previous = decoded_meta(existing_meta)
            merged.update({key: previous[key] for key in quality_keys if key in previous})
            return merged

        rows = list(rows)
        if not rows:
            return

        def perform_upsert():
            file_ids = sorted({row["file_id"] for row in rows})
            by_key = {}
            by_original = {}
            next_order = 0

            def add_to_original(state):
                if state["translation"]:
                    original_key = (state["file_id"], state["original"])
                    by_original.setdefault(original_key, {})[
                        state["key_path"]
                    ] = state

            def remove_from_original(state):
                if not state["translation"]:
                    return
                original_key = (state["file_id"], state["original"])
                candidates = by_original.get(original_key)
                if candidates is None:
                    return
                candidates.pop(state["key_path"], None)
                if not candidates:
                    by_original.pop(original_key, None)

            for offset in range(0, len(file_ids), 400):
                chunk = file_ids[offset:offset + 400]
                placeholders = ",".join("?" for _ in chunk)
                cursor = self.conn.execute(
                    "SELECT id, file_id, key_path, original, translation, status, locked, meta "
                    f"FROM entries WHERE file_id IN ({placeholders}) ORDER BY id",
                    chunk,
                )
                for existing_row in cursor:
                    state = dict(existing_row)
                    state["order"] = next_order
                    next_order += 1
                    key = (state["file_id"], state["key_path"])
                    by_key[key] = state
                    add_to_original(state)

            touched = {}
            for r in rows:
                new_status = r.get("status", "pending")
                incoming_meta = decoded_meta(r.get("meta", {}))
                key = (r["file_id"], r["key_path"])
                existing = by_key.get(key)
                previous = dict(existing) if existing is not None else None
                if existing is not None:
                    existing["meta"] = json.dumps(
                        decoded_meta(existing["meta"]), ensure_ascii=False,
                    )

                if existing is None and new_status == "pending":
                    candidates = sorted(by_original.get(
                        (r["file_id"], r["original"]), {}
                    ).values(), key=lambda row: row["order"])
                    translations = {row["translation"] for row in candidates}
                    if len(translations) == 1:
                        translation = translations.pop()
                        status = "translated" if any(
                            row["status"] == "translated" for row in candidates) else candidates[0]["status"]
                        locked = int(any(row["locked"] for row in candidates))
                        source_meta = next(
                            (row["meta"] for row in candidates
                             if row["translation"] == translation
                             and decoded_meta(row["meta"]).get("quality_passed") is True),
                            {},
                        )
                        migrated_meta = with_quality(incoming_meta, source_meta)
                        existing = {
                            "file_id": r["file_id"],
                            "key_path": r["key_path"],
                            "original": r["original"],
                            "translation": translation,
                            "status": status,
                            "locked": locked,
                            "meta": json.dumps(migrated_meta, ensure_ascii=False),
                            "order": next_order,
                        }
                if existing is None:
                    existing = {
                        "file_id": r["file_id"],
                        "key_path": r["key_path"],
                        "original": r["original"],
                        "translation": "",
                        "status": new_status,
                        "locked": 0,
                        "meta": json.dumps(incoming_meta, ensure_ascii=False),
                        "order": next_order,
                    }
                if previous is None:
                    next_order += 1

                if new_status == "skipped":
                    # 键位置：强制跳过（丢弃旧译文，键不可翻译）
                    if existing["status"] != "skipped":
                        existing["status"] = "skipped"
                        existing["translation"] = ""
                elif new_status == "pending":
                    # 重扫后始终刷新原文定位与元数据；已翻译的译文和状态保持不动。
                    # 这让规则升级后的 obj_has_values / offset 等防护信息能作用于历史译文。
                    if (previous is not None
                            and previous["original"] != r["original"]):
                        if existing["status"] != "skipped":
                            existing["original"] = r["original"]
                            existing["translation"] = ""
                            existing["status"] = "pending"
                            existing["meta"] = json.dumps(
                                incoming_meta, ensure_ascii=False,
                            )
                    elif existing["status"] != "skipped":
                        preserved_meta = with_quality(
                            incoming_meta, existing["meta"],
                        )
                        existing["original"] = r["original"]
                        existing["meta"] = json.dumps(
                            preserved_meta, ensure_ascii=False,
                        )

                if previous is not None:
                    remove_from_original(previous)
                by_key[key] = existing
                add_to_original(existing)
                touched[key] = existing

            self.conn.executemany(
                "INSERT INTO entries(file_id,key_path,original,translation,status,locked,meta) "
                "VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(file_id,key_path) DO UPDATE SET "
                "original=excluded.original, translation=excluded.translation, "
                "status=excluded.status, locked=excluded.locked, meta=excluded.meta",
                (
                    (
                        state["file_id"], state["key_path"], state["original"],
                        state["translation"], state["status"], state["locked"],
                        state["meta"],
                    )
                    for state in touched.values()
                ),
            )

        with self._lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                perform_upsert()
            except BaseException:
                self.conn.rollback()
                raise
            else:
                self.conn.commit()

    def update_translation(self, file_id, key_path, translation, status="translated"):
        with self._lock:
            row = self.conn.execute(
                "SELECT meta FROM entries WHERE file_id=? AND key_path=?",
                (file_id, key_path),
            ).fetchone()
            try:
                meta = json.loads(row["meta"] or "{}") if row else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}
            meta.update({
                "quality_passed": status == "translated" and bool(translation),
                "quality_reasons": [],
                "quality_source": "manual_api",
                "confidence_promoted": True,
            })
            self.conn.execute(
                "UPDATE entries SET translation=?, status=?, meta=? "
                "WHERE file_id=? AND key_path=?",
                (translation, status, json.dumps(meta, ensure_ascii=False),
                 file_id, key_path))
            self.conn.commit()

    def batch_update_translations(self, rows: list[tuple]) -> None:
        """批量写入译文状态（executemany + 单次提交，翻译大项目时避免逐条 commit）。"""
        if not rows:
            return
        with self._lock:
            self.conn.executemany(
                "UPDATE entries SET translation=?, status=? WHERE file_id=? AND key_path=?",
                rows)
            self.conn.commit()

    def batch_update_translation_results(self, entries) -> None:
        """原子保存译文、状态和质量元数据，同时保留扫描器定位信息。"""
        rows = list(entries)
        if not rows:
            return
        with self._lock:
            values = []
            for entry in rows:
                current = self.conn.execute(
                    "SELECT meta FROM entries WHERE file_id=? AND key_path=?",
                    (entry.file_id, entry.key_path),
                ).fetchone()
                try:
                    merged_meta = json.loads(current["meta"] or "{}") if current else {}
                except (json.JSONDecodeError, TypeError):
                    merged_meta = {}
                merged_meta.update(entry.meta)
                entry.meta = merged_meta
                values.append((
                    entry.translation, entry.status,
                    json.dumps(merged_meta, ensure_ascii=False),
                    entry.file_id, entry.key_path,
                ))
            self.conn.executemany(
                "UPDATE entries SET translation=?, status=?, meta=? "
                "WHERE file_id=? AND key_path=?",
                values,
            )
            self.conn.commit()

    def set_status(self, file_id, key_path, status):
        with self._lock:
            self.conn.execute("UPDATE entries SET status=? WHERE file_id=? AND key_path=?",
                              (status, file_id, key_path))
            self.conn.commit()

    def set_locked(self, file_id, key_path, locked: bool):
        with self._lock:
            self.conn.execute("UPDATE entries SET locked=? WHERE file_id=? AND key_path=?",
                              (1 if locked else 0, file_id, key_path))
            self.conn.commit()

    def set_manual(self, file_id, key_path, translation):
        """人工审校：非空译文通过；清空时恢复 pending。"""
        normalized = str(translation).strip()
        status = "translated" if normalized else "pending"
        self.update_translation(file_id, key_path, normalized, status)

    def get_entries(self, status: str | None = None) -> list[dict]:
        with self._lock:
            if status:
                return [dict(r) for r in self.conn.execute("SELECT * FROM entries WHERE status=?", (status,))]
            return [dict(r) for r in self.conn.execute("SELECT * FROM entries")]

    def count(self, status: str) -> int:
        with self._lock:
            row = self.conn.execute("SELECT COUNT(*) c FROM entries WHERE status=?", (status,)).fetchone()
            return row["c"] if row else 0

    def get_memory_hits(self, originals: list[str], model: str, lang: str) -> dict[str, str]:
        """返回 {原文: 译文} 命中缓存（单条 IN 查询，替代逐条 SELECT）。"""
        if not originals:
            return {}
        hashes = [(hashlib.md5(s.encode("utf-8")).hexdigest(), s) for s in originals]
        with self._lock:
            rows = self.conn.execute(
                "SELECT src_hash, translation FROM memory WHERE model=? AND lang=? "
                "AND src_hash IN (%s)" % ",".join("?" * len(hashes)),
                (model, lang, *(h for h, _ in hashes))).fetchall()
        by_hash = {r["src_hash"]: r["translation"] for r in rows}
        return {s: by_hash[h] for h, s in hashes if h in by_hash}

    def remove_memory(self, original: str, model: str, lang: str) -> None:
        source_hash = hashlib.md5(original.encode("utf-8")).hexdigest()
        with self._lock:
            self.conn.execute(
                "DELETE FROM memory WHERE src_hash=? AND model=? AND lang=?",
                (source_hash, model, lang),
            )
            self.conn.commit()

    def clear_translation_memory(self) -> int:
        """Atomically clear cached translations and return deleted row count."""
        with self._lock, self.conn:
            cursor = self.conn.execute("DELETE FROM memory")
            return cursor.rowcount

    def clear_records(self) -> tuple[int, int]:
        """清空识别与翻译记录(files/entries/memory),保留游戏档案。

        返回 (识别条目数, 翻译记忆条数),单事务提交。
        """
        with self._lock, self.conn:
            entries_rows = self.conn.execute("DELETE FROM entries").rowcount
            self.conn.execute("DELETE FROM files")
            memory_rows = self.conn.execute("DELETE FROM memory").rowcount
        return entries_rows, memory_rows

    def add_memory(self, original, translation, model, lang):
        h = hashlib.md5(original.encode("utf-8")).hexdigest()
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO memory(src_hash, original, translation, model, lang) VALUES (?,?,?,?,?)",
                (h, original, translation, model, lang))
            self.conn.commit()

    def batch_add_memory(self, rows: list[tuple]) -> None:
        """批量写入翻译记忆。rows: [(original, translation, model, lang)]"""
        if not rows:
            return
        with self._lock:
            self.conn.executemany(
                "INSERT OR REPLACE INTO memory(src_hash, original, translation, model, lang) "
                "VALUES (?,?,?,?,?)",
                [(hashlib.md5(o.encode("utf-8")).hexdigest(), o, t, m, l)
                 for o, t, m, l in rows])
            self.conn.commit()

    def get_files(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM files")]

    def remove_file(self, file_id: str):
        """删除一个文件及其全部条目（用于规则升级后清理已淘汰的噪音文件）。"""
        with self._lock:
            self.conn.execute("DELETE FROM entries WHERE file_id=?", (file_id,))
            self.conn.execute("DELETE FROM files WHERE id=?", (file_id,))
            self.conn.commit()

    def remove_entries(self, file_id: str, key_paths: list[str]):
        """删除指定文件中的特定条目（重扫后不再存在的旧条目，如已被过滤的键）。"""
        if not key_paths:
            return
        with self._lock:
            for kp in key_paths:
                self.conn.execute("DELETE FROM entries WHERE file_id=? AND key_path=?",
                                  (file_id, kp))
            self.conn.commit()

    # ── 项目级游戏档案 ──
    def get_profile(self) -> GameProfile:
        with self._lock:
            row = self.conn.execute("SELECT value FROM profile WHERE key='game_profile'").fetchone()
            if not row:
                return GameProfile()
            try:
                data = json.loads(row["value"])
                return GameProfile(**{k: v for k, v in data.items()
                                      if k in GameProfile.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError):
                return GameProfile()

    def set_profile(self, profile: GameProfile):
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO profile(key, value) VALUES ('game_profile', ?)",
                (json.dumps(profile.__dict__, ensure_ascii=False),))
            self.conn.commit()

    # ── 通用 profile key-value（扫描绑定清单持久化，2026-08-12） ──
    # --resume 续跑跳过扫描，但 write_all 输入闸门要求 _last_source_manifest
    # 非 None、IL2CPP 写回要求规范输入证据——成功扫描后把清单存库，
    # 续跑时恢复（faerie 续跑实证：resume 写回被「缺少成功扫描绑定的
    # 完整输入清单」拒绝）。
    def get_profile_value(self, key: str, default=None):
        """读取通用 profile 值（JSON 解析失败返回 default）。"""
        try:
            with self._lock:
                row = self.conn.execute(
                    "SELECT value FROM profile WHERE key=?", (key,)).fetchone()
        except sqlite3.OperationalError:
            return default   # profile 表尚未 init_schema（旧库/全新库）
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return default

    def set_profile_value(self, key: str, value) -> None:
        """写入通用 profile 值（JSON 序列化，覆盖旧值）。"""
        try:
            with self._lock:
                self.conn.execute(
                    "INSERT OR REPLACE INTO profile(key, value) VALUES (?, ?)",
                    (key, json.dumps(value, ensure_ascii=False)))
                self.conn.commit()
        except sqlite3.OperationalError:
            pass   # 表不存在时无法持久化——下次扫描（init_schema 后）重写

    def del_profile_value(self, key: str) -> None:
        """删除通用 profile 值（扫描失败清空绑定，防陈旧清单误用）。"""
        try:
            with self._lock:
                self.conn.execute("DELETE FROM profile WHERE key=?", (key,))
                self.conn.commit()
        except sqlite3.OperationalError:
            pass

    def close(self):
        with self._lock:
            self.conn.close()
