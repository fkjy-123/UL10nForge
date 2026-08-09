"""Conservative source-bound spans that may remain Latin in a CJK translation."""
from __future__ import annotations

import re
from collections.abc import Iterable

from hanhua.core.engine_strings import (CORE_MENU_SOURCE_TERMS,
                                        interaction_input_tokens,
                                        is_interaction_prompt)
from hanhua.core.placeholders import extract_placeholders

_RICH_TAG = re.compile(
    r"<(?:#[0-9A-Fa-f]{3,8}|/?[A-Za-z][^<>]*?)>")
_CONTROL_ESCAPE = re.compile(r"\\(?:r\\n|n|r|t)")
_RICH_CONTENT = re.compile(
    r"<(?P<tag>b|i|strong|em|color)(?:\s[^<>]*)?>"
    r"(?P<content>[^<>\r\n]+)</(?P=tag)>",
    re.I,
)
_LATIN_TOKEN = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_.-]*(?![A-Za-z0-9_])")
_QUOTED_KEY = re.compile(r"['\"]([A-Za-z])['\"]")
_BY_NAME = re.compile(
    r"(?i:\bby\b)\s+"
    r"([A-Z0-9][A-Za-z0-9'.-]*(?:\s+[A-Z0-9][A-Za-z0-9'.-]*){0,3})")
_CREDIT_LABEL = re.compile(
    r"(?i:\b(?:developer|voices?|models?|supporters?|author|patreon|thanks?)\b)")
_CREDIT_VALUE = re.compile(
    r"(?:[-:：]\s*|(?i:\bby\b)\s+|(?i:\bthanks?\s+to\b)\s+)"
    r"([A-Z0-9][A-Za-z0-9'.-]*"
    r"(?:\s+(?:and\s+)?[A-Z0-9][A-Za-z0-9'.-]*){0,4})")
_PAREN_CONTENT = re.compile(r"\(([A-Z0-9][A-Za-z0-9'.-]*(?:\s+[A-Z0-9][A-Za-z0-9'.-]*){0,3})\)")
_BRAND_RICH_TEXT = re.compile(
    r"(?:[A-Za-z]*[A-Z][A-Za-z0-9.-]*[A-Z0-9][A-Za-z0-9.-]*"
    r"(?:\s+[A-Z][A-Za-z0-9.-]*){0,3}|"
    r"[A-Z][a-z]+\s+Dialogue|[A-Z]{2,}(?:\s+[A-Z][A-Za-z0-9.-]*){0,3})$")
_TRUSTED_ACRONYMS = frozenset({
    "API", "CPU", "DLC", "FPS", "GPU", "HDR", "HP", "ID", "LMB",
    "MP", "NPC", "RAM", "RMB", "SFX", "UI", "UX", "VFX", "VR", "WASD", "XP",
})
_TRUSTED_UPPERCASE_BRANDS = frozenset({
    "AMD", "EPIC", "GOG", "INTEL", "NVIDIA", "OCULUS", "OPENAI",
    "PLAYSTATION", "STEAM", "XBOX",
    # 平台/硬件/发行渠道品牌：模型保留原文合理（真实失败样本 Playstation/Xbox）
    "ANDROID", "DISCORD", "GEFORCE", "IPHONE", "LINUX", "MAC", "NINTENDO",
    "RTX", "STEAMVR", "SWITCH", "TWITCH", "UNITY", "VIVE", "WINDOWS",
})


def _strip_tags(text: str) -> str:
    return _RICH_TAG.sub("", text)


def _is_brand_token(token: str) -> bool:
    """品牌词判定：全大写（STEAM/NVIDIA）或 TitleCase（Playstation/Xbox）。

    TitleCase 要求首字母大写且其余小写——小写普通词（steam=蒸汽、unity=团结、
    windows=窗户）不是品牌，不保护（An epic battle 的 epic 等）
    """
    if token in _TRUSTED_UPPERCASE_BRANDS:
        return True
    return (len(token) > 1 and token.isalpha()
            and token.upper() in _TRUSTED_UPPERCASE_BRANDS
            and token == token.capitalize())


def _credit_terms(source: str) -> set[str]:
    plain = _strip_tags(source)
    terms = {match.group(1).strip() for match in _BY_NAME.finditer(plain)}
    supporter_block = False
    for raw_line in plain.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        has_credit_label = _CREDIT_LABEL.search(line) is not None
        if has_credit_label:
            supporter_block = "supporter" in line.casefold()
            for match in _CREDIT_VALUE.finditer(line):
                # "A and B" 拆成独立人名（译文可能用中文连接词）
                terms.update(
                    part.strip() for part in
                    re.split(r"\s+and\s+", match.group(1).strip())
                    if part.strip())
            terms.update(
                match.group(1).strip() for match in _PAREN_CONTENT.finditer(line))
            continue
        if supporter_block and re.fullmatch(
                r"[A-Z0-9][A-Za-z0-9'.-]*(?:\s+[A-Z0-9][A-Za-z0-9'.-]*){0,3}",
                line):
            terms.add(line)
    return {term for term in terms if term}


# 知名服务/产品名短语：品牌载体整体剥离（"Youtube Music" 模型只修正大小写
# 回显 → 保留原文合理；music 单独是 UI 词典词必须翻译，须按短语剥离）
_SERVICE_PHRASES = (
    "youtube music", "google play", "apple music", "spotify",
    "amazon music", "app store", "play store",
)


def _service_phrases(source: str) -> set[str]:
    plain = _strip_tags(source)
    return {plain[m.start():m.end()]
            for phrase in _SERVICE_PHRASES
            for m in re.finditer(re.escape(phrase), plain, re.I)}


def _rich_brand_terms(source: str) -> set[str]:
    return {
        content
        for match in _RICH_CONTENT.finditer(source)
        if (content := match.group("content").strip())
        and not (any(char.isalpha() for char in content)
                 and content.upper() == content
                 and content not in _TRUSTED_UPPERCASE_BRANDS)
        and _BRAND_RICH_TEXT.fullmatch(content)
    }


def _source_acronyms(source: str) -> set[str]:
    terms = set(interaction_input_tokens(source))
    terms.update(match.group(1) for match in _QUOTED_KEY.finditer(source))
    for match in _LATIN_TOKEN.finditer(_strip_tags(source)):
        token = match.group(0)
        if (any(char.isdigit() for char in token)
                or token in _TRUSTED_ACRONYMS
                or _is_brand_token(token)):
            terms.add(token)
        elif (len(token) == 1 and token.isupper()
              and is_interaction_prompt(source)):
            terms.add(token)
    plain_source = _strip_tags(source).strip().casefold()
    return {
        term for term in terms
        if not (plain_source == term.casefold()
                and term.casefold() in CORE_MENU_SOURCE_TERMS)
    }


def _remove_source_bound_term(text: str, source: str, term: str) -> str:
    if not term or term not in source:
        return text
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])")
    source_count = len(pattern.findall(source))
    return pattern.sub("", text, count=source_count)


def _remove_exact_term(text: str, term: str) -> str:
    if not term:
        return text
    return re.sub(
        rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])",
        "", text,
    )


def semantic_target_text(
        source: str,
        translation: str,
        extra_terms: Iterable[str] = ()) -> str:
    """Remove only markup and exact source-bound terms from target semantics."""
    semantic = _CONTROL_ESCAPE.sub("", _RICH_TAG.sub("", translation))
    protected = (
        _source_acronyms(source)
        | _rich_brand_terms(source)
        | _credit_terms(source)
        | _service_phrases(source)
    )
    for placeholder in extract_placeholders(source):
        semantic = semantic.replace(placeholder, "", 1)
    for term in sorted(protected, key=len, reverse=True):
        semantic = _remove_source_bound_term(semantic, source, term)
    for term in sorted(
            {str(term).strip() for term in extra_terms if str(term).strip()},
            key=len, reverse=True):
        semantic = _remove_exact_term(semantic, term)
    return semantic


def protected_slot_parts(source: str) -> tuple[tuple[bool, str], ...]:
    """Split *source* into exact protected slots and translatable semantics.

    The boolean is true for a slot which must be copied byte-for-byte into the
    rebuilt translation.  Overlapping recognizers are deliberately merged so
    an HTML tag, which is also reported as a placeholder, is emitted once.
    """
    spans: list[tuple[int, int]] = []

    def add(start: int, end: int) -> None:
        if 0 <= start < end <= len(source):
            spans.append((start, end))

    for pattern in (_RICH_TAG, re.compile(r"\r\n|\r|\n"), _CONTROL_ESCAPE):
        for match in pattern.finditer(source):
            add(match.start(), match.end())

    search_from = 0
    for placeholder in extract_placeholders(source):
        start = source.find(placeholder, search_from)
        if start < 0:
            start = source.find(placeholder)
        if start >= 0:
            add(start, start + len(placeholder))
            search_from = start + len(placeholder)

    for term in sorted(_source_acronyms(source), key=len, reverse=True):
        pattern = re.compile(
            rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])")
        for match in pattern.finditer(source):
            add(match.start(), match.end())

    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    parts: list[tuple[bool, str]] = []
    cursor = 0
    for start, end in merged:
        if cursor < start:
            parts.append((False, source[cursor:start]))
        parts.append((True, source[start:end]))
        cursor = end
    if cursor < len(source):
        parts.append((False, source[cursor:]))
    return tuple(parts)
