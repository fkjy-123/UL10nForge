"""v2 资源提取：UnityPy 解析 .assets / AssetBundle。
TextAsset 整文本 + MonoBehaviour 序列化原始字节字符串扫描（typetree 不可用时兜底）。"""
from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote

from hanhua.core.engine_strings import (CORE_MENU_SOURCE_TERMS,
                                         display_evidence_tier,
                                         has_display_text_evidence,
                                        is_code_action_binding,
                                        is_engine_string,
                                        is_engine_string_core,
                                        is_interaction_prompt,
                                        is_physical_binding_identifier)
from hanhua.core.extractor import ParsedFile, looks_like_noise_file
from hanhua.core.formats import json_format
from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.placeholders import (DISPLAY_WORDS, is_credit_like,
                                      is_hard_structural, is_key_style_identifier,
                                      should_skip, _HAS_LETTER, _LOG_TEMPLATE_TAIL,
                                      _QUALIFIED, _IDENTIFIER, _WORD_CASE)
from hanhua.core.scanner import (_has_unity_bundle_magic, _is_runtime_file,
                                 _walk_files)
import re as _re

_METHOD_NAME = _re.compile(r"^(?:get|set)_[A-Za-z_][A-Za-z0-9_]*$")
# InputSystem action 路径（Section/Action，每段 1-2 个标识符词）：
# Player/Move、Menu/dPadHoriz、Debug/Warp 0、Forward/Back Tilt。
# 翻译后 InputSystem 按原名查找 action 失败 → 键盘/手柄按键全部无反应
# （真实语料：ivor 323 条、doubleshake 48 条被误标 display 放行）。
# 仅二进制 rawstr 路径使用（_structural_reason），文本文件行扫描不经此规则，
# 因此 "fridge open/close" 类句子不受影响。
_INPUT_ACTION_PATH = _re.compile(
    r"^[A-Za-z][A-Za-z0-9]*(?: [A-Za-z0-9]+)?/"
    r"[A-Za-z][A-Za-z0-9_]*(?: [A-Za-z0-9]+)?$")
_QUALIFIED_TYPE = _re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_+`]*\.)+[A-Z_][A-Za-z0-9_+`]*$")
# 类型引用：`Namespace.Type, Assembly`（如 Fungus.Flowchart, Fungus）。
# 程序集部分不设白名单——`A.B, C` 形态（点连标识符 + 逗号分隔）本身
# 就是 .NET 类型引用信号，显示文本几乎不出现（真实语料：
# level1 str 数组 Fungus.Flowchart, Fungus 曾被误判 natural_language，
# 译成「真菌.流程图」写回，破坏类型引用）。版本/公钥段可选。
_ASSEMBLY_REFERENCE = _re.compile(
    r"^(?:"
    r"[A-Za-z_][A-Za-z0-9_+`]*(?:\.[A-Za-z_][A-Za-z0-9_+`]*)+,\s*"
    r"[A-Za-z_][A-Za-z0-9_.-]*"
    r"|[A-Za-z_][A-Za-z0-9_+`]*,\s*Assembly-[A-Za-z0-9_.-]+"
    r")"
    r"(?:,\s*Version=[^,\s]+(?:,\s*Culture=[^,\s]+,\s*"
    r"PublicKeyToken=[^,\s]+)?)?$",
    _re.I,
)
_LIFECYCLE_METHODS = frozenset({
    "Awake", "Start", "Update", "FixedUpdate", "LateUpdate",
    "OnEnable", "OnDisable", "OnDestroy", "Reset",
})
# 代码驱动 UI 方法名（2026-08-15 minato 实证「no translation found
# for 音频」）：level0 obj 3311 是 [Minato(对象名), audio(子对象名),
# TMPro.TMP_Text(类型引用), SetText(方法名)]——audio 被白名单词规则
# 放行翻译成「音频」，写回后游戏按对象名查找失败。SetText 此前在
# 引擎串过滤中（不贡献 code 信号），导致 direct_code_signal_count
# 只计到 1（TMPro 类型引用），is_code_heavy 判定不足。这些方法名
# 说明该对象文本由代码运行时设置——对象内其余单词是名字/引用，
# 不是静态显示文本（静态按钮对象的 Save/Load 不含这些方法，仍按
# has_ui_evidence 正常放行，不误伤）。
_CODE_DRIVEN_METHODS = frozenset({
    "SetText", "SetActive", "SetActiveGameObject", "SendMessage",
    "SetTextMeshProText", "set_text",
})
_UNITY_CONTROL_STATE_NAMES = frozenset({
    "normal", "highlighted", "pressed", "selected", "disabled",
})
_INPUT_BINDING_NAMES = frozenset({
    "move", "wasd", "fire", "look", "dpad",
    "right click", "square button", "x button", "y button",
    "square/x/y button",
})
# Unity InputSystem 默认模板 action 名——仅当对象含 action map 名
# （InputSystem 对象）时降级为输入绑定，普通游戏里 SELECT 按钮文本不受影响
_INPUTSYSTEM_MAP_NAMES = frozenset({"gameactions"})
_INPUTSYSTEM_ACTION_NAMES = frozenset({
    "select", "cancel", "submit", "click", "point", "scroll",
    "navigate", "move", "look",
})
_TIMELINE_TRACK = _re.compile(
    r"^(?:Activation|Animation|Audio|Control|Group|Marker|Playable|Signal|Cinemachine) "
    r"Track(?:\s*\(\d+\))?$",
    _re.I,
)
# Input System 序列化绑定路径：<Keyboard>/z、<Mouse>/position、<Gamepad>/leftStick。
# 只出现在 InputActionAsset/InputActionMap 配置对象中，是「对象是输入配置」的强信号。
_INPUT_BINDING_PATH = _re.compile(
    r"^<[A-Za-z0-9_.]+>/(?:[A-Za-z0-9_./-]+)?$")
# Input System interactions 触发方式串（Press(behavior=2) 等）——同上，输入配置强信号。
_INPUTSYSTEM_INTERACTION = _re.compile(
    r"^(?:press|hold|tap|slowtap|multitap|doubletap|"
    r"pressandrelease|pressdelay|presspoint)\s*\(.*\)$",
    _re.I,
)
# 引擎配置对象程序集信号：MonoBehaviour 序列化含 m_AssemblyTypeName 程序集限定名，
# 若其中出现 Input System / Timeline 程序集，对象内的名字串都是引擎配置而非显示文本。
_INPUTSYSTEM_ASSEMBLY_SIGNALS = (
    "UnityEngine.InputSystem", "Unity.InputSystem")
_TIMELINE_ASSEMBLY_SIGNALS = (
    "UnityEngine.Timeline", "UnityEngine.Playables", "Unity.Timeline")
# Timeline 对象常见轨道/标记 displayName（不带编号的裸词形式）
_TIMELINE_MARKER_NAMES = frozenset({"markers", "track"})

# Unity Localization 结构标记：出现这些串的对象是 Localization 表/共享数据对象
# （StringTable / SharedTableData）。其中标识符形态的字符串是表键（Key），绝不翻译。
_LOCALIZATION_MARKERS = ("UnityEngine.Localization", "Unity.Localization", "DistributedUIDGenerator")

# UnityEvent 事件绑定对象信号：MonoBehaviour 序列化内嵌 UnityEvent 持久化
# 回调字段（m_PersistentCalls/m_Target/m_MethodName）——方法名/目标名是
# 反射按名绑定键，翻译必断绑（知识库 writeback_case「替换 prefab/资源后
# UnityEvent 事件绑定断裂按钮无反应」转规则：点击回调链断裂 = 按键没反应）。
_UNITYEVENT_SIGNALS = frozenset({
    "m_PersistentCalls", "persistentCalls", "m_Listener",
    "m_Target", "m_MethodName", "m_Arguments",
})

# 署名/credit 形态：作者名 + 作品平台 ID/URL（pixiv/twitter/artstation 等
# 平台名 + 数字 ID 或用户名，或括号包裹）。「林まか (pixiv: 10768714)」
# （doog 实证）是作者署名+作品引用——翻译/半翻损坏引用信息，识别层跳过。
_SIGNATURE_CREDIT_RE = _re.compile(
    r"\(?\b(?:pixiv|twitter|x(?:\s*\(twitter\))?|facebook|instagram|"
    r"artstation|deviantart|newgrounds|sketchfab|youtube|furaffinity|"
    r"booth|fantia)\b\s*[:：]?\s*@?[\w.-]{2,}",
    _re.I,
)

ASSET_SUFFIXES = {".assets", ".ab", ".unity3d", ".bundle", ".pak"}
_BUNDLE_SUFFIXES = frozenset(ASSET_SUFFIXES - {".assets"})
_LEVEL_SCENE = _re.compile(r"^level\d+$")
# 老式布局（Unity ≤4.x）：游戏根目录的 mainData 是无后缀序列化场景索引，
# 含全部场景文本（hotel-paradise 识别不全的根因，见 ISSUES #192）。
# levelN 仅在「同目录存在 mainData」（老式布局证据）时才收——根目录裸
# level1 可能是游戏自有数据文件，拒绝（见 rejects_level_scene_outside_data_tree）。
_LEGACY_SCENE = _re.compile(r"^mainData$")

_LOCALIZATION_TABLE_BUNDLE = _re.compile(
    r"^localization-string-tables-(?P<locale>.+?)_assets_all\.bundle$", _re.I)
_ENGLISH_LOCALE = _re.compile(r"(?:^|[^a-z])english\s*\(en\)(?:[^a-z]|$)", _re.I)


def _string_table_logical_identity(tree: dict, locale: str) -> str | None:
    """Return a locale-independent identity for one StringTable tree."""
    shared = tree.get("m_SharedData")
    if isinstance(shared, dict):
        file_id = shared.get("m_FileID")
        path_id = shared.get("m_PathID")
        if (isinstance(file_id, int) and not isinstance(file_id, bool)
                and isinstance(path_id, int) and not isinstance(path_id, bool)
                and path_id != 0):
            return f"shared:{file_id}:{path_id}"
    name = tree.get("m_Name")
    if not isinstance(name, str) or not name.strip():
        return None
    base = name.strip()
    locale_variants = {
        locale.casefold(), locale.casefold().replace("-", "_"),
        locale.casefold().replace("_", "-"),
    }
    language = locale.casefold().replace("_", "-").split("-", 1)[0]
    locale_variants.add(language)
    for suffix in sorted(locale_variants, key=len, reverse=True):
        for separator in ("_", "-", " "):
            marker = separator + suffix
            if base.casefold().endswith(marker):
                return "name:" + base[:-len(marker)].casefold()
    return "name:" + base.casefold()


def _localization_bundle_probe(
        path: Path) -> tuple[frozenset[str], str] | None:
    """Read stable StringTable identities and one locale without mutation."""
    if not path.is_file():
        return None
    from UnityPy import Environment
    env = Environment()
    locales: set[str] = set()
    identities: set[str] = set()
    try:
        env.load([str(path)])
        for obj in env.objects:
            try:
                tree = obj.read_typetree()
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(tree, dict) or not _is_string_table_tree(tree):
                continue
            locale = (tree.get("m_LocaleId") or {}).get("m_Code")
            if isinstance(locale, str) and locale.strip():
                locale = locale.strip()
                identity = _string_table_logical_identity(tree, locale)
                if identity:
                    locales.add(locale)
                    identities.add(identity)
    except Exception:  # noqa: BLE001
        return None
    finally:
        from hanhua.core.unity.writer import _dispose_environment
        _dispose_environment(env)
    if len(locales) != 1 or not identities:
        return None
    return frozenset(identities), next(iter(locales))


def _localization_bundle_locale(path: Path) -> str | None:
    """Read a unique StringTable locale without mutating the source bundle."""
    probe = _localization_bundle_probe(path)
    return probe[1] if probe else None


def _is_english_locale(locale: str) -> bool:
    return locale.casefold().replace("_", "-").split("-", 1)[0] == "en"


def _is_localization_bundle_probe_candidate(path: Path) -> bool:
    return bool(
        _LOCALIZATION_TABLE_BUNDLE.match(path.name)
        or path.suffix.casefold() in _BUNDLE_SUFFIXES
        or _has_unity_bundle_magic(path)
    )


def _prefer_source_locale_bundles(paths: list[Path]) -> list[Path]:
    """多语言 StringTable 并存时只选择英文源表，其余资源原样保留。"""
    probes = {
        path: _localization_bundle_probe(path)
        for path in paths
        if _is_localization_bundle_probe_candidate(path)
    }
    groups: dict[frozenset[str], list[tuple[Path, str]]] = {}
    for path, probe in probes.items():
        if probe is not None:
            identity, locale = probe
            groups.setdefault(identity, []).append((path, locale))
    excluded: set[Path] = set()
    for group in groups.values():
        if any(_is_english_locale(locale) for _, locale in group):
            excluded.update(
                path for path, locale in group
                if not _is_english_locale(locale))

    remaining = [path for path in paths if path not in excluded]
    localization = [
        path for path in remaining
        if _LOCALIZATION_TABLE_BUNDLE.match(path.name)]
    tree_locales = {
        path: (probes[path][1] if probes[path]
               else _localization_bundle_locale(path))
        for path in localization}
    known_tree_locales = [locale for locale in tree_locales.values() if locale]
    if known_tree_locales:
        english = [path for path, locale in tree_locales.items()
                   if locale and _is_english_locale(locale)]
    else:
        english = [p for p in localization if _ENGLISH_LOCALE.search(p.name)]
    if not english:
        # No verified English source: retain every locale rather than guessing.
        return remaining
    localization_set = set(localization)
    english_set = set(english)
    return [p for p in remaining
            if (p not in localization_set or p in english_set
                or (known_tree_locales and tree_locales.get(p) is None))]


def _asset_file_name(obj) -> str:
    asset_file = getattr(obj, "assets_file", None)
    return str(getattr(asset_file, "name", "") or "")


def _object_identity(obj) -> tuple[str, int]:
    """返回可跨 UnityPy 环境重建的 SerializedFile 名称 + Path ID。"""
    return _asset_file_name(obj), int(obj.path_id)


def _is_string_table_tree(tree: dict) -> bool:
    locale_node = tree.get("m_LocaleId")
    locale = locale_node.get("m_Code") if isinstance(locale_node, dict) else None
    rows = tree.get("m_TableData")
    if not isinstance(locale, str) or not isinstance(rows, list):
        return False
    return all(
        isinstance(row, dict) and row.get("m_Id") is not None
        and isinstance(row.get("m_Localized"), str)
        for row in rows
    )


def _localization_entries_from_tree(file_id: str, obj_path_id: int,
                                    tree: dict, asset_file_name: str = "") -> list[TextEntry]:
    """从 Unity Localization StringTable 类型树中只提取显示值。"""
    locale = (tree.get("m_LocaleId") or {}).get("m_Code")
    rows = tree.get("m_TableData")
    if not locale or not isinstance(rows, list):
        return []
    entries: list[TextEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        entry_id = row.get("m_Id")
        value = row.get("m_Localized")
        if entry_id is None or not isinstance(value, str) or not value.strip():
            continue
        if is_hard_structural(value):
            # I2 复数模板（{0:p:mine|mines}）等结构值：模型必失败回显且
            # 翻译会破坏 plural 语法（minato 真实样本）
            continue
        prefix = f"asset#{asset_file_name}#{obj_path_id}" if asset_file_name else f"asset#{obj_path_id}"
        meta = {
            "kind": "localization",
            "obj": obj_path_id,
            "entry_id": entry_id,
            "locale": locale,
            "table": tree.get("m_Name", ""),
            "confidence": "high",
            "role": "display",
            "disposition": "translate",
            "reason": "localization_table_value",
        }
        if asset_file_name:
            meta["asset_file"] = asset_file_name
        entries.append(TextEntry(
            file_id=file_id,
            key_path=f"{prefix}/loc/{entry_id}",
            original=value,
            meta=meta,
        ))
    return entries


# 显示字段白名单登记制（识别 L7）：每字段带出处分组——新增字段必须
# 登记来源（指南 §3.2「所有 SerializedFile 对象的字符串字段」或游戏
# 实证锚点），防止无依据滥加。表单通用名（text/label）是双刃剑：误
# 放行键名会淹没真实文本；出处让每次新增可审计（0.14.1 证据分层）。
@dataclasses.dataclass(frozen=True)
class _DisplayField:
    name: str       # casefold 字段名（m_ 前缀由 _normalized_field_name 剥离）
    group: str      # 出处分组：ui / dialogue / locale / misc


_TYPETREE_DISPLAY_FIELD_ROWS: tuple[_DisplayField, ...] = (
    # ui：常见 UI 标签/提示字段（指南 §3.2）
    _DisplayField("text", "ui"), _DisplayField("label", "ui"),
    _DisplayField("title", "ui"), _DisplayField("description", "ui"),
    _DisplayField("displayname", "ui"),
    _DisplayField("tooltip", "ui"), _DisplayField("hint", "ui"),
    _DisplayField("prompt", "ui"), _DisplayField("placeholder", "ui"),
    _DisplayField("heading", "ui"), _DisplayField("header", "ui"),
    _DisplayField("footer", "ui"),
    # dialogue：对话/字幕/选项字段（指南 §3.2；Fungus/对话系统实证）
    _DisplayField("dialogue", "dialogue"), _DisplayField("line", "dialogue"),
    _DisplayField("lines", "dialogue"), _DisplayField("subtitle", "dialogue"),
    _DisplayField("message", "dialogue"), _DisplayField("messages", "dialogue"),
    _DisplayField("content", "dialogue"), _DisplayField("caption", "dialogue"),
    _DisplayField("question", "dialogue"), _DisplayField("answer", "dialogue"),
    _DisplayField("choice", "dialogue"), _DisplayField("choices", "dialogue"),
    _DisplayField("dialoguetext", "dialogue"),
    _DisplayField("questiontext", "dialogue"),
    # locale：本地化表字段（指南 §3.2；Localization 表实证）
    _DisplayField("singular", "locale"), _DisplayField("plural", "locale"),
    _DisplayField("format", "locale"), _DisplayField("template", "locale"),
    _DisplayField("prefix", "locale"), _DisplayField("suffix", "locale"),
    # misc：叙事/提示杂项（指南 §3.2）
    _DisplayField("objective", "misc"), _DisplayField("lore", "misc"),
    _DisplayField("bio", "misc"), _DisplayField("error", "misc"),
    _DisplayField("body", "misc"), _DisplayField("details", "misc"),
    _DisplayField("summary", "misc"), _DisplayField("greeting", "misc"),
    _DisplayField("farewell", "misc"), _DisplayField("notice", "misc"),
    _DisplayField("warning", "misc"), _DisplayField("help", "misc"),
)
# 派生 frozenset 保持既有接口（大小写归一后成员判定）。"name" 有意
# 排除——m_Name 是每个对象的标识名（inspector 标签/查找键），翻译会
# 淹没真实文本。
_TYPETREE_DISPLAY_FIELDS = frozenset(
    f.name for f in _TYPETREE_DISPLAY_FIELD_ROWS)
_TYPETREE_STRUCTURAL_FIELDS = frozenset(
    {"key", "keys", "id", "method", "binding", "path", "property", "code"})
# Unity 惯例不可变字段（镜像 writer._IMMUTABLE_FIELD_NAMES，casefold 化以
# 拦截 m_name/M_Name 等变体；裸 name 字段不受影响）。写回闸门同样拦截，
# 扫描端先拦避免 UI 展示不可写条目（review 实证）。
# TextAsset 数据文件判定：行内 ≥3 字母单词（fp_level_* 数据行实证）
_WORD_TOKEN = _re.compile(r"[A-Za-z]{3,}")
_TYPETREE_IMMUTABLE_FIELD_NAMES = frozenset(
    name.casefold() for name in {
        "m_Name", "m_Key", "m_Id", "m_EntryID", "m_GUID",
        "m_FileID", "m_PathID", "m_Path", "m_Address",
        "m_ControlPath", "m_Action", "m_ActionMap", "m_Script",
        "m_ClassName", "m_Namespace",
        "m_LocaleIdentifier", "m_LocaleCode", "m_SharedData",
    })
# 每对象候选条目上限：VisualTreeAsset 等深层结构可能含数千叶子，
# 防止「低置信证据层」膨胀数据库（识别 ≠ 全入库）。
_MAX_CANDIDATES_PER_OBJECT = 200


def _normalized_field_name(value: object) -> str:
    name = str(value).casefold()
    return name[2:] if name.startswith("m_") else name


def _field_name_tokens(value: object) -> frozenset[str]:
    name = str(value)
    if name[:2].casefold() == "m_":
        name = name[2:]
    separated = _re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return frozenset(
        token for token in _re.split(r"[^A-Za-z0-9]+", separated.casefold())
        if token)


def _encode_field_path(field_path: list[str | int]) -> str:
    """Encode path segments reversibly while retaining key/index types."""
    return "/".join(
        f"i:{segment}" if isinstance(segment, int)
        else f"k:{quote(segment, safe='')}"
        for segment in field_path)


def _decode_field_path(locator: str) -> list[str | int]:
    decoded: list[str | int] = []
    for segment in locator.split("/") if locator else []:
        if segment.startswith("i:"):
            decoded.append(int(segment[2:]))
        elif segment.startswith("k:"):
            decoded.append(unquote(segment[2:]))
        else:
            raise ValueError(f"invalid field path segment: {segment}")
    return decoded


_TYPE_DESCRIPTOR = _re.compile(
    r"^[A-Za-z_]\w* [A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+ [A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")


def _looks_like_type_descriptor(text: str) -> bool:
    """Unity Localization/序列化的类型描述字符串：``TypeName Namespace Assembly``。

    resonance-of-the-ocean 实测：SmartFormat 配置对象里
    "Parser UnityEngine.Localization.SmartFormat.Core.Parsing Unity.Localization"
    是类型引用（游戏按名反射加载），当文本翻译后 save_typetree 直接抛
    ValueError（Referenced type not found）。形态：恰好 3 段——段 1 标识符
    （类名）、段 2 点分命名空间、段 3 点分程序集。真实游戏文本（"Open the
    File. Read docs." 等）因段间标点/段内含点位置不符而被排除，误伤极低。
    """
    return bool(_TYPE_DESCRIPTOR.match(text.strip()))


def _typetree_string_entries(
        file_id: str, obj_path_id: int, tree: dict,
        asset_file_name: str = "",
        skipped: dict[str, int] | None = None
) -> tuple[list[TextEntry], list[TextEntry]]:
    """全叶子字符串分类：返回 (display 条目, 低置信候选条目)。

    display 层（可翻译）：
    - 白名单字段名（text/label/title/…）→ high；
    - 句子形态 / 显示证据（含对象级值特征）→ medium。
    候选层（不可翻译，仅作证据留档）：
    - 其余非键风格字符串 → status=skipped, role="candidate", confidence=low。
      写回与质量门禁（is_actionable_translation 要求 role=display 且
      confidence≠low）天然排除——「过滤不是删除」（指南 §2.4）。
    键风格标识符（should_skip）不产生条目——它们在各处已是键。
    """
    display: list[TextEntry] = []
    candidates: list[TextEntry] = []
    prefix = (f"asset#{asset_file_name}#{obj_path_id}"
              if asset_file_name else f"asset#{obj_path_id}")
    leaves: list[tuple[list[str | int], str, str, bool]] = []

    def visit(value, path: list[str | int], structural: bool = False) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized = _normalized_field_name(key)
                # m_Name 等 Unity 惯例对象标识字段（Inspector 标题/Find 查找
                # 键/引用/地址）：翻译破坏对象查找与回写（immutable_field_
                # protected 会拦截）——即使对象含值证据也不得升格 display
                # （doubleshake 实证）。casefold 拦截 m_name/M_Name 变体；
                # 裸 name 字段（对话角色名等）不受影响。
                blocked = structural or bool(
                    _field_name_tokens(key) & _TYPETREE_STRUCTURAL_FIELDS) \
                    or key.casefold() in _TYPETREE_IMMUTABLE_FIELD_NAMES
                child_path = [*path, key]
                if isinstance(child, str) and child.strip():
                    leaves.append((child_path, child, normalized, blocked))
                else:
                    visit(child, child_path, blocked)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, [*path, index], structural)

    visit(tree, [])

    # 对象级值特征：任一叶子是显示证据（句子/白名单字段/显示证据形态）
    # → 其余非键字符串也升 display（与 raw scan 的 obj_has_values 一致）
    has_value_evidence = any(
        not blocked and (
            normalized in _TYPETREE_DISPLAY_FIELDS
            or _has_sentence_shape(text.strip())
            or has_display_text_evidence(text)
        )
        for _, text, normalized, blocked in leaves)

    def append(kind: str, path: list[str | int], text: str, reason: str,
               confidence: str, status: str, role: str,
               extra_meta: dict | None = None) -> None:
        meta = {
            "kind": kind, "obj": obj_path_id, "field_path": path,
            "confidence": confidence, "role": role,
            "disposition": "translate" if role == "display" else "structural",
            "reason": reason,
            "obj_has_values": has_value_evidence,
        }
        if extra_meta:
            meta.update(extra_meta)
        if asset_file_name:
            meta["asset_file"] = asset_file_name
        target = display if role == "display" else candidates
        target.append(TextEntry(
            file_id=file_id,
            key_path=f"{prefix}/field/{_encode_field_path(path)}",
            original=text, status=status, meta=meta))

    # R5 留档：键/标识符/结构值/类型引用不再静默 continue（限量样本 +
    # skipped_count 承载真实总数），typetree 候选层同理。
    prefilter_counts: dict[str, int] = {}
    for path, text, normalized, blocked in leaves:
        if blocked:
            continue
        stripped = text.strip()
        if normalized in _TYPETREE_DISPLAY_FIELDS:
            append("typetree", path, text, "typetree_display_field",
                   "high", "pending", "display")
        elif (should_skip(text) or is_hard_structural(text)
              or _looks_like_type_descriptor(text)):
            prefilter = ("key_identifier" if should_skip(text)
                         else "hard_structural" if is_hard_structural(text)
                         else "type_descriptor")
            # 计数键带 prefilter_ 前缀 = 样本 meta 的 reason（回写同形）
            key = f"prefilter_{prefilter}"
            count = prefilter_counts[key] = \
                prefilter_counts.get(key, 0) + 1
            if count <= _PREFILTER_SAMPLE_LIMIT:
                append("typetree_prefilter", path, text,
                       f"prefilter_{prefilter}", "low", STATUS_SKIPPED,
                       "candidate", {"prefilter": prefilter,
                                     "skipped_count": count})
        elif (_has_sentence_shape(stripped) or has_display_text_evidence(text)
              or has_value_evidence):
            append("typetree", path, text, "typetree_display_evidence",
                   "medium", "pending", "display")
        elif len(candidates) < _MAX_CANDIDATES_PER_OBJECT:
            append("typetree_candidate", path, text, "typetree_candidate",
                   "low", STATUS_SKIPPED, "candidate")
        elif skipped is not None:
            # 识别 C5：候选层 200 上限不再静默截断——超限叶子无条目也无
            # 聚合计数时，整类截断在报告里不可见（与 R5「样本+skipped_
            # count」语义不一致）。按 reason 聚合计数留档，报告可见
            # 「该对象候选超限 N」。
            skipped["typetree_candidate_truncated"] = \
                skipped.get("typetree_candidate_truncated", 0) + 1
    _finalize_skipped_counts(display, prefilter_counts)
    _finalize_skipped_counts(candidates, prefilter_counts)
    return display, candidates


def find_asset_files(
        game_dir: str | Path, *, data_dir: str | Path | None = None,
        exclude_roots: Iterable[str | Path] = ()) -> list[Path]:
    """发现 Unity 二进制资源，应用与文本扫描一致的运行时排除。

    识别依据是内容探测（UnityFS 魔数 / SerializedFile 头部自洽 / WebFile 魔数），
    不是扩展名：
    - 任意后缀/无后缀文件只要命中即收（无后缀 level 场景、.dat 伪装资源、
      .bytes 数据文件此前整类漏检，指南 §3.3）；
    - 注意 Addressables catalog.bin 不是 SerializedFile（BinaryStorageBuffer，
      kMagic 0x0DE38942），头部大端自洽检查会拒绝它，由 Addressables 管线
      的字节级 CRC 替换处理（catalog 无文本，无需解析）；
    - .bytes/.dat/.bin 伪装文件只在探测确认 Unity 容器时收（纯文本 .bytes
      由文本扫描负责，避免 UnityPy 解析失败）。
    """
    from hanhua.core.scanner import (_BINARY_SUFFIXES, probe_file_kind)
    game_dir = Path(game_dir)
    explicit_data_dir = Path(data_dir) if data_dir is not None else None
    all_files = [p for p in _walk_files(game_dir, exclude_roots=exclude_roots)
                 if not _is_runtime_file(p, game_dir)]
    # 老式布局证据：mainData 所在目录（根目录裸 levelN 需与之同目录才收）
    legacy_data_dirs = {p.parent for p in all_files
                        if not p.suffix and _LEGACY_SCENE.fullmatch(p.name)}
    _UNITY_KINDS = frozenset({"unity", "serialized", "webfile"})
    found: list[Path] = []
    for p in all_files:
        suffix = p.suffix.lower()
        relative_parent_parts = p.relative_to(game_dir).parts[:-1]
        is_level_scene = (
            _LEVEL_SCENE.fullmatch(p.name)
            and (
                (explicit_data_dir is not None
                 and p.is_relative_to(explicit_data_dir))
                or any(part.endswith("_Data") for part in relative_parent_parts)
            )
        )
        is_legacy_main = (
            not p.suffix and _LEGACY_SCENE.fullmatch(p.name))
        is_legacy_level = (
            not p.suffix and _LEVEL_SCENE.fullmatch(p.name)
            and p.parent in legacy_data_dirs)
        if is_level_scene or is_legacy_main or is_legacy_level:
            found.append(p)
            continue
        if suffix in ASSET_SUFFIXES and suffix != ".bytes":
            found.append(p)
            continue
        if suffix in _BINARY_SUFFIXES:
            continue
        kind = probe_file_kind(p)
        if kind in _UNITY_KINDS:
            if suffix == ".bytes" and kind == "unity":
                found.append(p)
            elif suffix != ".bytes":
                found.append(p)
            continue
    return _prefer_source_locale_bundles(sorted(found))


_MAX_RAW_STRING_BYTES = 4096


def scan_strings(raw: bytes, min_len: int = 3,
                 max_len: int = _MAX_RAW_STRING_BYTES) -> list[tuple[int, str]]:
    """对齐扫描 Unity 序列化字符串（int32 长度头 + UTF-8）。返回 [(字节偏移, 文本)]。"""
    out: list[tuple[int, str]] = []
    for i in range(0, len(raw) - 3, 4):
        length = int.from_bytes(raw[i:i + 4], "little")
        data_offset = i + 4
        data_end = data_offset + length
        aligned_end = data_end + (-data_end % 4)
        if not (0 < length <= max_len and aligned_end <= len(raw)):
            continue
        if any(raw[data_end:aligned_end]):
            continue
        chunk = raw[data_offset:data_end]
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if "\x00" in text or len(text.strip()) < min_len:
            continue
        if not all(char.isprintable() or char in "\n\r\t" for char in text):
            continue
        out.append((data_offset, text))
    return out


_SHORT_LENGTH_HEADER = _re.compile(
    rb"(?=(?:[\x03-\xff][\x00-\x0f]|\x00[\x01-\x10])\x00\x00)")


def _scan_unaligned_display_strings(
        raw: bytes, occupied_offsets: set[int], min_len: int = 3,
        max_len: int = _MAX_RAW_STRING_BYTES) -> list[tuple[int, str]]:
    """Recover strongly display-like ASCII strings whose length header is shifted.

    The fallback searches only valid little-endian length headers up to the raw
    string safety bound,
    rather than walking every byte as a candidate.  This keeps large Unity objects
    cheap to scan and prevents arbitrary printable runs from becoming write targets.
    """
    out: list[tuple[int, str]] = []
    for match in _SHORT_LENGTH_HEADER.finditer(raw):
        header_offset = match.start()
        data_offset = header_offset + 4
        if data_offset in occupied_offsets or header_offset % 4 == 0:
            continue
        length = int.from_bytes(raw[header_offset:data_offset], "little")
        data_end = data_offset + length
        aligned_end = data_end + (-data_end % 4)
        if not (min_len <= length <= max_len and aligned_end <= len(raw)):
            continue
        if any(raw[data_end:aligned_end]):
            continue
        try:
            text = raw[data_offset:data_end].decode("utf-8")
        except UnicodeDecodeError:
            continue
        if ("\x00" in text
                or not all(char.isprintable() or char in "\n\r\t" for char in text)
                or not has_display_text_evidence(text)):
            continue
        out.append((data_offset, text))
    return out


_is_engine_string = is_engine_string   # 兼容别名（公共层 engine_strings.py）


def _structural_reason(text: str) -> str | None:
    """返回可确定解释的 raw 结构角色；None 表示仍需对象级判断。"""
    stripped = text.strip()
    if _INPUT_ACTION_PATH.match(stripped):
        return "input_action_path"
    if _INPUT_BINDING_PATH.match(stripped):
        return "input_binding"
    if is_code_action_binding(stripped):
        return "code_action_binding"
    if is_physical_binding_identifier(stripped):
        return "input_binding"
    if stripped.casefold() in _INPUT_BINDING_NAMES:
        return "input_binding"
    if _METHOD_NAME.match(stripped):
        return "method_name"
    if _QUALIFIED_TYPE.fullmatch(stripped) or _ASSEMBLY_REFERENCE.fullmatch(stripped):
        return "type_reference"
    if stripped == "New Text":
        return "default_placeholder"
    if _TIMELINE_TRACK.match(stripped):
        return "timeline_track"
    # 署名/credit 形态（doog 实证「林まか (pixiv: 10768714)」被当显示文本
    # 放行后模型改动大小写/半翻——作者署名+作品 ID 是引用信息不是翻译
    # 内容，翻译反而损坏署名信息）→ 结构跳过。
    if _SIGNATURE_CREDIT_RE.search(stripped):
        return "signature_credit"
    return None


def _has_sentence_shape(text: str) -> bool:
    # R3 统一阈值：句子档 = 句末标点或 ≥3 词（display_evidence_tier）。
    # 旧的「≥10 字符含空格即句子」把 'Player Idle'/'White Flash'/'Grass
    # Shader'（2 词引擎配置名）误判为句子放行；2 词短语归 phrase 档，
    # 由对象级证据（组件对象/UI 控件/白名单）决定放行与否。
    return display_evidence_tier(text.strip()) == "sentence"


# R5：预过滤留档样本上限——每对象每原因最多保留 N 条样本条目（防止
# 键列表对象/引擎串密集对象条目爆炸），完整计数由首条样本的
# skipped_count 承载，报告按 reason 聚合可得真实总数。
_PREFILTER_SAMPLE_LIMIT = 10


def _skipped_sample_entry(file_id: str, key_path: str, text: str, *,
                          kind: str, reason: str, count: int,
                          extra_meta: dict | None = None) -> TextEntry | None:
    """静默跳过限量样本（识别 L1：mono/il2cpp/text 提取器统一留档）。

    rawstr/typetree 路径 R5 已用 _prefilter_entry 留档；mono/il2cpp
    此前只有计数（skipped_reasons 聚合）——被跳过的具体内容不可见，
    用户无法区分「确为该跳」与「该翻未翻」。本工具为计数叠加限量
    样本条目（status=skipped，role=structural，skipped_count 承载
    真实总数）：内容可审计、报告聚合可得真数。超过样本上限返回
    None（防条目爆炸——样本数 ≠ 总数）。count 是累计值，提取函数
    末尾由 _finalize_skipped_counts 统一回写为该单元最终计数。"""
    if count > _PREFILTER_SAMPLE_LIMIT:
        return None
    meta = {
        "kind": kind, "confidence": "low", "role": "structural",
        "disposition": "structural", "reason": reason,
        "skipped_count": count,
    }
    if extra_meta:
        meta.update(extra_meta)
    return TextEntry(file_id=file_id, key_path=key_path, original=text,
                     status=STATUS_SKIPPED, meta=meta)


def _prefilter_entry(file_id: str, obj_path_id: int, idx: int, offset: int,
                     text: str, prefilter: str, count: int,
                     asset_file_name: str = "") -> TextEntry:
    """预过滤留档条目（审计 R5）：被引擎串/键标识符/高频串过滤的字符串
    不再静默丢弃，产生限量样本（status=skipped，role=structural）供审计。

    count = 该对象内同 prefilter 原因的累计跳过数；提取函数末尾统一
    回写为最终计数（_finalize_skipped_counts），报告按单元取 max 聚合
    即真实总数（样本数不等于总数）。
    """
    prefix = (f"asset#{asset_file_name}#{obj_path_id}"
              if asset_file_name else f"asset#{obj_path_id}")
    meta = {
        "kind": "rawstr", "obj": obj_path_id, "offset": offset,
        "confidence": "low", "role": "structural",
        "disposition": "structural",
        "reason": f"prefilter_{prefilter}",
        "prefilter": prefilter,
        "skipped_count": count,
    }
    if asset_file_name:
        meta["asset_file"] = asset_file_name
    return TextEntry(file_id=file_id, key_path=f"{prefix}/str/{idx}",
                     original=text, status=STATUS_SKIPPED, meta=meta)


def _finalize_skipped_counts(entries: list[TextEntry],
                             *count_sources: dict[str, int]) -> None:
    """样本计数回写（聚合语义修正）：限量样本的 skipped_count 是累计
    计数（1..10），报告聚合需真实总数——提取函数末尾用最终计数统一
    回写（同 reason 的样本最终值相同），消费端按 (file_id, reason, obj)
    去重取 max 即真数。样本条目标识 = meta 含 skipped_count（真实行无
    此键）；count_sources 按样本 meta 的 reason 键查最终值（typetree/
    rawstr 的 prefilter 计数键带 prefilter_ 前缀，与样本 reason 同形）。"""
    for e in entries:
        if "skipped_count" not in e.meta:
            continue
        reason = e.meta.get("reason") or ""
        for src in count_sources:
            final = src.get(reason)
            if isinstance(final, int) and final > 0:
                e.meta["skipped_count"] = final
                break


def _is_scriptable_object_shape(raw: bytes) -> bool:
    """MonoBehaviour 头部 m_GameObject 引用为空 → ScriptableObject 形态。

    资源配置对象（Timeline 剪辑/TrackAsset/InputActionAsset 等）没有
    m_GameObject（头部 12 字节全零）；场景组件对象（UI 脚本/对话组件等）带
    m_GameObject 引用（非零）。2019.3 及老版 PPtr 为 4+4 字节，新版本 4+8——
    空引用两种布局前 12 字节都全零，组件两种布局都非零（fileID=0 时 pathID
    落在第 4 或第 8 字节起）。
    """
    return len(raw) >= 12 and raw[:12] == b"\x00" * 12


# 识别 L8：高频串阈值相对化——硬编码 40 对小游戏不可达（该跳未跳、
# doubleshake 实证大游戏噪音串全跳）。相对阈值 = max(绝对下限,
# min(旧绝对阈值 40, 总出现次数 × 比例))：小游戏 ≥15 次即判高频
# （修复该跳未跳），大游戏封顶 40（保持升级前判定，噪音串全跳行为
# 不回归——全面复盘审查钉死：>20k 规模相对阈值放大有未验证回归面）。
_HIGH_FREQ_ABS_MIN = 15     # 绝对下限（对象重复/小游戏也适用）
_HIGH_FREQ_RATIO = 0.002    # 占总出现次数比例（小游戏相对收紧）
_HIGH_FREQ_CAP = 40         # 旧硬编码阈值（大游戏封顶，不改变既有判定）

# 识别 L6：确定性脚本类名（PPtr m_Script 解析）——包内脚本（DLL 编译）
# 的 MonoScript 对象在同类文件里，FileID=0 可解析；内建类型（FileID≠0）
# 解析不到，靠串池信号兜底。类名是确定性证据，优先于串池猜类。
_INPUT_SYSTEM_SCRIPT_CLASSES = frozenset({
    "InputActionAsset", "InputActionMap", "PlayerInput",
    "InputActionReference", "InputControlScheme",
})
_TIMELINE_SCRIPT_CLASSES = frozenset({
    "TimelineAsset", "PlayableDirector",
})


def _script_class_of(tree: dict, obj) -> str:
    """确定性脚本类名（识别 L6）：typetree m_Script PPtr（FileID=0）
    指向同文件 MonoScript → m_Name。解析失败返回 ""（串池信号兜底，
    不因解析失败改变既有判定）。"""
    pptr = tree.get("m_Script")
    if not isinstance(pptr, dict) or pptr.get("m_FileID") != 0:
        return ""
    assets_file = getattr(obj, "assets_file", None)
    objects = getattr(assets_file, "objects", None)
    if not isinstance(objects, dict):
        return ""
    mono = objects.get(pptr.get("m_PathID"))
    if mono is None:
        return ""
    if str(getattr(getattr(mono, "type", None), "name", "")) != "MonoScript":
        return ""
    try:
        st = mono.read_typetree()
    except Exception:  # noqa: BLE001
        return ""
    name = st.get("m_Name") if isinstance(st, dict) else None
    return str(name) if isinstance(name, str) else ""


def _high_freq_threshold(freq: dict[str, int]) -> int:
    """高频串相对阈值（识别 L8）：基于全文件 raw 串出现总次数缩放，
    封顶 _HIGH_FREQ_CAP——大游戏（total>20k 时相对值超 40）保持升级前
    判定，小游戏相对收紧。"""
    total = sum(freq.values())
    return max(_HIGH_FREQ_ABS_MIN,
               min(_HIGH_FREQ_CAP, int(total * _HIGH_FREQ_RATIO)))


def _raw_string_entries(file_id: str, obj_path_id: int, raw: bytes,
                        freq: dict[str, int], asset_file_name: str = "",
                        freq_threshold: int | None = None,
                        script_class: str = "") -> list[TextEntry]:
    """MonoBehaviour 原始字节扫描 + 智能过滤。

    关键规则（多层防线，防止把键名当文本翻译）：
    1) 同对象重复字符串（I2/字典结构键值对）：第一次出现是「键」，最后一次是「值」。
    2) 键风格标识符（ui_newGame / MENU_PLAY / en）：should_skip 直接剔除。
    3) 对象级键列表判定：对象内键风格标识符占绝大多数（≥85% 且 ≥3 个），或含
       Unity Localization 结构标记 → 该对象是 SharedTableData 等键存储结构，
       其中全部标识符形态字符串都是键。
    4) 单词式写法（Bold / WASD / Move / Fire）**条件放行**：单词式字符串只有
       在「值特征对象」中才是显示文本（Localization 表值 CREDITOS / SETTINGS）；
       在无值特征的配置/代码型对象（InputActionAsset、UI 样式等）里是
       绑定名/枚举名/引擎名——游戏按原名查找，翻译必然破坏功能（输入失效）。
       值特征 = 对象含 Localization 标记，或含句子形态字符串（标点结尾或长句）。
    5) 预过滤（引擎串/键风格标识符/全游戏高频串）不静默丢弃（R5）：产生
       限量样本条目（status=skipped，带 reason）供审计——用户能区分
       「日志/键」与「该翻未翻」，且对象级统计可告警（消灭哑信号）。
    """
    aligned = scan_strings(raw)
    recovered = _scan_unaligned_display_strings(
        raw, {offset for offset, _ in aligned})
    scanned_with_mode = sorted(
        [(offset, text, "aligned") for offset, text in aligned]
        + [(offset, text, "unaligned") for offset, text in recovered],
        key=lambda item: item[0],
    )
    if freq_threshold is None:
        freq_threshold = _high_freq_threshold(freq)
    scanned = [(idx, offset, s) for idx, (offset, s, _) in enumerate(scanned_with_mode)]
    scan_modes = {offset: mode for offset, _, mode in scanned_with_mode}
    # 每个字符串在对象内的出现次数
    counts: dict[str, int] = {}
    for _, _, s in scanned:
        counts[s] = counts.get(s, 0) + 1
    # 标记串（UnityEngine.Localization 等程序集名）本身会被引擎过滤剔除，
    # 因此标记检测必须在完整扫描列表上做，而不是过滤后的 non_engine。
    has_marker = any(m in s for s in (s for _, _, s in scanned) for m in _LOCALIZATION_MARKERS)
    # 每个字符串已出现次数（用于判断是否最后一次）
    seen: dict[str, int] = {}
    entries: list[TextEntry] = []
    non_engine: list[str] = []
    prefilter_counts: dict[str, int] = {}
    for idx, offset, s in scanned:
        seen[s] = seen.get(s, 0) + 1
        is_last = seen[s] == counts[s]
        structural_reason = _structural_reason(s)
        interaction_prompt = (
            structural_reason is None and is_interaction_prompt(s)
        )
        strong_display_evidence = (
            interaction_prompt
            or (structural_reason is None and has_display_text_evidence(s))
        )
        # R5 预过滤留档：引擎串/键风格标识符/全游戏高频串不再静默 continue。
        # 产生限量样本条目（status=skipped，带 reason）供审计与报告聚合
        # ——用户能区分「日志/键（该跳）」与「该翻未翻（误跳）」（审计 R5：
        # the-supper 893 条 unverified 零告警的机制根源是静默丢弃）。
        # 注意：should_skip/freq 串仍进 non_engine（与原语义一致——它们是
        # 对象字符串池成员，贡献对象级值证据；只有引擎串不进池）。
        if _is_engine_string(s) and structural_reason is None:
            prefilter = "engine_string"
        else:
            non_engine.append(s)
            if should_skip(s) and structural_reason is None:
                prefilter = "key_identifier"
            elif (freq.get(s, 0) >= freq_threshold
                  and not strong_display_evidence):
                prefilter = "high_frequency"
            else:
                prefilter = None
        if prefilter is not None:
            # 计数键带 prefilter_ 前缀 = 样本 meta 的 reason（回写同形）
            key = f"prefilter_{prefilter}"
            count = prefilter_counts[key] = \
                prefilter_counts.get(key, 0) + 1
            if count <= _PREFILTER_SAMPLE_LIMIT:
                entries.append(_prefilter_entry(
                    file_id, obj_path_id, idx, offset, s,
                    prefilter, count, asset_file_name))
            continue
        # 非键风格显示文本每次出现都 pending。原“首键末值”规则（首次=键、
        # 末次=值）只对 I2/Localization 字典（has_marker）有意义——其键是
        # 标识符，已被 should_skip 剔除；普通 UI 对象里相同文本多处出现
        # （同一按钮在多个面板 / 多状态 Text）若只留末条可译，游戏里就只有
        # 一种 UI 状态被汉化（deadbeat 暂停菜单 Pause 按钮 ×3 实证）。
        if interaction_prompt or (
                structural_reason is None
                and (not has_marker or is_last)):
            status = "pending"
        else:
            status = "skipped"
        prefix = f"asset#{asset_file_name}#{obj_path_id}" if asset_file_name else f"asset#{obj_path_id}"
        meta = {"kind": "rawstr", "obj": obj_path_id, "offset": offset,
                "scan_mode": scan_modes[offset]}
        if structural_reason:
            meta["structural_reason"] = structural_reason
        if script_class:
            meta["script_class"] = script_class
        if asset_file_name:
            meta["asset_file"] = asset_file_name
        entries.append(TextEntry(
            file_id=file_id, key_path=f"{prefix}/str/{idx}",
            original=s, status=status,
            meta=meta))

    # 值特征：含 Localization 标记，或含句子形态字符串（标点结尾 / 较长含空格句）
    has_value_evidence = has_marker or any(
        _has_sentence_shape(s) and _structural_reason(s) is None
        for s in non_engine)

    # InputSystem 对象信号：确定性脚本类名（识别 L6：PPtr m_Script 解析，
    # morfosigame/deadbeat 输入配置对象的类名证据优先于串池猜类）或
    # action map 名（GameActions 等）/绑定路径（<Keyboard>/z）/interactions
    # 串（Press(behavior=2)）/InputSystem 程序集串 → 该对象是输入配置，
    # 对象内 action 名等全是运行时按名查找的键。翻译必然破坏按键交互
    # （morfosigame 实证：默认模板 map 名 'Normal' 不在名单里，
    # Proceed/SkipCutscene 动作名全被翻译 → 点击对话/F 跳过全部无反应）。
    is_input_system_object = (
        script_class in _INPUT_SYSTEM_SCRIPT_CLASSES
        or any(
            s.strip().casefold() in _INPUTSYSTEM_MAP_NAMES
            or bool(_INPUT_BINDING_PATH.match(s.strip()))
            or bool(_INPUTSYSTEM_INTERACTION.match(s.strip()))
            for _, _, s in scanned)
        or any(
            sig in s for s in (s for _, _, s in scanned)
            for sig in _INPUTSYSTEM_ASSEMBLY_SIGNALS))

    # Timeline 对象信号：确定性脚本类名（识别 L6）或轨道名（Animation
    # Track (1) 带编号形式）/Markers 标记/Timeline/Playables 程序集串 →
    # 轨道名/剪辑名/动画状态名按名查找，翻译破坏演出（morfosigame 实证：
    # 'Animation Track (1)' 被拆成 '动画轨道'+' (1)'，字符串计数 2→4
    # 结构错乱，Timeline 反序列化失败）。
    is_timeline_object = (
        script_class in _TIMELINE_SCRIPT_CLASSES
        or any(
            bool(_TIMELINE_TRACK.match(s.strip()))
            or s.strip().casefold() in _TIMELINE_MARKER_NAMES
            for _, _, s in scanned)
        or any(
            sig in s for s in (s for _, _, s in scanned)
            for sig in _TIMELINE_ASSEMBLY_SIGNALS))

    # UnityEvent 事件绑定对象信号：对象字符串池含持久化回调字段
    # （m_PersistentCalls/m_Target/m_MethodName）→ 对象是事件绑定配置，
    # 其中方法名/目标名是反射按名绑定键（知识库案例「UnityEvent 事件
    # 绑定断裂按钮无反应」转规则）。判定在完整扫描列表上做（引擎串被
    # 过滤不影响信号——与 InputSystem/Timeline 信号同模式）。
    is_unityevent_object = any(
        sig in s for s in (s for _, _, s in scanned)
        for sig in _UNITYEVENT_SIGNALS)

    # 共享资源小配置对象：非场景文件（level*）里无句子形态、≤2 个不同短词串的对象
    # （Timeline 剪辑 displayName 'Timothy'、'White Flash'、动画状态 'Player Idle' 等）。
    # 场景（level）里的同形对象是对话说话者名（TIMOTHY），按现有规则正常翻译——
    # 文件位置 + 内容形态双条件区分（morfosigame 实证：sharedassets4 116 字节
    # 'Timothy' 对象是 AnimationPlayableAsset 剪辑名，level 对话对象含句子）。
    is_shared_resource = not (
        asset_file_name and Path(asset_file_name).name.casefold().startswith("level"))
    small_words = {s.strip() for s in non_engine if s.strip()}
    # UI 控件配置对象信号：串池含 UI 控件词缀（Button/Label 等）——对象是
    # UI 元素配置（Corgi Engine 按钮实证 the-supper obj 1643：对象名
    # 'NewGameButton' + 按钮文本 'New Game'）。控件词缀是显式形态证据，
    # 优先于「小配置对象=引擎键」的对象级猜测（证据分层，审计 R1）：
    # 该对象里的普通词串是按钮/标签显示文本，必须放行翻译。
    # 词缀只取最强形态（Button/Label）——menu/screen/panel 等歧义词（可能
    # 是场景对象名/引擎资源名）不纳入，防过宽。
    ui_control_signal = any(
        s.strip().casefold().endswith(("button", "btn", "label"))
        for _, _, s in scanned)
    # 小配置对象形态判定（无豁免的原始条件）：ScriptableObject 形态 +
    # 共享资源 + ≤2 个非句子短词。豁免（ui_control_signal/ui_word_signal）
    # 只在本形态内生效——绑定名对象（down/left/right，InputActionAsset
    # 非 ScriptableObject 头部）里白名单词仍是键，不得豁免。
    is_small_config_shape = (
        _is_scriptable_object_shape(raw)
        and is_shared_resource
        and not has_marker
        and 1 <= len(small_words) <= 2
        and all(
            not _has_sentence_shape(s) and len(s) <= 16
            for s in small_words))
    # 白名单显示词证据：小配置形态对象中任一词在显式显示词白名单
    # （Pause/Menu/Save/Load/Language/Off/Talk 等 UI 界面词）——该对象
    # 是 UI 配置（Corgi Engine UIMenu 面板实证 the-supper obj 1755
    # 'Pause'+'Menu'），其词串是界面文本。白名单词是显式显示词证据
    # （形态性），不得被「小配置=引擎键」的猜测性规则推翻（证据分层）；
    # 引擎配置名（'Timothy'/'Player Idle'/'White Flash'）不在白名单，
    # 不受影响。
    ui_word_signal = is_small_config_shape and any(
        s.strip().casefold() in DISPLAY_WORDS for s in small_words)
    # 引擎配置对象（无豁免的小配置形态）：Timeline 剪辑名/动画状态名
    # 不含控件词缀且不在白名单，仍按配置跳过。
    is_small_config_object = (
        is_small_config_shape
        and not ui_control_signal
        and not ui_word_signal)

    # 对象级键列表判定：键列表对象中的标识符全部降级为 skipped（写回也据此跳过）。
    # 单词式写法（CREDITOS / Settings）是显示值不算键风格标识符——避免西语等
    # 全单词 UI 表被误判为键列表。
    idents = [s for s in non_engine
              if _IDENTIFIER.match(s) and not _WORD_CASE.match(s)]
    is_key_list = (len(idents) >= 3 and len(idents) / max(1, len(non_engine)) >= 0.85) or \
        has_marker
    direct_code_signal_count = sum(
        _structural_reason(s) in ("method_name", "type_reference")
        or s.strip() in _CODE_DRIVEN_METHODS
        for _, _, s in scanned
    )
    lifecycle_signal_count = sum(
        s.strip() in _LIFECYCLE_METHODS for _, _, s in scanned)
    is_code_heavy = (direct_code_signal_count >= 2 or
                     (direct_code_signal_count >= 1 and lifecycle_signal_count >= 1))
    core_menu_terms = {
        s.strip().casefold() for s in non_engine
        if s.strip().casefold() in CORE_MENU_SOURCE_TERMS
    }
    is_core_menu_collection = len(core_menu_terms) >= 2
    control_states = {
        s.strip().casefold() for _, _, s in scanned
        if s.strip().casefold() in _UNITY_CONTROL_STATE_NAMES
    }
    is_core_menu_control = len(control_states) >= 3
    is_single_visible = len(scanned) == 1 and len(entries) == 1
    # 词表/字典对象判定（happy-cat-tavern 实证 2026-08-12）：打字游戏
    # 单词库对象——字符串几乎全部是单 token 单词且数量大（level1#1311
    # 1700 条 100% 单词）。此类对象中白名单常见词（play/time/gold…）
    # 被 direct_code_signal/ui_control_signal 误放行进池翻译，写回后
    # 玩家无法按英文打字（打字玩法破坏）。大型全单词数组是确定性词表
    # 结构证据，优先于形态性猜测（证据分层）；正常 UI 对象含句式/描述
    # 文本且条目数少（设置菜单 <50 条），不触发。
    _stripped_pool = [s.strip() for s in non_engine if s.strip()]
    is_word_table = (
        len(_stripped_pool) >= 50
        and sum(1 for s in _stripped_pool if _WORD_TOKEN_RE.match(s))
        / len(_stripped_pool) >= 0.95
    )
    # TMP 资产对象判定（headache 实证 2026-08-12）：TextMeshPro 字体/
    # 精灵资产序列化对象——m_AssetVersion 值 '1.1.0' + 字体名含独立
    # token 'sdf'（'BaiJamjuree-Medium SDF'）或精灵资产名 'sprite
    # asset'（'Default Sprite Asset'）。资产名是 <font>/<sprite
    # name=...> 按名引用键（Winkle/Smiley/Bai Jamjuree Medium），
    # 翻译断引用——写回后 Sprite 变体/表情/字体全部丢失。资产对象
    # 字符串是资产元数据（名字+GUID+版本），非可译 UI 文本，对象级
    # 判定整体跳过。'1.1.0' 词边界防普通文本 "v1.1.0" 误伤。
    # 检测用完整 scanned 池（含引擎串）：资产名本身被引擎串过滤拦截
    # （不进 non_engine），但同对象其余串（精灵名 Smiley/Wink、布局
    # 参数 Character/Line Spacing）进池——资产名是判定证据必须可见。
    _pool_lower = " ".join(s.strip().casefold() for _, _, s in scanned)
    is_tmp_asset_object = (
        _re.search(r"\b1\.1\.0\b", _pool_lower) is not None
        and (_re.search(r"\bsdf\b", _pool_lower) is not None
             or "sprite asset" in _pool_lower)
    )
    for entry in entries:
        # R5：预过滤留档条目（prefilter_*）的 reason/role 已由
        # _prefilter_entry 定稿，不再走分类链（否则会被
        # duplicate_key_position 等后处理覆盖）。
        if entry.meta.get("prefilter"):
            continue
        reason = entry.meta.pop("structural_reason", None)
        stripped = entry.original.strip()
        if is_word_table:
            # 词表对象条目：整体跳过（含白名单词——词表词翻译破坏
            # 打字玩法；白名单显示词证据只在真实 UI 组件对象生效）
            entry.status = STATUS_SKIPPED
            entry.meta["obj_is_key_list"] = True
            reason = "word_table_object"
            confidence, role = "low", "structural"
        elif is_tmp_asset_object:
            # TMP 字体/精灵资产序列化对象：资产名是 <font>/<sprite>
            # 引用键（翻译断引用→Sprite 变体/表情丢失），对象整体跳过
            entry.status = STATUS_SKIPPED
            reason = "tmp_asset_object"
            confidence, role = "low", "structural"
        elif reason:
            entry.status = STATUS_SKIPPED
            if reason == "input_binding":
                entry.meta["obj_is_key_list"] = True
            confidence, role = "low", "structural"
        elif _is_script_code_line(stripped):
            # 单行代码（Lua 命令块/类型全名/函数签名链）：翻译即破坏功能。
            # 0.25.0 地毯式实证：a-catfiends 的 runblock/setcharacter/local
            # choice/elseif 行与 "System.Boolean, mscorlib, ..." 类型全名、
            # InvertVector2(...) 签名链被句子形状规则误放行进池、模型回显
            # 或乱译、质量门拦截成失败——代码文本不进池（硬结构规则）。
            entry.status = STATUS_SKIPPED
            entry.meta["obj_is_key_list"] = True
            reason = "code_line"
            confidence, role = "low", "structural"
        elif not any(ch.isalpha() for ch in stripped):
            # 纯符号串（{0} : {1} 等格式占位/分隔符/图标字符）：无字母 =
            # 无语言内容可翻，模型常回显或乱改（实证 {0} : {1} 失败）。
            entry.status = STATUS_SKIPPED
            reason = "symbols_only"
            confidence, role = "low", "structural"
        elif entry.status == STATUS_SKIPPED:
            reason = "duplicate_key_position"
            confidence, role = "low", "structural"
        elif is_interaction_prompt(stripped):
            entry.status = "pending"
            reason = "interaction_prompt"
            confidence, role = "high", "display"
        elif stripped in _LIFECYCLE_METHODS:
            entry.status = STATUS_SKIPPED
            reason = "lifecycle_method"
            confidence, role = "low", "structural"
        elif is_input_system_object or is_timeline_object or is_unityevent_object or is_small_config_object:
            # 引擎配置对象（输入/时间线/UnityEvent 事件绑定/动画配置）：
            # 其中的短词串是运行时按名查找的键（动作名/轨道名/方法名/
            # 状态名），翻译破坏功能（UnityEvent 绑定断裂 → 按钮无反应，
            # 知识库案例转规则）；强显示证据串理论上不出现，保守放行防
            # 误伤。注意不能用 _has_sentence_shape（≥10 字符含空格即真，
            # 'Arrow Keys' 10 字符会被误判为句子）。
            if has_display_text_evidence(stripped):
                reason = "natural_language"
                confidence, role = "medium", "display"
            else:
                entry.status = STATUS_SKIPPED
                entry.meta["obj_is_key_list"] = True
                reason = (
                    "input_system_object" if is_input_system_object
                    else "timeline_object" if is_timeline_object
                    else "unityevent_object" if is_unityevent_object
                    else "shared_resource_config_object")
                confidence, role = "low", "structural"
        elif (is_single_visible
              and Path(asset_file_name).name.casefold() == "resources.assets"
              and _IDENTIFIER.match(stripped)):
            if stripped.casefold() in DISPLAY_WORDS:
                # 显示词白名单优先于资源猜测：a-catfiends-impending-relapse
                # 实证（0.25.0 地毯式）：Fungus 对话按钮 Continue/Save/Load/
                # Restart/Submit/Cancel 在 resources.assets 单串对象里被
                # 资源标识符规则整组跳过——白名单是显式显示词证据（形态性），
                # 不得被「单串即资源键」的猜测性规则推翻（证据分层）。
                entry.status = "pending"
                reason = "single_visible_string"
                confidence, role = "high", "display"
            else:
                entry.status = STATUS_SKIPPED
                reason = "resource_identifier_without_display_evidence"
                confidence, role = "low", "structural"
        elif is_single_visible:
            # 孤立纯小写长词（≥10 字符）：触发器/字段名形态（fieldtrigger
            # 12 字符实证——MonoBehaviour rawstr 数组里孤立的代码词被
            # 无条件放行后模型回显恒败）。对象内无其他显示证据可参照，
            # 长纯小写词无空格无分隔符是代码标识符形态；真实显示文本
            # 的孤立长词（staircase/hallway 等场景词）短于此阈值。
            if (stripped.islower() and stripped.isalpha()
                    and len(stripped) >= 10):
                entry.status = STATUS_SKIPPED
                reason = "isolated_lowercode_word"
                confidence, role = "low", "structural"
            else:
                entry.status = "pending"
                reason = "single_visible_string"
                confidence, role = "high", "display"
        elif is_key_list and _IDENTIFIER.match(stripped):
            entry.status = STATUS_SKIPPED
            entry.meta["obj_is_key_list"] = True
            reason = "localization_key_list"
            confidence, role = "low", "structural"
        elif is_code_heavy and stripped in _LIFECYCLE_METHODS:
            entry.status = STATUS_SKIPPED
            reason = "lifecycle_method"
            confidence, role = "low", "structural"
        elif is_code_heavy:
            # 白名单显示词（Play/Instructions 等按钮文本）仅在对象有 UI 证据
            # （交互提示/控件状态）时放行——hotel-paradise 真实按钮对象含
            # Normal/Highlighted/Pressed 状态；纯 code 对象（无 UI 证据）中的
            # 单词仍跳过（防代码常量误放行）。core_menu_terms 不能作为证据——
            # 那是被检查词自身，用它会循环放行菜单词。
            has_ui_evidence = bool(
                len(control_states) >= 3 or interaction_prompt)
            # 控件状态名（Normal/Highlighted/Pressed/Selected/Disabled）是
            # Unity VisualState 引擎文本，即使在本按钮对象中也不翻译
            # （hotel-paradise 真实误伤：按钮对象的 Normal 被错误放行）
            in_control_state = stripped.casefold() in control_states
            if (_has_sentence_shape(stripped)
                    or (has_ui_evidence and not in_control_state
                        and stripped.casefold() in DISPLAY_WORDS)):
                reason = ("natural_language_in_code_object"
                          if _has_sentence_shape(stripped)
                          else "code_heavy_display_word")
                confidence, role = "medium", "display"
            else:
                entry.status = STATUS_SKIPPED
                reason = "code_heavy_identifier"
                confidence, role = "low", "structural"
        elif ((is_core_menu_collection or is_core_menu_control)
              and stripped.casefold() in CORE_MENU_SOURCE_TERMS):
            entry.status = "pending"
            reason = (
                "core_menu_collection" if is_core_menu_collection
                else "core_menu_control")
            confidence, role = "high", "display"
        elif _has_sentence_shape(stripped):
            reason = "natural_language"
            confidence, role = "medium", "display"
        elif has_value_evidence:
            reason = "object_has_display_evidence"
            confidence, role = "medium", "display"
        elif _IDENTIFIER.match(stripped):
            if (stripped.casefold() in DISPLAY_WORDS
                    and stripped.casefold() not in control_states
                    and (direct_code_signal_count >= 1
                         or ui_control_signal
                         or ui_word_signal)):
                # 显示词白名单仅在「真实组件对象」中优先于通用标识符规则
                # （0.25.0 地毯式实证：a-catfiends 的 Save/Load/Rewind 按钮
                # 在「单显示词+类型引用」对象（MonoBehaviour 组件实例）里被
                # 通用标识符规则误杀——组件含 type_reference 信号 = 组件实例
                # 证据，其白名单词是按钮文本；无组件信号的纯字符串对象
                # （绑定名 down/left/right）中白名单词仍是键，维持跳过）。
                # UI 控件词缀信号（ui_control_signal，the-supper 实证
                # QuitButton 对象里的 'Quit'）与白名单显示词信号
                # （ui_word_signal，UIMenu 面板 'Pause'+'Menu' 实证）与
                # 组件信号同等权重——对象名含 Button/Label 或对象词串
                # 是白名单 UI 词即 UI 元素配置，白名单词是按钮/标签文本。
                reason = "display_phrase"
                confidence, role = "medium", "display"
            else:
                entry.status = STATUS_SKIPPED
                entry.meta["obj_is_key_list"] = True
                reason = "identifier_without_display_evidence"
                confidence, role = "low", "structural"
        else:
            reason = "display_phrase"
            confidence, role = "medium", "display"
        entry.meta.update({
            "confidence": confidence,
            "role": role,
            "disposition": "translate" if role == "display" else "structural",
            "reason": reason,
            "obj_is_code_heavy": is_code_heavy,
        })
    for e in entries:
        e.meta["obj_has_values"] = has_value_evidence
    _finalize_skipped_counts(entries, prefilter_counts)
    return entries


# 词库型 TextAsset 判定（0.26 地毯式实证：force-reboot 脏话检测黑名单）。
# 单词行 = 无空格纯 ASCII 词（字母/数字/常见词内符号，≤40 字符）。
_LEXICON_WORD_RE = _re.compile(r"^[A-Za-z0-9][A-Za-z0-9'_.-]{0,39}$")
# 词表对象单词 token（happy-cat-tavern 实证 2026-08-12：打字游戏单词库
# 条目形态——纯字母单词，无空格/符号/数字）。
_WORD_TOKEN_RE = _re.compile(r"^[A-Za-z]+$")
_LEXICON_MIN_LINES = 30        # 少于 30 行不做词库判定（防误伤短名单/词典）
_LEXICON_MIN_RATIO = 0.90      # 单词行占比阈值（对话/字幕句行必含空格）


def _is_lexicon_word(s: str) -> bool:
    return bool(s and _LEXICON_WORD_RE.match(s))


def _textasset_entries(file_id: str, obj_path_id: int, raw: bytes,
                       asset_file_name: str = "",
                       skipped: dict[str, int] | None = None) -> list[TextEntry]:
    """TextAsset 内容：嵌套格式探测（JSON → XML → YAML → CSV），否则按行拆分。

    结构化条目 meta 带 "textasset_format"（写回用 apply_format_text 整体重建，
    m_Script 是可变长 byte[]，不受容量限制）与 "inner_path"（裸格式路径）。

    文件级源码检测（a-catfiends-impending-relapse 实证：resources.assets#69
    整文件是 inspect.lua 脚本库，被按行拆成 264 条进池、模型翻译代码被
    质量门拦截成 264 条失败）：代码特征行占比 ≥30% 且 ≥8 行 → 整文件
    按代码处理不产生条目（代码文本翻译即破坏功能，属于硬结构规则）。
    """
    if _looks_like_script_source(raw):
        return []
    prefix = (f"asset#{asset_file_name}#{obj_path_id}"
              if asset_file_name else f"asset#{obj_path_id}")
    base_meta = {
        "obj": obj_path_id,
        "confidence": "medium",
        "role": "display",
        "disposition": "translate",
        "reason": "textasset_display_text",
    }
    if asset_file_name:
        base_meta["asset_file"] = asset_file_name
    import json as _json
    # 二进制 TextAsset 过滤（嵌套探测之前，省去大文件 decode）：
    # 非可打印字节（\x00-\x1f 除 \t\r\n）占比 >5% → 音频/网格/压缩等
    # 二进制内容（调查实证：electric-trains fp_level_*、2.1G 字符的
    # project-arrhythmia 巨型 TextAsset 中混有二进制），不做条目。
    def _skip(morph: str) -> None:
        if skipped is not None:
            skipped[morph] = skipped.get(morph, 0) + 1

    if raw and sum(1 for b in raw if b < 0x20 and b not in (0x09, 0x0a, 0x0d)) / len(raw) > 0.05:
        _skip("textasset_binary")
        return []
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # F3：非 UTF-8 文本（GBK/Latin-1 等编码误判）。errors="replace"
        # 会把非法字节变成 U+FFFD，提取出的条目是 mojibake，翻译写回
        # 必然损坏原始字节——整文件不产生条目（过滤不是删除，写回侧
        # 同样 strict 拒绝，闭环安全）。
        _skip("textasset_decode_failed")
        return []
    # 双重 BOM 处理（a-catfiends obj70 实证）：UnityPy 读出的 str 已含
    # U+FEFF，调用方 encode("utf-8-sig") 又加一个 → decode 只移除一个，
    # 残留 BOM 卡住 JSON 分支（startswith("{") False），类型注册表 JSON
    # 被按行拆分、代码标识符进池。lstrip 前先彻底剥掉 BOM。
    if text.startswith("﻿"):
        text = text[len("﻿"):]
    stripped = text.lstrip()

    def _stamp(out: list, fmt: str) -> list:
        # 结构化格式（JSON/XML/YAML/CSV）提取的条目统一过单行代码判定：
        # .NET 类型注册表（registerTypes 数组）里的类型全名经 JSON 提取后
        # 无引号、会被句子形状规则放行（a-catfiends obj71 实证 8 条失败）。
        # 真实对话 JSON（字典/字幕）不受影响（模式为确定性代码特征）。
        kept = [e for e in out if not _is_script_code_line(e.original)]
        if len(kept) != len(out):
            _skip(f"structured_code_line_{fmt}")
        out = kept
        for e in out:
            inner = e.key_path
            e.key_path = f"{prefix}/{fmt}/{inner}"
            e.meta = {**base_meta, **e.meta,
                      "textasset_format": fmt, "inner_path": inner}
        return out

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            _json.loads(stripped)
        except Exception:  # noqa: BLE001
            data = None
        else:
            data = True
        if data is not None:
            return _stamp(json_format.extract_json_text(stripped, file_id), "json")
    if stripped.startswith("<") and ">" in stripped:
        from hanhua.core.formats.xml_format import extract_xml_text
        try:
            out = extract_xml_text(stripped, file_id)
        except Exception:  # noqa: BLE001
            out = []
        if out:
            return _stamp(out, "xml")
    from hanhua.core.formats.csv_format import extract_csv_text, looks_like_csv_text
    from hanhua.core.formats.yaml_format import extract_yaml_text, looks_like_yaml_text
    if looks_like_yaml_text(text):
        return _stamp(extract_yaml_text(text, file_id), "yaml")
    if looks_like_csv_text(text):
        out, _ = extract_csv_text(text, file_id)
        return _stamp(out, "csv")
    # 数据文件过滤：字母密度 <50% 的行占多数 → 关卡/配置数字表
    # （fp_level_* 的 "0:12:-1:none" 行 36% 字母实证），不做条目。
    # 真文本（字典/字幕）行字母密度高（missions=Missioni ≈88%），不误伤。
    all_lines = text.splitlines()
    if all_lines:
        alpha = sum(
            1 for ln in all_lines
            if sum(c.isalpha() for c in ln) / max(1, len(ln)) >= 0.5)
        if alpha / len(all_lines) < 0.5:
            _skip("textasset_low_alpha_density")
            return []
    # 词库型 TextAsset（0.26 地毯式实证：force-reboot data.unity3d#obj268
    # 是脏话检测黑名单——1100+ 行全英文短词，被当显示文本 974 条全翻译
    # 写回，游戏过滤逻辑失效）：单词行（无空格纯词）占比 ≥90% 且 ≥30 行
    # 的纯词表是比对数据（黑名单/词典/名单），非显示文本——对话/字幕必
    # 有句子结构（空格/标点），占比远低于阈值；短名单（<30 行）不判定防
    # 误伤，且正常短名单（missions=Missioni 等含 = 的行）不匹配单词行。
    if (_LEXICON_MIN_LINES
            and len(all_lines) >= _LEXICON_MIN_LINES):
        lexicon_lines = sum(
            1 for ln in all_lines if _is_lexicon_word(ln.strip()))
        if lexicon_lines / len(all_lines) >= _LEXICON_MIN_RATIO:
            _skip("textasset_lexicon")
            return []
    lines: list[TextEntry] = []
    for i, line in enumerate(all_lines):
        content = line.strip()
        if not content:
            continue
        # C4 识别侧留档：行级跳过的每一类都记 skipped_count（引擎串/键
        # 标识符/代码行），不再静默 continue——「纯文本行跳过、判定规律
        # 未定位到代码层」（222am 实证）的排查入口：报告按 reason 聚合
        # 即得各类真实总数，哑识别可见化。
        if _is_engine_string(content):
            _skip("textasset_engine_string")
            continue
        if should_skip(content):
            _skip("textasset_key_identifier")
            continue
        # 整文件未达代码阈值（<8 行或占比不足）时的行级代码兜底：
        # 短 Lua 块/单行调用仍按代码跳过（_is_script_code_line 强特征）
        if _is_script_code_line(content):
            _skip("textasset_code_line")
            continue
        lines.append(TextEntry(
            file_id=file_id, key_path=f"{prefix}/line/{i}",
            original=content,
            meta={**base_meta, "kind": "textasset", "line": i}))
    return lines


# ── TextAsset 源码检测（整文件代码判定，0.25.0 地毯式排查实证） ──
# 源码特征行模式（Lua/JS/C# 等）：命中任一即算代码特征行。
_SCRIPT_LINE_PATTERNS = (
    # Lua：local/function/end/return 与控制流
    _re.compile(r"^\s*local\s+\w+\s*="),
    _re.compile(r"^\s*function\b"),
    _re.compile(r"^\s*end\s*$"),
    _re.compile(r"^\s*return\s+\w"),
    _re.compile(r"\b(setmetatable|rawset|rawget|pairs|ipairs|gsub|"
                r"coroutine|table\.)\s*\("),
    _re.compile(r"\b\w+\.\w+\s*=\s*function"),
    _re.compile(r"^\s*if\s+.+then\s*$"),
    _re.compile(r"^\s*for\s+.+do\s*$"),
    # Lua 注释（整行注释在 a-catfiends obj72 实证中占 11/49 行，
    # 缺此模式会导致 FungusLua 模块命中率跌破阈值漏判）
    _re.compile(r"^\s*--"),
    # FungusLua 命令（say/choose/wait/runblock/setcharacter 行首命令：
    # 对话混在 Lua 命令中，整文件判定，不逐行提取）
    _re.compile(r"^\s*(?:say|choose|wait|runblock|setcharacter)\b"),
    # JS/C#/Python：声明/作用域/导入
    _re.compile(r"^\s*(?:const|let|var|static|public|private|protected|"
                r"internal)\s+\w+"),
    _re.compile(r"^\s*(?:def|class|struct|interface|namespace|using|"
                r"import|from|require)\b"),
    _re.compile(r"^\s*(?:if|elif|else|for|while|switch|case|catch|"
                r"finally)\b"),
    _re.compile(r"\b=>\s*\{?\s*$"),
    _re.compile(r"^\s*[{}\[\]]\s*$"),          # 裸括号行
    _re.compile(r"[;\s]{1}--\s"),              # Lua 注释
    _re.compile(r"^\s*(?:function|async)\s+[\w.]+\s*\("),
)
_SCRIPT_MIN_CODE_LINES = 8       # 少于 8 行不做代码判定（防误伤短文本）
_SCRIPT_MIN_CODE_RATIO = 0.30    # 特征行占比阈值（inspect.lua 实证 45%）

# 单行级代码特征（整文件级检测的补充，0.25.0 地毯式实证）：
# Fungus 游戏的 Lua 命令块/变量行以单行形式散落在 assets 对象里
# （runblock/setcharacter/local choice/elseif/function M.start()），
# 整文件检测不覆盖（不在 TextAsset 或占比不足）；.NET 类型全名
# （"System.Boolean, mscorlib, Version=2.0.0.0, ..."）与函数签名链
# （InvertVector2(invertX=false),ScaleVector2(...)）也被句子形状规则
# 误放行。这些模式是确定性代码特征，单行命中即判代码（硬结构规则）。
_CODE_LINE_PATTERNS = (
    # Lua 语句：声明/控制流
    _re.compile(r"^\s*local\s+\w+\s*="),
    _re.compile(r"^\s*elseif\b"),
    _re.compile(r"^\s*function\s+[\w.]+\s*\("),
    _re.compile(r"^\s*if\s+.+then\s*$"),
    _re.compile(r"^\s*for\s+.+do\s*$"),
    _re.compile(r"^\s*return\s+\w"),
    _re.compile(r"^\s*--"),                      # Lua 整行注释
    _re.compile(r"\)\s*--\s"),                   # 语句后的行尾注释（不用裸 --\s
                                                 # 防口语破折号 'I -- I can't'）
    # .NET 类型全名（可选前导引号 + 程序集 + Version=；JSON 提取剥离引号
    # 后为无引号形态——a-catfiends obj71 registerTypes 实证）
    _re.compile(r'^\s*"?\s*(?:System|Unity|Mono)\.[\w.]+\s*,\s*[\w.]+\s*,\s*Version=\d'),
    # 赋值表达式（M = {} 空表声明等 Lua 模块形态）
    _re.compile(r"^\s*\w+\s*=\s*\{"),
    # 命名参数函数调用（InvertVector2(invertX=false)）
    _re.compile(r"\b\w+\(\s*[A-Za-z_]\w*=[^(),)]*\)"),
    # Lua 命令式调用（runblock(flowchart, "Intro") 含字符串参数）
    _re.compile(r"^\s*\w+\([^)]*\"[^)]*\"[^)]*\)\s*$"),
    # FungusLua 行首命令（wait(1)/say "..."/choose {...} 等：翻译整行
    # 破坏命令名，与整文件级模式同源；对话行首为 say 前缀在真实对话
    # 中不存在，0 误伤实证）
    _re.compile(r"^\s*(?:say|choose|wait|runblock|setcharacter)\b"),
)


def _is_script_code_line(text: str) -> bool:
    """单行是否确定性代码行（单行即判，不聚合行数/占比）。

    与整文件级 _looks_like_script_source 互补：整文件检测只覆盖 TextAsset
    聚合形态；rawstr 对象内的散落代码行（Fungus Lua 命令块）与引擎内部
    类型/调用签名需要行级判定。正常显示文本（含 Fungus 富文本标签
    {punch=3,2}* Y A W N *{w=3}{x}）不命中任何模式（实证 0 误伤）。
    """
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < 6:
        return False
    return any(p.search(stripped) for p in _CODE_LINE_PATTERNS)


def _looks_like_script_source(raw: bytes) -> bool:
    """TextAsset 整文件是否源码脚本（整文件跳过，不产生条目）。

    判定：非空行中命中脚本特征行的占比 ≥30% 且非空行 ≥8。
    实证锚点：a-catfiends-impending-relapse resources.assets#69
    （inspect.lua 库 264 行）命中 45%；真实对话文本 0%。
    """
    if not raw:
        return False
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < _SCRIPT_MIN_CODE_LINES:
        return False
    hits = sum(1 for ln in lines
               if any(p.search(ln) for p in _SCRIPT_LINE_PATTERNS))
    return hits / len(lines) >= _SCRIPT_MIN_CODE_RATIO


# 原生（非 MonoBehaviour）文本承载类型：场景里的 Text/TextMesh 等组件。
# 它们的字符串走 typetree 全叶子分类（不跑 raw scan——scene 字节噪音大，
# 且这些类型的显示字段在 typetree 中完整可见）。
_NATIVE_TEXT_TYPES = frozenset({
    "Text", "TextMesh", "GUIText", "InputField",
    "VisualTreeAsset", "TextMeshPro", "TextMeshProUGUI", "TMP_Text",
})


def _should_downgrade_pending(entry: TextEntry) -> bool:
    """提取后置降级闸门（证据分层）。

    引擎串与键风格标识符照降；is_hard_structural 硬结构（JSON/URL/路径/
    GUID/纯数字…翻译会破坏功能）照降；但**确定性显示证据**条目（typetree
    UI 字段白名单 high）只被硬结构降级，署名/版权类软猜测规则不得推翻
    UI 字段证据（lilys-day-off level13 结局画廊实证：'A game by Kyuppin'
    在 m_Text 显示字段被 credit 规则降级错过）。
    """
    if entry.status != "pending" or entry.meta.get("kind") == "localization":
        return False
    fmt = entry.meta.get("textasset_format")
    inner = str(entry.meta.get("inner_path", ""))
    if fmt == "xml" and ("/value" in inner or inner.endswith("/value")):
        # xml value 节点是确定性显示文本证据（doog 的 messages/
        # message[N]/value 是游戏内显示文本）——后置闸门的**软猜测
        # 反模式**（引擎串编程命名形态 PascalCase/驼峰、key_style
        # 混合大小写、_QUALIFIED 标识符形态、credit_like 句子署名、
        # log_template 冒号结尾）不得推翻格式判定（doog 实证 33 条
        # xml value 罗马音台词 FeeNGAh/Konbanmio-n、西语 UI
        # 'Seleccione dificultad:'、英文成就句 'Get revived by…' 被
        # 误降级哑跳过）。仅形态标记明确的机器数据（URL/GUID/JSON/
        # 纯数字/输入设备/绑定路径/base64/路径/已知引擎词表）与无
        # 语言内容短串仍降级。key 节点（全大写键名 PICKUP_* 由
        # key_style 判定跳过）不豁免。
        s = entry.original.strip()
        if len(s) < 2 or not _HAS_LETTER.search(s):
            return True
        if is_engine_string_core(s):
            return True
        if not is_hard_structural(s):
            return False
        return not (
            is_credit_like(s)                       # 'Get revived by…' 含 by 被当署名
            or _QUALIFIED.match(s)                  # 'Konbanmio-n' 连字符被当程序集名
            or (len(s) >= 20 and _LOG_TEMPLATE_TAIL.search(s))  # 冒号结尾西语 UI 被当日志模板
        )
    if _is_engine_string(entry.original):
        return True
    if is_key_style_identifier(entry.original):
        return True
    if not is_hard_structural(entry.original):
        return False
    if (entry.meta.get("confidence") == "high"
            and entry.meta.get("reason") == "typetree_display_field"
            and is_credit_like(entry.original)):
        return False
    return True


def extract_asset_file(path: str | Path, file_id: str | None = None,
                       progress_cb: Callable | None = None, *,
                       typetree_generator: Any | None = None) -> ParsedFile:
    """提取一个资源文件 → ParsedFile（含文件级噪音判定）。

    容器：UnityPy 的 Environment.objects 自动递归 BundleFile/WebFile 嵌套
    （Addressables bundle 里的 bundle、UnityWebData 容器），seen_objects 去重。

    typetree_generator：UnityPy.helpers.TypeTreeGenerator 实例（Mono 游戏
    专用，从游戏 Managed DLL 生成脚本 typetree）。资产构建未带 typetree
    （BuildAssetBundleOptions.DisableWriteTypeTree / Player 构建 strip）时，
    MonoBehaviour 全部读取失败、文本只能靠 raw scan 兜底——挂上生成器后
    脚本字段可完整读取（hickory 实证：1890/1898 失败 → 1884/1898 成功，
    主菜单 Options/Quit 与对话文本全部字段级提取）。Mono 游戏 + Managed
    目录由扫描管线负责构建并传入；缺省 None 时行为与旧版一致。
    """
    from UnityPy import Environment
    p = Path(path)
    fid = file_id or str(p).replace("\\", "/")
    env = Environment()
    if typetree_generator is not None:
        env.typetree_generator = typetree_generator
    entries: list[TextEntry] = []
    raw_items: list[tuple[str, int, bytes, set[str], str]] = []
    freq: dict[str, int] = {}
    deferred_candidates: list[tuple[str, int, list[TextEntry]]] = []
    seen_objects: set[tuple[str, int]] = set()
    skipped: dict[str, int] = {}  # R5 静默跳过留档（哑识别可见化）
    # 识别 L7：typetree 覆盖率持续度量——每容器记录成功/失败对象数，
    # 失败靠 raw scan 兜底（Unity 6000 264/268 失败实证）但必须可量化
    typetree_ok = 0
    typetree_failed = 0
    try:
        try:
            env.load([str(p)])
        except Exception:  # noqa: BLE001
            # 无法解析的容器（未知魔数/截断/加密）→ 空结果，交给文本侧处理
            return ParsedFile(fid, str(p), "v2_asset", [], "utf-8", "\n",
                              {"kind": "asset"}, False, skipped)
        for obj in env.objects:
            object_key = _object_identity(obj)
            if object_key in seen_objects:
                continue
            seen_objects.add(object_key)
            tname = obj.type.name
            asset_name = _asset_file_name(obj)
            if tname == "TextAsset":
                try:
                    data = obj.read()
                    script = getattr(data, "m_Script", None)
                    if isinstance(script, str):
                        # 老 Unity（4.x/5.x）：TextAsset.m_Script 是 str
                        # （electric-trains 实证）。UnityPy 对二进制内容用
                        # surrogateescape 解码（\udc80 等），encode 必须用
                        # surrogateescape 还原原始字节，否则 3 个游戏
                        # （mimic-search/morfosigame/the-black-iris 实证）
                        # 的 TextAsset 全部抛 UnicodeEncodeError 被吞
                        script = script.encode(
                            "utf-8-sig", errors="surrogateescape")
                    entries.extend(_textasset_entries(
                        fid, obj.path_id, script or b"", asset_name, skipped))
                except Exception:  # noqa: BLE001
                    continue
            elif (tname in ("MonoBehaviour", "ScriptableObject")
                  or tname in _NATIVE_TEXT_TYPES):
                tree = None
                script_class = ""
                try:
                    tree = obj.read_typetree()
                    typetree_ok += 1
                except Exception:  # noqa: BLE001
                    # 识别 L7：typetree 失败率留档（覆盖率指标数据源）——
                    # 失败对象靠 raw scan 兜底（Unity 6000 实证），但失败
                    # 率必须可量化：逐容器记录 + skipped 原因聚合
                    typetree_failed += 1
                    skipped["typetree_failed"] = (
                        skipped.get("typetree_failed", 0) + 1)
                if isinstance(tree, dict):
                    # 识别 L6：确定性脚本类名（m_Script PPtr → MonoScript）
                    # 优先于串池信号，对象级判定直接使用
                    script_class = _script_class_of(tree, obj)
                    if _is_string_table_tree(tree):
                        entries.extend(_localization_entries_from_tree(
                            fid, obj.path_id, tree, asset_name))
                        continue
                    shared_rows = tree.get("m_Entries")
                    if isinstance(shared_rows, list) and any(
                            isinstance(row, dict) and "m_Key" in row for row in shared_rows):
                        continue
                    display, candidates = _typetree_string_entries(
                        fid, obj.path_id, tree, asset_name, skipped)
                    entries.extend(display)
                    if display:
                        # typetree 已覆盖全部叶子，display 存在时不跑 raw scan；
                        # 候选同时入库（低置信证据层，写回自动排除）
                        entries.extend(candidates)
                        continue
                    # 无 display 条目：候选暂存，待 raw scan 后取补集
                    # （raw scan 的对象级值特征/UI 证据分类更准确）
                    if candidates:
                        deferred_candidates.append(
                            (asset_name, int(obj.path_id), candidates))
                if tname not in _NATIVE_TEXT_TYPES:
                    try:
                        raw = obj.get_raw_data()
                    except Exception:  # noqa: BLE001
                        continue
                    if raw and len(raw) < 8_000_000:
                        raw_strings = {s for _, s in scan_strings(raw)}
                        raw_items.append(
                            (asset_name, int(obj.path_id), raw, raw_strings,
                             script_class))
                        for s in raw_strings:
                            freq[s] = freq.get(s, 0) + 1
    finally:
        from hanhua.core.unity.writer import _dispose_environment
        _dispose_environment(env)
    # 识别 L8：高频串阈值按全文件规模算一次，所有对象共用（避免每对象
    # 重复 sum(freq.values())——对象上千时 O(N×M)）
    freq_threshold = _high_freq_threshold(freq)
    for asset_name, path_id, raw, _, script_class in raw_items:
        entries.extend(_raw_string_entries(
            fid, path_id, raw, freq, asset_name, freq_threshold,
            script_class))
    # 候选补集：raw scan 已发现的原文以 raw 分类为准，候选只补漏网证据
    covered_by_raw = {(name, pid): strings
                      for name, pid, _, strings, _ in raw_items}
    for asset_name, path_id, candidates in deferred_candidates:
        covered = covered_by_raw.get((asset_name, path_id), set())
        entries.extend(
            c for c in candidates if c.original not in covered)
    for e in entries:
        if _should_downgrade_pending(e):
            e.status = STATUS_SKIPPED
    noise = looks_like_noise_file(entries)
    meta: dict = {"kind": "asset"}
    # 识别 L7：typetree 覆盖率入容器 meta（每容器可用率可查）——
    # 低覆盖率容器是「字段证据缺失、靠 raw 兜底」的量化信号
    if typetree_ok or typetree_failed:
        meta["typetree_coverage"] = typetree_ok / (
            typetree_ok + typetree_failed)
        meta["typetree_objects"] = typetree_ok + typetree_failed
    return ParsedFile(fid, str(p), "v2_asset", entries, "utf-8", "\n",
                      meta, noise, skipped)
