"""知识库 CLI 查询工具（六库体系 §0.4.3）。

用法：
  python scripts/kb_query.py --stats              # 六库统计（条数/命中/kind 分布）
  python scripts/kb_query.py --game-stats         # 按游戏沉淀统计
  python scripts/kb_query.py <domain> [kind]      # 按库/子类查询（hits 降序）
  python scripts/kb_query.py --keyword 关键词      # 跨库全文检索
  python scripts/kb_query.py --match "问题描述"     # 失败案例智能复用检索
  python scripts/kb_query.py --solve "问题描述"     # 六库联动检索（全部答案）
  python scripts/kb_query.py --all                # 全库条目

domain ∈ unity_structure/fail_case/text/component_compat/quality/writeback。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hanhua.core.knowledge import KnowledgeBase  # noqa: E402

DB = Path.home() / ".hanhua" / "knowledge.db"
LIB_NAMES = {
    "unity_structure": "① Unity 结构库",
    "fail_case": "② 失败案例库",
    "text": "③ 文本规则库",
    "component_compat": "④ 组件兼容库",
    "quality": "⑤ 翻译质量库",
    "writeback": "⑥ 写回验证库",
}


def show_rows(rows: list[dict], title: str = "") -> None:
    if title:
        print(f"\n{title}（{len(rows)} 条）")
    for r in rows:
        lib = LIB_NAMES.get(r.get("domain", ""), r.get("domain", ""))
        hits = r.get("hits", 0) or 0
        src = r.get("source", "")
        print(f"  [{lib} / {r.get('kind', '')}] hits={hits} src={src}")
        print(f"    {r.get('pattern', '')[:90]}")
        if r.get("map_to"):
            print(f"    → {r['map_to'][:90]}")
        if r.get("note"):
            print(f"    注 {r['note'][:90]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="知识库查询（六库体系）")
    ap.add_argument("domain", nargs="?", help="库名")
    ap.add_argument("kind", nargs="?", help="子类")
    ap.add_argument("--keyword", help="跨库全文检索")
    ap.add_argument("--match", help="失败案例智能复用检索")
    ap.add_argument("--solve", help="六库联动检索（一个问题的全部答案）")
    ap.add_argument("--stats", action="store_true", help="六库统计")
    ap.add_argument("--game-stats", action="store_true", help="按游戏统计")
    ap.add_argument("--all", action="store_true", help="全部条目")
    args = ap.parse_args()

    kb = KnowledgeBase(DB)
    if args.stats or not (args.domain or args.keyword or args.match
                          or args.solve or args.all or args.game_stats):
        for lib, st in kb.library_stats().items():
            kinds = " ".join(f"{k}×{v}" for k, v in st["kinds"].items())
            print(f"{LIB_NAMES[lib]:16s} {st['count']:3d} 条"
                  f" · 命中 {st['hits']:4d} · {kinds}")
    elif args.game_stats:
        for game, st in kb.game_stats().items():
            print(f"  {game:44s} {st['count']:3d} 条 hits={st['hits']}"
                  f" · {', '.join(f'{d}×{c}' for d, c in st['domains'].items())}")
    elif args.keyword:
        show_rows(kb.search_keyword(args.keyword),
                  f"跨库检索「{args.keyword}」")
    elif args.match:
        show_rows(kb.match_case(args.match),
                  f"失败案例智能复用「{args.match}」")
    elif args.solve:
        for lib, rows in kb.solve(args.solve).items():
            if rows:
                show_rows(rows, f"「{args.solve}」→ {LIB_NAMES[lib]}")
    elif args.all:
        show_rows(kb.list_knowledge(), "全库")
    else:
        rows = kb.list_knowledge(domain=args.domain, kind=args.kind)
        title = f"{LIB_NAMES.get(args.domain, args.domain or '全部')}"
        if args.kind:
            title += f" / {args.kind}"
        show_rows(rows, title)
    kb.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
