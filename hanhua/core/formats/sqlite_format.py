"""SQLite 数据库文本提取与写回。

- 只读打开（mode=ro）枚举表/列，对 TEXT 列按主键定位取值；
- 写回：把译文 UPDATE 回副本数据库（参数化、单事务、保留 schema）；
- 防护：文件 >200MB 跳过；单文件最多 20000 条；BLOB 列与超长值跳过。
"""
from __future__ import annotations
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.placeholders import should_skip

MAX_DB_BYTES = 200 * 1024 * 1024
MAX_ROWS = 20000
MAX_VALUE_BYTES = 4096
_TEXT_TYPES = frozenset({"TEXT", "VARCHAR", "CHAR", "NVARCHAR", "CLOB", "STRING"})


def _table_text_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    out: list[str] = []
    try:
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    except sqlite3.Error:
        return out
    for row in rows:
        _cid, name, type_name, _notnull, _dflt, _pk = row
        upper = (type_name or "").upper()
        if any(upper.startswith(t) for t in _TEXT_TYPES):
            out.append(str(name))
    return out


def _table_pk(conn: sqlite3.Connection, table: str) -> list[str]:
    try:
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    except sqlite3.Error:
        return []
    return [str(row[1]) for row in rows if row[5]]


def extract_sqlite(path: str | Path, file_id: str | None = None) -> list[TextEntry]:
    p = Path(path)
    fid = file_id or p.name
    if p.stat().st_size > MAX_DB_BYTES:
        return []
    entries: list[TextEntry] = []
    try:
        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'").fetchall()]
        for table in tables:
            text_cols = _table_text_columns(conn, table)
            pk = _table_pk(conn, table)
            if not text_cols:
                continue
            for col in text_cols:
                if len(entries) >= MAX_ROWS:
                    break
                try:
                    rows = conn.execute(
                        f'SELECT {",".join("\"" + c + "\"" for c in pk + [col])}'
                        f' FROM "{table}" WHERE "{col}" IS NOT NULL'
                        f' AND trim("{col}") != ""').fetchall()
                except sqlite3.Error:
                    continue
                for row in rows:
                    if len(entries) >= MAX_ROWS:
                        break
                    value = row[-1]
                    if not isinstance(value, str):
                        continue
                    if len(value.encode("utf-8", errors="ignore")) > MAX_VALUE_BYTES:
                        continue
                    if should_skip(value):
                        continue
                    pk_map = {pk[i]: row[i] for i in range(len(pk))}
                    key = json.dumps(pk_map, ensure_ascii=False) if pk_map else str(len(entries))
                    entries.append(TextEntry(
                        file_id=fid, key_path=f"db/{table}/{col}/{key}",
                        original=value,
                        meta={"kind": "sqlite", "table": table, "column": col,
                              "pk": pk_map}))
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return entries


def apply_sqlite(src_path: Path, entries: list[TextEntry]) -> bytes:
    """把译文写回 SQLite 副本 → 返回补丁后的字节（参数化 UPDATE、单事务）。"""
    by_target: dict[tuple[str, str], list[tuple[dict, str]]] = {}
    for e in entries:
        if e.status == STATUS_SKIPPED or not e.translation:
            continue
        if e.meta.get("kind") != "sqlite" or not e.meta.get("pk"):
            continue
        by_target.setdefault(
            (e.meta["table"], e.meta["column"]), []).append(
                (e.meta["pk"], e.translation))
    if not by_target:
        return src_path.read_bytes()
    fd, tmp_name = tempfile.mkstemp(prefix="hanhua_sqlite_", suffix=".db")
    os.close(fd)
    try:
        import shutil
        shutil.copy2(src_path, tmp_name)
        conn = sqlite3.connect(tmp_name)
        try:
            for (table, col), updates in by_target.items():
                where = " AND ".join(f'"{k}" = ?' for k in next(iter(updates))[0])
                sql = f'UPDATE "{table}" SET "{col}" = ? WHERE {where}'
                for pk_map, translation in updates:
                    try:
                        conn.execute(sql, [translation, *pk_map.values()])
                    except sqlite3.Error:
                        continue
            conn.commit()
        finally:
            conn.close()
        with open(tmp_name, "rb") as stream:
            return stream.read()
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
