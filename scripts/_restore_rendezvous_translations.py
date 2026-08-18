# -*- coding: utf-8 -*-
"""Rendezvous 译文恢复（2026-08-17）：扫描库被删后，从昨日交付记录
(docs/all record/Rendezvous.rar/text/translated.txt) 按 (文件, 原文)
恢复译文到新扫描库（sweep/1dbe255992）。review.json 判定 flag 的 17 条
不恢复（保留 pending，宁漏勿坏）。重复原文不恢复（防错配）。
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECORD = Path(r"C:\Users\mingming\Desktop\AI项目\unity游戏汉化工具\docs\all record\Rendezvous.rar")
DB = Path.home() / ".hanhua_sweep" / "projects" / "1dbe255992" / "project.db"

FIELD = re.compile(r"^(来源|键位|对象|原文|译文|置信度|原因|角色|质量|状态|跳过原因|失败原因|详情)：", re.M)


def parse_translated(path: Path) -> dict[tuple[str, str], str]:
    """解析 translated.txt → {(来源, 原文): 译文}。原文含换行时按字段行
    前缀切分；重复 (来源, 原文) 的丢弃（防错配）。"""
    text = path.read_text(encoding="utf-8")
    out: dict[tuple[str, str], str] = {}
    dup: set[tuple[str, str]] = set()
    # 按条目分隔符切块
    blocks = re.split(r"\n─{10,}\n", text)
    for block in blocks:
        # 定位字段：字段名行 + 后续到下一个字段名行
        matches = list(FIELD.finditer(block))
        fields: dict[str, str] = {}
        for i, m in enumerate(matches):
            name = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
            fields[name] = block[start:end].strip()
        source = fields.get("来源", "").strip()
        original = fields.get("原文", "").strip()
        translation = fields.get("译文", "").strip()
        if not source or not original or not translation:
            continue
        key = (source, original)
        if key in out:
            dup.add(key)
            out.pop(key, None)
        elif key not in dup:
            out[key] = translation
    return out


def load_excluded(path: Path) -> set[tuple[str, str]]:
    """review.json 判定 flag 的条目 → {(文件, 键位)} 排除集。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    excluded: set[tuple[str, str]] = set()
    for item in data:
        if item.get("verdict") != "pass":
            loc = str(item.get("locator", ""))
            if ":" in loc:
                file_part, _, key = loc.partition(":")
                excluded.add((file_part, key))
    return excluded


def main() -> int:
    if not DB.is_file():
        print(f"[错误] 扫描库不存在（先跑扫描步骤）: {DB}")
        return 1
    translations = parse_translated(RECORD / "text" / "translated.txt")
    excluded = load_excluded(RECORD / "review" / "review.json")
    print(f"translated.txt 解析: {len(translations)} 条（唯一键）")
    print(f"review flag 排除: {len(excluded)} 条")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, file_id, key_path, original, status, meta FROM entries"
    ).fetchall()
    print(f"库条目: {len(rows)}")

    # 库内 (file_id, original) 出现次数（重复不恢复）
    orig_counts: Counter = Counter((r["file_id"], r["original"]) for r in rows)
    # 排除集中的键位
    excluded_keys = {
        (f, k) for f, k in excluded
    }
    excluded_paths = {k for _f, k in excluded}
    # 匹配并恢复
    restored = 0
    skipped_dup = 0
    skipped_excluded = 0
    skipped_not_in_record = 0
    for r in rows:
        if r["status"] != "pending":
            continue
        key = (r["file_id"], r["original"])
        if key in excluded_keys or r["key_path"] in excluded_paths:
            skipped_excluded += 1
            continue
        if orig_counts[key] > 1:
            skipped_dup += 1
            continue
        translation = translations.get(key)
        if translation is None:
            skipped_not_in_record += 1
            continue
        conn.execute(
            "UPDATE entries SET translation=?, status='translated' WHERE id=?",
            (translation, r["id"]))
        restored += 1
    conn.commit()
    print(f"恢复: {restored} | 跳过重复原文: {skipped_dup} | "
          f"跳过审核不合格: {skipped_excluded} | 记录缺失: {skipped_not_in_record}")
    # 复核
    st = conn.execute("SELECT status, COUNT(*) FROM entries GROUP BY status").fetchall()
    print("状态分布:", dict(st))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
