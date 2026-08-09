"""Ink (.ink) / Yarn (.yarn) 剧情脚本提取与写回。

只提取「玩家可见对白」：Ink 的选择项文本与普通行、Yarn 的
`说话人: 文本` 值与普通行；流程控制（跳转/标记/变量/命令/注释/
代码块）原样保留。`{...}` 变量与 `[...]` 交替文本由 placeholders
保护，模型不可改动。
"""
from __future__ import annotations
import re
from pathlib import Path

from hanhua.core.formats import read_text
from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.placeholders import should_skip

# Ink 流程标记行
_INK_FLOW = re.compile(
    r"^(?:->|\s*->|===|==|===)|^\{|\}$|^\[\[|\]$|^\s*&|^~|^!|^VAR\b|^LIST\b|"
    r"^CONST\b|^TODO\b|^INCLUDE\b|^EXTERNAL\b|^#")
# Ink 选择项：* 文本 或 + 文本（尾部可带 -> 跳转）
_INK_CHOICE = re.compile(
    r"^(?P<marker>\*|\+)[ \t]+(?P<text>[^\r\n]*?)(?P<tail>[ \t]*->[^\r\n]*)?$")
# Yarn 命令/流程行
_YARN_FLOW = re.compile(
    r"^(?:<<|>>|\[\[|]]|\s*->|^===|^//|^#|^\{|^\}|^\|)")
_YARN_KV = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_ -]{0,40}):(?P<value>.*)$")
# Yarn 选项：[[链接|目标]] / [[目标]]
_YARN_LINK = re.compile(r"^\[\[(?P<label>[^|\]]+)(?:\|[^\]]+)?\]\]\s*$")


def extract_ink_yarn(path: str | Path, file_id: str | None = None,
                     kind: str | None = None) -> list[TextEntry]:
    p = Path(path)
    fid = file_id or p.name
    fmt = (kind or p.suffix.lstrip(".").lower()).split(".")[0]
    lines = read_text(p).splitlines()
    entries: list[TextEntry] = []
    for i, line in enumerate(lines):
        meta = {"line_no": i, "raw": line, "script_kind": fmt}
        stripped = line.strip()
        if not stripped:
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "blank"}))
            continue
        flow = _INK_FLOW.match(stripped) if fmt == "ink" else _YARN_FLOW.match(stripped)
        if flow:
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "flow"}))
            continue
        if fmt == "ink":
            m = _INK_CHOICE.match(line)
            if m:
                text = m.group("text").strip()
                if should_skip(text):
                    entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                             status=STATUS_SKIPPED, meta={**meta, "kind": "noise"}))
                else:
                    entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=text,
                                             meta={**meta, "kind": "choice",
                                                   "marker": m.group("marker")}))
                continue
            entries.append(TextEntry(file_id=fid, key_path=f"text/{i}",
                                     original=line.rstrip("\r"),
                                     meta={**meta, "kind": "text"}))
            continue
        # Yarn
        link = _YARN_LINK.match(stripped)
        if link:
            label = link.group("label").strip()
            if label and not should_skip(label):
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=label,
                                         meta={**meta, "kind": "link",
                                               "prefix": stripped[:stripped.index(label)]}))
            else:
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                         status=STATUS_SKIPPED, meta={**meta, "kind": "flow"}))
            continue
        m = _YARN_KV.match(line)
        if m and m.group("value").strip():
            value = m.group("value").strip()
            if should_skip(value):
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                         status=STATUS_SKIPPED, meta={**meta, "kind": "noise"}))
            else:
                entries.append(TextEntry(
                    file_id=fid, key_path=f"line/{i}", original=value,
                    meta={**meta, "kind": "kv", "prefix": m.group("key") + ":"}))
            continue
        entries.append(TextEntry(file_id=fid, key_path=f"text/{i}",
                                 original=line.rstrip("\r"),
                                 meta={**meta, "kind": "text"}))
    return entries


def apply_ink_yarn(entries: list[TextEntry]) -> str:
    """按行号重建；text/choice/kv/link 行 rfind 替换文本段，其余原样。"""
    by_line: dict[int, str] = {}
    for e in entries:
        kind = e.meta.get("kind")
        line_no = e.meta["line_no"]
        if kind in ("blank", "flow", "noise"):
            by_line[line_no] = e.meta["raw"]
        elif e.status == STATUS_SKIPPED or not e.translation:
            by_line[line_no] = e.meta["raw"]
        else:
            raw = e.meta["raw"]
            idx = raw.rfind(e.original)
            by_line[line_no] = (
                raw[:idx] + e.translation + raw[idx + len(e.original):]
                if idx >= 0 else raw)
    return "\n".join(by_line[i] for i in sorted(by_line))
