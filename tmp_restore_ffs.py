"""ffs 库重建 + 从本次重跑导出恢复译文（写回成功后库被清理）。

恢复路径（faerie 先例）：scan_all 重建库 → 解析导出 → 匹配导入。
关键差异：导出译文全部重新过**新质量门**（术语污染修复后判定）——
通过的导入 translated，失败的留 pending 由补翻脚本重翻（旧判定失败
2077 条误杀译文在新判定下 94.6% 转通过）。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hanhua.core.project import Project  # noqa: E402

GAME = Path(r"D:\游戏\ffs-full-game-demo")
APP = Path.home() / ".hanhua_sweep"
OUT = Path(__file__).resolve().parent / "docs/all record/ffs-full-game-demo/text"


def parse_export(path: Path) -> list[tuple[str, str, str, str]]:
    """解析导出：来源/键位/原文/译文 逐行匹配（faerie 脚本同款）。"""
    records: list[tuple[str, str, str, str]] = []
    cur: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("来源："):
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
        records.append((cur["file_id"], cur["key_path"], cur["original"],
                        cur.get("translation", "")))
    return records


print("== 1/4 扫描重建库 ==")
p = Project.open_game_dir(GAME, APP)
report = p.scan_all()
print("  unblocked:", report.unblocked, "| completable:", report.completable)
if not report.unblocked:
    sys.exit(1)

print("== 2/4 解析导出 ==")
translated_recs = parse_export(OUT / "translated.txt")
failed_recs = parse_export(OUT / "failed.txt")
print(f"  translated.txt {len(translated_recs)} 条 · failed.txt {len(failed_recs)} 条")

print("== 3/4 新质量门验证并导入 ==")
from hanhua.core.batch_translator import BatchTranslator  # noqa: E402
from hanhua.core.models import TextEntry  # noqa: E402


class FakeClient:
    def chat(self, system, messages):
        raise AssertionError("恢复脚本只判定不翻译")


translator = BatchTranslator(
    FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")

entries = p.store.get_entries()
by_key: dict[tuple[str, str], dict] = {
    (e["file_id"], e["key_path"]): e for e in entries}
by_orig: dict[tuple[str, str], dict] = {
    (e["file_id"], e["original"]): e for e in entries}

matched, missed, fail_kept = 0, 0, 0
pending_for_retry = []
for records in (translated_recs, failed_recs):
    for file_id, key_path, original, translation in records:
        e = by_key.get((file_id, key_path)) or by_orig.get((file_id, original))
        if e is None:
            missed += 1
            continue
        if not translation:
            continue
        entry = TextEntry(
            file_id=e["file_id"], key_path=e["key_path"], original=e["original"],
            translation=translation, status=e.get("status", "pending"),
            locked=bool(e.get("locked", 0)), id=e.get("id"),
            meta={"role": "display", "disposition": "translate"},
            confidence="high")
        ok = translator._apply_quality(entry, translation)
        if not ok:
            # 新判定失败（方向译错/回显/换行）→ 留 pending 重翻
            fail_kept += 1
            pending_for_retry.append((e["file_id"], e["key_path"]))
            continue
        entry.status = "translated"
        entry.meta["quality_passed"] = True
        entry.meta["confidence"] = "medium"
        entry.quality_reasons = ()
        p.store.batch_update_translation_results([entry])
        matched += 1
print(f"  导入 {matched} · 新判定失败留 pending {fail_kept} · 未匹配 {missed}")

from hanhua.core.memory import ProjectStore
store = ProjectStore(p.store.db)
print("  库状态:", dict((s, store.count(s)) for s in
                     ("translated", "failed", "skipped", "pending")))
print(f"  待补翻 pending 数：{store.count('pending')}（含恢复时判定失败的 {fail_kept} 条）")
