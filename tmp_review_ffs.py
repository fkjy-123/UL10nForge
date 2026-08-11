"""一次性：对 ffs-full-game-demo 已翻译条目做全量语义审核（基础设施实证）。

数据源：text/translated.txt（runner 导出记录；项目库已按 keep_library=False
清理，导出记录为持久数据源）。
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from hanhua.core.reviewer import (SemanticReviewer, ReviewItem,  # noqa: E402
                                  _default_config, extract_term_pairs)

OUT = Path("docs/all record/ffs-full-game-demo/review")
SRC = Path("docs/all record/ffs-full-game-demo/text/translated.txt")

_SEP = re.compile(r"^─{20,}$")


def parse_export(path: Path) -> list[dict]:
    """解析 translated.txt 记录块 → {source, key, original, translation}。"""
    out: list[dict] = []
    cur: dict = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or _SEP.match(line):
            continue
        if line.startswith("["):
            if cur.get("original"):
                out.append(cur)
            cur = {}
            continue
        for prefix, key in (("原文：", "original"), ("译文：", "translation"),
                            ("来源：", "source"), ("键位：", "key")):
            if line.startswith(prefix):
                cur[key] = line[len(prefix):]
                break
    if cur.get("original"):
        out.append(cur)
    return out


rows = parse_export(SRC)
print("translated rows:", len(rows))
rows = [r for r in rows
        if r.get("translation") and r.get("translation") != r.get("original")]
print("reviewable:", len(rows))

r = SemanticReviewer(_default_config())
items, originals, locators = [], {}, {}
for i, row in enumerate(rows):
    eid = f"e{i}"
    items.append(ReviewItem(
        entry_id=eid,
        original=str(row.get("original", ""))[:600],
        translation=str(row.get("translation", ""))[:600],
        text_type="UI 显示文本" if "asset" in str(row.get("source", ""))
        else "游戏文本"))
    originals[eid] = str(row.get("original", ""))
    locators[eid] = f"{row.get('source', '')}:{row.get('key', '')}"

t0 = time.time()
results = r.review_batch(items)
dt = time.time() - t0
flagged = [v for v in results.values() if v.verdict == "flag"]
print(f"reviewed {len(results)} / flagged {len(flagged)} / {dt:.0f}s")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "review.json").write_text(
    json.dumps([{
        "locator": locators.get(x.entry_id, x.entry_id),
        "original": originals.get(x.entry_id, ""),
        "verdict": x.verdict, "issue": x.issue,
        "reason": x.reason, "suggestion": x.suggestion,
    } for x in results.values()], ensure_ascii=False, indent=1),
    encoding="utf-8")

by_issue: dict[str, int] = {}
for x in flagged:
    by_issue[x.issue or "其他"] = by_issue.get(x.issue or "其他", 0) + 1
pairs = extract_term_pairs(flagged, originals)
lines = [
    "# ffs-full-game-demo 语义审核报告", "",
    f"- 审核模型：{r.config.model}",
    f"- 审核条数：{len(results)}（跳过回显/未翻译）",
    "- 不合格：" + f"{len(flagged)} 条（"
    + "、".join(f"{k} {v}" for k, v in by_issue.items()) + "）",
    "- 术语词对候选：" + f"{len(pairs)}（"
    + "、".join(f"{a}→{b}" for a, b in pairs[:10])
    + ("…" if len(pairs) > 10 else "") + "）",
    "", "## 不合格清单（前 60 条）", "",
]
for i, x in enumerate(flagged[:60], 1):
    lines += [
        f"[{i}] {locators.get(x.entry_id, x.entry_id)}",
        f"  原文：{originals.get(x.entry_id, '')[:100]}",
        f"  译文：{x.suggestion or '（无建议）'}",
        f"  问题：{x.issue}——{x.reason[:80]}",
    ]
lines.append("")
(OUT / "review-report.md").write_text("\n".join(lines), encoding="utf-8")
print("report written:", OUT)
