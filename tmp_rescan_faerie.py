"""faerie 扫描补跑：向现有项目库持久化 source_manifest。

背景：--resume 修复（2026-08-12）后写回可从库恢复扫描绑定清单，
但 faerie 现有库是修复前扫描的（profile 无清单键）。本脚本用新代码
重跑 scan_all（upsert 保留已有译文，不删库），把清单持久化进库，
使后续 `--resume` 写回通过输入闸门。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hanhua.core.project import Project  # noqa: E402

GAME = Path(r"D:\游戏\faerie-afterlight")
APP = Path.home() / ".hanhua_sweep"

p = Project.open_game_dir(GAME, APP)
report = p.scan_all()
print("unblocked:", report.unblocked)
print("completable:", report.completable)
print("input_protected:", report.input_protected)
print("source_manifest 持久化:", bool(p._last_source_manifest))
print("text_scan_manifest:", p._last_text_scan_manifest is not None)
print("il2cpp_hashes:", p._last_il2cpp_input_hashes is not None)
if report.unblocked:
    print("OK：清单已入库，--resume 写回可过闸门")
else:
    print("FAIL：扫描未解锁")
    sys.exit(1)
