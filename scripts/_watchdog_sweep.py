"""8morelives 大翻译任务 watchdog：监控翻译进度，服务死亡时自动重跑。

runner 长跑中 llama-server 偶发被静默终止（两次实证：985/835 条处
服务消失、runner 死等）——本脚本轮询项目库 translated 计数，超过
stall 秒无进展则杀 runner/服务重跑（从零开始，每轮 ~1000 条，
无人值守推进大文本量游戏）。
"""
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = Path.home() / ".hanhua_sweep" / "projects" / "a61ae49375" / "project.db"
STALL_SECONDS = 300   # 5 分钟无进展判定停滞
MAX_ROUNDS = 40


def translated_count() -> int:
    try:
        db = sqlite3.connect(str(DB))
        n = db.execute(
            "SELECT COUNT(*) FROM entries WHERE status='translated'"
        ).fetchone()[0]
        db.close()
        return n
    except Exception:
        return -1


def kill_all():
    subprocess.run(["taskkill", "/F", "/IM", "python.exe"],
                   capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                   capture_output=True)
    time.sleep(3)


def main() -> int:
    total = translated_count()
    print(f"watchdog 启动，当前 translated={total}", flush=True)
    for rnd in range(MAX_ROUNDS):
        # 确保服务干净后启动 runner
        subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                       capture_output=True)
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "all_record_runner.py"),
             r"D:\游戏\8morelives", "--no-review", "--batch", "4"],
            cwd=str(ROOT), stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        last = translated_count()
        last_move = time.time()
        while proc.poll() is None:
            cur = translated_count()
            if cur != last:
                last, last_move = cur, time.time()
            elif time.time() - last_move > STALL_SECONDS:
                print(f"[round {rnd+1}] 停滞 {STALL_SECONDS}s "
                      f"（translated={cur}），重启", flush=True)
                kill_all()
                break
            time.sleep(20)
        if proc.poll() is not None:
            rc = proc.wait()
            cur = translated_count()
            print(f"[round {rnd+1}] runner 退出 rc={rc} "
                  f"translated={cur}", flush=True)
            if rc == 0 and cur >= total + 1000:
                total = cur
                # 0 退出可能成功（写回完成）也可能服务死全败
                # 写回完成标志：final report 存在
                fr = ROOT / "docs" / "all record" / "8morelives" / \
                    "final report" / "final-report.md"
                if fr.exists():
                    print("8morelives 已闭环（final report 存在）", flush=True)
                    return 0
            kill_all()
    print("watchdog 轮次耗尽", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
