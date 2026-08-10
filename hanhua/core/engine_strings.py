"""引擎字符串过滤（公共层）：v1 文本提取与 v2 二进制提取共用。

Unity 运行时/模板内容有确定性特征：着色器属性、Input System 绑定、URP 后处理、
TMP 演示文本、字体名、emoji 名等。这些永远不是游戏显示文本。
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Literal

CORE_MENU_SOURCE_TERMS = frozenset({
    "settings", "quit", "resolution", "sfx", "volume", "resume", "controls",
})

_ENGINE_PROP = re.compile(r"^_[A-Za-z]|^m_[A-Za-z]")
_ENGINE_NAME = re.compile(
    r"UnityEngine|UnityEditor|Unity\.RenderPipelines|Unity\.Addressables|"
    r"Unity\.Services|ShaderGraph|TextMeshPro/|DebugUI|Texture2D_|\.dll$", re.I)

# 确定性引擎字符串（与 _is_engine_string 的 strip 语义一致，不带首尾空格）
ENGINE_STRINGS = {
    # Input System 默认绑定
    "navigate", "joystick", "gamepad", "touch", "keyboard", "mouse", "scrollwheel",
    "middleclick", "rightclick", "leftclick", "trackeddeviceposition",
    "trackeddeviceorientation", "trackeddirection", "2dvector", "keyboard&mouse",
    "pointer", "tap", "click", "press",
    # URP 后处理 Volume 组件/效果
    "lifgammagain", "splittoning", "motionblur", "coloradjustments", "filmgrain",
    "tonemapping", "paniniprojection", "probevolumesoptions", "whitebalance",
    "defaultinputactions", "quaternion", "volume profile",
    "liberation sans", "liberationsans sdf", "screen space", "ambient occlusion",
    "depth of field", "bloom", "vignette", "chromatic aberration", "lut", "color lut",
    "widescreen", "target framerate",
    "graphics quality", "texture quality", "anisotropic filtering",
    "colorlookup", "depthoffield", "lensdistortion",
    "volumetricfogvolumecomponent", "channelmixer", "bloomcomponent", "vignettecomponent",
    "coloradjustmentscomponent", "tonemappingcomponent", "filmgraincomponent",
    "motionblurcomponent", "splittoningcomponent", "whitebalancecomponent",
    "paniniprojectioncomponent", "liftgammagain", "liftgammagaincomponent",
    "probevolumesoptionscomponent",
    "screenspacelensflare", "shadowsmidtoneshighlights", "colorcurves",
    "liberationsans sdf - fallback", "volumeprofile",
    # UGUI 回调/组件
    "ondecrement", "onincrement", "onscrollbarclicked", "panel title",
    "resetdebugmanager", "bitfield", "selectpreviousitem", "selectnextitem",
    "onaction",
    # 数学类型
    "vector4", "vector2", "vector3",
    # TMP 资源/演示
    "tmp settings", "message text", "foldout", "face with tears of joy",
    "default style sheet", "dropcap numbers", "emojione", "emoji one",
    "default sprite asset", "unity sdf", "unity logo", "electronic highway sign",
    "text -", "pts - lorem ipsum", "montserrat", "semibold", "bangers", "oswald",
    "anton", "roboto", "noto sans", "droid sans", "arial", "impact", "times new roman",
    "comic sans", "open sans", "source sans", "lobster", "pacifico", "bebas",
    "cinzel", "playfair", "merriweather", "raleway", "ubuntu", "poppins", "nunito",
    "work sans", "inter", "segoe", "calibri", "cambria", "georgia", "garamond",
    "palatino", "futura", "century", "courier", "verdana", "tahoma", "trebuchet",
    "geneva", "lucida", "monaco", "menlo", "consolas", "dejavu", "liberation",
    # Addressables/Unity 包
    "standalonewindows64", "addressablesmaincontentcatalog",
    "20-7e,a0,200b,2026",
    # Unity Localization 表名
    "monologuetable", "dialoguetable", "uitable", "monologuetable shared data",
    "dialoguetable shared data", "uitable shared data",
    # TMP/EmojiOne 表情名（精确匹配；与显示词歧义大的不放这里）
    "smiley", "wink", "winking", "smirk", "blush", "grinning", "stuck out tongue",
    "tongue", "kissing", "pensive", "weary", "grimacing", "sleeping", "sleepy",
    "scream", "hugging", "thinking", "zipper mouth", "money mouth", "nerd",
    "smiling imp", "imp", "skull", "poop", "sob", "cold sweat", "eye roll",
    "smile cat", "joy cat", "yum", "dizzy", "astonished", "hushed", "sweat",
    "laughing", "whaaat", "whaaat!", ".notdef",
}
_ENGINE_STRINGS_LOWER = {s.strip().lower() for s in ENGINE_STRINGS}
# 前缀匹配引擎串（演示文本等带后缀的确定性内容；_is_engine_string 会先 strip 再匹配）
_ENGINE_PREFIX = ("text -", "pts - lorem ipsum", "bitfield", "default sprite asset")

_ENGINE_PATTERNS = [
    re.compile(r"^;"),                                              # ;Gamepad
    re.compile(r"[;&].*[;&]"),                                      # Keyboard&Mouse;Gamepad 组合绑定
    re.compile(r"^[0-9a-fA-F]{32}$"),                               # 32 位哈希
    re.compile(r"^[0-9a-fA-F]{40}$"),                               # 40 位哈希
    re.compile(r"\bto\b.*[-–—]\s*(vertical|horizontal|diagonal|radial)$", re.I),
    re.compile(r"^[0-9A-Fa-f][0-9A-Fa-f, -]+$"),                    # 字符区间表 20-7E,A0,2026
    re.compile(r"\bsdf$", re.I),                                    # TMP 字体名 … SDF
    re.compile(r"^(?:<[^>]{1,60}>)+[^\w]?$"),                       # 整行纯 TMP 富文本标签
    re.compile(r"^(smiling face|grinning face|face with|slightly smiling|"
               r"rolling on the floor|thinking face|winking face|kissing face|"
               r"pensive face|confused face|flushed face|disappointed face|"
               r"worried face|angry face|pouting face|crying face|loudly crying|"
               r"frowning face|weary face|tired face|grimacing face|lying face|"
               r"relieved face|neutral face|expressionless face)", re.I),  # emoji 字符名
    re.compile(r"^[A-Za-z]+ \([a-z]{2,3}\)$"),                      # 语言名 English (en)
    re.compile(r"table shared data$", re.I),                        # Localization 表名 XxxTable Shared Data
    re.compile(r"table_[a-z]{2}$", re.I),                           # 表名语言变体 MonologueTable_es
    # HTTP 协议状态行（websocket-sharp.dll 网络库内部串，非游戏文本）
    re.compile(r"^HTTP/\d(?:\.\d)? \d{3} [A-Za-z][A-Za-z ]*$", re.I),
    # Input System 序列化绑定路径（<Keyboard>/z、<Mouse>/position、<Gamepad>/leftStick）。
    # 设备路径是引擎语法，翻译后 InputSystem 反序列化/查找绑定失败 → 按键全部无反应
    # （morfosigame 实证：Proceed/SkipCutscene 动作被译后点击与跳过失效）。
    re.compile(r"^<[A-Za-z0-9_.]+>/(?:[A-Za-z0-9_./-]+)?$"),
    # Input System interactions 触发方式串（Press(behavior=2)、Hold()、Tap()）：
    # 运行时按名字解析交互，翻译必然破坏触发条件。
    re.compile(r"^(?:press|hold|tap|slowtap|multitap|doubletap|"
               r"pressandrelease|pressdelay|presspoint)\s*\(.*\)$", re.I),
    # Timeline 动画资源 displayName（"AnimationPlayableAsset of Recorded"）
    re.compile(r"^animationplayableasset of\b", re.I),
    # Timeline 轨道 displayName（Animation Track (1) 带编号形式——轨道重名自动加序号，
    # 翻译后字符串结构破坏且按名查找失败，morfosigame 实证被拆成 '动画轨道'+' (1)'）
    re.compile(r"^(?:Activation|Animation|Audio|Control|Group|Marker|Playable|"
               r"Signal|Cinemachine) Track(?:\s*\(\d+\))?$", re.I),
    re.compile(r"^version=0\.0\.0\.0, culture=neutral", re.I),      # 程序集限定名尾部
    # Unity Localization 表键 / 编程命名：无空格、小写开头、含内部大写或下划线
    # （lockedEntrance、ui_newGame、takeTools）
    re.compile(r"^[a-z][a-zA-Z0-9_]*[A-Z][a-zA-Z0-9_]*$"),
    re.compile(r"^[a-z]+_[a-zA-Z0-9_]+$"),
    # PascalCase 数据/类名（FlashlightData、MonologueTable）
    re.compile(r"^[A-Z][a-z]+[A-Z][a-zA-Z0-9]*$"),
]

_DISPLAY_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿА-Яа-я]{2,}")
_SENTENCE_PUNCT = re.compile(r"[.!?。！？]$")
_CODE_QUALIFIED = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*\.)+[A-Za-z_][A-Za-z0-9_]*$")
_INTERACTION_ACTION = (
    r"open|interact|use|continue|pick\s*up|talk|enter|exit|close|read|"
    r"unlock|activate|inspect|grab|drop|hide|show|jump|crouch|sprint|run|"
    r"reload|fire|shoot|attack|aim|block|dodge|pause|select|confirm|cancel|"
    r"equip|consume|throw|climb|descend|drive|take|put|move|begin|insert|break"
)
_ACTION_OBJECT_WORD = r"[A-Za-z0-9][A-Za-z0-9'_-]*"
_IMPERATIVE_ACTION_CLAUSE = (
    rf"(?P<action>(?:{_INTERACTION_ACTION})\b"
    rf"(?:[ \t]+{_ACTION_OBJECT_WORD}){{0,12}})"
)
_ACTION_VERB_PREFIX = re.compile(rf"^(?:{_INTERACTION_ACTION})\b", re.I)
_ACTION_DETERMINERS = {"a", "an", "the", "your", "my", "this", "that"}
_ACTION_FUNCTION_WORDS = {
    *_ACTION_DETERMINERS,
    "in", "on", "into", "from", "with", "through", "at", "to",
    "down", "up", "out", "away", "back", "not",
}
_SECONDARY_AUXILIARIES = {
    "am", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "has", "have", "had", "will", "would",
    "could", "should", "must", "may", "might", "won't", "can't", "cannot",
    "doesn't", "didn't", "isn't", "wasn't", "weren't", "aren't",
    "couldn't", "wouldn't", "shouldn't", "hasn't", "haven't", "hadn't",
    "don't",
}
# Finite result verbs seen after an already complete action complement.  Keep
# ``can`` out of the auxiliary set because Unity prompts commonly name oil cans.
_SECONDARY_FINITE_PREDICATES = {
    "fell", "broke", "went", "gone", "came",
    "ran", "got", "failed", "fails", "appears", "disappears", "vanishes",
    "breaks", "falls", "opens", "closes", "shut", "shows", "displays",
    "times", "crashes", "expires", "collapses", "stops", "succeeds",
    "hangs", "freezes", "froze", "jams", "dies",
}
_SECONDARY_PARTICIPLE_MODIFIERS = {"fallen", "broken", "frozen"}
_AMBIGUOUS_NOMINAL_FINITE = {"remains", "errors", "ends", "works", "returns"}
_AMBIGUOUS_NOMINAL_MODIFIERS = {
    "fallen", "frozen", "system", "loose", "collected", "tax",
}
_ACTION_ADVERBS = {
    "again", "hard", "once", "twice", "today", "tomorrow", "yesterday",
    "now", "soon", "later", "already", "yet", "forever", "here", "there",
    "repeatedly", "unexpectedly", "suddenly", "briefly", "eventually",
    "initially", "previously", "currently",
}
_INTERACTION_PROMPT = re.compile(
    rf"(?:\b(?:press|hold|tap|click|push)\b\s+"
    rf"(?:\[[^\]\r\n]+\]|\([^\)\r\n]+\)|<[^>\r\n]+>|"
    rf"[A-Za-z0-9]+(?:[ \t]+[A-Za-z0-9]+){{0,2}}?)"
    rf"(?:[ \t]+key)?[ \t]+(?:to[ \t]+)?(?:{_INTERACTION_ACTION})\b)"
    rf"|(?:^[ \t]*(?:\[[^\]\r\n]+\]|\([^\)\r\n]+\)|[A-Za-z0-9]+)"
    rf"[ \t]*[-:：][ \t]*(?:to[ \t]+)?(?:{_INTERACTION_ACTION})\b)"
    rf"|(?:(?:按下?|长按|点击|轻触)[ \t]*"
    rf"(?:\[[^\]\r\n]+\]|\([^\)\r\n]+\)|[A-Za-z0-9]+)[ \t]*键?[ \t]*"
    rf"(?:以便|来|以)?[ \t]*(?:打开|互动|交互|继续|拾取|对话|进入|退出|关闭|阅读|解锁|激活|检查))",
    re.I | re.M,
)
_INTERACTION_ACTION_WORD = re.compile(
    rf"\b(?:press|hold|tap|click|push|{_INTERACTION_ACTION})\b", re.I)
_COMMON_NAMED_PHYSICAL_INPUT = (
    r"d-pad[ \t]+(?:up|down|left|right)|page[ \t]+(?:up|down)|"
    r"(?:arrow[ \t]+(?:up|down|left|right)|(?:up|down|left|right)[ \t]+arrow)|"
    r"(?:caps|num|scroll)[ \t]+lock|print[ \t]+screen|"
    r"backspace|delete|insert|home|end|enter|return|tab|space|esc(?:ape)?"
)
_PHYSICAL_INPUT_COMPONENT = (
    rf"(?:{_COMMON_NAMED_PHYSICAL_INPUT})|"
    r"(?:left|right)[ \t]+(?:shift|ctrl|control|alt)|"
    r"mouse[0-9]+|f[0-9]+|shift|ctrl|control|alt|"
    r"numpad[ \t]+[A-Za-z0-9+_-]+|"
    r"(?-i:[A-Z][A-Z0-9_-]{1,23})|[A-Za-z0-9]"
)
_PHYSICAL_INPUT_CHORD = (
    rf"(?:{_PHYSICAL_INPUT_COMPONENT})"
    rf"(?:[ \t]*\+[ \t]*(?:{_PHYSICAL_INPUT_COMPONENT}))+"
)
_PHYSICAL_BINDING_COMPONENT_PATTERN = (
    r"(?:ctrl|control|shift|alt|esc(?:ape)?|backspace|delete|insert|"
    r"home|end|enter|return|tab|space|pageup|pagedown|"
    r"mouse[0-9]+|f[0-9]+|l[0-9]+|r[0-9]+|lb|rb)"
)
_PHYSICAL_BINDING_CHORD = (
    rf"(?:{_PHYSICAL_BINDING_COMPONENT_PATTERN})"
    rf"(?:[_-](?:{_PHYSICAL_BINDING_COMPONENT_PATTERN}))+"
)
_D_PAD_BINDING = re.compile(
    r"d-pad[ \t]+(?:up|down|left|right)", re.I)
_PHYSICAL_BINDING_COMPONENT = re.compile(
    _PHYSICAL_BINDING_COMPONENT_PATTERN,
    re.I,
)
# 物理按键名（casefold）：交互提示中这些词通常作为按键出现
# （"press z or enter" 的 enter 是按键不是动词），译文保留按键名是正确行为。
# 注意 enter/return/space 等同时是动作词——按语境区分（见 quality.py）。
PHYSICAL_KEY_NAMES_CASEFOLD = {
    "escape", "esc", "enter", "return", "space", "tab", "backspace",
    "delete", "del", "insert", "home", "end", "pageup", "pagedown",
    "shift", "ctrl", "control", "alt", "capslock", "numlock",
    "scrolllock", "printscreen", "prtsc", "pause", "break",
    *{f"f{i}" for i in range(1, 13)},
}
_LITERAL_GLYPH = (
    r"'[^'\r\n]{1,24}'|\[[^\]\r\n]{1,24}\]|"
    r"\([^\)\r\n]{1,24}\)|<[^>\r\n]{1,24}>|"
    rf"(?:{_PHYSICAL_INPUT_CHORD})|"
    rf"(?:{_PHYSICAL_BINDING_CHORD})|"
    rf"(?:{_COMMON_NAMED_PHYSICAL_INPUT})|"
    r"(?:left|right)[ \t]+(?:shift|ctrl|control|alt)|"
    r"mouse[0-9]+|f[0-9]+|shift|ctrl|control|alt|"
    r"[A-Za-z0-9](?![A-Za-z0-9+_-])"
)
_PREFIX_LITERAL_EVENT = re.compile(
    rf"\b(?:press|hold|tap|push|click)\b[ \t]*"
    rf"(?P<token>{_LITERAL_GLYPH})(?![A-Za-z0-9+_-])",
    re.I,
)
_PREFIX_NAMED_LITERAL_EVENT = re.compile(
    r"(?i:\b(?P<command>press|hold|tap|push|click)\b)[ \t]*"
    r"(?P<token>[A-Z][A-Z0-9+_-]{1,23}|(?i:numpad)[ \t]+[A-Za-z0-9+_-]+)"
    r"(?=[ \t]*(?:(?i:key)\b)?(?:[ \t]+(?i:to|then|on)\b|[,;]|$))"
)
_CHINESE_LITERAL_EVENT = re.compile(
    rf"(?:按下?|长按|轻触|点击)[ \t]*(?P<token>{_LITERAL_GLYPH})"
    rf"(?![A-Za-z0-9+_-])",
    re.I,
)
_LEADING_LITERAL_EVENT = re.compile(
    rf"^[ \t]*(?P<token>{_LITERAL_GLYPH})(?![A-Za-z0-9+_-])"
    r"[ \t]*[-:：][ \t]*(?P<action>[^\r\n]+)",
    re.I | re.M,
)
_ARTICLE_KEY_EVENT = re.compile(
    rf"\b(?:press|hold|tap|push|click)\b[ \t]+the[ \t]+"
    rf"(?P<token>{_COMMON_NAMED_PHYSICAL_INPUT})"
    r"(?:[ \t]+(?:key|button))?\b",
    re.I,
)
_STRONG_PREFIX_PROMPT = re.compile(
    rf"\b(?:press|hold|tap|push|click)\b[ \t]*"
    rf"(?:{_LITERAL_GLYPH})(?![A-Za-z0-9+_-])"
    rf"(?:[ \t]+key)?[ \t]+to[ \t]+"
    + _IMPERATIVE_ACTION_CLAUSE,
    re.I,
)
_STRONG_ARTICLE_KEY_PROMPT = re.compile(
    rf"\b(?:press|hold|tap|push|click)\b[ \t]+(?:the[ \t]+)?"
    rf"(?:{_COMMON_NAMED_PHYSICAL_INPUT})"
    r"(?:[ \t]+(?:key|button))?\b",
    re.I,
)
_LONG_ARTICLE_KEY_INSTRUCTION = re.compile(
    rf"(?:^|[.!?。！？][ \t]+)"
    rf"(?:(?:when|once|after|before|to)\b[^.!?。！？]{{0,48}},[ \t]*|"
    rf"(?:then|please)[ \t]+){_STRONG_ARTICLE_KEY_PROMPT.pattern}"
    rf"(?:[ \t]+on[ \t]+your[ \t]+keyboard)?"
    rf"(?=$|[.!?。！？])",
    re.I,
)
_STRONG_ARTICLE_KEY_ACTION_PROMPT = re.compile(
    rf"{_STRONG_ARTICLE_KEY_PROMPT.pattern}[ \t]+to[ \t]+"
    + _IMPERATIVE_ACTION_CLAUSE,
    re.I,
)
_LONG_ARTICLE_KEY_ACTION_INSTRUCTION = re.compile(
    rf"(?:^|[.!?。！？][ \t]+)"
    rf"(?:(?:when|once|after|before|to)\b[^.!?。！？]{{0,48}},[ \t]*|"
    rf"(?:then|please)[ \t]+){_STRONG_ARTICLE_KEY_ACTION_PROMPT.pattern}"
    rf"(?=$|[.!?。！？])",
    re.I,
)
_LONG_LITERAL_ACTION_INSTRUCTION = re.compile(
    rf"(?:^|[.!?。！？][ \t]+)"
    rf"(?:(?:when|once|after|before|to)\b[^.!?。！？]{{0,48}},[ \t]*|"
    rf"(?:then|please)[ \t]+){_STRONG_PREFIX_PROMPT.pattern}"
    rf"(?=$|[.!?。！？])",
    re.I,
)
_INTERACTION_DIAGNOSTIC_CONTEXT = re.compile(
    r"\b(?:message|prompt|state|event)\b[^.!?。！？]{0,64}"
    r"\b(?:(?:was|were|is|are)[ \t]+)?"
    r"(?:missing|not[ \t]+(?:displayed|shown)|observed|failed)\b",
    re.I,
)
_CODE_ACTION = re.compile(
    r"(?:(?:[A-Za-z_][A-Za-z0-9_]*\.)+[A-Za-z_][A-Za-z0-9_]*|"
    r"(?:get|set)_[A-Za-z_][A-Za-z0-9_]*|m_[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\(\)|\[[0-9]+\])?"
)
_SEMANTIC_INPUT_EVENT = re.compile(
    r"\b(?:press|hold|tap|push|click)\b[ \t]+(?P<any_key>any[ \t]+key)\b|"
    r"(?P<right_click>\bright[ \t]+click\b)|"
    r"(?P<button>\b(?:square(?:/x/y)?|x|y)[ \t]+button\b)",
    re.I,
)
_SEMANTIC_PROMPT = re.compile(
    r"\b(?:press|hold|tap|push|click)\b[ \t]+"
    r"(?:any[ \t]+key|(?:square(?:/x/y)?|x|y)[ \t]+button)\b|"
    r"\bright[ \t]+click\b(?=[ \t]+(?:with|to)\b|[ \t]*[-:：])|"
    r"\b(?:square(?:/x/y)?|x|y)[ \t]+button[ \t]*[-:：][ \t]*\S",
    re.I,
)


@dataclass(frozen=True)
class InputEvent:
    kind: Literal["literal_glyph", "semantic_input"]
    value: str


def _normalize_input_value(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if ((normalized[0], normalized[-1])
            in {("[", "]"), ("(", ")"), ("<", ">"), ("'", "'")}):
        return normalized[1:-1].strip()
    return normalized


def is_code_action_binding(text: str) -> bool:
    """Return whether a glyph-action row targets a code symbol, not display text."""
    match = _LEADING_LITERAL_EVENT.fullmatch(text.strip())
    return bool(match and _CODE_ACTION.fullmatch(match.group("action").strip()))


def is_physical_binding_identifier(text: str) -> bool:
    """Return whether a bare value is a physical-key binding identifier."""
    stripped = text.strip()
    if _D_PAD_BINDING.fullmatch(stripped):
        return True
    parts = re.split(r"[_-]", stripped)
    return (len(parts) > 1
            and all(_PHYSICAL_BINDING_COMPONENT.fullmatch(part) for part in parts))


def interaction_input_events(text: str) -> tuple[InputEvent, ...]:
    """Parse typed input events from a user-visible interaction prompt."""
    stripped = text.strip()
    positioned: list[tuple[int, InputEvent]] = []
    semantic_spans: list[tuple[int, int]] = []
    literal_spans: list[tuple[int, int]] = []
    for match in _SEMANTIC_INPUT_EVENT.finditer(stripped):
        group = next(name for name, value in match.groupdict().items()
                     if value is not None)
        start, end = match.span(group)
        semantic_spans.append((start, end))
        positioned.append((start, InputEvent("semantic_input", match.group(group))))
    for pattern in (_ARTICLE_KEY_EVENT, _PREFIX_LITERAL_EVENT, _CHINESE_LITERAL_EVENT,
                    _LEADING_LITERAL_EVENT):
        for match in pattern.finditer(stripped):
            action = match.groupdict().get("action")
            if action is not None and _CODE_ACTION.fullmatch(action.strip()):
                continue
            start, end = match.span("token")
            if any(start < semantic_end and semantic_start < end
                   for semantic_start, semantic_end in semantic_spans):
                continue
            literal_spans.append((start, end))
            positioned.append((start, InputEvent(
                "literal_glyph", _normalize_input_value(match.group("token")))))
    for match in _PREFIX_NAMED_LITERAL_EVENT.finditer(stripped):
        command_start, command_end = match.span("command")
        if any(command_start < semantic_end and semantic_start < command_end
               for semantic_start, semantic_end in semantic_spans):
            continue
        start, end = match.span("token")
        if any(start < other_end and other_start < end
               for other_start, other_end in semantic_spans + literal_spans):
            continue
        positioned.append((start, InputEvent(
            "literal_glyph", _normalize_input_value(match.group("token")))))
    positioned.sort(key=lambda item: item[0])
    return tuple(event for _, event in positioned)


def is_engine_string(s: str) -> bool:
    """引擎内部字符串判定：着色器属性、序列化引用、程序集限定名、已知引擎字符串。"""
    s2 = s.strip()
    if _ENGINE_PROP.match(s2) or _ENGINE_NAME.search(s2):
        return True
    low = s2.lower()
    if low in _ENGINE_STRINGS_LOWER or low.startswith(_ENGINE_PREFIX):
        return True
    if any(p.search(s2) for p in _ENGINE_PATTERNS):
        return True
    return False


def has_display_text_evidence(text: str) -> bool:
    """Return whether a raw Unity string has strong user-visible language evidence."""
    stripped = text.strip()
    if not stripped or is_engine_string(stripped) or _CODE_QUALIFIED.fullmatch(stripped):
        return False
    if is_interaction_prompt(stripped):
        return True
    words = _DISPLAY_WORD.findall(stripped)
    return bool(_SENTENCE_PUNCT.search(stripped) or len(words) >= 3)


def is_interaction_prompt(text: str) -> bool:
    stripped = text.strip()
    if is_code_action_binding(stripped):
        return False
    return bool(
        any(event.kind == "literal_glyph"
            for event in interaction_input_events(stripped))
        or _SEMANTIC_PROMPT.search(stripped)
        or _INTERACTION_PROMPT.search(stripped)
    )


def _is_safe_imperative_match(match: re.Match[str] | None) -> bool:
    if match is None:
        return False
    action = str(match.groupdict().get("action") or "")
    verb = _ACTION_VERB_PREFIX.match(action)
    if verb is None:
        return False
    complement = re.findall(_ACTION_OBJECT_WORD, action[verb.end():])
    entity_count = 0
    entities: list[str] = []
    determined_phrase = False
    for index, token in enumerate(complement):
        normalized = token.casefold()
        if normalized in _ACTION_DETERMINERS:
            determined_phrase = True
            continue
        if normalized in _ACTION_FUNCTION_WORDS:
            continue
        later_entity = any(
            later.casefold() not in _ACTION_FUNCTION_WORDS
            and later.casefold() not in _ACTION_ADVERBS
            and not later.casefold().endswith("ly")
            for later in complement[index + 1:]
        )
        is_contextual_can = (
            normalized == "can" and entity_count > 0
            and index + 1 < len(complement)
            and complement[index + 1].casefold() == "not"
        )
        is_proper_name = (
            normalized in {"may", "will"}
            and token[:1].isupper()
            and entity_count == 0
        )
        is_determined_will = (
            normalized == "will" and determined_phrase
            and entity_count == 0 and not later_entity
        )
        if ((normalized in _SECONDARY_AUXILIARIES
             and not is_proper_name and not is_determined_will)
                or is_contextual_can):
            return False
        if normalized in _AMBIGUOUS_NOMINAL_FINITE:
            is_nominal = (
                not later_entity
                and ((determined_phrase and entity_count == 0)
                     or (entity_count > 0 and entities[-1]
                         in _AMBIGUOUS_NOMINAL_MODIFIERS))
            )
            if is_nominal:
                entity_count += 1
                entities.append(normalized)
                continue
            return False
        if normalized in _SECONDARY_FINITE_PREDICATES:
            return False
        looks_like_participle = (
            normalized in _SECONDARY_PARTICIPLE_MODIFIERS
            or (len(normalized) > 4 and normalized.endswith("ed"))
        )
        if looks_like_participle:
            if entity_count == 0 and later_entity:
                entity_count += 1
                entities.append(normalized)
                continue
            return False
        entity_count += 1
        entities.append(normalized)
    return True


def is_strong_interaction_prompt(text: str) -> bool:
    """Return only interaction evidence safe without UI call provenance."""
    stripped = text.strip()
    if is_code_action_binding(stripped):
        return False
    if re.match(r"^(?:debug|error|warning|failed|unable|exception)\b", stripped,
                re.I):
        return False
    if _INTERACTION_DIAGNOSTIC_CONTEXT.search(stripped):
        return False
    bare_command = stripped.rstrip(" .!?。！？")
    has_prefix_input = bool(
        _PREFIX_LITERAL_EVENT.fullmatch(bare_command)
        or _PREFIX_NAMED_LITERAL_EVENT.fullmatch(bare_command)
        or _CHINESE_LITERAL_EVENT.fullmatch(bare_command))
    sentence_marks = sum(stripped.count(mark) for mark in ".!?。！？")
    prefix_action = _STRONG_PREFIX_PROMPT.fullmatch(bare_command)
    article_action = _STRONG_ARTICLE_KEY_ACTION_PROMPT.fullmatch(bare_command)
    long_action = (
        _LONG_ARTICLE_KEY_ACTION_INSTRUCTION.search(stripped)
        or _LONG_LITERAL_ACTION_INSTRUCTION.search(stripped)
    )
    long_instruction = (
        len(stripped) >= 40
        and sentence_marks >= 2
        and bool(_LONG_ARTICLE_KEY_INSTRUCTION.search(stripped)
                 or _is_safe_imperative_match(long_action)))
    return bool(
        _is_safe_imperative_match(prefix_action)
        or _is_safe_imperative_match(article_action)
        or _STRONG_ARTICLE_KEY_PROMPT.fullmatch(bare_command)
        or has_prefix_input
        or _SEMANTIC_PROMPT.match(stripped)
        or (_LEADING_LITERAL_EVENT.match(stripped)
            and _INTERACTION_PROMPT.match(stripped))
        or long_instruction
    )


def interaction_input_tokens(text: str) -> tuple[str, ...]:
    """Return literal keyboard/button tokens that an interaction prompt must retain."""
    return tuple(event.value for event in interaction_input_events(text)
                 if event.kind == "literal_glyph")


def interaction_action_words(text: str) -> tuple[str, ...]:
    """Return only known interaction verbs that must not survive untranslated."""
    return tuple(match.group(0) for match in _INTERACTION_ACTION_WORD.finditer(text))
