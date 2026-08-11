"""译文在落库和字体语料前必须通过的确定性质量门。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Iterable, Literal

from hanhua.core.engine_strings import (PHYSICAL_KEY_NAMES_CASEFOLD,
                                        interaction_action_words,
                                        interaction_input_events,
                                        is_interaction_prompt)
from hanhua.core.models import TextEntry
from hanhua.core.placeholders import (DISPLAY_WORDS, FORMAT_TAG_PATTERN,
                                      SAFE_KEEPERS, _STRIP_RICH_TEXT,
                                      is_hipster_ipsum,
                                      validate_translation)
from hanhua.core.knowledge import (_UPPERCASE_ACTION_VERBS,
                                   _is_spaced_action,
                                   _is_uppercase_action)
from hanhua.core.protected_spans import semantic_target_text

_DISPLAY_WORDS_CASEFOLD = {word.casefold() for word in DISPLAY_WORDS}
# 行首星号 bullet 占位符（undertale_bullet 提取的固定串 "* "）：译文
# 新增 bullet 是模型对星号的规范化（"*SIGH*" → "* sigh *"、" *Added"
# → "* 加空格"），无结构风险——placeholder_mismatch 放行专用
_BULLET_PLACEHOLDER = re.compile(r"^\* $")


@dataclass(frozen=True)
class QualityResult:
    passed: bool
    confidence: Literal["high", "medium", "low"]
    reasons: tuple[str, ...]
    normalized_translation: str


_ENGLISH_WORD = re.compile(r"[A-Za-z]{3,}")
# 独立 ASCII 小写词：\b 按 unicode 词边界（á 等非 ASCII 字母算 \w）→
# 'Stefánsson' 的 ASCII 碎片 'nsson' 不是独立词（前邻 á），不会误判小写
_LOWER_ASCII_WORD = re.compile(r"\b[a-z]+\b")
# lorem ipsum 家族占位文本（游戏开发者填充的假拉丁文本，无真实语义）。
# 标记词：标准 lorem ipsum 及其错拼变体（zero-deaths 'Loem iipsum solar'）。
# 判定：原文含任一标记词 + 所有词都在家族表 → 模型回显是合理行为。
_LOREM_IPSUM_MARKERS = {
    "lorem", "loem", "ipsum", "iipsum", "dolor", "sit", "amet",
    "consectetur", "adipiscing", "labore", "dolore", "incididunt",
}
_LOREM_IPSUM_FAMILY = _LOREM_IPSUM_MARKERS | {
    "elit", "sed", "do", "eiusmod", "tempor", "magna", "aliqua", "ut",
    "enim", "ad", "minim", "veniam", "quis", "nostrud", "exercitation",
    "ullamco", "laboris", "nisi", "aliquip", "ex", "ea", "commodo",
    "consequat", "duis", "aute", "irure", "in", "reprehenderit",
    "voluptate", "velit", "esse", "cillum", "fugiat", "nulla", "pariatur",
    "excepteur", "sint", "occaecat", "cupidatat", "non", "proident",
    "sunt", "culpa", "qui", "officia", "deserunt", "mollit", "anim",
    "id", "est", "laborum",
    # zero-deaths 特有错拼变体
    "solar", "em", "demit", "solo", "demmy", "sorenson",
}
def is_lorem_ipsum_placeholder(text: str) -> bool:
    words = [w.casefold() for w in _ENGLISH_WORD.findall(
        SAFE_KEEPERS.sub(" ", text))]
    if not words or not any(w in _LOREM_IPSUM_MARKERS for w in words):
        if is_hipster_ipsum(text):
            return True
        return False
    if all(w in _LOREM_IPSUM_FAMILY for w in words):
        return True
    # 开发占位混合串："The achievement's description goes here ipsum dolor
    # lorem sit amet..."（说明性前缀 + lorem 词，Incremental RTS 真实样本）
    # → 开发者填充文本，无真实语义，模型回显合理
    return bool(re.search(r"\bgoes? here\b", text, re.I)) and len(words) <= 25


def _max_case_run(text: str) -> int:
    """最大连续同大小写段长（'DeAD' → 1、'Continue' → 7）。"""
    run = best = 0
    prev: str | None = None
    for ch in text:
        if not ch.isalpha():
            run = 0
            prev = None
            continue
        cur = "upper" if ch.isupper() else "lower"
        if cur == prev:
            run += 1
        else:
            run = 1
            prev = cur
        best = max(best, run)
    return best


def _artistic_case_echo(original: str, normalized: str) -> bool:
    """艺术化混排字回显（'DeAD' → 'deAD'，deadbeat 实证）：原文是
    交替大小写的艺术写法（段 ≤2）、译文是其大小写噪声变体（casefold
    相同）→ 回显是正确行为（把艺术写法当普通词翻译成'死亡'是错误）。
    多行逐行对齐检查（'DeAD\\nbEAt' 每行 ≤8 才豁免，0.25.0 修复；
    任一行是普通词如 'Continue' 则整体不豁免）。
    'dead'/'DEAD' 规范形态段长 4 > 2 不豁免，UI 词典词检查仍生效；
    'Continue' TitleCase 段长 7 不豁免，仍判该译未译。"""
    orig_lines = original.splitlines() or [original]
    norm_lines = normalized.splitlines() or [normalized]
    if len(orig_lines) != len(norm_lines):
        # 行结构不一致 → 逐行不可对齐，回退整条判断（行数差即整条结构已变）
        if len(original) > 8 or len(normalized) > 8:
            return False
        orig_lines, norm_lines = [original], [normalized]
    for o, n in zip(orig_lines, norm_lines):
        if len(o) > 8 or len(n) > 8:
            return False
        if o.casefold() != n.casefold():
            return False
        if not (_max_case_run(o) <= 2
                and any(c.isupper() for c in o)
                and any(c.islower() for c in o)):
            return False
    return True


def _ui_check_words(words: list[str]) -> list[str]:
    """专名回显的 UI 词检查词集：多词时跳过末位词（版本后缀形态）。

    'UCLA Gold' 的 Gold 是版本后缀（UCLA Gold 是 Baldis 的版本彩蛋名），
    回显保留合理——Gold 在 UI 词典（金币类 UI 词）曾使专名回显豁免失败
    （baldis 实证）。单词（'SFX'/'Continue'）仍全查，真漏翻照常拦截。
    """
    if len(words) <= 1:
        return words
    return words[:-1]


def is_camel_tech_abbreviation(word: str) -> bool:
    """驼峰技术缩写（VSync/MonoBehaviour/YouTube）：首大写 + 内部混合大小写。

    界面标准术语，保留原文合理（vincent 'VSync: OFF' → 'VSync：关闭'）；形态
    要求首大写 + 内部混合大小写——全大写 SETTINGS/TitleCase Save 不算。
    """
    return (len(word) > 1 and word[0].isupper()
            and any(char.islower() for char in word[1:])
            and any(char.isupper() for char in word[1:]))


def has_independent_lower_word(text: str) -> bool:
    """原文是否存在独立 ASCII 小写词（'iipsum' 是、'Stefánsson' 的 nsson 不是）。

    rich text 标签参数（<color=red> 的 red、<size=50> 的 size）不是语义词——
    NULL 回显曾因 color=red 的 red 被当小写词 → 专名回显豁免失败
    （baldis 实证：'<color=red>NULL NULL…' 的 NULL 是游戏内实体名，保留
    合理）。剥标签后再检查。
    属格尾巴（Playtime's 的 s、don't 的 t）不是独立小写词——'Square Button:
    Jump During Playtime's Jumprope Minigame' 的 s 曾误判小写词 → 译文
    已含中文仍被 untranslated_text 拒（baldis 实证 [6]）。单字母 + 前邻
    撇号 → 撇号缩写的字母碎片，跳过。
    花括号占位符紧邻的单字母（'v{0}' 版本号模板的 v、'{0}' 后接单位字母）
    是格式串载体不是普通词——deepest-sword 实证：版本号模板 'v{0}' 回显
    是正确行为，v 被当独立小写词 → proper_name_echo 豁免失效 →
    target_script_mismatch 恒败。
    """
    cleaned = _STRIP_RICH_TEXT.sub(" ", SAFE_KEEPERS.sub(" ", text))
    for match in _LOWER_ASCII_WORD.finditer(cleaned):
        if (len(match.group(0)) == 1 and match.start() > 0
                and cleaned[match.start() - 1] == "'"):
            continue
        if (len(match.group(0)) == 1
                and ((match.start() > 0
                      and cleaned[match.start() - 1] in "{}")
                     or (match.end() < len(cleaned)
                         and cleaned[match.end()] in "{}"))):
            continue
        return True
    return False
# \u8bd1\u6587\u5f15\u53f7\u5185\u4e13\u540d\u77ed\u8bed\uff08\u6a21\u578b\u7528\u5f15\u53f7\u5305\u88f9\u4e13\u540d\uff1a\u6309\u94ae "Jump During Playtime" \u7684
# \u5f3a\u8c03\u6807\u8bb0\uff09\u2014\u2014\u5f15\u53f7\u5185\u5168 TitleCase \u4e14\u6bcf\u4e2a\u8bcd\u90fd\u5728\u539f\u6587\u51fa\u73b0 \u2192 \u4e13\u540d\u77ed\u8bed\uff0c
# \u52a8\u4f5c\u8bcd/\u82f1\u6587\u6b8b\u7559\u68c0\u67e5\u8c41\u514d\uff08baldis \u5b9e\u8bc1\uff1a'Square Button: Jump During
# Playtime's Jumprope Minigame' \u7684 Jump \u662f\u5c0f\u6e38\u620f\u540d\uff0c\u4e0d\u662f\u52a8\u4f5c\u52a8\u8bcd\uff09\u3002
# \u8981\u6c42\u8bcd\u5728\u539f\u6587\u51fa\u73b0\u9632\u8bef\u8bd1\u653e\u884c\uff08'Jump Along' \u7684 Along \u4e0d\u5728\u539f\u6587 \u2192 \u4e0d\u8c41\u514d\uff09\u3002
_QUOTED_SPAN = re.compile(
    r"[\"\u201c\u201d\u00ab\u00bb\u300c\u300d\u300e\u300f]([^\"\u201c\u201d\u00ab\u00bb\u300c\u300d\u300e\u300f]{1,80})[\"\u201c\u201d\u00ab\u00bb\u300c\u300d\u300e\u300f]")


def _complete_tag_pairs(tags: list[str]) -> bool:
    """缺失标签是否全是完整标签对（<x> 与 </x> 同名成对）。

    模型整体省略彩色强调标签（<color=green>Paused</color> 整对变中文
    引号包裹，baldis 实证 1.8B 稳定行为）→ 样式整对损失、无崩溃风险；
    单个标签缺失（留 <color=red> 丢 </color>）会破坏显示 → 仍需
    self_heal/失败暴露。数据占位符（{0}/{name}）不是 < 开头 → False。
    """
    if not tags or any(not tag.startswith("<") for tag in tags):
        return False
    open_names = [
        tag[1:].split(">")[0].split("=")[0].casefold()
        for tag in tags if not tag.startswith("</")]
    close_names = [
        tag[2:].split(">")[0].casefold()
        for tag in tags if tag.startswith("</")]
    return bool(open_names) and Counter(open_names) == Counter(close_names)


def quoted_proper_terms(translation: str, original: str) -> set[str]:
    """\u8bd1\u6587\u5f15\u53f7\u5185\u5168 TitleCase \u4e13\u540d\u77ed\u8bed\uff08\u6bcf\u4e2a\u8bcd\u90fd\u5728\u539f\u6587\u51fa\u73b0\uff09\u7684\u8bcd\u96c6\u3002

    \u5f15\u53f7\u5185\u5bb9\u542b\u5c0f\u5199\u666e\u901a\u8bcd\uff08\u6309\u94ae "play"\uff09\u2192 \u7a7a\u96c6\uff08\u4e0d\u8c41\u514d\uff09\uff1b
    \u8bcd\u4e0d\u5728\u539f\u6587\uff08'Jump Along' \u8bef\u8bd1\u4e13\u540d\uff09\u2192 \u7a7a\u96c6\uff08\u9632\u8bef\u8bd1\u653e\u884c\uff09\u3002
    \u8c03\u7528\u65b9\u8d1f\u8d23\u91cd\u97f3\u5f52\u4e00\u5316\uff08\u5e26\u91cd\u97f3\u4e13\u540d\u62c6\u788e\u540e\u9996\u5b57\u6bcd\u5224\u5b9a\u5931\u771f\uff09\u3002
    """
    original_terms = {word.casefold()
                      for word in _ENGLISH_WORD.findall(original)}
    quoted: set[str] = set()
    for match in _QUOTED_SPAN.finditer(translation):
        words = _ENGLISH_WORD.findall(match.group(1))
        if not words:
            continue
        title_case = all(word[0].isupper() for word in words)
        no_ui_words = all(word.casefold() not in _DISPLAY_WORDS_CASEFOLD
                          for word in words)
        if (title_case or no_ui_words) and all(
                word.casefold() in original_terms for word in words):
            quoted.update(word.casefold() for word in words)
    return quoted


_CJK = re.compile(
    r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002FA1F]")


def is_chinese_source(text: str) -> bool:
    """\u4e2d\u6587\u6e90\u5224\u5b9a\uff1aCJK \u2265 2 \u4e2a\u4e14\u5360\u5b57\u6bcd \u2265 50%\uff08deadbeat 0.25.0 \u6536\u7d27\uff09\u3002

    \u6e38\u620f\u81ea\u5e26\u4e2d\u6587\u8bed\u8a00\u5305\uff08Language/CH/*.subs\uff09\u539f\u6587\u5373\u4e2d\u6587 \u2192 \u76f4\u63a5\u653e\u884c\u3002
    \u4f46\u539f\u6587\u542b\u5355\u4e2a\u65e5\u6587\u6c49\u5b57\uff08\u6b4c\u8bcd '\u6226\u4e89'\uff09+ \u5927\u91cf\u82f1\u6587\u65f6\u6574\u6761\u88ab\u8bef\u5224\u4e2d\u6587\u6e90
    \u653e\u884c\u662f\u91cd\u5927 bug\uff08\u5b9e\u8bc1\uff1a1719 \u5b57\u7b26\u82f1\u6587\u539f\u6837\u653e\u884c\uff09\u2014\u2014\u6536\u7d27\u4e3a CJK \u2265 2
    \u4e14 CJK \u5360\u5b57\u6bcd\u5b57\u7b26 \u2265 50%\uff0c\u82f1\u6587\u4e3a\u4e3b\u7684\u6b4c\u8bcd\u884c\u4e0d\u518d\u8bef\u653e\u884c\u3002
    \u97e9\u6587\u539f\u6587\uff08\u65e0\u5047\u540d CJK\uff09\u5360\u6bd4\u8db3\u591f\u65f6\u540c\u6837\u653e\u884c\uff1b\u65e5\u6587\u539f\u6587\uff08\u542b\u5047\u540d\uff09\u7531
    _is_multilingual_source \u515c\u5e95\u4e0d\u8d70\u6b64\u8def\u5f84\u3002"""
    cjk = len(_CJK.findall(text))
    if cjk < 2:
        return False
    letters = len(re.findall(r"[A-Za-z\u3400-\u9fff\uf900-\ufaff]",
                             text))
    if letters == 0:
        return True
    return cjk * 2 >= letters
# 解释式垃圾输出：模型把「翻译不了」的词当成提问，输出解释段落而非译文
# （containment 实证：Mierda → '该文本看起来像是随机组合的文字，没有
# 明确的含义。以下是可能的解释：…'；CreditsVolume (1) Profile →
# '参考以下翻译："Volume"可译为"音量"'）。两类：①「译文：」输出包装
# 前缀——正常译文不会以此开头，任何长度都判；②解释特征句式——正常
# 译文不会出现精确短语（「以下是重要信息」不在模式内），但需 ≥20
# 字符防「没有明确的含义」式短句误伤（原文可能是 "has no clear
# meaning" 的描述性文本）
_EXPLANATORY_PREFIX = re.compile(
    r"^(?:translation|translated text|译文|翻译)\s*[:：]", re.I)
_EXPLANATORY_PATTERN = re.compile(
    r"以下是(?:可能的)?(?:解释|翻译)[:：]?"
    r"|参考以下翻译[:：]?"
    r"|该文本看起来像是|这个文本看起来像是|看起来像是随机"
    r"|没有明确的含义", re.I)


def _has_illegal_controls(value: str) -> bool:
    return any((ord(char) < 0x20 and char not in "\t\n\r")
               or 0x7F <= ord(char) <= 0x9F for char in value)


def _newline_events(value: str) -> tuple[str, ...]:
    names = {r"\n": "literal", "\r\n": "crlf", "\r": "cr", "\n": "lf"}
    return tuple(names[match.group(0)]
                 for match in re.finditer(r"\\n|\r\n|\r|\n", value))


def _line_content_topology(value: str) -> tuple[bool, ...]:
    return tuple(bool(part.strip())
                 for part in re.split(r"\\n|\r\n|\r|\n", value))


def _blank_line_compression(original: str, normalized: str) -> bool:
    """译文换行结构是否等于「原文删除 ≤4 个空行」：
    模型压缩连续空行（\n\n\n→\n\n）是稳定行为，中文排版无视觉差异
    （mimic-search 两处压缩累计 3、interdream 1）。只允许删除空行
    （strip 后为空的行），不允许删除/新增/移位内容行或空行位置。
    """
    source = _line_content_topology(original)
    target = _line_content_topology(normalized)
    if len(target) > len(source) or source == target:
        return False
    skipped = 0
    j = 0
    for line in source:
        if j < len(target) and target[j] == line:
            j += 1
        elif line is False:
            skipped += 1
            if skipped > 4:
                return False
        else:
            return False
    return j == len(target) and skipped > 0


def _normalize_translation(original: str, translation: str) -> str:
    """Trim model wrappers while restoring source boundary line breaks."""
    core = re.sub(r"[ \t]+(?=\r?$)", "", translation.strip(), flags=re.M)
    leading = re.match(r"^(?:\r\n|\r|\n)*", original).group(0)
    trailing = re.search(r"(?:\r\n|\r|\n)*$", original).group(0)
    return leading + core + trailing


def _input_token_events(value: str, source_tokens: tuple[str, ...]) -> tuple[str, ...]:
    if not source_tokens:
        return ()
    alternatives = sorted(
        {token.casefold(): token for token in source_tokens}.values(),
        key=len, reverse=True,
    )
    pattern = re.compile(
        r"(?<![A-Za-z0-9])(?:" +
        "|".join(re.escape(token) for token in alternatives) +
        r")(?![A-Za-z0-9])",
        re.I,
    )
    return tuple(match.group(0).casefold() for match in pattern.finditer(value))


def _glossary_pairs(glossary: Iterable) -> list[tuple[str, str]]:
    pairs = []
    for item in glossary:
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            source, target = item[0], item[1]
        elif isinstance(item, dict):
            source, target = item.get("term"), item.get("translation")
        else:
            source = getattr(item, "term", None)
            target = getattr(item, "translation", None)
        if isinstance(source, str) and source and isinstance(target, str) and target:
            pairs.append((source, target))
    return pairs


def source_term_applies(term: str, source_text: str) -> bool:
    """Match alphanumeric glossary terms as complete source tokens."""
    term = term.strip()
    if not term:
        return False
    if re.search(r"[A-Za-z0-9_]", term):
        return bool(re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])",
            source_text, re.I,
        ))
    return term.casefold() in source_text.casefold()


def _is_lyric_like(text: str) -> bool:
    """歌词文本特征：含假名/汉字（日文歌词）或括号音乐标记/重复结构
    （(Guh)/(Let it die)/Sha la la）。普通词术语在歌词中常被押韵词/
    拟声词误命中——'Miss, hit' 的 Miss 是'小姐'非'未命中'（deadbeat
    歌词实证），歌词整体豁免普通词术语检查（keep 型与专名豁免仍生效）。"""
    if len(text) < 200:
        return False
    if re.search(r"[぀-ヿ一-鿿]", text):
        return True
    return bool(re.search(r"\((?:[A-Za-z ,'!?]{2,20})\)", text))


def _glossary_proper_phrase(term: str, source_text: str) -> bool:
    """术语在原文中的出现处邻接 TitleCase 词 → 术语是专名的一部分，与
    术语表的普通词含义无关。deadbeat 'Miss Fire Spitting' 角色名实证：
    Miss 邻接 Fire（TitleCase）→ 与 (miss, 未命中) 术语无关 → 豁免；
    'Slash key' 的 Slash 右邻 key（小写）→ 不豁免（触发术语确定性修复）。
    """
    term = term.strip()
    if not term:
        return False
    # UI 词典词（Settings/Save/Options…在 DISPLAY_WORDS）：显示文本，
    # 邻接 TitleCase 词不构成专名证据——'Open Settings menu' 的 Settings
    # 左邻 Open（普通动词），Settings 仍是 UI 术语，译文必须含其译名
    # （test_translation_term_missing_target_still_fails 固化）→ 不豁免
    if term.casefold() in _DISPLAY_WORDS_CASEFOLD:
        return False
    # 专名形态术语（Moon Key 等 TitleCase 组合）：自身即专名短语，
    # 邻接 TitleCase 词不构成豁免——'Use Moon Key to open...' 的 Moon
    # 左邻 Use（句首动词），译文偏离译名（月之钥匙 vs 月光钥匙）仍是
    # 真 drift（test_quality_rejects_untranslated_english_and_glossary_
    # drift 固化）。豁免只适用于普通词形态术语（小写 miss 在 'Miss
    # Fire Spitting' 专名中被 TitleCase 化 → 与 (miss, 未命中) 无关）
    if re.fullmatch(r"[A-Z][a-z'-]*(?:\s+[A-Z][a-z'-]*)*", term):
        return False
    for m in re.finditer(
            rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])",
            source_text, re.I):
        before = re.match(r"([A-Z][a-z'-]*)\s*$",
                          source_text[:m.start()])
        after = re.match(r"^\s*([A-Z][a-z'-]*)",
                         source_text[m.end():])
        if before or after:
            return True
    return False


def _glossary_keep_echo(original: str, translation: str, glossary) -> bool:
    """保留型术语回显豁免：glossary 中 keep 型术语（source==target
    casefold，署名专名/缩写保留映射）全部覆盖原文、译文无中文且与原文
    字母序列一致（大小写变体）→ 回显是模型对术语的保留，不是漏翻
    （'hiss pop collection' → 'Hiss Pop Collection'，222am 实证：署名
    专名，模型 TitleCase 化回显保留合理）。与 proper_name_echo 的区别：
    原文可含小写普通词（hiss/pop/collection 全是小写词），身份由
    glossary keep 规则证明，不需要 proper_name role。"""
    if _CJK.search(translation):
        return False
    keep_sources = [
        str(source) for source, target in _glossary_pairs(glossary)
        if str(source).strip()
        and str(target).strip()
        and str(source).strip().casefold() == str(target).strip().casefold()
        and source_term_applies(str(source), original)]
    if not keep_sources:
        return False
    letters_src = re.sub(r"[^A-Za-z]", "", original).casefold()
    letters_dst = re.sub(r"[^A-Za-z]", "", translation).casefold()
    if letters_src != letters_dst:
        return False
    # keep 术语覆盖全部原文词：剥离术语后无剩余字母才算"原文全是保留术语"
    rest = original
    for term in sorted(keep_sources, key=len, reverse=True):
        rest = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])",
            " ", rest, flags=re.I)
    return not re.search(r"[A-Za-z]", rest)



def validate_translation_quality(
    entry: TextEntry,
    translation: str,
    glossary: Iterable = (),
    *,
    check_placeholders: bool = True,
) -> QualityResult:
    normalized = (_normalize_translation(entry.original, translation)
                  if isinstance(translation, str) else "")
    reasons = []
    if not normalized:
        reasons.append("empty_translation")
    if _has_illegal_controls(normalized):
        reasons.append("illegal_control")
    if (_EXPLANATORY_PREFIX.search(normalized)
            or (_EXPLANATORY_PATTERN.search(normalized)
                and len(normalized) >= 20)):
        reasons.append("explanatory_prefix")
    if ("```" in normalized
            or (normalized.startswith(("- ", "* "))
                and not normalized.rstrip().endswith((" -", " *"))
                # "* (You felt...)" 选项文案风格不是 markdown 列表——按原文判定
                and not entry.original.lstrip().startswith(("* (", "- ("))
                # 原文本身以 -/* 开头（"-Love, Sean" 签名、"- Quality Settings -"
                # 装饰标题）→ 译文的 "- " 是原文破折号的延续，不是 markdown 列表
                and not entry.original.lstrip().startswith(("-", "*")))):
        reasons.append("markdown_wrapper")
    if check_placeholders and normalized:
        placeholders_ok, missing_ph, extra_ph = validate_translation(
            entry.original, normalized)
        if not placeholders_ok:
            # 缺失占位符全是完整标签对（<color=green>Paused</color> 整对
            # 丢失、模型用引号替代彩色强调）→ 样式整对损失无崩溃风险、
            # 译文已含中文 → 不算 mismatch（baldis 实证：1.8B 对彩色强调
            # 词的稳定行为是引号替代）。字面 \n（C# 转义换行）缺失同样
            # 放宽：模型把它输出为真实换行/并入相邻行是等价行为（格式
            # 标记非数据，测试实证 '{0}kg\n£{1:0.00}' 首译缺失 \n）。数据
            # 占位符 {0}/{name} 缺失仍判失败（运行时展开会崩溃/显示错误）；
            # extra（模型新增）不在 missing 内、仍由校验失败暴露。
            non_escape_missing = [
                ph for ph in missing_ph if not ph.startswith("\\")]
            # 行首星号规范化：原文 "*SIGH*" / " *Added"（星号紧接词）→
            # 译文 "* sigh *" / "* 加空格"（模型把星号规范为强调/列表
            # 标记）。extra 全为 bullet 且无缺失 → 样式规范化无结构
            # 风险，放行（containment Changelog 4 条实证）；无缺失且
            # extra 非 bullet → 模型新增占位符仍判失败
            extra_all_bullet = bool(extra_ph) and all(
                _BULLET_PLACEHOLDER.fullmatch(ph) for ph in extra_ph)
            if not (missing_ph and _CJK.search(normalized)
                    and (not non_escape_missing
                         or _complete_tag_pairs(non_escape_missing))):
                if not (not missing_ph and extra_all_bullet):
                    reasons.append("placeholder_mismatch")
    src_tags = FORMAT_TAG_PATTERN.findall(entry.original)
    dst_tags = FORMAT_TAG_PATTERN.findall(normalized)
    if src_tags != dst_tags:
        missing_tags = list((Counter(src_tags) - Counter(dst_tags)).elements())
        if not (missing_tags and _CJK.search(normalized)
                and _complete_tag_pairs(missing_tags)):
            reasons.append("rich_text_mismatch")
    if (_newline_events(entry.original) != _newline_events(normalized)
            and not _blank_line_compression(entry.original, normalized)
            # 歌词豁免：引擎单行存储超长歌词（无 \n），模型按句分行输出
            # 是歌词的自然渲染（deadbeat 歌词实证）——分行非结构破坏，
            # 判失败会丢弃完整中文译文。非歌词文本原文单行译文多行仍判。
            and not _is_lyric_like(entry.original)):
        reasons.append("newline_mismatch")
    if (_line_content_topology(entry.original)
            != _line_content_topology(normalized)
            and not _blank_line_compression(entry.original, normalized)
            and not _is_lyric_like(entry.original)):
        reasons.append("line_content_mismatch")
    input_tokens = tuple(
        event.value for event in interaction_input_events(entry.original)
        if event.kind == "literal_glyph"
    )
    source_input_events = tuple(token.casefold() for token in input_tokens)
    # 译文按键序列须包含原文按键序列（子序列语义：顺序一致、允许译文出现
    # 原文按键外的额外字面量 —— "Press 1 for Chapter 1" 的章节号 1、
    # "A: " 说话人标记 A 出现在译文中不算破坏按键顺序）
    target_input_events = _input_token_events(normalized, input_tokens)
    pos = 0
    for token in source_input_events:
        while pos < len(target_input_events) and target_input_events[pos] != token:
            pos += 1
        if pos == len(target_input_events):
            reasons.append("input_token_mismatch")
            break
        pos += 1
    original_words = _ENGLISH_WORD.findall(entry.original)
    translated_words = _ENGLISH_WORD.findall(normalized)
    if is_interaction_prompt(entry.original):
        action_words = interaction_action_words(entry.original)
        # 原文中被识别为按键的字面量（"press z or enter" 的 enter 是按键不是动词）
        # 或物理键名动作词（enter/return/space…交互提示中多为按键）——
        # 译文保留按键名是正确行为 → 从动作词检查中豁免
        key_tokens = {
            event.value.casefold()
            for event in interaction_input_events(entry.original)
            if event.kind == "literal_glyph"
        }
        key_tokens |= ({word.casefold() for word in action_words}
                       & PHYSICAL_KEY_NAMES_CASEFOLD)
        # 译文引号内专名短语（按钮 "Jump During Playtime"）→ 动作词在
        # 引号内且短语在原文出现 → 是专名短语不是动作残留（baldis 实证：
        # 'Square Button: Jump During Playtime's Jumprope Minigame' 的
        # Jump 是 Jump During Playtime 小游戏名，模型引号包裹保留合理）
        quoted_terms = quoted_proper_terms(normalized, entry.original)
        if any(
            word.casefold() not in key_tokens
            and word.casefold() not in quoted_terms
            and re.search(
                rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])",
                normalized, re.I)
            for word in action_words):
            reasons.append("untranslated_text")
    # 源词剥离专名载体（域名 itch.io / @用户名 / 版本号）后仍无小写词
    # → 专名回显合理（one-thousand-acts-of-decency 真实样本：
    #   "@_domeDev\ndomedev.itch.io" 回显是作者署名，不算未翻译）
    source_words = _ENGLISH_WORD.findall(
        SAFE_KEEPERS.sub(" ", entry.original))
    # 驼峰技术缩写回显豁免（VSync/MonoBehaviour）：译文全部残留词都是原文
    # 含有的驼峰缩写 → 保留原文合理（vincent 'VSync: OFF' 真实样本）
    source_terms_cf = {word.casefold() for word in original_words}
    camel_echo = (
        bool(translated_words)
        and all(is_camel_tech_abbreviation(word) and word.casefold() in source_terms_cf
                for word in translated_words))
    # 小写词用独立词检查（'Stefánsson' 的 ASCII 碎片 nsson 不是小写普通词）；
    # lorem ipsum 占位文本回显是合理行为（zero-deaths 'Loem iipsum solar'）
    # 知识库特殊文本：全大写动作指令（TOSS TRASH）与间隔动作词（* Y A W N *）
    # 是可翻译语义文本，回显一律判失败（不依赖小写词/UI 词典——大写形态
    # 指令既无小写词又常不在 UI 词典，曾被 proper_name_echo 当专名豁免）
    special_action = _is_uppercase_action(entry.original) or _is_spaced_action(
        entry.original)
    # 知识库规则：大写动作指令的译文不得残留原动作动词——"TOSS 垃圾" 是
    # 半翻译（TOSS 是动作动词，必须译成中文"丢"）。回显（无中文）已被
    # untranslated_text 拦截；此检查补充「有中文但残留动作动词」的场景。
    # 判失败触发重试：native 降级路径带 knowledge 译例后模型输出"丢垃圾"
    if special_action and _CJK.search(normalized):
        for word in re.findall(r"[A-Z][A-Z0-9']{1,}", entry.original):
            if (word.casefold() in _UPPERCASE_ACTION_VERBS
                    and re.search(
                        rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])",
                        normalized, re.I)):
                reasons.append("action_word_residue")
                break
    if (original_words and translated_words and not _CJK.search(normalized)
            and semantic_target_text(entry.original, entry.original)
            and not is_lorem_ipsum_placeholder(entry.original)
            and not camel_echo
            and not _artistic_case_echo(entry.original, normalized)
            and not _glossary_keep_echo(entry.original, normalized, glossary)
            and (has_independent_lower_word(entry.original)
                 or special_action
                 or any(
                    word.casefold() in _DISPLAY_WORDS_CASEFOLD
                    for word in _ui_check_words(source_words)))):
        # 纯品牌/署名串（Playstation、Xbox）模型保留原文是合理行为，不算未翻译
        # （传原文自身：从原文中移除其保护术语后仍有内容才算未翻译；
        #  原文全为专名形态（Crash Bandicoot/Roquette/Profiler 无小写词、
        #  不在 UI 词典）时模型回显也是合理行为；'Continue'/'SFX' 在 UI
        #  词典 → 回显仍判失败；glossary keep 术语组成的原文（hiss pop
        #  collection）TitleCase 化回显是模型保留术语 → 豁免）
        reasons.append("untranslated_text")
    for source, target in _glossary_pairs(glossary):
        # 大小写不敏感：自动沉淀的专名保留映射（KRAPOS→KRAPOS）与模型
        # 回显的 TitleCase 变体（Krapos）是同一词形态变体——大小写敏感
        # 检查把合法专名回显误判 glossary_mismatch（count-my-coins
        # 'Krapos' 实证：learn 时保留检测 casefold，quality 检查却没
        # casefold，自相矛盾）
        if (source_term_applies(source, entry.original)
                and target.casefold() not in normalized.casefold()):
            # 保留型术语（term→term 原样，learn_proper_names 自动沉淀的
            # 专名/缩写保留映射）：模型把该词翻译成中文是合理行为——
            # "FPS" 译成"帧率"优于强制保留（backrooms 实证：自动沉淀
            # FPS→FPS 后质量门拒绝更忠实的「输入自定义帧率...」）。
            # 仅当译文无中文翻译（纯回显/丢失）时保留型术语仍判失败。
            if (target.strip().casefold() == source.strip().casefold()
                    and _CJK.search(normalized)):
                continue
            # 专名邻接豁免：术语在原文中邻接 TitleCase 词 → 术语是专名
            # 的一部分，与术语表普通词含义无关（deadbeat 'Miss Fire
            # Spitting' 角色名的 Miss 邻接 Fire，误命中 (miss, 未命中)；
            # 'Slash key' 的 Slash 右邻 key 小写 → 不豁免，触发术语
            # 确定性修复）
            if _glossary_proper_phrase(source, entry.original):
                continue
            # 歌词语境豁免：歌词文本整体豁免普通词术语检查（押韵词/
            # 拟声词与术语表无关，'Miss, hit' 实证；keep 型与专名豁免
            # 已在上方处理，此处只豁免普通词术语）
            if _is_lyric_like(entry.original):
                continue
            reasons.append("glossary_mismatch")
            break
    max_chars = entry.meta.get("max_chars")
    if (type(max_chars) is int and max_chars > 0 and len(normalized) > max_chars):
        # 超长不判失败：译文质量合格只是物理容量放不下——写回端 _fit_bytes
        # 按容量收尾 + 省略号（部分翻译）。判失败会把好译文整体丢弃、游戏
        # 里只剩原文（taxes 'I did ' 实证 9 字符译文 vs 6 码元容量）。
        # 超出的量记入 meta，写回报告与人工校对可见。
        entry.meta = dict(entry.meta)
        entry.meta.setdefault("length_over_budget", len(normalized) - max_chars)
    ordered = tuple(dict.fromkeys(reasons))
    confidence = entry.confidence if entry.confidence in {"high", "medium", "low"} else "medium"
    return QualityResult(not ordered, confidence, ordered, normalized)


def is_write_ready(status: str, translation: str, meta) -> bool:
    """只有已验且非低置信（或经人工提升）的译文可自动写回。"""
    if status != "translated" or not translation:
        return False
    if isinstance(meta, str):
        try:
            import json
            evidence = json.loads(meta or "{}")
        except (json.JSONDecodeError, TypeError):
            return False
    elif isinstance(meta, dict):
        evidence = meta
    else:
        return False
    if evidence.get("quality_passed") is not True:
        return False
    return (evidence.get("confidence", "medium") != "low"
            or evidence.get("confidence_promoted") is True)
