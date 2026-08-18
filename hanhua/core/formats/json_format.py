from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from hanhua.core.formats import read_text
from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.placeholders import (
    is_key_style_identifier,
    looks_like_key_field,
    should_skip,
)


TypedPath = tuple[str | int, ...]


@dataclass(frozen=True)
class _StringSpan:
    start: int
    end: int
    value: str


@dataclass(frozen=True)
class _Document:
    data: Any
    value_spans: dict[TypedPath, _StringSpan]


@dataclass(frozen=True)
class _Pairs:
    items: list[tuple[str, Any]]


def _preserve_pairs(pairs: list[tuple[str, Any]]) -> _Pairs:
    return _Pairs(pairs)


def _normalize(node: Any) -> Any:
    if isinstance(node, _Pairs):
        result: dict[str, Any] = {}
        for key, value in node.items:
            if key in result:
                del result[key]
            result[key] = _normalize(value)
        return result
    if isinstance(node, list):
        return [_normalize(value) for value in node]
    return node


def _mask_jsonc(text: str) -> str:
    chars = list(text)
    state = "normal"
    quote_start = -1
    comment_start = -1
    i = 0
    while i < len(chars):
        char = chars[i]
        if state == "normal":
            if char == '"':
                state = "string"
                quote_start = i
            elif char == "/" and i + 1 < len(chars) and chars[i + 1] == "/":
                state = "line_comment"
                chars[i] = chars[i + 1] = " "
                i += 1
            elif char == "/" and i + 1 < len(chars) and chars[i + 1] == "*":
                state = "block_comment"
                comment_start = i
                chars[i] = chars[i + 1] = " "
                i += 1
        elif state == "string":
            if char == "\\":
                state = "escape"
            elif char == '"':
                state = "normal"
        elif state == "escape":
            state = "string"
        elif state == "line_comment":
            if char in "\r\n":
                state = "normal"
            else:
                chars[i] = " "
        elif state == "block_comment":
            if char == "*" and i + 1 < len(chars) and chars[i + 1] == "/":
                chars[i] = chars[i + 1] = " "
                i += 1
                state = "normal"
            elif char not in "\r\n":
                chars[i] = " "
        i += 1

    if state in {"string", "escape"}:
        raise JSONDecodeError("Unterminated string", text, quote_start)
    if state == "block_comment":
        raise JSONDecodeError("Unterminated block comment", text, comment_start)

    masked = "".join(chars)
    chars = list(masked)
    state = "normal"
    i = 0
    while i < len(chars):
        char = chars[i]
        if state == "normal":
            if char == '"':
                state = "string"
            elif char == ",":
                lookahead = i + 1
                while lookahead < len(chars) and chars[lookahead].isspace():
                    lookahead += 1
                if lookahead < len(chars) and chars[lookahead] in "}]":
                    chars[i] = " "
        elif state == "string":
            if char == "\\":
                state = "escape"
            elif char == '"':
                state = "normal"
        else:
            state = "string"
        i += 1
    return "".join(chars)


def _load_data(text: str) -> tuple[Any, str]:
    extra_bom = text.find("\ufeff", 1 if text.startswith("\ufeff") else 0)
    if extra_bom != -1:
        raise JSONDecodeError("U+FEFF is only allowed at document start", text, extra_bom)
    parse_text = " " + text[1:] if text.startswith("\ufeff") else text
    # F56\uff08Rendezvous \u5b9e\u8bc1\uff09\uff1a\u7a7a/\u7eaf\u7a7a\u767d JSON \u6587\u4ef6\uff08steam_settings \u7834\u89e3
    # \u914d\u7f6e\u7684\u7a7a achievements.json\uff09\u2014\u2014json.loads('') \u629b "Expecting value"
    # \u5bfc\u81f4\u6574\u573a\u626b\u63cf\u5d29\u6e83\u3002\u7a7a\u6587\u6863 \u2192 \u7a7a\u7ed3\u679c\uff08\u4e0d\u629b\u2014\u2014\u626b\u63cf\u5bb9\u9519\uff09\u3002
    if not parse_text.strip():
        return {}, ""
    try:
        data = json.loads(parse_text, object_pairs_hook=_preserve_pairs)
        return data, parse_text
    except JSONDecodeError:
        masked = _mask_jsonc(parse_text)
        data = json.loads(masked, object_pairs_hook=_preserve_pairs)
        return data, masked


def _collect_value_tokens(source: str, parse_text: str) -> list[_StringSpan]:
    spans: list[_StringSpan] = []
    i = 0
    while i < len(parse_text):
        if parse_text[i] != '"':
            i += 1
            continue
        start = i
        i += 1
        while i < len(parse_text):
            if parse_text[i] == "\\":
                i += 2
            elif parse_text[i] == '"':
                i += 1
                break
            else:
                i += 1
        else:
            raise JSONDecodeError("Unterminated string", source, start)

        end = i
        lookahead = end
        while lookahead < len(parse_text) and parse_text[lookahead].isspace():
            lookahead += 1
        if lookahead < len(parse_text) and parse_text[lookahead] == ":":
            continue
        value = json.loads(source[start:end])
        spans.append(_StringSpan(start, end, value))
    return spans


def _remove_path_subtree(
    value_spans: dict[TypedPath, _StringSpan], prefix: TypedPath
) -> None:
    for path in list(value_spans):
        if path[: len(prefix)] == prefix:
            del value_spans[path]


def _pair_value_spans(
    node: Any,
    spans: list[_StringSpan],
    value_spans: dict[TypedPath, _StringSpan],
    path: TypedPath = (),
    position: int = 0,
) -> int:
    if isinstance(node, _Pairs):
        seen: set[str] = set()
        for key, value in node.items:
            child_path = path + (key,)
            if key in seen:
                _remove_path_subtree(value_spans, child_path)
            seen.add(key)
            position = _pair_value_spans(
                value, spans, value_spans, child_path, position
            )
    elif isinstance(node, list):
        for index, value in enumerate(node):
            position = _pair_value_spans(
                value, spans, value_spans, path + (index,), position
            )
    elif isinstance(node, str):
        if position >= len(spans) or spans[position].value != node:
            raise ValueError("JSON string value/span mismatch")
        value_spans[path] = spans[position]
        position += 1
    return position


def _load_document(text: str) -> _Document:
    occurrences, parse_text = _load_data(text)
    spans = _collect_value_tokens(text, parse_text)
    value_spans: dict[TypedPath, _StringSpan] = {}
    consumed = _pair_value_spans(occurrences, spans, value_spans)
    if consumed != len(spans):
        raise ValueError("JSON string value/span count mismatch")
    data = _normalize(occurrences)
    if any(_value_at(data, path) != span.value for path, span in value_spans.items()):
        raise ValueError("JSON effective value/span mismatch")
    return _Document(data, value_spans)


def _value_at(data: Any, path: TypedPath) -> Any:
    node = data
    try:
        for segment in path:
            node = node[segment]
    except (KeyError, IndexError, TypeError):
        return _MISSING
    return node


_MISSING = object()


def _escape_segment(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _unescape_segment(segment: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(segment):
        if segment[i] != "~":
            result.append(segment[i])
            i += 1
            continue
        if i + 1 >= len(segment) or segment[i + 1] not in "01":
            raise ValueError(f"invalid RFC 6901 segment: {segment!r}")
        result.append("~" if segment[i + 1] == "0" else "/")
        i += 2
    return "".join(result)


def _encode_path(path: TypedPath) -> str:
    return "/".join(
        str(segment) if isinstance(segment, int) else _escape_segment(segment)
        for segment in path
    )


def _resolve_path(data: Any, key_path: str) -> TypedPath:
    if key_path == "" and not isinstance(data, (dict, list)):
        return ()
    node = data
    typed: list[str | int] = []
    for segment in key_path.split("/"):
        if isinstance(node, list):
            if not segment.isascii() or not segment.isdecimal():
                raise ValueError(f"invalid JSON array index: {segment!r}")
            index = int(segment)
            node = node[index]
            typed.append(index)
        elif isinstance(node, dict):
            key = _unescape_segment(segment)
            node = node[key]
            typed.append(key)
        else:
            raise ValueError(f"JSON path traverses a scalar: {key_path!r}")
    return tuple(typed)


def extract_json(path: str | Path, file_id: str | None = None) -> list[TextEntry]:
    p = Path(path)
    return extract_json_text(read_text(p), file_id or p.name)


def extract_json_text(text: str, file_id: str | None = None) -> list[TextEntry]:
    document = _load_document(text)
    out = [
        TextEntry(
            file_id=file_id or "json",
            key_path=_encode_path(path),
            original=span.value,
        )
        for path, span in document.value_spans.items()
    ]
    for entry, path in zip(out, document.value_spans, strict=True):
        if ((path and any(isinstance(seg, str) and looks_like_key_field(seg)
                          for seg in path))
                or should_skip(entry.original)):
            # 键字段值或结构值跳过：Addressables catalog 的 m_AssemblyName 值
            # （.NET 程序集全名）、m_InternalId（URL）、m_Address（Assets 路径）、
            # m_InternalIds/N（数组父段是键字段，叶子是数字索引）都是真实漏网案例
            entry.status = STATUS_SKIPPED
    return out


def detect_indent(text: str) -> int | str | None:
    for line in text.splitlines():
        if line.startswith("\t"):
            return "\t"
        stripped = line.lstrip(" ")
        if line != stripped:
            return len(line) - len(stripped)
    return None


def apply_json(
    entries: list[TextEntry], source_text: str, ensure_ascii: bool = False
) -> str:
    document = _load_document(source_text)
    translations: dict[TypedPath, str] = {}
    for entry in entries:
        if not entry.translation:
            continue
        path = _resolve_path(document.data, entry.key_path)
        leaf = path[-1] if path else None
        if is_key_style_identifier(entry.original) or (
            isinstance(leaf, str) and looks_like_key_field(leaf)
        ):
            continue
        span = document.value_spans.get(path)
        # strip 容差（Rendezvous 实证 2026-08-17）：ink 对话行提取时
        # original 经 strip（'...Tyrell! ' 尾空格被去），写回校验严格
        # 相等失败——首尾空白是格式噪音，strip 后相等即匹配
        if (span is None
                or (span.value != entry.original
                    and span.value.strip() != entry.original.strip())):
            raise ValueError(
                f"JSON translation target does not match source: {entry.key_path!r}"
            )
        translations[path] = entry.translation

    if not translations:
        return source_text

    replacements = [
        (
            document.value_spans[path].start,
            document.value_spans[path].end,
            json.dumps(translation, ensure_ascii=ensure_ascii),
        )
        for path, translation in translations.items()
    ]
    result = source_text
    for start, end, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result
