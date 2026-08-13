# -*- coding: utf-8 -*-
"""Phase E：量化效果评估（固定集 + 闭环记录回测）。

用法：
    python eval/run_eval.py --record-stats 3     # 最近 3 款闭环游戏记录统计
    python eval/run_eval.py --live               # 固定集过本地审核模型评估
    python eval/run_eval.py --record-stats 3 --live   # 两者都跑

record-stats（记录回测，零模型成本）：
  每款闭环游戏从 review.json + summary.md 聚合：
  - 污染率 = flagged / reviewed（语义审核判定「不合格」占比）
  - 审核覆盖率 = reviewed / translated（已翻译条目中被审核覆盖的比例）
  - 复用收益 = 记忆命中（翻译阶段记忆直接应用）+ 术语沉淀（词对入全局库）
  收敛率口径缺口：闭环记录未落盘重译收敛数据 → 如实标注（live 补）。

live（固定集评估，本地审核模型）：
  - 错译集（200）：检出率 = 被判定 flag / 有译文条数（CRITICAL+MAJOR 检出）
  - 正确对照集（200）：误报率 = 被判定 flag / 200
  - 多义词跨语境集（12）：pass 语境译文应通过（消歧通过率）、flag 语境
    译文应检出（坏译检出率）
  判定错误条目输出到 eval/results/live_errors.jsonl 供人工复核。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))   # 任意 cwd 启动均能 import hanhua
RECORDS = REPO_ROOT / "docs" / "all record"
SETS = Path(__file__).resolve().parent / "sets"
RESULTS = Path(__file__).resolve().parent / "results"

# 计划口径：最近闭环的 8 款（按收官顺序，后进在前）
GAMES = [
    "hickory", "honorplusplus", "hotel-paradise", "hunt",
    "inch-by-inch", "incremental-rts", "interdream", "isolated-inhale",
]
RECENT = list(reversed(GAMES))      # isolated-inhale 最新


# ── 记录回测 ──────────────────────────────────────────────────────

def _load_json(path: Path) -> list[dict]:
    """review.json 是标准 JSON 数组（含多行缩进）。"""
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    """固定评估集（sets/*.jsonl）逐行 JSON。"""
    if not path.is_file():
        return []
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _summary_field(game: str) -> dict:
    """summary.md 解析：完成数/记忆命中/审核条数/不合格/术语沉淀。"""
    path = RECORDS / game / "summary.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    field: dict = {}
    m = re.search(r"总条目：(\d+) · 完成：(\d+)(?:（记忆命中 (\d+)）)?", text)
    if m:
        field["total"] = int(m.group(1))
        field["translated"] = int(m.group(2))
        field["memory_hits"] = int(m.group(3) or 0)
    m = re.search(r"审核条数：(\d+) · 不合格：(\d+) · 术语沉淀：(\d+)", text)
    if m:
        field["reviewed"] = int(m.group(1))
        field["flagged"] = int(m.group(2))
        field["pairs"] = int(m.group(3))
    return field


def record_stats(n: int = 3) -> dict:
    games = RECENT[:n]
    rows = []
    for game in games:
        reviews = _load_json(RECORDS / game / "review" / "review.json")
        flagged = sum(1 for r in reviews if r.get("verdict") == "flag")
        field = _summary_field(game)
        reviewed = field.get("reviewed", len(reviews))
        rows.append({
            "game": game,
            "reviewed": reviewed,
            "flagged": flagged,
            "pollution_rate": round(flagged / reviewed, 4) if reviewed else 0.0,
            "translated": field.get("translated", 0),
            "coverage": round(reviewed / field["translated"], 4)
            if field.get("translated") else 0.0,
            "memory_hits": field.get("memory_hits", 0),
            "pairs": field.get("pairs", 0),
        })
    agg = {
        "reviewed": sum(r["reviewed"] for r in rows),
        "flagged": sum(r["flagged"] for r in rows),
        "translated": sum(r["translated"] for r in rows),
        "memory_hits": sum(r["memory_hits"] for r in rows),
        "pairs": sum(r["pairs"] for r in rows),
    }
    agg["pollution_rate"] = round(
        agg["flagged"] / agg["reviewed"], 4) if agg["reviewed"] else 0.0
    agg["coverage"] = round(
        agg["reviewed"] / agg["translated"], 4) if agg["translated"] else 0.0
    return {"games": rows, "aggregate": agg}


def print_record_stats(n: int = 3) -> None:
    data = record_stats(n)
    agg = data["aggregate"]
    print(f"═══ 闭环记录回测（最近 {n} 款） ═══")
    print(f"{'游戏':<18}{'审核':>6}{'不合格':>7}{'污染率':>9}"
          f"{'已翻':>7}{'覆盖率':>9}{'记忆命中':>8}{'术语沉淀':>8}")
    for r in data["games"]:
        print(f"{r['game']:<18}{r['reviewed']:>6}{r['flagged']:>7}"
              f"{r['pollution_rate']:>9.1%}{r['translated']:>7}"
              f"{r['coverage']:>9.1%}{r['memory_hits']:>8}{r['pairs']:>8}")
    print("-" * 71)
    print(f"{'聚合':<18}{agg['reviewed']:>6}{agg['flagged']:>7}"
          f"{agg['pollution_rate']:>9.1%}{agg['translated']:>7}"
          f"{agg['coverage']:>9.1%}{agg['memory_hits']:>8}{agg['pairs']:>8}")
    print(f"\n复用收益：记忆直接应用 {agg['memory_hits']} 条 + "
          f"术语沉淀 {agg['pairs']} 条词对 → 全局库（后续游戏自动约束）")
    print("口径缺口：收敛率（重译收敛/重译条数）未落盘于闭环记录"
          "——需 live 模式或 runner 补记")


# ── live 固定集评估（本地审核模型） ───────────────────────────────

def _reviewer():
    from hanhua.core.reviewer import ReviewItem, SemanticReviewer

    reviewer = SemanticReviewer(app_dir=REPO_ROOT)
    if not reviewer.usable:
        raise SystemExit("本地审核模型不可用（models/ 缺 Qwen3.5-4B GGUF）")
    return reviewer, ReviewItem


def live_eval() -> None:
    from hanhua.core.reviewer import ReviewItem, SemanticReviewer

    print("═══ 固定集 live 评估（本地审核模型） ═══")
    reviewer = SemanticReviewer(app_dir=REPO_ROOT)
    if not reviewer.usable:
        raise SystemExit("本地审核模型不可用（models/ 缺 Qwen3.5-4B GGUF）")
    RESULTS.mkdir(parents=True, exist_ok=True)
    errors_out = []

    # 1) 错译集：检出率
    errors = _load_jsonl(SETS / "semantic_errors.jsonl")
    error_items = [e for e in errors if e.get("translation")]
    detected = 0
    error_results = []
    for i, item in enumerate(error_items):
        result = reviewer.review_one(ReviewItem(
            entry_id=f"{item['game']}:{item['locator'][:40]}",
            original=item["original"], translation=item["translation"]))
        if result.error:
            error_results.append("error")
            continue
        if result.verdict == "flag":
            detected += 1
        elif result.verdict == "pass":
            errors_out.append({"set": "semantic_errors", "item": item,
                               "result": "漏检(pass)"})
        if (i + 1) % 25 == 0:
            print(f"  错译集 {i + 1}/{len(error_items)}…")
    n_error = len(error_items) - error_results.count("error")
    detect_rate = detected / n_error if n_error else 0.0

    # 2) 正确对照集：误报率
    correct = _load_jsonl(SETS / "correct_translations.jsonl")
    correct_items = [c for c in correct if c.get("translation")]
    false_pos = 0
    n_correct = 0
    for i, item in enumerate(correct_items):
        result = reviewer.review_one(ReviewItem(
            entry_id=f"{item['game']}:{item['locator'][:40]}",
            original=item["original"], translation=item["translation"]))
        if result.error:
            continue
        n_correct += 1
        if result.verdict == "flag":
            false_pos += 1
            errors_out.append({"set": "correct", "item": item,
                               "result": "误报(flag)"})
        if (i + 1) % 25 == 0:
            print(f"  正确集 {i + 1}/{len(correct_items)}…")

    # 3) 多义词跨语境集：消歧通过率 + 坏译检出率
    polysemy = _load_jsonl(SETS / "polysemy_cross_context.jsonl")
    disambig_ok = 0
    bad_detected = 0
    n_poly = 0
    for i, item in enumerate(polysemy):
        if not (item.get("pass_translation") and item.get("flag_translation")):
            continue
        n_poly += 1
        ok = reviewer.review_one(ReviewItem(
            entry_id=f"poly-{i}:pass",
            original=item["text"], translation=item["pass_translation"]))
        bad = reviewer.review_one(ReviewItem(
            entry_id=f"poly-{i}:flag",
            original=item["text"], translation=item["flag_translation"]))
        if not ok.error and ok.verdict == "pass":
            disambig_ok += 1
        elif not ok.error:
            errors_out.append({"set": "polysemy_pass", "item": item,
                               "result": "误报(flag)"})
        if not bad.error and bad.verdict == "flag":
            bad_detected += 1
        elif not bad.error:
            errors_out.append({"set": "polysemy_flag", "item": item,
                               "result": "漏检(pass)"})

    (RESULTS / "live_errors.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in errors_out)
        + "\n", encoding="utf-8")

    print(f"\n错译集检出率：{detected}/{n_error} = {detect_rate:.1%}"
          f"（审核对真实错译的捕获能力）")
    print(f"正确集误报率：{false_pos}/{n_correct} = "
          f"{false_pos / n_correct:.1%}" if n_correct else "正确集无可用样本")
    print(f"多义词：消歧通过 {disambig_ok}/{n_poly} · "
          f"坏译检出 {bad_detected}/{n_poly}")
    print(f"判定错误明细 → eval/results/live_errors.jsonl"
          f"（{len(errors_out)} 条，供人工复核）")
    print(f"审核模型：{reviewer.model_name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase E 量化评估")
    parser.add_argument("--record-stats", type=int, nargs="?", const=3,
                        default=3, metavar="N",
                        help="最近 N 款闭环游戏记录回测（默认 3）")
    parser.add_argument("--live", action="store_true",
                        help="固定集过本地审核模型评估（需要模型）")
    parser.add_argument("--no-record-stats", action="store_true",
                        help="跳过记录回测（只跑 --live）")
    args = parser.parse_args()
    if not args.no_record_stats:
        print_record_stats(args.record_stats)
    if args.live:
        print()
        live_eval()
    return 0


if __name__ == "__main__":
    sys.exit(main())
