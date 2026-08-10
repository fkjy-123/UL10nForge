from __future__ import annotations
from collections import Counter
import json
import re

from hanhua.core.engine_strings import (interaction_input_events,
                                        is_interaction_prompt)

BB_TAG_PATTERN = re.compile(
    r"\[/?(?:b|i|u|s|color|size|font|url|sprite)(?:=[^\]\r\n]+)?\]",
    re.I,
)
FORMAT_TAG_PATTERN = re.compile(
    r"</?[A-Za-z][^>\r\n]{0,49}>|"
    r"\[/?(?:b|i|u|s|color|size|font|url|sprite)(?:=[^\]\r\n]+)?\]",
    re.I,
)

PLACEHOLDER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("brace",   re.compile(
        r"\{/?[a-zA-Z0-9_.\-]+(?:=[^{}\r\n]*)?(?:,-?\d+)?(?::[^{}\r\n]+)?\}")),
    # {0} {name} {1:0.00} {0,-10:N2} {w=1.5} {/i}（含 Ren'Py 等号值/结束标签）
    ("percent", re.compile(r"%[-+0-9.l]*[a-zA-Z%]")),      # %s %d %1.2f %%
    ("html",    re.compile(r"</?[a-zA-Z][^>]{0,49}>")),    # <b> </b> <color=#fff>
    ("bb",      BB_TAG_PATTERN),                              # [b] [color=#fff]
    ("newline", re.compile(r"\\n")),                       # 字面 \n
    # Undertale 系对话脚本标记：行首 "* " 对话符（模型常整段丢弃，DELTATRAVELER
    # 真实样本）→ 逐字保护；"* (选项)" 的括号是可选样式（既有行为允许去括号）
    ("undertale_bullet", re.compile(r"(?m)^\* ")),
    # 行尾计时码（"…)^05" 等，多行对话逐行收尾）→ 模型常丢 "^NN" → 保护
    ("undertale_timing", re.compile(r"\)\^[0-9]{1,2}")),
]

_DEV_TEMPLATE_PLACEHOLDER = re.compile(
    r"(?i)^(?:[a-z0-9]+ ){0,4}"
    r"(?:description|name|title|text|content|info|details|dialog|dialogue) here!*$",
)

_HTML_OR_BB = re.compile(
    r"^(?:<[^>]+>|\[/?(?:b|i|u|s|color|size|font|url|sprite)(?:=[^\]]+)?\])$",
    re.I,
)
_URL = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9+.-]*://|www\.)\S+$|"
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)
_ONLY_SYMBOL = re.compile(r"^[\W_]+$")
# 星号前缀单词（*shit / *beaner）：TextAsset 脚本里的词表/列表条目
# （baldis resources.assets#71 实证）。模型对 * 前缀短词稳定回显
# （* 被当强调标记），翻译无意义 → 词表条目跳过。星号+空格
# （"* (text)" 对话格式）不匹配。
_STAR_PREFIXED_WORD = re.compile(r"^\*[a-z]{3,}$")
# 混合符号 token：无空格、含至少一个强代码符号（%#&^$@|\）、含字母。
# 匹配随机 token/编码串（'xChDC-Gs%OmaMl+g'）；正常英文句子的强符号
# 都是 '100% sure' 式带空格或有 '=' 成对出现（a=b），不匹配。
# 不含 ! ~（'Kyahaaaaa~!' 日式语气词、'WOW!!!' 是正常文本，误伤
# 实证：unityscript 粒子文本测试）。
_MIXED_SYMBOL_TOKEN = re.compile(
    r"^(?=.*[%#&^$@|\\])(?=.*[A-Za-z])[^\s]+$")
_HAS_LETTER = re.compile(r"[^\W_0-9]")
_STRIP_RICH_TEXT = re.compile(r"<[^>]+>")
# Unity 实例化对象名：frameVertical(Clone) / Player(Clone)(Clone)
_CLONE_SUFFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\(Clone\))+$")
# 点开头扩展名：.spriteatlas
_DOT_EXTENSION = re.compile(r"^\.[A-Za-z0-9_]{2,12}$")
# GUID 标识符：GUID:cef3ca5fc32178c449992c58120ccded
_GUID_IDENTIFIER = re.compile(r"^GUID:[0-9a-fA-F]{32}$")
# I2 Localization 复数模板占位：{0:p:mine|mines}（运行时按数量展开单复数；
# 翻译会破坏 I2 的 plural 语法，minato 等 I2 游戏真实失败样本）
_I2_PLURAL_BLOCK = re.compile(r"\{[^{}\n]*:p:[^{}\n]*\}")
# IL2CPP 生成的模块调试行：\nmodule.renderOrderPriority: （引擎内部字符串，
# 非游戏文本，翻译必失败；minato global-metadata.dat 真实样本）
_IL2CPP_MODULE_DEBUG = re.compile(r"^module\.[A-Za-z0-9_]+:\s*$")
# 开发者重复占位行：Hello\nHello\nHello\nHello（同一短行重复 ≥4 次，
# 模型必回显，flabby-pizza 真实样本；长行/低重复是真实戏剧文本）
_REPEATED_PLACEHOLDER_LINE = re.compile(
    r"^([^\r\n]{1,16})\n\1(?:\n\1){2,}$")
# Master Audio 插件总线行：\t2810670744\tSoundFX\t\\Default Work Unit\\Master Audio Bus\\
_MASTER_AUDIO_BUS = re.compile(
    r"^[\t ]*\d{6,}[\t ]+[^\r\n]*\\Default[ \t]+Work[ \t]+Unit\\")
# 署名年份行：Darien Gore (Fleebs) 2019 / 3DI70R 2024（人名 + 可选别名 + 年份）；
# Level/Stage 等关卡前缀词 + 年份（Level 2024）不算署名
_CREDIT_YEAR_LINE = re.compile(
    r"^(?!(?:level|stage|chapter|episode|area|zone|round|day|week|wave|"
    r"room|floor|world)\b)(?:[A-Za-z0-9][A-Za-z0-9' -]*"
    r"(?:\([^)]*\))?[\t ]*)(?:19|20)\d{2}$",
    re.I)
# Unity 内部符号：metadata 字符串字面量里的调试符号/程序集引用
# （Unity.Burst.Intrinsics.X86, Unity.Collections.AllocatorManager+SlabAllocator,
#  Unity.Burst, Version=...::DoGetCSRTrampoline() 等——不是游戏文本，
#  模型翻译反而吃逗号/改坏符号，panzershoot/faerie-afterlight 等真实失败样本）
_UNITY_SYMBOL = re.compile(r"^Unity\.[A-Za-z][^\r\n]*$")
_PDB_ALT_PATH = re.compile(r'^PdbAltPath="[^"\r\n]*"$')
# 版本号横幅：\t**\t\tVERSION 0.4.3\t\t**（版本标题保留原文是行业惯例）
_VERSION_BANNER = re.compile(
    r"^[\t ]*\*{1,2}[\t ]*VERSION[ \t]+\d+\.\d+[^\r\n]*$", re.I)
# zalgo 乱码：组合字符叠加的字体艺术文本（翻译必然失败/请求错误）
_COMBINING_MARKS = re.compile(
    r"[̀-ͯ᪰-᫿᷀-᷿"
    r"⃐-⃿︠-︯]")
# 模型正确保留的专名载体（目标脚本/未翻译检查前从语义中移除）：
# 3+ 段路径（User/Blah/Hey/HotelParadiseScreenshot）、域名（itch.io /
# OpenGameArt.com）、@用户名（@zkfie）、版本号（0.4.0beta）、文件扩展名
# （SPOLOUS.exe）、代码标记（[var:ID]）
SAFE_KEEPERS = re.compile(
    r"[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+){2,}"
    r"|[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:com|net|org|io|gg|dev|me|it|ru|de|jp)\b"
    r"|@[\w.-]+"
    r"|[a-z0-9]+(?:\.[a-z0-9]+)+\b"          # 用户名/艺名（yu.una）
    r"|\d+\.\d+[.\d]*[a-z]*\b"
    r"|\.[A-Za-z]{2,5}\b"                    # 文件扩展名（SPOLOUS.exe 的 .exe）
    r"|\[[A-Za-z_][A-Za-z0-9_:#.-]*\]")      # 代码标记（[var:ID]）
# Lorem ipsum 占位文本（minato 真实样本：模型不翻译占位符是正常行为）
_LOREM_IPSUM = re.compile(r"^Lorem ipsum\b", re.I)
# Shell 命令（something-bad-on-the-moon 真实样本：find /var/log -name ... | tar）
_SHELL_COMMAND = re.compile(
    r"^(?:find|tar|ls|grep|sudo|chmod|rm|mkdir|unzip|wget|curl|mv|cp)\b"
    r"[^\r\n]*(\|[^\r\n]*)?$")
# 游戏 jam 署名（roots 真实样本："made in 48h\nfor Ludum Dare 48"，
# 允许前导空白/换行：" \nmade in 48h"）
_JAM_CREDIT = re.compile(r"^[\s]*made in \d+\s*h\b", re.I)
# 键盘噪音/乱打文本（开发者测试占位符，真实样本：
# panzershoot "asdasdasd\nasda sdasd"、the-keeper "fdji ijsdijn j jnf oij..."）
# ——无真实单词，模型必然回显，跳过。
# 触发条件（全小写、无中日韩文字、非 URL 方案）：
#  a) 存在 ≥8 字符长词且含重复 3-gram（asdasdasd = 'asd'×3）
#  b) 或存在纯辅音词（jnf/tdr——真实英语几乎不存在无元音词；
#     排除 https/ftp 方案与 www）
_KEYBOARD_NOISE = re.compile(
    r"^(?=[^A-Z㐀-鿿぀-ヿ]*$)"
    r"(?:(?=.*\b[a-z]{8,}\b)(?=.*([a-z]{3}).*\1)"
    r"|(?=.*\b(?!www\b)[bcdfghjklmnpqrstvwxz]{3,}(?!://)\b))"
    r".*$", re.S)
# 路径/文件名/版本号等标识符风格值（无空格，点号或斜杠分隔）：如 Unity 程序集名、文件路径
_WINDOWS_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)[^\r\n]+$")
_UNIX_PATH = re.compile(r"^/(?:[^/\r\n]+/)*[^/\r\n]*$")
_EXPLICIT_RELATIVE_PATH = re.compile(r"^\.{1,2}[\\/][^\r\n]+$")
_BACKSLASH_PATH = re.compile(
    r"^(?!.*\\n)\\?[A-Za-z0-9_. -]+(?:\\[A-Za-z0-9_. -]+)+$")
_THREE_SEGMENT_PATH = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+$")
_EXTENSION_PATH = re.compile(
    r"^[A-Za-z0-9_.-]+/(?:[A-Za-z0-9_.-]+/)*"
    r"[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,16}$")
_UNITY_ROOTED_PATH = re.compile(
    r"^(?:Assets|Packages|ProjectSettings|Library|StreamingAssets)[\\/].+$",
    re.I,
)
_INPUT_SYSTEM_BINDING = re.compile(
    r"^<[A-Za-z][A-Za-z0-9_.-]*>/[A-Za-z0-9_./*{}-]+$")
_INPUT_ACTION_IDENTIFIER = re.compile(
    r"^(?:UI/[A-Za-z0-9_.{}*-]+|\*/\{[A-Za-z0-9_.-]+\})$")
_ASSET_FOLDER = re.compile(
    r"^(?:[A-Za-z0-9][A-Za-z0-9 &_.-]{0,71})?"
    r"(?:Assets|Materials|Presets)/$",
    re.I,
)
_DANGLING_FORMAT_SUFFIX = re.compile(
    r"^[^\w\s]+(?:</[A-Za-z][^>\r\n]{0,49}>)+$")
# .NET 日期/时间格式串（HH:mm dd MMMM, yyyy 等）：翻译破坏格式语义
# （a-catfiends Fungus.dll us#49189 实证：模型回显恒败）。token 段间由
# 分隔符连接（: 空格 , / - .），不匹配则为普通文本（'May the 4th' 等）。
_DATETIME_FORMAT = re.compile(
    r"^(?:HH|hh|mm|MM|MMMM|MMM|dd|yyyy|yy|ss|tt|zzz)"
    r"(?:[: ,./\-]+(?:HH|hh|mm|MM|MMMM|MMM|dd|yyyy|yy|ss|tt|zzz))+$")
# C# format 字符串转义大括号：{{ / }} 是 string.Format 的转义写法，
# 常与 {0} 占位符共存于代码常量模板（a-catfiends Unity.ProBuilder.dll
# us#32180 实证：'{0} : {1}\nCPAPI:{{"cmd":"Watch" "name":"{0}"}}'——多行
# 含字母绕过了单行纯符号/纯占位符检测，模型翻译恒败）。显示文本几乎
# 不会含 {{，命中即代码/数据模板。
_ESCAPED_BRACES = re.compile(r"\{\{|\}\}")
# 颜色表条目：HTML/CSS 色名列表（ProBuilder 材质/顶点着色 UI 的数据表，
# 无翻译价值，模型对专有名词回显恒败）。固定标注格式：
# 'Gray (HTML/CSS Gray)'、'Green (HTML/CSS Color)'、'Air Force Blue (USAF)'
_COLOR_TABLE_ENTRY = re.compile(
    r"\(HTML(?:/CSS)?(?: [A-Z][A-Za-z]+)?\)|\(USAF\)")
# 纯富文本标签串：整串都是 {tag} 序列（Fungus/UGUI 样式模板拆分出的
# 标签行，a-catfiends resources.assets obj1292 实证：'{customName}'、
# '{/customName}'、'{color=blue}'、'{audio=AudioTag}'——模型回显合理，
# 但翻译无意义，且写回因无变化被静默过滤造成统计虚高）。对话文本
# 含真实内容（'{punch=3,2}* Y A W N *{w=3}{x}'）不命中锚定模式。
_PURE_TAG_SEQUENCE = re.compile(r"^(?:\{[^}\r\n]*\})+$")
_QUALIFIED = re.compile(r"^[a-zA-Z0-9_]+([.\-][a-zA-Z0-9_]+)+$")
# .NET 程序集全名：Namespace.Type, Version=x.y.z, Culture=neutral, PublicKeyToken=null
# （Addressables catalog m_AssemblyName 真实值，project-arrhythmia 失败样本）
_ASSEMBLY_REF = re.compile(
    r"^[^,]+,\s*Version=\d[\w.]*(?:,\s*[A-Za-z]+=[\w.]+)*$")
# 协议相对 URL：//host/path（A* 库版权文件真实值，morfosigame 失败样本）
_PROTOCOL_RELATIVE_URL = re.compile(r"^//[A-Za-z0-9][^\r\n]*$")
# InputAction 绑定路径：前缀多段路径 + 方括号绑定段
# （swallow-the-sea level0 真实值：SwallowControls/MousePosition[/Mouse/position]）。
# 带空格或单段前缀的显示文本（Save[/b]、Credits [More]）不受影响
_BRACKETED_PATH = re.compile(
    r"^[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+(?:\[[^\s\[\]]+\])+$")
# CLI 参数（无空格、- 开头）：--platform=Windows（Burst 命令记录真实值）
_CLI_ARG = re.compile(r"^--?[A-Za-z][^\s]*$")
# base64 序列化数据（Addressables catalog m_BucketDataString 真实值）
_BASE64 = re.compile(r"^[A-Za-z0-9+/]{16,}={0,2}$")
# credit/署名行：- from X / by X 结尾 / created by X 开头 / ©版权行
# （真实失败样本：CREDITS.txt 逐行、level0 的 Created by Sam Hogan）
_CREDIT_ATTRIBUTION = re.compile(
    r"(?i:^created\s+by\s+[A-Z0-9]|"
    r"[-:：]\s*(?:from|by)\s+[A-Z0-9]|"
    r"\sby\s+[A-Z][a-zA-Z0-9'.]*(?:\s+[A-Z][a-zA-Z0-9'.]*){0,3}$|"
    r"©|(?i:\bcopyright\b)[^\d]{0,40}\d{4})")
# TMP SDF 字体资产名（Signed Distance Field 字体）：X SDF Y / X SDF 形状
# （真实失败样本：ComicsCarToon SDF Zesty、roquetteplain SDF Bonus）
_SDF_FONT = re.compile(r"(?i:\bSDF\b)")
# 语言文件键码（§m_quit ### / §e1_credits_1 ###：§ 前缀菜单/对话键 +
# ' ###' 空值分隔符，butterflies 真实样本 97 条——localization 键值模板
# 的键且值缺失 → 无译义内容，模型回显恒败）
_SECTION_KEY = re.compile(r"^§[a-zA-Z0-9_]+ ###$")
# 语言代码目录标记（EN/ / DE/：双语 TextAsset 的语种分隔行，butterflies 样本）
_LANG_CODE_WITH_SLASH = re.compile(r"^[a-zA-Z]{2}/$")
# 多行键位映射（"k\nm\n/\nh"：键盘快捷键组合提示，每行恰好 1 个字符，
# butterflies 真实样本 4 条）——无译义内容，模型回显恒败
_SINGLE_CHAR_KEYMAP_LINES = re.compile(r"^(?:[^\r\n])(?:\n[^\r\n])+$")
# XXXX 占位名（XXXX t'a：游戏内未命名角色/玩家的占位名，XXXX 是标准
# 名字占位符）→ 保留原文合理
_XXXX_PLACEHOLDER_NAME = re.compile(r"^XXXX(?: [A-Za-z]+(?:'[a-z]+)?)?$")
# credit 名单对齐行：双无空格 token 多空格分隔（kangaroovindaloo    qubodup /
# pcaeldries          RICHERlandTV：制作人名单两列对齐，无译义）
_CREDIT_ALIGNED = re.compile(r"^[A-Za-z0-9]+ {2,}[A-Za-z0-9]+$")
# 音乐合作名单（Highraiser ft. inkoutlines, MC Cruel Addict：ft. =
# featuring 合作标签，游戏音乐/音效署名行）
_FT_CREDIT = re.compile(r"(?i:\bft\.)")
# 普通句子标记：credit 形状的行若含这些虚词仍是可翻译句子。
# 注意不含单字母 a——标题/选项（Option A、A* star）中的 A 不是虚词
_SENTENCE_MARKERS = re.compile(
    r"(?i:\b(?:the|an|of|for|and|with|to|in|on|is|are|was|were|"
    r"it|we|you|your|our|this|that|have|has|had|will|would|can|could|"
    r"should|not|no|be|been)\b)")


def _is_full_value_path_or_binding(text: str) -> bool:
    """Match a complete path/binding after protecting embedded rich tags."""
    if _INPUT_SYSTEM_BINDING.fullmatch(text):
        return True
    without_rich_tags = FORMAT_TAG_PATTERN.sub("", text).strip()
    return bool(
        _URL.fullmatch(without_rich_tags)
        or _WINDOWS_PATH.fullmatch(without_rich_tags)
        or _UNIX_PATH.fullmatch(without_rich_tags)
        or _EXPLICIT_RELATIVE_PATH.fullmatch(without_rich_tags)
        or _BACKSLASH_PATH.fullmatch(without_rich_tags)
        or _THREE_SEGMENT_PATH.fullmatch(without_rich_tags)
        or _EXTENSION_PATH.fullmatch(without_rich_tags)
        or _UNITY_ROOTED_PATH.fullmatch(without_rich_tags)
    )

# ── 键名识别（Localization 表键/字典键/标识符，绝不能翻译） ──────────────────
# 无空格的标识符形态（3–64 字符）：LOCALIZATION 表键（ui_newGame、MENU_PLAY）、
# 对象名（UITable_en）、程序标识符（FlashlightData）、语言代码（en/ru/zh）等。
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{2,63}$")
_LOCALE_CODE = re.compile(r"^[a-z]{2}$")   # en/ru/zh/ja… 语言代码
# 单词式写法（TitleCase / ALL-CAPS，可含单连字符）：CREDITOS、Settings、V-SYNC
# 是显示文本（任意语言的 UI 标签），不是键——键采用 snake/camel/下划线等编程命名。
_WORD_CASE = re.compile(r"^[A-Z]+(?:-[A-Z]+)*$|^[A-Z][a-z]+(?:-[A-Z][a-z]+)*$")

# 显示单词白名单：标识符形态但确实是游戏显示文本（UI 标签/短对话）。
# 仅这些无空格单词允许翻译；其余标识符一律视为键名跳过。
# 注意：白名单单词若作为键使用（SharedData 键列表），由对象级键列表规则覆盖（见 unity/extractor）。
DISPLAY_WORDS = {
    # 确认/导航
    "ok", "yes", "no", "on", "off", "go", "hi", "hey", "hello", "bye",
    "goodbye", "thanks", "thank", "sorry", "welcome", "wait", "back", "next",
    "prev", "enter", "exit", "leave", "return", "cancel", "confirm", "accept",
    "apply", "close", "open", "skip", "retry", "continue", "start", "stop",
    "pause", "resume", "restart", "reset", "default", "backtomenu",
    # 菜单/UI
    "menu", "mainmenu", "newgame", "loadgame", "savegame", "settings", "options",
    "language", "volume", "audio", "video", "graphics", "quality", "screen",
    "window", "fullscreen", "sound", "music", "brightness", "sensitivity",
    "controls", "keyboard", "mouse", "gamepad", "controller", "resolution",
    "vsync", "v-sync", "credits", "help", "instructions", "pause", "paused",
    "loading", "waiting",
    "ready", "locked", "unlocked", "failed", "success", "victory", "defeat",
    "gameover", "difficulty", "easy", "normal", "hard", "nightmare", "beginner",
    "expert", "custom", "high", "medium", "low", "max", "min", "auto", "manual",
    # 通用动作/名词
    "new", "play", "save", "load", "quit", "use", "talk", "buy", "sell", "shop",
    "map", "quest", "item", "inventory", "attack", "defend", "heal", "flee",
    "run", "walk", "jump", "read", "look", "take", "give", "drop", "hold",
    "left", "right", "up", "down", "win", "lose", "dead", "hide", "show",
    "toggle", "enable", "disable", "delete", "warning", "danger", "help",
    "score", "level", "wave", "round", "time", "health", "mana", "stamina",
    "energy", "ammo", "money", "gold", "coins", "online", "offline",
    "singleplayer", "multiplayer", "coop", "pvp", "chat", "friend", "party",
    "guild", "lobby", "2d", "3d",
}

# JSON 字段名视为键字段（值不翻译）：Key/ID/GUID/Hash/Ref/语言代码等
_KEY_FIELD_NAMES = {
    "key", "id", "guid", "gid", "hash", "ref", "refid", "m_key", "keyid",
    "key_id", "keyname", "idname", "locale", "lang", "language", "culture",
    "region", "country", "tag", "type", "category", "class", "kind", "section",
    "group", "index", "order", "flag", "state", "mode", "status",
    # Addressables catalog 结构字段（Unity 序列化名）：值分别是资源地址/程序集名/
    # 加载器类型，翻译必然破坏资源加载（catalog.json 真实失败样本 21 条）
    "m_address", "m_assetpath", "m_internalid", "m_providerid",
    "m_assemblyname", "m_objecttype", "m_typename", "m_type",
    "m_sceneproviderdata", "m_instanceproviderdata",
    "m_internalids", "m_bucketdatastring", "m_entrydatastring",
    "m_keydatastring", "m_extradatastring",  # base64 键/额外数据（interdream request_error 样本）
}


def is_key_style_identifier(text: str) -> bool:
    """键风格标识符 → 永不翻译。

    判定：标识符形态且「不是单词式写法」且「不是显示单词」。
    - 键：ui_newGame、MENU_PLAY、phone_call_01、UITable_en、en/ru 语言代码
    - 显示值（允许翻译）：CREDITOS / Settings / V-SYNC（单词式写法，任意语言）、
      start / menu（显示单词白名单）
    """
    s = text.strip()
    if _LOCALE_CODE.match(s):
        return True                       # en/ru/zh… 语言代码
    if not _IDENTIFIER.match(s):
        return False
    if _WORD_CASE.match(s):
        return False                      # CREDITOS / Settings / V-SYNC → 显示文本
    if s.lower() in DISPLAY_WORDS:
        return False                      # start / menu / ok → 显示文本
    return True                           # ui_newGame / MENU_PLAY → 键


def is_code_identifier(text: str) -> bool:
    """代码字符串池（DLL #US / IL2CPP metadata / 配置资源）标识符 → 键，永不翻译。

    代码池中的无空格 ASCII 标识符（Bold / WASD / Move / Fire / Unity / Enum）
    是枚举名、Input 绑定名、引擎名、UI 控件名——游戏代码按原名查找，
    翻译必然破坏功能。单词式写法也**不**放行（与 is_key_style_identifier 相反：
    Bundle 表值可能是显示文本，代码池字面量几乎都是标识符）。
    """
    s = text.strip()
    if _LOCALE_CODE.match(s):
        return True                       # en/ru/zh… 语言代码
    return bool(_IDENTIFIER.match(s))


def looks_like_key_field(field_name: str) -> bool:
    """JSON 字段名是否为键字段（其值不应翻译）。"""
    n = field_name.strip().lower()
    if n in _KEY_FIELD_NAMES:
        return True
    return n.startswith("key_") or n.endswith(("_key", "_id", "_guid", "_hash", "_ref"))


def extract_placeholders(text: str) -> list[str]:
    """按出现顺序返回文本中的全部占位符。"""
    found: list[tuple[int, int, int, str]] = []
    for pattern_index, (_, pat) in enumerate(PLACEHOLDER_PATTERNS):
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), pattern_index, m.group(0)))
    found.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in found]


_LITERAL_NEWLINE = re.compile(r"\\n")
_OPENING_TAG = re.compile(
    r"<[A-Za-z][^>\r\n]{0,49}>|"
    r"\[(?:b|i|u|s|color|size|font|url|sprite)(?:=[^\]\r\n]+)?\]",
    re.I,
)
_CLOSING_TAG = re.compile(
    r"</[A-Za-z][^>\r\n]{0,49}>|\[/(?:b|i|u|s|color|size|font|url|sprite)\]",
    re.I,
)


def _placeholder_spans(text: str) -> list[tuple[int, int, str]]:
    found: list[tuple[int, int, int, str]] = []
    for pattern_index, (_, pat) in enumerate(PLACEHOLDER_PATTERNS):
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), pattern_index, m.group(0)))
    found.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(start, end, text) for start, end, _idx, text in found]


def self_heal_format_tags(original: str, translation: str) -> str:
    """确定性修复译文的占位符缺口与闭合标签乱序（无模型调用）。

    仅两类修改，不引入原文没有的标记：
    1. **缺口补全**：译文占位符序列是原文序列的子序列（无 extra）→ 缺失
       占位符按原文顺序插回原位置（a-catfiends 丢 {w=0.5}、interdream 丢
       </color>——模型漏写标记是稳定行为，语义译文本身正确）。
    2. **闭合重排**：译文占位符 multiset 与原文相等但顺序不同 → 开标签
       顺序一致时，把闭合标签序列重排为原文顺序（the-keeper 的
       </b></color> 逆序——内容正确只是闭合顺序颠倒）。

    模型新增占位符（extra）或顺序彻底破坏时原样返回（仍由判定失败暴露）。
    """
    src_spans = _placeholder_spans(original)
    dst_spans = _placeholder_spans(translation)
    src_texts = [s[2] for s in src_spans]
    dst_texts = [d[2] for d in dst_spans]
    if src_texts == dst_texts:
        return translation
    if (Counter(src_texts) == Counter(dst_texts)
            and _OPENING_TAG.findall(original) == _OPENING_TAG.findall(translation)
            and _CLOSING_TAG.findall(original) != _CLOSING_TAG.findall(translation)):
        # 闭合标签 multiset 相同且开标签顺序一致 → 重排闭合标签为原文顺序
        closing_iter = iter(_CLOSING_TAG.findall(original))
        return _CLOSING_TAG.sub(lambda match: next(closing_iter), translation)
    # 缺口补全：贪心子序列匹配（译文占位符 = 原文子序列，无 extra）
    missing_idx: list[int] = []
    dst_to_src: dict[int, int] = {}
    i = 0
    for di, dtext in enumerate(dst_texts):
        while i < len(src_texts) and src_texts[i] != dtext:
            missing_idx.append(i)
            i += 1
        if i >= len(src_texts):
            return translation
        dst_to_src[di] = i
        i += 1
    while i < len(src_texts):
        missing_idx.append(i)
        i += 1
    if not missing_idx:
        return translation
    # 字面 \n 缺口不补：换行结构缺失必须由 multiline repair 重建分隔符，
    # 自愈插入会改变行拓扑（补到相邻占位符前 → 空行压缩豁免误放行）
    missing_idx = [i for i in missing_idx
                   if not _LITERAL_NEWLINE.fullmatch(src_texts[i])]
    if not missing_idx:
        return translation
    if len(missing_idx) >= len(dst_texts):
        # 译文保留的占位符 ≤ 缺失量 → 结构锚点不足（模型完全没翻/全丢标签），
        # 补全会把标记堆到末尾（位置全错）→ 交 protected/multiline repair 重建
        return translation
    # 每个缺失占位符插到「其后第一个已匹配译文占位符」之前（末尾缺口 → append）
    by_pos: dict[int, list[str]] = {}
    for mi in missing_idx:
        nxt = next((di for di, si in dst_to_src.items() if si > mi), None)
        pos = dst_spans[nxt][0] if nxt is not None else len(translation)
        by_pos.setdefault(pos, []).append(src_texts[mi])
    for pos in sorted(by_pos, reverse=True):
        translation = (translation[:pos] + "".join(by_pos[pos])
                       + translation[pos:])
    return translation


def validate_translation(original: str, translation: str) -> tuple[bool, list[str], list[str]]:
    """译文必须保留占位符次数与顺序。返回 (是否通过, 缺失, 多余)。"""
    src = extract_placeholders(original)
    dst = extract_placeholders(translation)
    missing_counts = Counter(src) - Counter(dst)
    extra_counts = Counter(dst) - Counter(src)
    missing = []
    extra = []
    for placeholder in src:
        if missing_counts[placeholder] > 0:
            missing.append(placeholder)
            missing_counts[placeholder] -= 1
    for placeholder in dst:
        if extra_counts[placeholder] > 0:
            extra.append(placeholder)
            extra_counts[placeholder] -= 1
    return src == dst, missing, extra


def is_credit_like(text: str) -> bool:
    """署名/版权反模式（软猜测规则）：制作者署名/版权行。

    'A game by Kyuppin' / 'made in 48h' / 'Created by Sam Hogan' /
    '© 2021 Some Studio' 等。用于 is_hard_structural 的署名分支；但
    **确定性显示证据**（typetree m_Text 等 UI 字段）中的署名是真实
    显示文本（lilys-day-off level13 结局画廊实证：'A game by Kyuppin'
    被此规则降级跳过）——extractor 降级闸门据此做证据分层：确定性
    显示条目不被此软猜测降级，只被硬结构规则降级。
    """
    s = text.strip()
    if not s or len(s) > 90:
        return False
    if re.match(r"(?i:^created\s+by\s+[A-Z0-9])", s):
        return True              # created by X（短行，对话不会以此开头）
    if (_CREDIT_ATTRIBUTION.search(s) or _CREDIT_ALIGNED.match(s)
            or _FT_CREDIT.search(s)) and not _SENTENCE_MARKERS.search(s):
        return True              # credit/署名/版权行（无句子虚词）
    if _CREDIT_YEAR_LINE.match(s) and not _SENTENCE_MARKERS.search(s):
        return True              # 人名 + 年份署名行（Darien Gore (Fleebs) 2019）
    return bool(_JAM_CREDIT.match(s))   # 游戏 jam 署名（made in 48h）


def is_hard_structural(text: str) -> bool:
    """Return whether *text* is structural regardless of display provenance."""
    s = text.strip()
    if not s or len(s) < 2:
        return True
    if s.isdigit():
        return True
    if s.startswith(("{", "[")):
        # JSON 序列化字符串（引擎把结构化数据序列化后存成字符串）。
        # 能解析成 JSON 就是数据而非人读文本；翻译会破坏 JSON 语法致游戏崩溃。
        try:
            json.loads(s)
            return True
        except Exception:  # noqa: BLE001 - 非 JSON（对话以 {/[ 开头很常见）
            pass
    if _DEV_TEMPLATE_PLACEHOLDER.match(s):
        # 开发者模板占位（"beast description here" / "Option description here!!!"）：
        # 内容未填写的占位字符串，翻译无意义（真实语料漏检样本）
        return True
    if _URL.match(s) or _ONLY_SYMBOL.match(s) or _HTML_OR_BB.match(s):
        return True
    if _DANGLING_FORMAT_SUFFIX.fullmatch(s):
        return True
    if _DATETIME_FORMAT.match(s):
        return True                  # .NET 日期/时间格式串（HH:mm dd MMMM, yyyy）
    if _ESCAPED_BRACES.search(s):
        return True                  # C# format 转义 {{/}} → 代码/数据模板
    if _COLOR_TABLE_ENTRY.search(s):
        return True                  # 颜色表条目（Gray (HTML/CSS Gray) 等）
    if _PURE_TAG_SEQUENCE.fullmatch(s):
        return True                  # 纯 {tag} 序列（Fungus 样式模板标签行）
    if (_INPUT_ACTION_IDENTIFIER.fullmatch(s)
            or _ASSET_FOLDER.fullmatch(s)
            or _ASSEMBLY_REF.fullmatch(s)
            or _PROTOCOL_RELATIVE_URL.fullmatch(s)
            or _BRACKETED_PATH.fullmatch(s)
            or _CLI_ARG.fullmatch(s)):
        return True
    # 代码注释行（// 前缀）：C#/JS 风格注释不是游戏文本（baldis 实证：
    # resources.assets TextAsset 脚本里 '//        word:replacement:
    # notCaseSensitive' 注释行被模型当文本翻译成乱语）。要求 // 后跟
    # 空白（//host/path 协议相对 URL、//server/share UNC 路径无空白，
    # 已由 _PROTOCOL_RELATIVE_URL/URL 分支处理，不重复拦截）。
    if s.startswith("//") and (len(s) == 2 or s[2].isspace()):
        return True
    # 混合符号 token：无空格、含强代码符号（%#&^$@!|\~）与字母、长度 ≥8
    # 的串多为随机会话 token/加密串/编码数据（baldis 实证：
    # 'xChDC-Gs%OmaMl+g' 模型回显恒败）。'%' 等强符号在正常英文句中
    # 极少独立成串（'100% sure' 有空格不匹配），base64 已单列判定。
    # 先剥 rich text 标签：<color=#fff> 的 # 颜色码不是 token 符号
    if (len(s) >= 8 and _MIXED_SYMBOL_TOKEN.match(
            _STRIP_RICH_TEXT.sub("", s))
            and not _URL.match(s)):
        return True
    # 剥掉富文本标签（<color=...>）后只有数字与符号 → 纯装饰/字符画（▓ 颜色条）
    if not _HAS_LETTER.search(_STRIP_RICH_TEXT.sub("", s)):
        return True
    if _CLONE_SUFFIX.match(s):
        return True                  # Unity 实例化对象名 frameVertical(Clone)
    if _DOT_EXTENSION.match(s):
        return True                  # 点开头扩展名 .spriteatlas
    if _GUID_IDENTIFIER.match(s):
        return True                  # GUID:xxxxxxxx 资源标识符
    if _MASTER_AUDIO_BUS.match(s):
        return True                  # Master Audio 总线行（插件内部音频路径）
    if _I2_PLURAL_BLOCK.search(s):
        return True                  # I2 复数模板（{0:p:mine|mines} 运行时展开）
    if _IL2CPP_MODULE_DEBUG.match(s):
        return True                  # IL2CPP 模块调试行（module.renderOrderPriority:）
    if _REPEATED_PLACEHOLDER_LINE.match(s):
        return True                  # 开发者重复占位行（Hello×4）
    if _UNITY_SYMBOL.match(s) or _PDB_ALT_PATH.match(s):
        return True                  # Unity 内部符号/PDB 调试路径
    if _VERSION_BANNER.match(s):
        return True                  # 版本号横幅（VERSION 0.4.3 保留原文）
    zalgo = _COMBINING_MARKS.findall(s)
    if zalgo and len(zalgo) >= len(_HAS_LETTER.findall(s)):
        return True                  # zalgo 乱码（组合字符 ≥ 字母数）
    if _LOREM_IPSUM.match(s):
        return True                  # Lorem ipsum 占位文本（模型不翻占位符是正常行为）
    if _SHELL_COMMAND.match(s):
        return True                  # Shell 命令（find/tar/rm…不是游戏文本）
    if _KEYBOARD_NOISE.match(s):
        return True                  # 键盘噪音测试文本（asdasdasd / fdji ijsdijn…）
    if _STAR_PREFIXED_WORD.match(s):
        return True                  # 星号前缀词表条目（*shit：脚本示例词）
    if _SECTION_KEY.match(s):
        return True                  # § 键码（§m_quit ###：语言文件键值模板键）
    if _LANG_CODE_WITH_SLASH.match(s):
        return True                  # 语言代码目录标记（EN/ / DE/）
    if _SINGLE_CHAR_KEYMAP_LINES.match(s):
        return True                  # 多行键位映射（k\nm\n/\nh 快捷键提示）
    if _XXXX_PLACEHOLDER_NAME.match(s):
        return True                  # XXXX 占位名（XXXX t'a：未命名角色名）
    if _BASE64.fullmatch(s) and any(char.isdigit() for char in s):
        return True                  # base64 序列化数据（catalog m_BucketDataString）
    if s.startswith("UEsDB") and _BASE64.fullmatch(s):
        return True                  # base64 编码的 ZIP 包（TextAsset 序列化数据，
                                     # PK\x03\x04 魔数；Morfosi level5 str/0 实证——
                                     # 此前 '=' 填充符不在 _BASE64 字符集，fullmatch
                                     # 失败漏网，模型整段回显恒败）
    if len(s) <= 48 and _SDF_FONT.search(s):
        return True                  # TMP SDF 字体资产名（对话不会含 SDF 词）
    if is_credit_like(s):
        return True                  # 署名/版权行（软猜测，见 is_credit_like）
    path_text = s
    if is_interaction_prompt(s):
        for event in interaction_input_events(s):
            if event.kind == "semantic_input":
                path_text = path_text.replace(event.value, "", 1)
    if (_is_full_value_path_or_binding(path_text)
            or _QUALIFIED.match(s)):   # 路径/程序集名/版本号等标识符
        return True
    return False


def should_skip(text: str) -> bool:
    """无需翻译的文本：hard structural 值或无 display provenance 的键风格值。"""
    if is_hard_structural(text):
        return True
    s = text.strip()
    if is_key_style_identifier(s):     # 键风格标识符（ui_newGame / MENU_PLAY / en）
        return True
    return False
