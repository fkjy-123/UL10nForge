"""全量扫描回归：对 D:\\游戏 每个 Unity 游戏执行 scan_all，收集识别层问题。

输出: D:\\游戏\\_scan_report.json（每个游戏：文件数/条目数/状态分布/异常）
用法: python scripts/mass_scan_all.py [--limit N] [--games a,b,c]
"""
from __future__ import annotations
import json
import sys
import time
import traceback
from pathlib import Path

APP_DIR = Path.home() / ".hanhua_mass"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hanhua.core.project import Project  # noqa: E402


def scan_game(game_dir: Path) -> dict:
    rec: dict = {"game": game_dir.name, "ok": False}
    t0 = time.monotonic()
    try:
        project = Project.open_game_dir(game_dir, APP_DIR)
        report = project.scan_all()
        rec["ok"] = True
        rec["runtime"] = report.fingerprint.runtime
        rec["unity_version"] = report.fingerprint.unity_version
        rec["text_files"] = report.text_files
        rec["v2_files"] = report.v2_files
        rec["recognized_entries"] = report.recognized_entries
        rec["status_counts"] = dict(report.status_counts)
        rec["confidence"] = dict(report.confidence_counts)
        rec["unblocked"] = report.unblocked
        rec["completable"] = report.completable
        rec["warnings"] = list(report.warnings)
        rec["route"] = [
            {"id": s.step_id, "status": s.status, "required": s.required}
            for s in report.route
        ]
        rec["font_capability"] = {
            "provider": report.font_capability.provider_id,
            "supported": report.font_capability.provider_supported,
            "static_allowed": report.font_capability.static_writeback_allowed,
        }
        rec["elapsed_s"] = round(time.monotonic() - t0, 1)
    except Exception as exc:  # noqa: BLE001
        rec["ok"] = False
        rec["error"] = str(exc)[:500]
        rec["traceback"] = traceback.format_exc(limit=5)[-1500:]
        rec["elapsed_s"] = round(time.monotonic() - t0, 1)
    return rec


def main() -> None:
    args = [a for a in sys.argv[1:]]
    limit = None
    only = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if "--games" in args:
        only = set(args[args.index("--games") + 1].split(","))
    base = Path(r"D:\游戏")
    survey = json.loads((base / "_survey.json").read_text(encoding="utf-8"))
    games = [base / r["name"] for r in survey if r["unity"]]
    if only:
        games = [g for g in games if g.name in only]
    if limit:
        games = games[:limit]
    out = []
    t0 = time.monotonic()
    for i, game_dir in enumerate(games, 1):
        print(f"[{i}/{len(games)}] {game_dir.name} ...", flush=True)
        rec = scan_game(game_dir)
        out.append(rec)
        (base / "_scan_report.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  ok={rec['ok']} files={rec.get('text_files')}/{rec.get('v2_files')} "
              f"entries={rec.get('recognized_entries')} "
              f"status={rec.get('status_counts')} {rec.get('elapsed_s')}s",
              flush=True)
        if not rec["ok"]:
            print(f"  ERROR: {rec.get('error', '')[:200]}", flush=True)
    print(f"TOTAL {round(time.monotonic() - t0, 1)}s -> {base / '_scan_report.json'}")
    fails = [r for r in out if not r["ok"]]
    print(f"failed: {len(fails)}/{len(out)}")
    for r in fails:
        print(f"  - {r['game']}: {r.get('error', '')[:150]}")


if __name__ == "__main__":
    main()
