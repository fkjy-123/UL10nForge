"""faerie 库重建 + 从第 1 轮导出恢复译文。

背景（2026-08-12）：runner 写回失败后也删库（keep_library=False），
faerie 库连同译文被删；text/translated.txt 被空跑导出覆盖。译文数据
在 git HEAD（第 1 轮 03:38 导出，18698 条）完好。

流程：
1. scan_all 重建库（新代码扫描 + 持久化 source_manifest）
2. 解析第 1 轮 translated.txt（来源/键位/原文/译文）
3. file_id+key_path 精确匹配导入；不匹配尝试 original 匹配
4. 验证导入数
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hanhua.core.project import Project  # noqa: E402

GAME = Path(r"D:\游戏\faerie-afterlight")
APP = Path.home() / ".hanhua_sweep"
EXPORT = Path(__file__).resolve().parent / "docs/all record/faerie-afterlight/text/translated.txt"

# ── 1. 扫描重建库 ────────────────────────────────────────────────
print("== 1/3 扫描重建库 ==")
p = Project.open_game_dir(GAME, APP)
report = p.scan_all()
print("  unblocked:", report.unblocked, "| completable:", report.completable)
if not report.unblocked:
    sys.exit(1)

# ── 2. 解析第 1 轮导出 ───────────────────────────────────────────
print("== 2/3 解析第 1 轮导出 ==")
records: list[tuple[str, str, str, str]] = []  # (file_id, key_path, original, translation)
cur: dict[str, str] = {}
with open(EXPORT, encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if line.startswith("来源："):
            # 新记录开始：先归档上一条
            if cur.get("file_id") and cur.get("key_path") and "original" in cur:
                records.append((
                    cur["file_id"], cur["key_path"],
                    cur.get("original", ""), cur.get("translation", "")))
            cur = {"file_id": line[len("来源："):]}
        elif line.startswith("键位："):
            cur["key_path"] = line[len("键位："):]
        elif line.startswith("原文："):
            cur["original"] = line[len("原文："):]
        elif line.startswith("译文："):
            cur["translation"] = line[len("译文："):]
if cur.get("file_id") and cur.get("key_path") and "original" in cur:
    records.append((cur["file_id"], cur["key_path"], cur["original"], cur.get("translation", "")))
print(f"  解析记录 {len(records)} 条")

# ── 3. 匹配导入 ──────────────────────────────────────────────────
print("== 3/3 匹配导入 ==")
entries = p.store.get_entries()
by_key: dict[tuple[str, str], dict] = {
    (e["file_id"], e["key_path"]): e for e in entries}
by_orig: dict[tuple[str, str], dict] = {
    (e["file_id"], e["original"]): e for e in entries}

matched_key, matched_orig, missed = 0, 0, 0
missed_samples = []
for file_id, key_path, original, translation in records:
    e = by_key.get((file_id, key_path))
    if e is None:
        e = by_orig.get((file_id, original))
        if e is not None:
            matched_orig += 1
        else:
            missed += 1
            if len(missed_samples) < 5:
                missed_samples.append(f"{file_id}:{key_path} = {original[:40]!r}")
            continue
    else:
        matched_key += 1
    if not translation:
        continue  # 回显原文（译文==原文）也要导入？——是，回显是合法译文
    p.store.batch_update_translations([(translation, "translated", e["file_id"], e["key_path"])])

print(f"  键位精确匹配 {matched_key} · 原文匹配 {matched_orig} · 未匹配 {missed}")
for s in missed_samples:
    print("    未匹配:", s)

from hanhua.core.memory import ProjectStore
store = ProjectStore(p.store.db)
print("  库最终状态:", dict(
    (s, store.count(s)) for s in ("translated", "failed", "skipped", "pending")))
