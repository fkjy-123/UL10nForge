"""8morelives 翻译监控：每 5 分钟打印进度 + F42 重启事件。"""
import sqlite3
import time
from pathlib import Path

DB = Path.home() / ".hanhua_sweep" / "projects" / "a61ae49375" / "project.db"
LOG = Path(r"logs\8morelives-run.log")


def main() -> None:
    last = -1
    while True:
        try:
            db = sqlite3.connect(str(DB))
            cnt = db.execute(
                "SELECT COUNT(*) FROM entries WHERE status='translated'"
            ).fetchone()[0]
            db.close()
        except Exception:
            cnt = last
        evts = []
        if LOG.exists():
            text = LOG.read_text(encoding="utf-8", errors="replace")
            evts = [l.strip() for l in text.splitlines()
                    if "[F42]" in l or "写回" in l or "记录完成" in l]
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {cnt}/31379", flush=True)
        for e in evts[-3:]:
            print(f"   {e}", flush=True)
        time.sleep(300)


if __name__ == "__main__":
    main()
