"""阶段 4：外部游戏（GitHub Releases 下载）全流程闭环。

用法：python scripts/external_closure.py <游戏路径> [游戏路径 ...]
复用 flow_closure_check.run_closure：扫描 → 规则翻译 → 写回 → 重开验证。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flow_closure_check import run_closure  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python scripts/external_closure.py <游戏路径> [...]")
        return 2
    work_root = Path(tempfile.mkdtemp(prefix="ext-closure-"))
    print(f"工作目录: {work_root}", flush=True)
    report = []
    for src in sys.argv[1:]:
        p = Path(src)
        name = p.name
        print(f"\n=== {name} ===", flush=True)
        try:
            r = run_closure(name, p, work_root)
        except Exception as exc:  # noqa: BLE001
            r = {"game": name, "error": f"{type(exc).__name__}: {exc}"}
        if r.get("error") and "必需 writer 路由不可用" in r["error"]:
            # 预期阻断（如 .fnt 位图字体无可重开验证注入器，写回被
            # 正确拒绝以保护游戏）——不是失败，与真错误区分。
            r = {**r, "blocked": True,
                 "reason": r["error"].split("：")[-1]}
        report.append(r)
        print(json.dumps(r, ensure_ascii=False, indent=1), flush=True)
    print("\n===== 汇总 =====", flush=True)
    ok = 0
    for item in report:
        if item.get("error") and not item.get("blocked"):
            print(f"  {item['game']} 失败: {item['error']}", flush=True)
        elif item.get("blocked"):
            print(f"  {item['game']} 阻断(预期): {item['reason']}", flush=True)
        elif item.get("skipped"):
            print(f"  {item['game']} 跳过: {item['reason']}", flush=True)
        else:
            ok += 1
            print(
                f"  {item['game']} pending={item['pending']} 写入={item['written']} "
                f"闸门={item['gates_overall']} 重开错误={len(item['reopen_parse_errors'])} "
                f"译文缺失={item['reopen_missing_values']} 键保持={item['reopen_key_ok']} "
                f"源未变={item['source_unchanged']} "
                f"译文可寻回={item['rescan_zh_recovered']}/{item['written']} "
                f"英文残留={item['rescan_en_leftover_display']}",
                flush=True)
    print(f"通过 {ok}/{len(report)}", flush=True)
    return 0 if ok == len(report) else 1


if __name__ == "__main__":
    sys.exit(main())
