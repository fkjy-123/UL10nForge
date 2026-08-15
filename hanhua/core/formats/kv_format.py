"""KV 词典写回：键与行结构保留，只替换值部分。

electric-trains 实证：多语言词典的键是运行时按键查找键——整行翻译
会改键断查找（missions= 被译成 任务=），因此提取侧只产值条目
（original=值），写回侧按行 rfind 替换值尾。
"""
from __future__ import annotations

from hanhua.core.models import TextEntry


def apply_kv(entries: list[TextEntry], text: str) -> str:
    by_line: dict[int, tuple[str, str]] = {}
    for e in entries:
        line = e.meta.get("line")
        if line is None or not e.translation:
            continue
        by_line[int(line)] = (e.original, e.translation)
    lines = text.splitlines(keepends=True)
    for idx, (original, translation) in sorted(by_line.items()):
        if idx < 0 or idx >= len(lines):
            continue
        raw = lines[idx]
        pos = raw.rfind(original)
        if pos < 0:
            continue
        lines[idx] = (raw[:pos] + translation
                      + raw[pos + len(original):])
    return "".join(lines)
