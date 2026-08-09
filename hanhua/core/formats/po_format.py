"""PO 本地化文件提取与写回（gettext 格式）。

提取 msgid / msgid_plural 为原文；写回时把译文写入对应的 msgstr /
msgstr[N] 槽位（msgid 永不改动——它是键）。支持：
- 多行引号拼接（"..." 续行）
- msgctxt 上下文
- 复数 msgid_plural / msgstr[0] / msgstr[1]
- 注释（# / #. / #: / #|）与模糊标记原样保留
"""
from __future__ import annotations
import re
from pathlib import Path

from hanhua.core.formats import read_text
from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.placeholders import should_skip

# 键行：msgctxt / msgid / msgid_plural / msgstr / msgstr[N]
_PO_KEY = re.compile(
    r'^(?P<key>msgctxt|msgid(?:_plural)?|msgstr(?:\[[0-9]+\])?) (?P<value>.*)$')
# 注释行
_PO_COMMENT = re.compile(r"^#")
# 续行引号
_PO_CONT = re.compile(r'^"(.*)"$', re.S)


def _parse_block(lines: list[str], start: int) -> tuple[dict[str, list[str]], int]:
    """解析一个 PO 条目块 → {key: [值片段]}，返回 (块, 下一行号)。"""
    block: dict[str, list[str]] = {}
    current_key: str | None = None
    i = start
    while i < len(lines):
        line = lines[i]
        m = _PO_KEY.match(line)
        if m:
            current_key = m.group("key")
            block.setdefault(current_key, []).append(m.group("value"))
            i += 1
            continue
        if line.startswith('"') and current_key is not None:
            block[current_key].append(line.rstrip())
            i += 1
            continue
        break
    return block, i


def _join_parts(parts: list[str]) -> str:
    """拼接多行引号片段并去引号。"""
    out = []
    for part in parts:
        m = _PO_CONT.match(part.strip())
        if m:
            out.append(m.group(1))
        else:
            out.append(part.strip())
    return "".join(out)


def _escape(text: str) -> str:
    """PO 单行 msgstr 转义（反斜杠与双引号与换行）。"""
    return (text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n"))


def extract_po(path: str | Path, file_id: str | None = None) -> list[TextEntry]:
    p = Path(path)
    fid = file_id or p.name
    lines = read_text(p).splitlines()
    entries: list[TextEntry] = []
    block_index = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        meta = {"line_no": i, "raw": line, "po_block": block_index}
        if not stripped or _PO_COMMENT.match(stripped):
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "comment"}))
            i += 1
            continue
        if _PO_KEY.match(line):
            block, next_i = _parse_block(lines, i)
            block_index += 1
            for e in _entries_from_block(fid, block, block_index - 1):
                entries.append(e)
            i = next_i
            continue
        entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                 status=STATUS_SKIPPED, meta={**meta, "kind": "other"}))
        i += 1
    return entries


def _entries_from_block(fid: str, block: dict[str, list[str]],
                        block_index: int) -> list[TextEntry]:
    """一个 PO 条目块 → 0~2 个条目（msgid 与 msgid_plural 各一）。"""
    context = _join_parts(block.get("msgctxt", []))
    out: list[TextEntry] = []
    base = {"kind": "po", "po_block": block_index, "msgctxt": context}
    msgid = _join_parts(block.get("msgid", []))
    plural = _join_parts(block.get("msgid_plural", []))
    if not msgid:
        # 无 msgid 的块（header/杂项）不产生条目
        return out
    if should_skip(msgid):
        return out
    if plural:
        out.append(TextEntry(file_id=fid, key_path=f"po/{block_index}/msgid",
                             original=msgid,
                             meta={**base, "slot": "msgstr", "has_plural": True}))
        if not should_skip(plural):
            out.append(TextEntry(file_id=fid, key_path=f"po/{block_index}/plural",
                                 original=plural,
                                 meta={**base, "slot": "msgstr[1]", "has_plural": True}))
    else:
        out.append(TextEntry(file_id=fid, key_path=f"po/{block_index}/msgid",
                             original=msgid, meta={**base, "slot": "msgstr"}))
    return out


def apply_po(entries: list[TextEntry], text: str) -> str:
    """重建 PO：按块号把译文写入 msgstr / msgstr[N] 槽位行，其余原样。"""
    by_block: dict[int, dict[str, str]] = {}
    for e in entries:
        if e.meta.get("kind") != "po":
            continue
        if e.status != STATUS_SKIPPED and e.translation:
            by_block.setdefault(e.meta["po_block"], {})[e.meta["slot"]] = e.translation
    lines = text.splitlines()
    out_lines = list(lines)
    block_index = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if _PO_KEY.match(line):
            block, next_i = _parse_block(lines, i)
            slot_values = by_block.get(block_index, {})
            if slot_values and block.get("msgid", []):
                applied: dict[str, str] = {}
                # 逐行替换：msgstr 行（及其 [N] 变体）在块内出现的首个位置
                keys = list(block.keys())
                # 先处理 msgstr[N]，再 msgstr（确保 msgstr 不覆盖 msgstr[0]）
                for key in sorted(keys, key=lambda k: (not k.startswith("msgstr["), k)):
                    if key.startswith("msgstr") and key not in applied:
                        slot = key if key != "msgstr" else "msgstr"
                        if key == "msgstr" and "msgstr[0]" in block:
                            slot = "msgstr[0]"
                        translation = slot_values.get(slot) or slot_values.get(key)
                        if translation is not None:
                            target_line = next(
                                (idx for idx in range(i, next_i)
                                 if _PO_KEY.match(lines[idx])
                                 and _PO_KEY.match(lines[idx]).group("key") == key),
                                None)
                            if target_line is not None:
                                out_lines[target_line] = (
                                    f"{key} \"{_escape(translation)}\"")
                                applied[key] = translation
            block_index += 1
            i = next_i
            continue
        i += 1
    return "\n".join(out_lines)
