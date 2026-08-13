# -*- coding: utf-8 -*-
"""Phase E：从已闭环游戏记录抽取固定评估集（可重跑，seed 固定）。

数据源：docs/all record/<game>/review/review.json（每款闭环游戏的语义
审核全量判定：locator/original/verdict(pass|flag)/issue/reason/suggestion）。

产出（eval/sets/，静态资产，评估脚本只读不重抽）：
- semantic_errors.jsonl         200 条错译（按 issue 主类分层 + 游戏配额）
- correct_translations.jsonl    200 条正确对照（过滤短文本/占位符）
- vector_labeled.jsonl          100 条向量标注（跨游戏同原文，按终态标注
                                可复用性：译文一致且全 pass → 1，否则 0）
- polysemy_cross_context.jsonl  40 条多义词跨语境对（同原文一 pass 一 flag）

口径说明：
- issue 主类 = issue 字符串按「/」分隔取首段（如「术语一致性/语义错误」→
  术语一致性）；「数量/单复数」这类主类本身含 / 时保留整串（白名单）。
- 随机种子固定 SEED=20260813 → 重跑结果与首次一致（固定集不漂移）。
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDS = REPO_ROOT / "docs" / "all record"
OUT_DIR = Path(__file__).resolve().parent / "sets"

# 计划口径：最近闭环的 8 款（按收官顺序）
GAMES = [
    "hickory", "honorplusplus", "hotel-paradise", "hunt",
    "inch-by-inch", "incremental-rts", "interdream", "isolated-inhale",
]

SEED = 20260813
TARGET_ERRORS = 200
TARGET_CORRECT = 200
TARGET_VECTOR = 100
TARGET_POLYSEMY = 40

# issue 主类白名单：这些主类自身含「/」，不拆分
_MAIN_ISSUE_KEEP = {
    "数量/单复数", "术语/语义一致性", "术语/语义错误", "语言/术语",
    "人物关系/因果逻辑", "人物关系/逻辑", "人物关系与因果",
    "人物关系与因果逻辑", "否定与语义", "语气与语义偏差",
}


def main_issue(issue: str) -> str:
    issue = (issue or "").strip()
    if not issue:
        return "未分类"
    if issue in _MAIN_ISSUE_KEEP or "/" not in issue:
        return issue
    return issue.split("/")[0]


def load_reviews(game: str) -> list[dict]:
    path = RECORDS / game / "review" / "review.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_translations(game: str) -> dict[str, str]:
    """text/translated.txt 的 {原文: 译文} 映射（live 评估回填译文用）。

    注意：原文可为多行（如多行报错串）——「原文：」起、「译文：」止的
    全部行都是原文；译文同样延续到下一个「原文：」或分隔线。
    """
    path = RECORDS / game / "text" / "translated.txt"
    if not path.is_file():
        return {}
    mapping: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("原文："):
            original = [line[len("原文："):]]
            i += 1
            while i < n and not lines[i].startswith("译文："):
                original.append(lines[i])
                i += 1
            if i < n:  # 找到「译文：」
                translation = [lines[i][len("译文："):]]
                i += 1
                while i < n and not lines[i].startswith(
                        ("原文：", "────")):
                    translation.append(lines[i])
                    i += 1
                mapping["\n".join(original).strip()] = \
                    "\n".join(translation).strip()
            else:
                i = n
        else:
            i += 1
    return mapping


def _valid_correct(item: dict) -> bool:
    """正确集过滤：短文本/纯占位符/格式化串会制造无区分度样本。"""
    original = (item.get("original") or "").strip()
    if len(original) < 4:
        return False
    if len(item.get("reason") or "") < 6:
        return False
    # 纯数字/单符号/占位符模板
    import re
    if re.fullmatch(r"[0-9\s%.:;\-+*/=<>_\[\]()#]+", original):
        return False
    return True


def extract() -> None:
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_flag: list[dict] = []
    all_pass: list[dict] = []
    trans_maps: dict[str, dict[str, str]] = {}
    for game in GAMES:
        trans_maps[game] = load_translations(game)
        for item in load_reviews(game):
            item["game"] = game
            # 译文回填（live 评估 original+translation 对）
            item["translation"] = trans_maps[game].get(
                (item.get("original") or "").strip(), "")
            if item.get("verdict") == "flag":
                all_flag.append(item)
            elif item.get("verdict") == "pass":
                all_pass.append(item)
    n_with_trans = sum(1 for i in all_flag + all_pass if i["translation"])
    print(f"全量：flag={len(all_flag)} pass={len(all_pass)}"
          f"（译文可回填 {n_with_trans}）")

    # ── 1 错译集：按 issue 主类分层 + 每游戏配额上限 ──────────────
    by_issue: dict[str, list[dict]] = defaultdict(list)
    for item in all_flag:
        by_issue[main_issue(item.get("issue", ""))].append(item)
    # 主类按样本量降序，配额按比例
    ordered = sorted(by_issue.items(), key=lambda kv: -len(kv[1]))
    total = len(all_flag)
    errors: list[dict] = []
    for issue, items in ordered:
        quota = max(1, round(TARGET_ERRORS * len(items) / total))
        pool = [i for i in items if i["game"] in GAMES]
        rng.shuffle(pool)
        per_game: dict[str, int] = defaultdict(int)
        picked: list[dict] = []
        for item in pool:
            if len(picked) >= quota:
                break
            if per_game[item["game"]] >= 40:  # 单游戏上限防垄断
                continue
            per_game[item["game"]] += 1
            picked.append(item)
        errors.extend(picked)
    rng.shuffle(errors)
    errors = errors[:TARGET_ERRORS]
    (OUT_DIR / "semantic_errors.jsonl").write_text(
        "\n".join(json.dumps(
            {"game": i["game"], "locator": i["locator"],
             "original": i["original"], "translation": i.get(
                 "translation", ""), "issue": main_issue(
                 i.get("issue", "")), "suggestion": i.get("suggestion", "")},
            ensure_ascii=False) for i in errors) + "\n", encoding="utf-8")
    issue_dist = Counter(i["issue"] for i in errors)
    print(f"错译集：{len(errors)} 条，主类分布：")
    for issue, n in issue_dist.most_common(12):
        print(f"  {issue}: {n}")

    # ── 2 正确对照集：按游戏分层配额 ───────────────────────────────
    by_game_pass: dict[str, list[dict]] = defaultdict(list)
    for item in all_pass:
        if _valid_correct(item):
            by_game_pass[item["game"]].append(item)
    correct: list[dict] = []
    for game in GAMES:
        pool = list(by_game_pass[game])
        rng.shuffle(pool)
        quota = max(1, round(TARGET_CORRECT * len(pool) / max(
            1, sum(len(v) for v in by_game_pass.values()))))
        correct.extend(pool[:quota])
    rng.shuffle(correct)
    correct = correct[:TARGET_CORRECT]
    (OUT_DIR / "correct_translations.jsonl").write_text(
        "\n".join(json.dumps(
            {"game": i["game"], "locator": i["locator"],
             "original": i["original"], "translation": i.get(
                 "translation", "")}, ensure_ascii=False)
            for i in correct) + "\n", encoding="utf-8")
    print(f"正确对照集：{len(correct)} 条")

    # ── 3 向量标注集：同原文多出现 → 按终态标可复用性 ──────────────
    # 通道 A（同源可复用）：同原文 ≥2 次出现且全部 pass → 1
    # 通道 B（近似不可盲用）：高相似文本对（SequenceMatcher 0.55~0.99，
    # 原文不同）→ 0——向量检索的噪声来源，必须靠重排/语境区分
    by_text: dict[str, list[dict]] = defaultdict(list)
    for item in all_pass + all_flag:
        by_text[item["original"].strip()].append(item)
    vector: list[dict] = []
    seen_texts: set[str] = set()
    for text, items in by_text.items():
        if len(items) < 2 or text in seen_texts:
            continue
        seen_texts.add(text)
        verdicts = {i.get("verdict") for i in items}
        vector.append({
            "text": text, "games": sorted({i["game"] for i in items}),
            "label": 1 if verdicts == {"pass"} else 0,
            "kind": "same_source", "count": len(items),
            "verdicts": sorted(verdicts),
        })
        if len(vector) >= TARGET_VECTOR // 2:
            break
    import difflib
    pool_texts = [i["original"].strip() for i in all_pass + all_flag]
    rng.shuffle(pool_texts)
    source_texts = [v["text"] for v in vector]
    used_pairs: set[tuple[str, str]] = set()
    for a in source_texts:
        if len(vector) >= TARGET_VECTOR:
            break
        for b in pool_texts:
            if a == b or (b, a) in used_pairs:
                continue
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            if 0.5 <= ratio < 0.95:
                used_pairs.add((a, b))
                vector.append({
                    "text": a, "similar_to": b,
                    "similarity": round(ratio, 3),
                    "label": 0, "kind": "near_dup",
                })
                break
    (OUT_DIR / "vector_labeled.jsonl").write_text(
        "\n".join(json.dumps(v, ensure_ascii=False) for v in vector) + "\n",
        encoding="utf-8")
    n_reuse = sum(1 for v in vector if v["label"] == 1)
    print(f"向量标注集：{len(vector)} 条（可复用 {n_reuse} / "
          f"近似不可盲用 {len(vector) - n_reuse}）")

    # ── 4 多义词跨语境集：同原文多出现且判定混合（pass+flag） ─────
    polysemy: list[dict] = []
    seen_texts.clear()
    for text, items in by_text.items():
        if len(polysemy) >= TARGET_POLYSEMY:
            break
        pass_items = [i for i in items if i.get("verdict") == "pass"]
        flag_items = [i for i in items if i.get("verdict") == "flag"]
        if not (pass_items and flag_items) or text in seen_texts:
            continue
        seen_texts.add(text)
        p = rng.choice(pass_items)
        f = rng.choice(flag_items)
        polysemy.append({
            "text": text,
            "pass_translation": p.get("translation", ""),
            "flag_translation": f.get("translation", ""),
            "pass_context": {"game": p["game"], "locator": p["locator"]},
            "flag_context": {"game": f["game"], "locator": f["locator"],
                             "issue": main_issue(f.get("issue", "")),
                             "reason": f.get("reason", "")},
        })
    (OUT_DIR / "polysemy_cross_context.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in polysemy)
        + "\n", encoding="utf-8")
    cross_game = sum(1 for x in polysemy
                     if x["pass_context"]["game"] != x["flag_context"]["game"])
    print(f"多义词跨语境集：{len(polysemy)} 条"
          f"（跨游戏 {cross_game} / 同游戏 {len(polysemy) - cross_game}）")


if __name__ == "__main__":
    sys.exit(extract())
