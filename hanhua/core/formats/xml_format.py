from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from hanhua.core.models import TextEntry
from hanhua.core.formats import read_text

TRANSLATABLE_ATTRS = {"name", "title", "text", "tooltip", "label", "caption", "hint", "description"}
# 形如 menu_start / accept / quest_3 的值视为键而非显示文本，不翻译
_ID_LIKE = re.compile(r"^[a-z][a-zA-Z0-9_.\-]{1,40}$")


def _tag(el: ET.Element) -> str:
    return el.tag.split("}")[-1] if isinstance(el.tag, str) else str(el.tag)


def _xpath(el: ET.Element, parent_path: str = "") -> str:
    return f"{parent_path}/{_tag(el)}"


def extract_xml(path: str | Path, file_id: str | None = None) -> list[TextEntry]:
    p = Path(path)
    fid = file_id or p.name
    return extract_xml_text(read_text(p), fid)


def extract_xml_text(text: str, file_id: str | None = None) -> list[TextEntry]:
    """文本直取（zip 内层 / TextAsset / 伪装文件复用）。"""
    fid = file_id or "xml"
    root = ET.fromstring(text)
    entries: list[TextEntry] = []

    def walk(
        el: ET.Element,
        parent_path: str,
        depth: int,
        sibling_count: int = 1,
        sibling_index: int = 0,
    ):
        path = _xpath(el, parent_path)
        if depth >= 1 and (sibling_count > 1 or depth == 1):
            path = f"{path}[{sibling_index}]"
        for attr, val in el.attrib.items():
            v = val.strip()
            if attr.lower() in TRANSLATABLE_ATTRS and v and not _ID_LIKE.match(v):
                entries.append(TextEntry(file_id=fid, key_path=f"{path}/@{attr}", original=v))
        if el.text:
            t = el.text.strip()
            if t and not _ID_LIKE.match(t):
                # 文本节点的 key_path 即元素路径本身；属性路径以 @ 开头
                entries.append(TextEntry(file_id=fid, key_path=path, original=t))
        children = list(el)
        tag_counts = Counter(_tag(child) for child in children)
        seen: dict[str, int] = {}
        for child in children:
            tag = _tag(child)
            index = seen.get(tag, 0)
            seen[tag] = index + 1
            walk(child, path, depth + 1, tag_counts[tag], index)

    walk(root, "", 0)
    return entries


def _split_path(key_path: str) -> tuple[list[tuple[str, int | None]], str]:
    """'/root/dialogue[0]/text' → ([('root',None),('dialogue',0),('text',None)], 'text')；
    最后段 '@name' 表示属性替换（导航时跳过该段）。"""
    parts = key_path.lstrip("/").split("/")
    path: list[tuple[str, int | None]] = []
    for p in parts:
        idx = None
        name = p
        if p.endswith("]") and "[" in p:
            name, _, idx_s = p[:-1].partition("[")
            idx = int(idx_s)
        path.append((name, idx))
    return path, parts[-1]


class XmlRewriteUnsafeError(Exception):
    """XML 含 CDATA/DOCTYPE 等重序列化会丢失的结构（调查报告 F7）。

    ET.fromstring+ET.tostring 重序列化会丢 CDATA 块与 DOCTYPE 声明、
    规范化格式；此类文件拒绝整体重建，写回侧改为整文件跳过（零损坏）。
    """


# F7：检测重序列化不安全的 XML 结构（CDATA 块 / DOCTYPE 声明）
_CDATA_DOCTYPE = re.compile(r"<!\[CDATA\[|<!DOCTYPE", re.IGNORECASE)


def apply_xml(entries: list[TextEntry], source_text: str) -> str:
    """按 key_path 替换文本节点/属性，重新序列化（结构保留；格式化规范化为 2 空格缩进）。

    含 CDATA/DOCTYPE 时抛 XmlRewriteUnsafeError（拒绝重序列化），
    由调用方决定降级/警示。
    """
    if _CDATA_DOCTYPE.search(source_text):
        raise XmlRewriteUnsafeError(
            "XML 含 CDATA/DOCTYPE，ET 重序列化会丢失，拒绝重建")
    root = ET.fromstring(source_text)
    by_path = {e.key_path: e for e in entries if e.translation}
    if not by_path:
        return source_text
    for kp, e in by_path.items():
        path, last = _split_path(kp)
        el: ET.Element | None = root
        nav = path[1:-1] if last.startswith("@") else path[1:]   # 首段是根元素自身；属性段不导航
        for name, idx in nav:
            children = [c for c in el if _tag(c) == name]
            if idx is not None and idx < len(children):
                el = children[idx]
            elif len(children) == 1:
                el = children[0]
            else:
                el = None
                break
        if el is None:
            continue
        if last.startswith("@"):
            attr = last[1:]
            if attr in el.attrib:
                el.attrib[attr] = e.translation
        else:
            orig = el.text or ""
            stripped = orig.strip()
            if stripped:
                idx = orig.rfind(stripped)
                el.text = orig[:idx] + e.translation + orig[idx + len(stripped):]
    if "\n" in source_text:
        ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    head = source_text.lstrip()
    end = head.find("?>")
    if end > 0 and head.startswith("<?xml"):
        body = head[:end + 2] + "\n" + body
    if source_text.endswith("\n"):
        body += "\n"
    return body
