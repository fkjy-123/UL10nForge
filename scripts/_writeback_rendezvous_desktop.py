# -*- coding: utf-8 -*-
r"""Rendezvous 桌面汉化版写回发布（复用 GUI 库，与 GUI 同一套 write_all）。

用法：python scripts/_writeback_rendezvous_desktop.py
输出：C:\Users\mingming\Desktop\Rendezvous.rar_汉化_汉化
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from hanhua.core.project import Project  # noqa: E402
from hanhua.core.models import FontConfig  # noqa: E402

GAME_DIR = Path(r"C:\Users\mingming\Desktop\Rendezvous.rar_汉化")
APP_DIR = Path.home() / ".hanhua"
OUT_DIR = GAME_DIR.parent / (GAME_DIR.name + "_汉化")


def main() -> int:
    print(f"═══ 写回发布：{GAME_DIR} ═══")
    print(f"输出：{OUT_DIR}")
    project = Project.open_game_dir(GAME_DIR, APP_DIR)
    project.store.init_schema()

    # 1. 统一扫描：更新输入清单绑定（write_all 强制要求成功扫描绑定）
    print("[1/3] 统一扫描…", flush=True)
    report = project.scan_all()
    print(f"  文本文件 {report.text_files} · v2 文件 {report.v2_files}"
          f" · 识别条目 {report.recognized_entries}", flush=True)
    if not report.unblocked:
        print("[阻断] 扫描未通过", flush=True)
        return 2

    # 翻译状态复核
    st = {}
    for r in project.store.get_entries():
        st[r["status"]] = st.get(r["status"], 0) + 1
    print(f"  库状态：{st}", flush=True)

    # 2. 写回（启用中文字体部署；批量闭环免实机：确认候选字体发布）
    font_cfg = FontConfig(
        enabled=True, filename="SimplifiedChinese/NotoSerifCJKsc-Medium.otf")
    print("[2/3] 写回（复制游戏 + 静态译文 + 字体部署 + 验证）…", flush=True)
    result = project.write_all(
        font_config=font_cfg,
        allow_partial=True,
        allow_unverified_font_candidate=True,
    )
    print(f"  文本文件 {result['text_files']} · 字体 {result['font']}", flush=True)
    v2 = result["v2"]
    print(f"  写回：attempted={v2.attempted} written={v2.written}"
          f" rejected={len(v2.rejected or ())}"
          f" truncated={len(v2.truncated_items or ())}", flush=True)
    ver = result["verification"]
    print(f"  验证：{ver}", flush=True)

    # 3. 报告输出
    out = OUT_DIR
    if out.exists():
        print(f"  输出目录：{out}（已存在，覆盖完成）", flush=True)
    else:
        print(f"[错误] 输出目录未生成：{out}", flush=True)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
