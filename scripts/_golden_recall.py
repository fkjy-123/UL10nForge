"""金标准识别率测量：已汉化项目库的验证译文 vs 当前提取池。

口径：
- 金标准 = ~/.hanhua/projects/<md5(game_dir)[:10]>/project.db 中
  status=translated 且 translation 非空的条目原文（人类验收过的真实
  显示文本全集）；
- 提取池 = 当前提取器（asset/mono/il2cpp 三通道）产出的全部条目原文；
- 识别率 = |金标准 ∩ 提取池| / |金标准|——「已知文本必须进池」的
  真实召回数字；
- 遗漏按来源文件分解：缺口在哪类载体直接可见。

用法：runtime/python/python.exe scripts/_golden_recall.py <语料目录> [游戏名过滤...]
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hanhua.core.recognition_report import build_report


def _project_dbs(game_dir: Path) -> list[Path]:
    """GUI 库（~/.hanhua）与 runner 批量库（~/.hanhua_sweep）都查。"""
    slug = hashlib.md5(str(game_dir).encode("utf-8")).hexdigest()[:10]
    candidates = [
        Path.home() / ".hanhua" / "projects" / slug / "project.db",
        Path.home() / ".hanhua_sweep" / "projects" / slug / "project.db",
    ]
    return [db for db in candidates if db.is_file()]


def _golden_entries(db: Path) -> dict[str, dict]:
    """原文 → {translation, status, file_id}（translated 且非空译文）。"""
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT original, translation, status, file_id FROM entries"
            " WHERE status='translated' AND translation IS NOT NULL"
            " AND trim(translation) != ''").fetchall()
    finally:
        conn.close()
    return {r[0]: {"translation": r[1], "status": r[2], "file_id": r[3]}
            for r in rows}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    filters = sys.argv[2:]
    games = sorted(p for p in root.iterdir()
                   if p.is_dir() and not p.name.startswith(("_", "."))
                   and (not filters or p.name in filters))
    print(f"语料 {len(games)} 个游戏，反查已汉化库……")
    with_projects = [(g, db) for g in games
                     for db in _project_dbs(g)]
    print(f"{len(with_projects)} 个游戏有已汉化项目库\n")
    total_golden = total_found = 0
    for game, db in with_projects:
        golden = _golden_entries(db)
        if not golden:
            continue
        print(f"===== {game.name}：金标准 {len(golden)} 条 =====")
        try:
            report = build_report(game)
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERROR] 提取失败: {exc!r}\n")
            continue
        pool = report.pool_originals
        found = sum(1 for text in golden if text in pool)
        total_golden += len(golden)
        total_found += found
        recall = found / len(golden)
        print(f"  识别率: {found}/{len(golden)} = {recall:.1%}")
        missed = [text for text in golden if text not in pool]
        if missed:
            by_file: dict[str, list[str]] = {}
            for text in missed[:200]:
                by_file.setdefault(golden[text]["file_id"], []).append(text)
            print(f"  遗漏 {len(missed)} 条（前 200 按来源文件分解）：")
            for fid, texts in sorted(
                    by_file.items(), key=lambda kv: -len(kv[1]))[:8]:
                sample = texts[0][:60].replace("\n", " ")
                print(f"    {fid} ×{len(texts)}  例: {sample!r}")
        print()
    if total_golden:
        print(f"===== 合计识别率: {total_found}/{total_golden} = "
              f"{total_found / total_golden:.1%} =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
