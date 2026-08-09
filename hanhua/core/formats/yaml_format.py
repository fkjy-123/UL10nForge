"""YAML 行级提取与写回（轻量子集，无第三方依赖）。

覆盖游戏本地化常用的 YAML 形态：注释/空行、缩进映射 `key: value`、
列表 `- item`、块标量 `key: |` / `key: >`。锚点/别名/标签/内联结构
（[a, b] / {a: b}）视为结构性跳过——它们不是显示文本。

写回与 txt 相同：按行号重建 + 在原始行内 rfind 替换值段，保留全部
格式与缩进；翻译失败/未翻译的行原样输出。
"""
from __future__ import annotations
import re
from pathlib import Path

from hanhua.core.formats import read_text
from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.placeholders import is_hard_structural, should_skip

# 映射行：缩进 + key + ':' + 值（值可为空 = 嵌套映射起点）
_YAML_KV = re.compile(
    r"^(?P<indent>[ \t]*)(?P<key>[^#\r\n]*?):(?P<sp>[ \t]*)(?P<value>.*)$")
_YAML_LIST = re.compile(
    r"^(?P<indent>[ \t]*)-(?P<sp>[ \t]+)(?P<value>.*)$")
# 块标量起始：key: | / key: >（可带折叠修饰符 +-数字）
_BLOCK_SCALAR = re.compile(r"^(?P<key>[^#\r\n]*?):[ \t]*[|>][+-]?[0-9]*[ \t]*(?:#.*)?$")
# 结构性行：文档标记/锚点/别名/标签/合并键
_STRUCTURAL = re.compile(
    r"^(?:---|\.\.\.|&[A-Za-z0-9_-]+|\*[A-Za-z0-9_-]+|"
    r"![A-Za-z0-9_./-]*\S*|<<:|<< |~)\s*$")
_SCALAR_LITERAL = re.compile(
    r"^[+-]?(?:0|[1-9][0-9_]*)(?:\.[0-9_]*)?(?:[eE][+-]?[0-9]+)?$")
_BOOL_LITERALS = frozenset({"true", "false", "null", "none", "yes", "no", "on", "off"})


def _strip_quote(value: str) -> str:
    """去掉单/双引号外壳；转义保持原样（写回按 rfind 原值替换）。"""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _is_structural_value(value: str) -> bool:
    """布尔/数字/空/内联结构/锚点等非显示值。"""
    stripped = value.strip()
    if not stripped or stripped[0] in "[{" or stripped == "~":
        return True
    if is_hard_structural(stripped):
        return True
    if _SCALAR_LITERAL.fullmatch(stripped):
        return True
    return stripped.casefold() in _BOOL_LITERALS


def extract_yaml(path: str | Path, file_id: str | None = None) -> list[TextEntry]:
    p = Path(path)
    return extract_yaml_text(read_text(p), file_id or p.name)


def extract_yaml_text(text: str, file_id: str | None = None) -> list[TextEntry]:
    """文本直取（TextAsset / zip 内层 / 伪装文件复用）。"""
    fid = file_id or "yaml"
    lines = text.splitlines()
    entries: list[TextEntry] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        meta = {"line_no": i, "raw": line}
        stripped = line.strip()
        if not stripped:
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "blank"}))
            i += 1
            continue
        if stripped.startswith("#"):
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "comment"}))
            i += 1
            continue
        if _STRUCTURAL.match(stripped):
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "structural"}))
            i += 1
            continue
        if _BLOCK_SCALAR.match(line):
            indent = len(line) - len(line.lstrip())
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "section"}))
            i = _collect_block_scalar(entries, fid, lines, i + 1, indent)
            continue
        m = _YAML_KV.match(line) or _YAML_LIST.match(line)
        if m and m.group("value").strip():
            value = m.group("value").strip()
            if _is_structural_value(value):
                entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                         status=STATUS_SKIPPED,
                                         meta={**meta, "kind": "kv_structural"}))
            else:
                original = _strip_quote(value)
                if should_skip(original):
                    entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                             status=STATUS_SKIPPED,
                                             meta={**meta, "kind": "kv_structural"}))
                else:
                    entries.append(TextEntry(
                        file_id=fid, key_path=f"line/{i}", original=original,
                        meta={**meta, "kind": "kv"}))
        elif m:
            # 空值 = 嵌套映射/序列起点 → 结构行
            entries.append(TextEntry(file_id=fid, key_path=f"line/{i}", original=line,
                                     status=STATUS_SKIPPED, meta={**meta, "kind": "section"}))
        else:
            entries.append(TextEntry(file_id=fid, key_path=f"plain/{i}",
                                     original=line.rstrip("\r"),
                                     meta={**meta, "kind": "plain"}))
        i += 1
    return entries


def looks_like_yaml_text(text: str) -> bool:
    """TextAsset 内嵌 YAML 判据：kv/list/块标量行占比高，且值多为非句子形态。

    对话脚本（"Speaker: Hello."）值常以标点结尾，占比高时判为行文本，
    交给 txt 的 kv 逻辑（保留说话人前缀）——YAML 提取会丢弃 key 部分。
    """
    _VALUE_SENTENCE = re.compile(r"[.!?:，。！？;；]$")
    _HAS_WORD = re.compile(r"[A-Za-z]{3,}")
    # 自然语言值：≥2 个空格分隔的单词（数据行的 "12:-1:none" 仅 1 个
    # 伪词，不命中；"Hello world" 命中）
    _TWO_WORDS = re.compile(r"[A-Za-z]{3,}[\w'.-]*\s+[A-Za-z]{3,}")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    matched = 0
    sentence_values = 0
    wordy_values = 0
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("#") or _STRUCTURAL.match(stripped):
            continue
        if _BLOCK_SCALAR.match(ln):
            return True
        m = _YAML_KV.match(ln) or _YAML_LIST.match(ln)
        if m:
            matched += 1
            value = m.group("value").strip()
            if value and _VALUE_SENTENCE.search(value):
                sentence_values += 1
            if _TWO_WORDS.search(value) or (
                    m.re is _YAML_KV and _HAS_WORD.search(m.group("key"))):
                wordy_values += 1
    if matched < 2:
        return False
    # 纯数字键值数据表（关卡/配置，"0:12:-1:none" 行实证）：key 与
    # value 均无 ≥3 字母单词 → 非 yaml 文本，避免按 yaml 重建破坏文件
    if wordy_values / matched < 0.3:
        return False
    return matched / len(lines) >= 0.7 and sentence_values / matched < 0.5


def _collect_block_scalar(entries: list[TextEntry], fid: str, lines: list[str],
                          start: int, parent_indent: int) -> int:
    """收集块标量内容行（缩进大于起始行的连续行）→ 单条多行条目；返回下一行号。"""
    body: list[str] = []
    body_lines: list[int] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= parent_indent:
            break
        body.append(line.rstrip("\r"))
        body_lines.append(i)
        i += 1
    if body:
        text = "\n".join(body)
        if not should_skip(text):
            entries.append(TextEntry(file_id=fid, key_path=f"block/{start}",
                                     original=text,
                                     meta={"kind": "block_scalar", "raw": text,
                                           "lines": body_lines, "line_no": start}))
    return i


def apply_yaml(entries: list[TextEntry]) -> str:
    """按行号重建；kv/plain/block 行 rfind 替换原值段，其余原样输出。"""
    by_line: dict[int, str] = {}
    for e in entries:
        kind = e.meta.get("kind")
        if kind in ("blank", "comment", "section", "structural", "kv_structural"):
            by_line[e.meta["line_no"]] = e.meta["raw"]
        elif kind == "block_scalar":
            translated_lines = e.translation.splitlines() \
                if e.status != STATUS_SKIPPED and e.translation else None
            for i, raw_line in enumerate(e.meta["raw"].splitlines()):
                if translated_lines is not None and i < len(translated_lines):
                    by_line[e.meta["lines"][i]] = translated_lines[i]
                else:
                    by_line[e.meta["lines"][i]] = raw_line
        elif e.status == STATUS_SKIPPED or not e.translation:
            by_line[e.meta["line_no"]] = e.meta["raw"]
        else:
            raw = e.meta["raw"]
            idx = raw.rfind(e.original)
            if idx >= 0:
                by_line[e.meta["line_no"]] = (
                    raw[:idx] + e.translation + raw[idx + len(e.original):])
            else:
                by_line[e.meta["line_no"]] = raw
    return "\n".join(by_line[i] for i in sorted(by_line))
