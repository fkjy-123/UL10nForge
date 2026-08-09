"""字幕文件提取与写回：SRT / VTT / ASS / SSA / LRC。

只提取可见对白文本；时间码、序号、头部元数据、样式事件原样保留。
写回按行号重建 + rfind 替换文本段（与 txt 同构），样式标签（<b>、
{\\i1} 等）由 placeholders 保护，模型不可改动。
"""
from __future__ import annotations
import re
from pathlib import Path

from hanhua.core.formats import read_text
from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.placeholders import should_skip

# SRT 时间码行：00:00:01,000 --> 00:00:03,500
_SRT_TS = re.compile(r"^\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}")
# VTT 时间码行（可带 cue settings）
_VTT_TS = re.compile(
    r"^(?:\d{2}:)?\d{2}:\d{2}\.\d{1,3}\s*-->\s*(?:\d{2}:)?\d{2}:\d{2}\.\d{1,3}")
# VTT 头部/设置行
_VTT_HEADER = re.compile(r"^(?:WEBVTT|Kind:|Language:|Region:|Style:|STYLE|NOTE)")
# ASS 事件行：Dialogue: 层,起,止,样式,名,边缘,对齐,效果,,文本
_ASS_DIALOGUE = re.compile(
    r"^(?P<prefix>Dialogue:\s*\d+,\s*[\d:.,]+,\s*[\d:.,]+,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,)"
    r"(?P<text>.*)$")
# ASS 部分头：[Script Info] / [Events] 等
_ASS_SECTION = re.compile(r"^\[[^\]]+\]\s*$")
# LRC 行：[mm:ss.xx]文本（支持多时间戳 [t1][t2]文本）
_LRC_LINE = re.compile(r"^(\[[0-9:.\[\]]+\])(?P<text>.*)$")
# LRC/元数据行
_LRC_META = re.compile(r"^\[(?:ar|ti|al|by|offset|length|re|ve|au):.*\]$")
# 纯时间戳行
_ONLY_TS = re.compile(r"^\[[0-9:.]+\]$")
# 通用字幕噪音行：序号、URL、注释
_SUB_NOISE = re.compile(r"^\d+\s*$")


def extract_subtitle(path: str | Path, file_id: str | None = None,
                     kind: str | None = None) -> list[TextEntry]:
    p = Path(path)
    fid = file_id or p.name
    fmt = (kind or p.suffix.lstrip(".").lower()).split(".")[0]
    lines = read_text(p).splitlines()
    entries: list[TextEntry] = []
    for i, line in enumerate(lines):
        meta = {"line_no": i, "raw": line, "subtitle_kind": fmt}
        stripped = line.strip()
        if not stripped:
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "blank"}))
            continue
        is_ts = bool(_SRT_TS.match(stripped) or _VTT_TS.match(stripped))
        if is_ts:
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "timing"}))
            continue
        if fmt in ("srt", "vtt"):
            if fmt == "vtt" and (i < 6 or _VTT_HEADER.match(stripped)):
                # VTT 头部块（WEBVTT/Kind/Language/Style/NOTE）与 cue 标识行
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                         status=STATUS_SKIPPED, meta={**meta, "kind": "header"}))
                continue
            if _SUB_NOISE.match(stripped) or stripped.startswith(("http://", "https://")):
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                         status=STATUS_SKIPPED, meta={**meta, "kind": "noise"}))
                continue
            # VTT cue 标识行：下一行是时间码 → 是标识符不是对白
            if fmt == "vtt" and i + 1 < len(lines) and _VTT_TS.match(lines[i + 1].strip()):
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                         status=STATUS_SKIPPED, meta={**meta, "kind": "cue_id"}))
                continue
            entries.append(TextEntry(file_id=fid, key_path=f"text/{i}",
                                     original=line.rstrip("\r"),
                                     meta={**meta, "kind": "text"}))
            continue
        if fmt in ("ass", "ssa"):
            if _ASS_SECTION.match(stripped) or not _ASS_DIALOGUE.match(line):
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                         status=STATUS_SKIPPED, meta={**meta, "kind": "meta"}))
                continue
            m = _ASS_DIALOGUE.match(line)
            text = m.group("text").rstrip()
            if should_skip(text):
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                         status=STATUS_SKIPPED, meta={**meta, "kind": "noise"}))
            else:
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=text,
                                         meta={**meta, "kind": "dialogue",
                                               "prefix": m.group("prefix")}))
            continue
        if fmt == "lrc":
            if _LRC_META.match(stripped) or _ONLY_TS.match(stripped):
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                         status=STATUS_SKIPPED, meta={**meta, "kind": "meta"}))
                continue
            m = _LRC_LINE.match(line)
            if m and m.group("text").strip():
                text = m.group("text").rstrip()
                if should_skip(text):
                    entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                             status=STATUS_SKIPPED, meta={**meta, "kind": "noise"}))
                else:
                    entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=text,
                                             meta={**meta, "kind": "lrc_text",
                                                   "prefix": m.group(1)}))
            else:
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                         status=STATUS_SKIPPED, meta={**meta, "kind": "noise"}))
            continue
        # 未知子类型：按普通文本行
        entries.append(TextEntry(file_id=fid, key_path=f"text/{i}",
                                 original=line.rstrip("\r"),
                                 meta={**meta, "kind": "text"}))
    return entries


def apply_subtitle(entries: list[TextEntry]) -> str:
    """按行号重建；text/dialogue/lrc_text 行 rfind 替换文本段，其余原样。"""
    by_line: dict[int, str] = {}
    for e in entries:
        kind = e.meta.get("kind")
        line_no = e.meta["line_no"]
        if kind in ("blank", "timing", "header", "cue_id", "noise", "meta"):
            by_line[line_no] = e.meta["raw"]
        elif e.status == STATUS_SKIPPED or not e.translation:
            by_line[line_no] = e.meta["raw"]
        else:
            raw = e.meta["raw"]
            if kind == "dialogue":
                prefix = e.meta.get("prefix")
                if prefix and raw.startswith(prefix):
                    tail = raw[len(prefix):]
                    idx = tail.rfind(e.original)
                    by_line[line_no] = raw if idx < 0 else (
                        raw[:len(prefix) + idx] + e.translation
                        + raw[len(prefix) + idx + len(e.original):])
                    continue
            idx = raw.rfind(e.original)
            by_line[line_no] = (
                raw[:idx] + e.translation + raw[idx + len(e.original):]
                if idx >= 0 else raw)
    return "\n".join(by_line[i] for i in sorted(by_line))
