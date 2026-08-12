"""分析全量写回回归报告，汇总失败模式与异常。

用法: python scripts/analyze_writeback_report.py [--report D:\\游戏\\_writeback_report.json]
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT = Path(r"D:\游戏\_writeback_report.json")


def main() -> None:
    path = Path(sys.argv[sys.argv.index("--report") + 1]) \
        if "--report" in sys.argv else DEFAULT
    recs = json.loads(path.read_text(encoding="utf-8"))
    print(f"游戏总数: {len(recs)}")

    fails = [r for r in recs if not r["ok"]]
    print(f"\n== 失败: {len(fails)} ==")
    for r in fails:
        print(f"  [{r['game']}] {r.get('elapsed_s')}s")
        print(f"    error: {str(r.get('error', ''))[:400]}")

    ok = [r for r in recs if r["ok"] and not r.get("no_text")]
    skipped = [r for r in recs if r.get("no_text")]
    print(f"\n== 通过: {len(ok)} | 零文本跳过: {len(skipped)} ==")
    for r in skipped:
        print(f"  (跳过) [{r['game']}] {r.get('runtime')} "
              f"Unity {r.get('unity_version')}")

    # 字体级别分布
    lvl = Counter(r["font"].get("level") for r in ok)
    provider = Counter(r["font"].get("provider_id") for r in ok)
    print(f"  字体级别: {dict(lvl)}")
    print(f"  字体通道: {dict(provider)}")

    # v2 写回不完整
    partial = [r for r in ok
               if r.get("v2_attempted")
               and r.get("v2_written", 0) < r["v2_attempted"]]
    print(f"\n== v2 写回不完整: {len(partial)} ==")
    for r in partial:
        print(f"  [{r['game']}] {r.get('v2_written')}/{r.get('v2_attempted')}")

    # 零文本游戏（可能漏检）—— 与 no_text 跳过去重
    zero = [r for r in ok if not r.get("v2_attempted") and not r.get("text_files")]
    print(f"\n== 有写回但零文本条目: {len(zero)} ==")
    for r in zero:
        print(f"  [{r['game']}]")

    # 验证警告聚合
    warn_counter = Counter()
    warn_games: dict[str, list[str]] = {}
    for r in ok:
        for w in r.get("verification", {}).get("warnings", []):
            key = w.split(":")[0][:60]
            warn_counter[key] += 1
            warn_games.setdefault(key, []).append(r["game"])
    print(f"\n== 验证警告: {sum(warn_counter.values())} 条, "
          f"{len(warn_counter)} 类 ==")
    for key, count in warn_counter.most_common(10):
        print(f"  x{count}  {key}")
        print(f"       例: {warn_games[key][:4]}")

    slow = sorted(ok, key=lambda r: -r.get("elapsed_s", 0))[:5]
    print("\n== 最慢 5 个 ==")
    for r in slow:
        print(f"  [{r['game']}] {r.get('elapsed_s')}s")


if __name__ == "__main__":
    main()
