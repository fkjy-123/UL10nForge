"""识别报告 CLI：对游戏目录跑提取池 + 普查 + 差集，打印识别率报告。

用法：runtime/python/python.exe scripts/_recognition_report.py <游戏目录> [更多...]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Windows 控制台 GBK 下 print 含 ␤/⚠ 等非 GBK 字符会 UnicodeEncodeError
# 崩溃（2026-08-16 实证，报告样本换行符用 ␤ 表示）——强制 UTF-8 输出
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hanhua.core.recognition_report import build_report, format_report


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for arg in sys.argv[1:]:
        try:
            report = build_report(arg)
        except Exception as exc:  # noqa: BLE001
            print(f"===== {arg} =====\n[ERROR] {exc!r}")
            continue
        print(format_report(report))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
