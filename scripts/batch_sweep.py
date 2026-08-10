"""地毯式排查批量串行执行器：连续跑多款游戏（服务复用 EXTERNAL）。

用法：python scripts/batch_sweep.py [游戏名...]
- 已闭环（docs/all record/<game>/final report/ 存在）→ 跳过
- 每款跑完输出摘要行（译/败/跳/写回）
- 全部跑完输出汇总表
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "docs" / "all record"
GAMES = Path("D:/游戏")


def is_done(name: str) -> bool:
    return (RECORDS / name / "final report").exists()


def run_one(name: str) -> str:
    if not (GAMES / name).is_dir():
        return f"{name}: 目录不存在，跳过"
    if is_done(name):
        return f"{name}: 已闭环，跳过"
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "all_record_runner.py"),
             str(GAMES / name)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=3600)
    except subprocess.TimeoutExpired:
        return f"{name}: 超时(1h)"
    out = proc.stdout or ""
    failed = 0
    done = 0
    for line in out.splitlines():
        line = line.strip()
        if line.startswith(" 完成："):
            # 完成：74 条（记忆 0） · 失败 0 · 请求 76 · 耗时 47.8s
            try:
                done = int(line.split("完成：")[1].split("条")[0])
            except (ValueError, IndexError):
                pass
            try:
                failed = int(line.split("失败 ")[1].split(" ·")[0])
            except (ValueError, IndexError):
                pass
        if "写回成功" in line:
            wb = line
    tail = "\n".join(out.splitlines()[-3:])
    return f"{name}: {done}译/{failed}败 | {tail}"


def main():
    names = sys.argv[1:]
    if not names:
        names = sorted(
            d.name for d in GAMES.iterdir()
            if d.is_dir() and not d.name.startswith("_"))
    results = []
    for name in names:
        print(f"▶ {name}", flush=True)
        results.append(run_one(name))
        print("  " + results[-1], flush=True)
    print("\n═══ 汇总 ═══")
    for line in results:
        print(line)


if __name__ == "__main__":
    main()
