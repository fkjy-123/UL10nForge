"""语料级盲区普查：对全部游戏跑 sweep_game，产出载体盲区清单。

只跑普查（sweep 不解析 Unity 容器，快），找「有未认领文本」的游戏：
- hits=0 或仅 app.info：提取管线已覆盖全部载体（分母干净）；
- hits 多：有未知载体/伪装扩展名文件带文本 → 新形态登记候选。

用法：runtime/python/python.exe scripts/_corpus_census.py <语料目录>
输出：每游戏 hits/文件数 + 命中文本样本（按可疑度排序）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hanhua.core.census import sweep_game


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    games = sorted(
        p for p in root.iterdir() if p.is_dir()
        and not p.name.startswith(("_", ".")))
    print(f"语料：{len(games)} 个目录")
    for i, game in enumerate(games):
        try:
            result = sweep_game(game)
        except Exception as exc:  # noqa: BLE001
            print(f"[{i + 1}/{len(games)}] {game.name}: ERROR {exc!r}")
            continue
        meaningful = [
            h for h in result.hits
            if "app.info" not in h.rel_path
        ]
        status = (f"盲区 {len(meaningful)} 命中"
                  f"（{result.files_scanned} 文件）"
                  if meaningful else
                  f"干净（{result.files_scanned} 文件扫过，"
                  f"无未认领文本）")
        print(f"[{i + 1}/{len(games)}] {game.name}: {status}")
        if meaningful:
            # 按可疑度抽样：长文本优先，每文件至多 2 条
            seen_files: set[str] = set()
            shown = 0
            for h in sorted(
                    meaningful,
                    key=lambda x: (len(x.text) >= 12, len(x.text)),
                    reverse=True):
                if h.rel_path in seen_files:
                    continue
                if len(seen_files) >= 6:
                    break
                seen_files.add(h.rel_path)
                shown += 1
                text = h.text.replace("\n", " ")[:60]
                print(f"    {h.rel_path}@{h.offset} [{h.encoding}]"
                      f" {text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
