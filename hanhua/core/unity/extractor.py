"""v2 资源提取：UnityPy 解析 .assets / AssetBundle。
TextAsset 整文本 + MonoBehaviour 序列化原始字节字符串扫描（typetree 不可用时兜底）。"""
from __future__ import annotations
from collections.abc import Iterable
from pathlib import Path
from typing import Callable
from urllib.parse import quote, unquote

from hanhua.core.engine_strings import (CORE_MENU_SOURCE_TERMS,
                                         has_display_text_evidence,
                                        is_code_action_binding,
                                        is_engine_string,
                                        is_interaction_prompt,
                                        is_physical_binding_identifier)
from hanhua.core.extractor import ParsedFile, looks_like_noise_file
from hanhua.core.formats import json_format
from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.placeholders import (DISPLAY_WORDS, is_credit_like,
                                      is_hard_structural, is_key_style_identifier,
                                      should_skip, _IDENTIFIER, _WORD_CASE)
from hanhua.core.scanner import (_has_unity_bundle_magic, _is_runtime_file,
                                 _walk_files)
import re as _re

# 句子形态：标点结尾（真正的显示文本，如 'BOSS: ...'、'Hello!'）
_SENTENCE_END = _re.compile(r"[.!?:，。！？;；]$")
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
_ASSEMBLY_REFERENCE = _re.compile(
    r"^[A-Za-z_][A-Za-z0-9_+`]*(?:\.[A-Za-z_][A-Za-z0-9_+`]*)*,\s*"
    r"(?:Assembly-[A-Za-z0-9_.-]+|Unity\.[A-Za-z0-9_.-]+|"
    r"UnityEngine(?:\.[A-Za-z0-9_.-]+)*|System(?:\.[A-Za-z0-9_.-]+)*|mscorlib)"
    r"(?:,\s*Version=[^,\s]+,\s*Culture=[^,\s]+,\s*PublicKeyToken=[^,\s]+)?$",
    _re.I,
)
_LIFECYCLE_METHODS = frozenset({
    "Awake", "Start", "Update", "FixedUpdate", "LateUpdate",
    "OnEnable", "OnDisable", "OnDestroy", "Reset",
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


# 指南 §3.2「所有 SerializedFile 对象的字符串字段」显示白名单：
# 常见 UI / 对话 / 本地化字段名（已 casefold）。"name" 有意排除——m_Name
# 是每个对象的标识名（inspector 标签/查找键），翻译会淹没真实文本。
_TYPETREE_DISPLAY_FIELDS = frozenset({
    "text", "label", "title", "description", "displayname",
    "dialogue", "line", "lines", "subtitle", "tooltip", "hint", "prompt",
    "message", "messages", "content", "caption", "question", "answer",
    "choice", "choices", "objective", "lore", "bio", "error", "format",
    "template", "prefix", "suffix", "singular", "plural", "header", "body",
    "details", "summary", "footer", "greeting", "farewell", "notice",
    "warning", "help", "placeholder", "heading", "questiontext", "dialoguetext",
})
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
        asset_file_name: str = "") -> tuple[list[TextEntry], list[TextEntry]]:
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
               confidence: str, status: str, role: str) -> None:
        meta = {
            "kind": kind, "obj": obj_path_id, "field_path": path,
            "confidence": confidence, "role": role,
            "disposition": "translate" if role == "display" else "structural",
            "reason": reason,
            "obj_has_values": has_value_evidence,
        }
        if asset_file_name:
            meta["asset_file"] = asset_file_name
        target = display if role == "display" else candidates
        target.append(TextEntry(
            file_id=file_id,
            key_path=f"{prefix}/field/{_encode_field_path(path)}",
            original=text, status=status, meta=meta))

    for path, text, normalized, blocked in leaves:
        if blocked:
            continue
        stripped = text.strip()
        if normalized in _TYPETREE_DISPLAY_FIELDS:
            append("typetree", path, text, "typetree_display_field",
                   "high", "pending", "display")
        elif (should_skip(text) or is_hard_structural(text)
              or _looks_like_type_descriptor(text)):
            continue        # 键/标识符/结构值/类型引用：不产生条目
        elif (_has_sentence_shape(stripped) or has_display_text_evidence(text)
              or has_value_evidence):
            append("typetree", path, text, "typetree_display_evidence",
                   "medium", "pending", "display")
        elif len(candidates) < _MAX_CANDIDATES_PER_OBJECT:
            append("typetree_candidate", path, text, "typetree_candidate",
                   "low", STATUS_SKIPPED, "candidate")
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
    return None


def _has_sentence_shape(text: str) -> bool:
    stripped = text.strip()
    return bool(_SENTENCE_END.search(stripped) or
                (len(stripped) >= 10 and " " in stripped))


def _is_scriptable_object_shape(raw: bytes) -> bool:
    """MonoBehaviour 头部 m_GameObject 引用为空 → ScriptableObject 形态。

    资源配置对象（Timeline 剪辑/TrackAsset/InputActionAsset 等）没有
    m_GameObject（头部 12 字节全零）；场景组件对象（UI 脚本/对话组件等）带
    m_GameObject 引用（非零）。2019.3 及老版 PPtr 为 4+4 字节，新版本 4+8——
    空引用两种布局前 12 字节都全零，组件两种布局都非零（fileID=0 时 pathID
    落在第 4 或第 8 字节起）。
    """
    return len(raw) >= 12 and raw[:12] == b"\x00" * 12


def _raw_string_entries(file_id: str, obj_path_id: int, raw: bytes,
                        freq: dict[str, int], asset_file_name: str = "") -> list[TextEntry]:
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
    """
    aligned = scan_strings(raw)
    recovered = _scan_unaligned_display_strings(
        raw, {offset for offset, _ in aligned})
    scanned_with_mode = sorted(
        [(offset, text, "aligned") for offset, text in aligned]
        + [(offset, text, "unaligned") for offset, text in recovered],
        key=lambda item: item[0],
    )
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
        if _is_engine_string(s) and structural_reason is None:
            continue
        non_engine.append(s)
        if should_skip(s) and structural_reason is None:
            continue
        if freq.get(s, 0) >= 40 and not strong_display_evidence:
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

    # InputSystem 对象信号：action map 名（GameActions 等）或绑定路径（<Keyboard>/z）
    # 或 interactions 串（Press(behavior=2)）或 InputSystem 程序集串出现 → 该对象是
    # 输入配置，对象内 action 名等全是运行时按名查找的键。翻译必然破坏按键交互
    # （morfosigame 实证：默认模板 map 名 'Normal' 不在名单里，Proceed/SkipCutscene
    # 动作名全被翻译 → 点击对话/F 跳过全部无反应；deadbeat obj 717 同理）。
    is_input_system_object = (
        any(
            s.strip().casefold() in _INPUTSYSTEM_MAP_NAMES
            or bool(_INPUT_BINDING_PATH.match(s.strip()))
            or bool(_INPUTSYSTEM_INTERACTION.match(s.strip()))
            for _, _, s in scanned)
        or any(
            sig in s for s in (s for _, _, s in scanned)
            for sig in _INPUTSYSTEM_ASSEMBLY_SIGNALS))

    # Timeline 对象信号：轨道名（Animation Track (1) 带编号形式）或 Markers 标记或
    # Timeline/Playables 程序集串 → 轨道名/剪辑名/动画状态名按名查找，翻译破坏演出
    # （morfosigame 实证：'Animation Track (1)' 被拆成 '动画轨道'+' (1)'，字符串
    # 计数 2→4 结构错乱，Timeline 反序列化失败）。
    is_timeline_object = (
        any(
            bool(_TIMELINE_TRACK.match(s.strip()))
            or s.strip().casefold() in _TIMELINE_MARKER_NAMES
            for _, _, s in scanned)
        or any(
            sig in s for s in (s for _, _, s in scanned)
            for sig in _TIMELINE_ASSEMBLY_SIGNALS))

    # 共享资源小配置对象：非场景文件（level*）里无句子形态、≤2 个不同短词串的对象
    # （Timeline 剪辑 displayName 'Timothy'、'White Flash'、动画状态 'Player Idle' 等）。
    # 场景（level）里的同形对象是对话说话者名（TIMOTHY），按现有规则正常翻译——
    # 文件位置 + 内容形态双条件区分（morfosigame 实证：sharedassets4 116 字节
    # 'Timothy' 对象是 AnimationPlayableAsset 剪辑名，level 对话对象含句子）。
    is_shared_resource = not (
        asset_file_name and Path(asset_file_name).name.casefold().startswith("level"))
    small_words = {s.strip() for s in non_engine if s.strip()}
    # ScriptableObject 形态（无 m_GameObject）才可能是引擎配置；场景组件
    # 即使单短词也是显示文本（UI 脚本，如 'Battery'），不触发本规则。
    is_small_config_object = (
        _is_scriptable_object_shape(raw)
        and is_shared_resource
        and not has_marker
        and 1 <= len(small_words) <= 2
        and all(
            not _has_sentence_shape(s) and len(s) <= 16
            for s in small_words))

    # 对象级键列表判定：键列表对象中的标识符全部降级为 skipped（写回也据此跳过）。
    # 单词式写法（CREDITOS / Settings）是显示值不算键风格标识符——避免西语等
    # 全单词 UI 表被误判为键列表。
    idents = [s for s in non_engine
              if _IDENTIFIER.match(s) and not _WORD_CASE.match(s)]
    is_key_list = (len(idents) >= 3 and len(idents) / max(1, len(non_engine)) >= 0.85) or \
        has_marker
    direct_code_signal_count = sum(
        _structural_reason(s) in ("method_name", "type_reference")
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
    for entry in entries:
        reason = entry.meta.pop("structural_reason", None)
        stripped = entry.original.strip()
        if reason:
            entry.status = STATUS_SKIPPED
            if reason == "input_binding":
                entry.meta["obj_is_key_list"] = True
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
        elif is_input_system_object or is_timeline_object or is_small_config_object:
            # 引擎配置对象（输入/时间线/动画配置）：其中的短词串是运行时按名查找的
            # 键（动作名/轨道名/状态名），翻译破坏功能；强显示证据串理论上不出现，
            # 保守放行防误伤。注意不能用 _has_sentence_shape（≥10 字符含空格即真，
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
                    else "shared_resource_config_object")
                confidence, role = "low", "structural"
        elif (is_single_visible
              and Path(asset_file_name).name.casefold() == "resources.assets"
              and _IDENTIFIER.match(stripped)):
            entry.status = STATUS_SKIPPED
            reason = "resource_identifier_without_display_evidence"
            confidence, role = "low", "structural"
        elif is_single_visible:
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
    return entries


def _textasset_entries(file_id: str, obj_path_id: int, raw: bytes,
                       asset_file_name: str = "") -> list[TextEntry]:
    """TextAsset 内容：嵌套格式探测（JSON → XML → YAML → CSV），否则按行拆分。

    结构化条目 meta 带 "textasset_format"（写回用 apply_format_text 整体重建，
    m_Script 是可变长 byte[]，不受容量限制）与 "inner_path"（裸格式路径）。
    """
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
    if raw and sum(1 for b in raw if b < 0x20 and b not in (0x09, 0x0a, 0x0d)) / len(raw) > 0.05:
        return []
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # F3：非 UTF-8 文本（GBK/Latin-1 等编码误判）。errors="replace"
        # 会把非法字节变成 U+FFFD，提取出的条目是 mojibake，翻译写回
        # 必然损坏原始字节——整文件不产生条目（过滤不是删除，写回侧
        # 同样 strict 拒绝，闭环安全）。
        return []
    stripped = text.lstrip()

    def _stamp(out: list, fmt: str) -> list:
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
            return []
    lines: list[TextEntry] = []
    for i, line in enumerate(all_lines):
        content = line.strip()
        if content and not _is_engine_string(content) and not should_skip(content):
            lines.append(TextEntry(
                file_id=file_id, key_path=f"{prefix}/line/{i}",
                original=content,
                meta={**base_meta, "kind": "textasset", "line": i}))
    return lines


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
                       progress_cb: Callable | None = None) -> ParsedFile:
    """提取一个资源文件 → ParsedFile（含文件级噪音判定）。

    容器：UnityPy 的 Environment.objects 自动递归 BundleFile/WebFile 嵌套
    （Addressables bundle 里的 bundle、UnityWebData 容器），seen_objects 去重。
    """
    from UnityPy import Environment
    p = Path(path)
    fid = file_id or str(p).replace("\\", "/")
    env = Environment()
    entries: list[TextEntry] = []
    raw_items: list[tuple[str, int, bytes, set[str]]] = []
    freq: dict[str, int] = {}
    deferred_candidates: list[tuple[str, int, list[TextEntry]]] = []
    seen_objects: set[tuple[str, int]] = set()
    try:
        try:
            env.load([str(p)])
        except Exception:  # noqa: BLE001
            # 无法解析的容器（未知魔数/截断/加密）→ 空结果，交给文本侧处理
            return ParsedFile(fid, str(p), "v2_asset", [], "utf-8", "\n",
                              {"kind": "asset"}, False)
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
                        fid, obj.path_id, script or b"", asset_name))
                except Exception:  # noqa: BLE001
                    continue
            elif (tname in ("MonoBehaviour", "ScriptableObject")
                  or tname in _NATIVE_TEXT_TYPES):
                tree = None
                try:
                    tree = obj.read_typetree()
                except Exception:  # noqa: BLE001
                    pass
                if isinstance(tree, dict):
                    if _is_string_table_tree(tree):
                        entries.extend(_localization_entries_from_tree(
                            fid, obj.path_id, tree, asset_name))
                        continue
                    shared_rows = tree.get("m_Entries")
                    if isinstance(shared_rows, list) and any(
                            isinstance(row, dict) and "m_Key" in row for row in shared_rows):
                        continue
                    display, candidates = _typetree_string_entries(
                        fid, obj.path_id, tree, asset_name)
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
                            (asset_name, int(obj.path_id), raw, raw_strings))
                        for s in raw_strings:
                            freq[s] = freq.get(s, 0) + 1
    finally:
        from hanhua.core.unity.writer import _dispose_environment
        _dispose_environment(env)
    for asset_name, path_id, raw, _ in raw_items:
        entries.extend(_raw_string_entries(fid, path_id, raw, freq, asset_name))
    # 候选补集：raw scan 已发现的原文以 raw 分类为准，候选只补漏网证据
    covered_by_raw = {(name, pid): strings
                      for name, pid, _, strings in raw_items}
    for asset_name, path_id, candidates in deferred_candidates:
        covered = covered_by_raw.get((asset_name, path_id), set())
        entries.extend(
            c for c in candidates if c.original not in covered)
    for e in entries:
        if _should_downgrade_pending(e):
            e.status = STATUS_SKIPPED
    noise = looks_like_noise_file(entries)
    return ParsedFile(fid, str(p), "v2_asset", entries, "utf-8", "\n", {"kind": "asset"}, noise)
