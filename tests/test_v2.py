"""v2 测试：字符串扫描、长度适配、TextAsset 提取、#US 堆、IL2CPP metadata。"""
import struct
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from hanhua.core.engine_strings import (InputEvent, has_display_text_evidence,
                                        interaction_input_events,
                                        interaction_input_tokens,
                                        is_interaction_prompt,
                                        is_strong_interaction_prompt)
from hanhua.core.memory import ProjectStore
from hanhua.core.models import STATUS_SKIPPED, TextEntry
from hanhua.core.unity.extractor import (_is_engine_string, _raw_string_entries,
                                        _decode_field_path,
                                        _encode_field_path,
                                        _localization_bundle_probe,
                                        _looks_like_type_descriptor,
                                        _prefer_source_locale_bundles,
                                        _should_downgrade_pending,
                                        _structural_reason,
                                        _textasset_entries,
                                        _typetree_string_entries, extract_asset_file,
                                        find_asset_files, scan_strings)
from hanhua.core.unity.il2cpp import parse_string_literals
from hanhua.core.unity.mono_dll import (_walk_us_heap, extract_dll_user_strings,
                                        find_dll_files)
from hanhua.core.unity.writer import _fit_bytes, _patch_textasset


# ── scan_strings ──
def _with_len(s: str) -> bytes:
    b = s.encode("utf-8")
    padding = b"\x00" * (-len(b) % 4)
    return struct.pack("<I", len(b)) + b + padding


def _write_cli_pe(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = bytearray(0x400)
    blob[:2] = b"MZ"
    struct.pack_into("<I", blob, 0x3C, 0x80)
    blob[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", blob, 0x84, 0x8664, 1, 0, 0, 0, 0xF0, 0x22)
    struct.pack_into("<H", blob, 0x98, 0x20B)
    struct.pack_into("<I", blob, 0x98 + 108, 16)
    section = 0x80 + 4 + 20 + 0xF0
    blob[section:section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", blob, section + 8, 0x200, 0x2000, 0x200, 0x200)
    struct.pack_into("<II", blob, 0x98 + 112 + 14 * 8, 0x2000, 0x48)
    struct.pack_into("<IHHII", blob, 0x200, 0x48, 2, 5, 0x2080, 0x20)
    struct.pack_into("<I", blob, 0x210, 1)
    blob[0x280:0x284] = b"BSJB"
    path.write_bytes(blob)


def test_typetree_recursively_extracts_display_fields_with_typed_paths():
    tree = {"m_Text": "Settings", "panel": {
        "title": "Options", "rows": [
            {"label": "Audio"}, {"description": "Adjust volume"}]}}

    display, _ = _typetree_string_entries("f", 7, tree, "fixture.assets")

    assert [(entry.original, entry.meta["field_path"]) for entry in display] == [
        ("Settings", ["m_Text"]),
        ("Options", ["panel", "title"]),
        ("Audio", ["panel", "rows", 0, "label"]),
        ("Adjust volume", ["panel", "rows", 1, "description"]),
    ]
    assert all(entry.meta["kind"] == "typetree" for entry in display)


def test_typetree_excludes_display_values_under_structural_fields():
    tree = {"keys": [{"label": "Settings"}],
            "binding": {"text": "Jump"},
            "method": {"title": "Start"},
            "panel": {"text": "Visible"}}

    display, _ = _typetree_string_entries("f", 8, tree)

    assert [entry.original for entry in display] == ["Visible"]


def test_typetree_type_descriptor_never_a_display_text():
    # resonance-of-the-ocean 实测：Localization SmartFormat 配置对象里
    # "TypeName Namespace Assembly" 是类型引用（游戏按名反射加载），当文本
    # 翻译后 save_typetree 抛 ValueError（Referenced type not found）。
    tree = {
        "m_SmartFormat": {
            "m_FormatterType":
                "Parser UnityEngine.Localization.SmartFormat.Core.Parsing "
                "Unity.Localization",
        },
        "panel": {"text": "Real text"},
    }

    display, candidates = _typetree_string_entries("f", 12, tree)

    assert [entry.original for entry in display] == ["Real text"]
    assert not any("FormatterType" in str(e.meta["field_path"])
                   for e in display + candidates)


def test_looks_like_type_descriptor_does_not_reject_real_text():
    # 三段式但段间不含点分命名空间/程序集的真实文本必须保持可译：
    # 段 2 无点 / 段 3 无点 / 段内尾点句子 / 段间标点。
    assert not _looks_like_type_descriptor("Press A to continue")
    assert not _looks_like_type_descriptor("Level 1.5 Patch 2")
    assert not _looks_like_type_descriptor("See the File. Read the docs.")
    assert not _looks_like_type_descriptor("Open File. Read Syntax. Now go.")
    # 标准形态（类名 + 点分命名空间 + 点分程序集）必须命中。
    assert _looks_like_type_descriptor(
        "Parser UnityEngine.Localization.SmartFormat.Core.Parsing "
        "Unity.Localization")
    assert _looks_like_type_descriptor(
        "Text UnityEngine.UI.Text UnityEngine.UI")


def _pending_entry(original, confidence="high", reason="typetree_display_field"):
    return TextEntry(file_id="f", key_path="asset#f#1/field/k:m_Text",
                     original=original, status="pending",
                     meta={"kind": "typetree", "confidence": confidence,
                           "reason": reason, "role": "display"})


def test_downgrade_gate_keeps_credit_like_text_in_display_fields():
    # lilys-day-off level13 结局画廊实证：'A game by Kyuppin' 是 m_Text 显示
    # 字段里的真实显示文本，但被 credit/署名软猜测规则降级错过。证据分层：
    # 确定性显示字段条目只被硬结构降级，署名/版权类软猜测不得推翻 UI 字段证据。
    assert not _should_downgrade_pending(
        _pending_entry("A game by Kyuppin"))
    assert not _should_downgrade_pending(
        _pending_entry("Created by Sam Hogan"))
    assert not _should_downgrade_pending(
        _pending_entry("made in 48h"))


def test_downgrade_gate_soft_guess_still_applies_without_display_evidence():
    # 无确定性证据（candidate/raw scan 形态）时，署名软猜测仍降级——原行为。
    assert _should_downgrade_pending(
        _pending_entry("A game by Kyuppin", confidence="low",
                       reason="typetree_candidate"))
    assert _should_downgrade_pending(
        _pending_entry("Created by Sam Hogan", confidence="medium",
                       reason="rawstr_display_evidence"))


def test_downgrade_gate_hard_structural_always_downgrades():
    # 硬结构（纯数字/URL）即使出现在 UI 显示字段也降级——翻译会破坏功能。
    assert _should_downgrade_pending(_pending_entry("9"))
    assert _should_downgrade_pending(_pending_entry("https://example.com/x"))
    assert _should_downgrade_pending(_pending_entry("Assets/UI/panel.png"))
    # 非 pending 条目不动
    from dataclasses import replace
    entry = replace(_pending_entry("A game by Kyuppin", reason="x"),
                    status=STATUS_SKIPPED)
    assert not _should_downgrade_pending(entry)


def test_typetree_m_name_is_never_a_display_text():
    # doubleshake 实证：m_Name 是 Unity 对象标识名（Inspector 标题/Find 键），
    # 即使对象有值证据也绝不能升格 display——否则写回被
    # immutable_field_protected 拒绝并阻断整个发布。
    # 裸 name 字段（对话角色名等）不受影响。
    tree = {
        "m_Name": "Button_Start",
        "m_Text": "Play",
        "sub": {"m_Name": "Panel_Main", "m_Text": "Quit"},
        "bare_name": {"name": "Start"},
    }

    display, candidates = _typetree_string_entries("f", 11, tree)

    assert [(e.original, e.meta["field_path"]) for e in display] == [
        ("Play", ["m_Text"]),
        ("Quit", ["sub", "m_Text"]),
        ("Start", ["bare_name", "name"]),
    ]
    # m_Name 值不落入候选层（完全屏蔽，不是降级）
    assert not any("m_Name" in str(e.meta["field_path"])
                   for e in display + candidates)


def test_typetree_structural_tokens_do_not_match_inside_semantic_words():
    tree = {
        "videoSettings": {"m_Title": "Video Settings"},
        "identity": {"m_Text": "Player Identity"},
        "keyboardPrompt": {"text": "Press E"},
        "key_list": [{"label": "Settings"}],
        "bindingPath": {"description": "Jump"},
        "method": {"title": "Start"},
        "id": {"text": "Internal"},
    }

    display, _ = _typetree_string_entries("f", 9, tree)

    assert [entry.original for entry in display] == [
        "Video Settings", "Player Identity", "Press E"]


def test_typetree_field_path_encoding_is_type_aware_and_collision_free():
    paths = [
        ["a/b", "text"], ["a", "b", "text"],
        ["rows", 0, "label"], ["rows/0", "label"],
    ]

    encoded = [_encode_field_path(path) for path in paths]

    assert len(set(encoded)) == len(paths)
    assert encoded == [
        "k:a%2Fb/k:text", "k:a/k:b/k:text",
        "k:rows/i:0/k:label", "k:rows%2F0/k:label",
    ]
    assert [_decode_field_path(locator) for locator in encoded] == paths


def test_typetree_colliding_legacy_paths_are_distinct_in_project_store(tmp_path):
    tree = {"a/b": {"text": "Slash"},
            "a": {"b": {"text": "Nested"}},
            "rows": [{"label": "Indexed"}],
            "rows/0": {"label": "Slash index"}}
    display, _ = _typetree_string_entries("f", 10, tree)
    store = ProjectStore(tmp_path / "project.db")
    store.init_schema()
    store.upsert_entries([{
        "file_id": entry.file_id, "key_path": entry.key_path,
        "original": entry.original, "meta": entry.meta,
    } for entry in display])

    stored = store.get_entries()

    assert len(display) == len(stored) == 4
    assert {row["original"] for row in stored} == {
        "Slash", "Nested", "Indexed", "Slash index"}


def test_unsupported_typetree_fields_fall_back_to_raw_without_typed_duplicates(
        tmp_path, monkeypatch):
    import UnityPy

    class FakeObject:
        type = SimpleNamespace(name="MonoBehaviour")
        assets_file = SimpleNamespace(name="fixture.assets")

        def __init__(self, path_id, tree, text):
            self.path_id, self.tree = path_id, tree
            self.raw = _with_len(text)

        def read_typetree(self): return self.tree
        def get_raw_data(self): return self.raw

    objects = [
        FakeObject(1, {"message": "Return to the village."},
                   "Return to the village."),
        FakeObject(2, {"caption": "A dangerous road."},
                   "A dangerous road."),
        FakeObject(3, {"dialogue": "We should leave now."},
                   "We should leave now."),
        FakeObject(4, {"method": "Start"}, "Start"),
        FakeObject(5, {"text": "Settings"}, "Settings"),
    ]

    class FakeEnvironment:
        def __init__(self): self.objects, self.files = [], {}
        def load(self, _paths): self.objects = objects

    monkeypatch.setattr(UnityPy, "Environment", FakeEnvironment)
    path = tmp_path / "fixture.assets"
    path.write_bytes(b"fixture")

    parsed = extract_asset_file(path, "f")

    assert {entry.original for entry in parsed.entries
            if entry.status == "pending"} == {
        "Return to the village.", "A dangerous road.",
        "We should leave now.", "Settings"}
    settings = [entry for entry in parsed.entries
                if entry.original == "Settings"]
    assert len(settings) == 1 and settings[0].meta["kind"] == "typetree"
    assert all(entry.status == "skipped" for entry in parsed.entries
               if entry.original == "Start")


def test_find_asset_files_discovers_extensionless_level_scene(tmp_path):
    data_dir = tmp_path / "Example_Data"
    data_dir.mkdir()
    scene = data_dir / "level0"
    scene.write_bytes(b"UnityFS")

    assert find_asset_files(tmp_path) == [scene]


def test_source_locale_probe_skips_serialized_assets_but_checks_bundle_candidates(
        tmp_path, monkeypatch):
    data_dir = tmp_path / "Example_Data"
    data_dir.mkdir()
    ordinary = data_dir / "sharedassets0.assets"
    scene = data_dir / "level0"
    named_bundle = tmp_path / "localization-string-tables-english(en)_assets_all.bundle"
    generic_bundle = tmp_path / "resources.bundle"
    hashed_bundle = tmp_path / "5f9b21c7"
    ordinary.write_bytes(b"serialized asset")
    # 无后缀 SerializedFile：大端自洽头（v22：metadata/file_size/version/data_offset）
    scene.write_bytes(
        struct.pack(">III I B 3x I Q Q 4x", 0, 4096, 22, 2048, 0, 1024, 4096, 2048)
        + b"\x00" * 64)
    named_bundle.write_bytes(b"bundle fixture")
    generic_bundle.write_bytes(b"bundle fixture")
    hashed_bundle.write_bytes(b"UnityFS")
    calls = []

    def probe(path):
        calls.append(path)
        return None

    monkeypatch.setattr(
        "hanhua.core.unity.extractor._localization_bundle_probe", probe)

    assert set(find_asset_files(tmp_path)) == {
        ordinary, scene, named_bundle, generic_bundle, hashed_bundle}
    assert set(calls) == {named_bundle, generic_bundle, hashed_bundle}


@pytest.mark.parametrize("suffix", [".ab", ".unity3d", ".bundle", ".pak"])
def test_source_locale_probe_groups_every_bundle_suffix(
        tmp_path, monkeypatch, suffix):
    english = tmp_path / f"english{suffix}"
    spanish = tmp_path / f"spanish{suffix}"
    english.write_bytes(b"bundle fixture")
    spanish.write_bytes(b"bundle fixture")
    identity = frozenset({"shared:2:1733287269080016787"})
    probes = {english: (identity, "en"), spanish: (identity, "es")}
    calls = []

    def probe(path):
        calls.append(path)
        return probes[path]

    monkeypatch.setattr(
        "hanhua.core.unity.extractor._localization_bundle_probe", probe)

    assert find_asset_files(tmp_path) == [english]
    assert set(calls) == {english, spanish}


def test_extensionless_string_tables_route_by_logical_identity_and_locale(
        tmp_path, monkeypatch):
    paths = {name: tmp_path / name for name in (
        "hash_en", "hash_es", "hash_ru", "hash_non_table", "hash_unknown")}
    for path in paths.values():
        path.write_bytes(b"UnityFS")
    table_identity = frozenset({"shared:2:1733287269080016787"})
    probes = {
        paths["hash_en"]: (table_identity, "en"),
        paths["hash_es"]: (table_identity, "es"),
        paths["hash_ru"]: (table_identity, "ru"),
        paths["hash_non_table"]: None,
        paths["hash_unknown"]: None,
    }
    calls = []

    def probe(path):
        calls.append(path)
        return probes[path]

    monkeypatch.setattr(
        "hanhua.core.unity.extractor._localization_bundle_probe", probe)

    assert set(find_asset_files(tmp_path)) == {
        paths["hash_en"], paths["hash_non_table"], paths["hash_unknown"]}
    assert set(calls) == set(paths.values())


def test_extensionless_string_tables_keep_all_when_english_is_absent(
        tmp_path, monkeypatch):
    spanish = tmp_path / "hash_es"
    russian = tmp_path / "hash_ru"
    for path in (spanish, russian):
        path.write_bytes(b"UnityFS")
    identity = frozenset({"shared:2:1733287269080016787"})
    probes = {spanish: (identity, "es"), russian: (identity, "ru")}
    monkeypatch.setattr(
        "hanhua.core.unity.extractor._localization_bundle_probe",
        lambda path: probes[path],
    )

    assert find_asset_files(tmp_path) == [spanish, russian]


def test_localization_bundle_probe_disposes_environment(tmp_path, monkeypatch):
    import UnityPy
    from hanhua.core.unity import writer

    path = tmp_path / "hash_en"
    path.write_bytes(b"UnityFS")
    tree = {
        "m_Name": "UITable_en",
        "m_LocaleId": {"m_Code": "en"},
        "m_SharedData": {"m_FileID": 2, "m_PathID": 1733287269080016787},
        "m_TableData": [{"m_Id": 1, "m_Localized": "Settings"}],
    }
    obj = SimpleNamespace(read_typetree=lambda: tree)

    class FakeEnvironment:
        def __init__(self): self.objects = []
        def load(self, loaded):
            assert loaded == [str(path)]
            self.objects = [obj]

    disposed = []
    monkeypatch.setattr(UnityPy, "Environment", FakeEnvironment)
    monkeypatch.setattr(writer, "_dispose_environment", disposed.append)

    assert _localization_bundle_probe(path) == (
        frozenset({"shared:2:1733287269080016787"}), "en")
    assert len(disposed) == 1


def test_find_asset_files_rejects_level_scene_outside_data_tree(tmp_path):
    outside_scene = tmp_path / "level1"
    outside_scene.write_bytes(b"not a Unity data-tree scene")

    assert find_asset_files(tmp_path) == []


def test_find_asset_files_requires_lowercase_level_scene_name(tmp_path):
    data_dir = tmp_path / "Example_Data"
    data_dir.mkdir()
    uppercase_scene = data_dir / "Level0"
    uppercase_scene.write_bytes(b"wrong-case scene name")

    assert find_asset_files(tmp_path) == []


def test_localization_source_selection_prefers_tree_locale_over_filename(
        monkeypatch):
    spanish_name = Path(
        "localization-string-tables-spanish(es)_assets_all.bundle")
    english_name = Path(
        "localization-string-tables-english(en)_assets_all.bundle")
    locales = {spanish_name: "en", english_name: "es"}
    monkeypatch.setattr(
        "hanhua.core.unity.extractor._localization_bundle_locale",
        lambda path: locales[path],
    )

    assert _prefer_source_locale_bundles([spanish_name, english_name]) == [
        spanish_name,
    ]


def test_localization_tree_locales_keep_all_when_english_is_absent(monkeypatch):
    first = Path("localization-string-tables-first_assets_all.bundle")
    second = Path("localization-string-tables-second_assets_all.bundle")
    locales = {first: "es", second: "ru"}
    monkeypatch.setattr(
        "hanhua.core.unity.extractor._localization_bundle_locale",
        lambda path: locales[path],
    )

    assert _prefer_source_locale_bundles([first, second]) == [first, second]


def test_scan_strings_finds_serialized():
    raw = b"\x00\x01\x02\x03" + _with_len("Hello player") + _with_len("第二行文本") + b"\xff\xfe"
    found = scan_strings(raw)
    texts = [s for _, s in found]
    assert "Hello player" in texts and "第二行文本" in texts


def test_scan_strings_filters_garbage():
    raw = b"\x00\x01\x02\x03" + _with_len("ok") + b"\x10\x00\x00\x00" + b"x" * 16
    found = scan_strings(raw)
    texts = [s for _, s in found]
    assert all(s != "ok" for s in texts)      # 过短不采


def test_scan_strings_requires_aligned_header_and_zero_padding():
    valid = struct.pack("<I", 5) + b"Hello" + b"\x00\x00\x00"
    unaligned_false_positive = b"X" + struct.pack("<I", 3) + b"`\tB"
    invalid_padding = struct.pack("<I", 5) + b"Hello" + b"XYZ"

    assert scan_strings(valid) == [(4, "Hello")]
    assert scan_strings(unaligned_false_positive) == []
    assert scan_strings(invalid_padding) == []


def test_raw_scan_keeps_651_byte_display_description():
    prefix = "This display description explains what the player must do. "
    description = (prefix + "More visible details. " * 40)[:650] + "."
    assert len(description.encode("utf-8")) == 651

    entries = _raw_string_entries("f1", 5, _with_len(description), {})

    assert len(entries) == 1
    assert entries[0].original == description
    assert entries[0].status == "pending"
    assert entries[0].meta["role"] == "display"


def test_unaligned_raw_scan_accepts_exact_4096_byte_boundary():
    description = ("Visible details for the player. " * 200)[:4095] + "."
    assert len(description.encode("utf-8")) == 4096
    encoded = description.encode("utf-8")
    raw = b"\xff" + struct.pack("<I", len(encoded)) + encoded
    raw += b"\x00" * (-len(raw) % 4)

    entries = _raw_string_entries("f1", 5, raw, {})

    assert len(entries) == 1
    assert entries[0].original == description
    assert entries[0].meta["scan_mode"] == "unaligned"


@pytest.mark.parametrize("prefix", [b"\xff", b"\xff\xfe", b"\xff\xfe\xfd"])
def test_raw_entries_recover_unaligned_interaction_prompt(prefix):
    encoded = b"Press E to open"
    raw = prefix + struct.pack("<I", len(encoded)) + encoded
    raw += b"\x00" * (-len(raw) % 4)

    entries = _raw_string_entries("f1", 5, raw, {})

    assert len(entries) == 1
    assert entries[0].original == "Press E to open"
    assert entries[0].status == "pending"
    assert entries[0].meta["role"] == "display"
    assert entries[0].meta["reason"] == "interaction_prompt"
    assert entries[0].meta["scan_mode"] == "unaligned"


@pytest.mark.parametrize("text", [
    "按 E 键打开",
    "Нажмите E, чтобы открыть.",
])
def test_raw_entries_recover_unaligned_utf8_display_text(text):
    encoded = text.encode("utf-8")
    raw = b"\xff" + struct.pack("<I", len(encoded)) + encoded
    raw += b"\x00" * (-len(raw) % 4)

    entries = _raw_string_entries("f1", 5, raw, {})

    assert len(entries) == 1
    assert entries[0].original == text
    assert entries[0].status == "pending"
    assert entries[0].meta["scan_mode"] == "unaligned"


@pytest.mark.parametrize("text", ["Move", "Fire", "set_clip", "TMPro.TMP_Text"])
def test_unaligned_structural_strings_are_not_promoted(text):
    raw = b"\xff" + struct.pack("<I", len(text.encode("utf-8"))) + text.encode("utf-8")
    raw += b"\x00" * (-len(raw) % 4)

    assert _raw_string_entries("f1", 5, raw, {}) == []


def test_is_engine_string():
    assert _is_engine_string("_MainTex")
    assert _is_engine_string("UnityEngine.Rendering.DebugUI")
    assert _is_engine_string("TextMeshPro/Mobile/Distance Field")
    assert _is_engine_string("Navigate")          # Input System 默认绑定
    assert _is_engine_string("Keyboard&Mouse")
    assert not _is_engine_string("Hello player")
    assert not _is_engine_string("要活下去")


def test_input_system_binding_path_and_interaction_are_engine_strings():
    # morfosigame 实证：InputActionAsset 序列化绑定路径/交互串是引擎语法，
    # 全局剔除（即使对象级判定漏网也不会被提取翻译）
    assert _is_engine_string("<Keyboard>/z")
    assert _is_engine_string("<Keyboard>/upArrow")
    assert _is_engine_string("<Mouse>/position")
    assert _is_engine_string("<Gamepad>/leftStick")
    assert _is_engine_string("<Gamepad>/buttonSouth")
    assert _is_engine_string("Press(behavior=2)")
    assert _is_engine_string("Hold()")
    assert _is_engine_string("Tap()")
    assert _is_engine_string("SlowTap()")
    assert not _is_engine_string("<b>Hello</b>")


def test_timeline_track_with_index_is_engine_string():
    # 带编号轨道名（Unity Timeline 轨道重名自动加 (1)）是引擎 displayName
    assert _is_engine_string("Animation Track (1)")
    assert _is_engine_string("Activation Track (2)")
    assert _is_engine_string("Audio Track (1)")
    assert _is_engine_string("Animation Track")
    assert not _is_engine_string("Track 7 night festival")


@pytest.mark.parametrize("text", [
    "Press E to open",
    "Hold [F] to interact",
    "Click to continue",
    "E - Open",
    "按 E 键打开",
    "Press E",
    "Press E to calibrate the flux capacitor",
    "Press E on the radar to mark a location",
    "E - Calibrate the flux capacitor",
    "right click with Harpoon equipped to reel in",
    "Square/X/Y Button: Jump",
])
def test_interaction_prompts_have_display_text_evidence(text):
    assert is_interaction_prompt(text)
    assert has_display_text_evidence(text)


@pytest.mark.parametrize("text", [
    "Move", "Fire", "WASD", "set_clip", "TMPro.TMP_Text",
])
def test_structural_strings_do_not_have_display_text_evidence(text):
    assert not has_display_text_evidence(text)


@pytest.mark.parametrize("text", [
    "F - MyGame.DispatchEvent",
    "F - set_clip",
    "E - m_Action",
    "F - Open.Method",
    "F - Use.Action",
    "E - Fire.Event",
    "F - MyGame.DispatchEvent()",
    "F - set_clip()",
    "E - m_Action[0]",
])
def test_code_actions_after_glyph_are_not_interaction_prompts(text):
    assert not is_interaction_prompt(text)
    assert not has_display_text_evidence(text)


@pytest.mark.parametrize("text", [
    "F - MyGame.DispatchEvent",
    "F - set_clip",
    "E - m_Action",
    "F - Open.Method",
    "F - Use.Action",
    "E - Fire.Event",
    "F - MyGame.DispatchEvent()",
    "F - set_clip()",
    "E - m_Action[0]",
])
def test_raw_code_actions_after_glyph_remain_structural(text):
    entries = _raw_string_entries("f1", 8, _with_len(text), {})

    assert len(entries) == 1
    entry = entries[0]
    assert entry.status == "skipped"
    assert entry.meta["confidence"] == "low"
    assert entry.meta["role"] == "structural"
    assert entry.meta["reason"] == "code_action_binding"


@pytest.mark.parametrize(("text", "tokens"), [
    ("Press SPACE to jump", ("SPACE",)),
    ("Click Mouse1 to fire", ("Mouse1",)),
    ("Hold Left Shift to sprint", ("Left Shift",)),
    ("E - Open", ("E",)),
    ("Press (E) to open", ("E",)),
    ("Press <E> to open", ("E",)),
    ("Press LB to block", ("LB",)),
    ("Press R1 to dodge", ("R1",)),
    ("Press Numpad 1 to select", ("Numpad 1",)),
    ("Press Esc to exit", ("Esc",)),
    ("Press Backspace to close", ("Backspace",)),
    ("Press Delete to remove", ("Delete",)),
    ("Press Enter to confirm", ("Enter",)),
    ("Press the Enter key to confirm", ("Enter",)),
    ("Hold the Space key to jump", ("Space",)),
    ("Press Tab to switch", ("Tab",)),
    ("Press Space to jump", ("Space",)),
    ("Press Page Up to scroll", ("Page Up",)),
    ("Press Page Down to scroll", ("Page Down",)),
    ("Press Home to return", ("Home",)),
    ("Press End to finish", ("End",)),
    ("Press Insert to toggle", ("Insert",)),
    ("Press D-Pad Up to select", ("D-Pad Up",)),
    ("Press D-Pad Down to select", ("D-Pad Down",)),
    ("Press D-Pad Left to select", ("D-Pad Left",)),
    ("Press D-Pad Right to select", ("D-Pad Right",)),
    ("Press Ctrl+Delete to remove", ("Ctrl+Delete",)),
    ("Press Page Up+Shift to scroll", ("Page Up+Shift",)),
    ("Press D-Pad Up+LB to select", ("D-Pad Up+LB",)),
])
def test_interaction_prompt_preserves_complete_input_glyph(text, tokens):
    assert is_interaction_prompt(text)
    assert interaction_input_tokens(text) == tokens


@pytest.mark.parametrize(("text", "token"), [
    ("Press Ctrl_Delete to remove", "Ctrl_Delete"),
    ("Press Ctrl-Delete to remove", "Ctrl-Delete"),
])
def test_interaction_position_preserves_physical_binding_chord(text, token):
    assert interaction_input_tokens(text) == (token,)


def test_interaction_position_does_not_capture_natural_hyphenated_phrase():
    assert interaction_input_tokens("Press Long-term plan") == ()


def test_interaction_input_events_type_literal_glyphs_in_source_order():
    text = "Press 'E', hold Shift, click Mouse1, tap [F], then press 2"

    assert interaction_input_events(text) == (
        InputEvent("literal_glyph", "E"),
        InputEvent("literal_glyph", "Shift"),
        InputEvent("literal_glyph", "Mouse1"),
        InputEvent("literal_glyph", "F"),
        InputEvent("literal_glyph", "2"),
    )


@pytest.mark.parametrize(("text", "value"), [
    ("Press Any Key", "Any Key"),
    ("right click with Harpoon equipped to reel in", "right click"),
    ("Square/X/Y Button: Jump", "Square/X/Y Button"),
    ("Press X Button to jump", "X Button"),
])
def test_interaction_input_events_type_translatable_semantic_inputs(text, value):
    assert interaction_input_events(text) == (InputEvent("semantic_input", value),)
    assert interaction_input_tokens(text) == ()


def test_multiline_interaction_glyph_does_not_absorb_previous_item_label():
    text = "Key30\nG - to throw\n"

    assert is_interaction_prompt(text)
    assert interaction_input_tokens(text) == ("G",)


def test_ambiguous_ui_words_are_not_global_engine_strings():
    for text in ("volume", "fullscreen", "vsync", "cancel", "submit"):
        assert not _is_engine_string(text)


# ── 长度适配 ──
def test_fit_bytes_short_pads():
    out, truncated = _fit_bytes("你好", 20, "utf-8")
    assert len(out) == 20 and not truncated
    assert out.endswith(b"\x00" * 14)


def test_fit_bytes_truncates_utf8():
    out, truncated = _fit_bytes("这是一句很长的中文", 9, "utf-8")
    assert truncated and len(out) == 9
    out.decode("utf-8")   # 必须是合法 UTF-8（字符边界截断）
    assert out.decode("utf-8", errors="replace").endswith("…")   # 末尾省略号提示


def test_fit_bytes_small_capacity_no_ellipsis():
    out, truncated = _fit_bytes("太长太长太长", 5, "utf-8")
    assert truncated and len(out) == 5
    assert "…" not in out.decode("utf-8")   # 容量太小不加省略号


def test_fit_bytes_utf16():
    out, truncated = _fit_bytes("开始游戏", 20, "utf-16-le")
    assert len(out) == 20 and not truncated
    out, truncated = _fit_bytes("This is a very long english string", 10, "utf-16-le")
    assert truncated and len(out) == 10


# ── TextAsset 提取与写回 ──
def test_textasset_lines_extract():
    raw = "Hello there\n第二行\nThird line with {name} tag\n".encode("utf-8")
    entries = _textasset_entries("f1", 100, raw)
    orig = {e.key_path: e.original for e in entries}
    assert orig["asset#100/line/0"] == "Hello there"
    assert orig["asset#100/line/1"] == "第二行"
    assert orig["asset#100/line/2"] == "Third line with {name} tag"
    assert all(entry.meta["disposition"] == "translate" for entry in entries)
    assert all(entry.meta["role"] == "display" for entry in entries)


def test_textasset_identity_includes_serialized_file_name():
    entries = _textasset_entries(
        "f1", 100, b"Hello there\n", "archive:/CAB-demo/CAB-demo")
    assert entries[0].key_path == (
        "asset#archive:/CAB-demo/CAB-demo#100/line/0")
    assert entries[0].meta["asset_file"] == "archive:/CAB-demo/CAB-demo"


def test_textasset_binary_control_chars_filtered():
    # 二进制 TextAsset（音频/网格/压缩）：非可打印字节占比 >5% → 无条目
    raw = b"\x00\x01\x02\x03" * 100 + b"Hello there\n"
    assert _textasset_entries("f1", 100, raw) == []


def test_textasset_data_rows_filtered():
    # 数据文件（关卡/配置数字表）：行内 ≥3 字母单词密度 <30% → 无条目
    # （electric-trains fp_level_* 实证）
    raw = "6098:1\r\n0:12:-1:none\r\n0:13:-1:none\r\n0:14:-1:none\r\n0:15:-1:none\r\n0:40:-1:none\r\n".encode()
    assert _textasset_entries("f1", 100, raw) == []


def test_textasset_data_rows_kept_when_wordy():
    # 真文本（字典/字幕）每行含单词 → 不被数据判定误伤
    raw = b"missions=Missioni\nfreeplay=Gioco gratuito\nsettings=Impostazioni\nexit=Uscita\n"
    entries = _textasset_entries("f1", 100, raw)
    assert len(entries) == 4
    assert entries[0].original == "missions=Missioni"


def test_extract_asset_file_deduplicates_wrapper_aliases_by_stable_identity(
        tmp_path, monkeypatch):
    import UnityPy

    class FakeObject:
        path_id = 100
        type = type("FakeType", (), {"name": "TextAsset"})()

        def __init__(self):
            self.assets_file = type(
                "FakeSerializedFile", (), {"name": "archive:/CAB-demo/CAB-demo"})()

        def read(self):
            return type("FakeTextAsset", (), {"m_Script": b"Hello there\n"})()

    class FakeEnvironment:
        def __init__(self):
            self.objects = [FakeObject(), FakeObject()]
            self.files = {}

        def load(self, _paths):
            return None

    monkeypatch.setattr(UnityPy, "Environment", FakeEnvironment)

    parsed = extract_asset_file(tmp_path / "sample.assets", "sample.assets")

    assert [entry.original for entry in parsed.entries] == ["Hello there"]


def test_extract_asset_file_keeps_same_path_id_from_different_serialized_files(
        tmp_path, monkeypatch):
    import UnityPy

    class FakeObject:
        path_id = 100
        type = type("FakeType", (), {"name": "TextAsset"})()

        def __init__(self, asset_file_name, text):
            self.assets_file = type(
                "FakeSerializedFile", (), {"name": asset_file_name})()
            self._text = text

        def read(self):
            return type("FakeTextAsset", (), {"m_Script": self._text})()

    class FakeEnvironment:
        def __init__(self):
            self.objects = [
                FakeObject("archive:/CAB-first/CAB-first", b"First text\n"),
                FakeObject("archive:/CAB-second/CAB-second", b"Second text\n"),
            ]
            self.files = {}

        def load(self, _paths):
            return None

    monkeypatch.setattr(UnityPy, "Environment", FakeEnvironment)

    parsed = extract_asset_file(tmp_path / "sample.bundle", "sample.bundle")

    assert [entry.original for entry in parsed.entries] == [
        "First text", "Second text",
    ]


def test_textasset_json_extract():
    raw = b'{"title": "Echoes", "items": ["Follow", "Leave"]}'
    entries = _textasset_entries("f1", 100, raw)
    orig = {e.key_path: e.original for e in entries}
    assert orig["asset#100/json/title"] == "Echoes"
    assert orig["asset#100/json/items/0"] == "Follow"


def test_textasset_patch_roundtrip():
    from hanhua.core.models import TextEntry, TranslateStats
    from hanhua.core.unity.writer import WriteResult
    script = "Hello there\nSecond Line\n".encode("utf-8")
    items = [({"original": "Hello there", "translation": "你好呀", "meta": "{}"},
              {"kind": "textasset", "line": 0})]
    out = _patch_textasset(script, items, [], WriteResult())
    # TextAsset 的 m_Script 是可变长 byte[] 字段——译文可自由变长，不截断
    assert out.decode("utf-8").startswith("你好呀")
    assert "Second Line" in out.decode("utf-8")
    assert len(out) != len(script)


def test_textasset_patch_long_translation_free():
    from hanhua.core.unity.writer import WriteResult
    script = "Hi\n".encode("utf-8")
    items = [({"original": "Hi", "translation": "很长很长的翻译没有任何长度限制",
               "meta": "{}"}, {"kind": "textasset", "line": 0})]
    res = WriteResult()
    out = _patch_textasset(script, items, [], res)
    assert res.truncated == 0
    assert out.decode("utf-8").startswith("很长很长的翻译没有任何长度限制")


def test_raw_string_entries_filters_engine():
    from hanhua.core.models import TextEntry
    raw = (b"\x00" * 8) + _with_len("_MainTex") + _with_len("Follow the light") + _with_len("Yes")
    entries = _raw_string_entries("f1", 5, raw, {"_MainTex": 300, "Follow the light": 1, "Yes": 1})
    orig = [e.original for e in entries]
    assert "Follow the light" in orig
    assert "_MainTex" not in orig      # 引擎属性
    assert "Yes" in orig               # 显示单词（白名单）→ 可翻译


def test_single_string_object_is_high_confidence_display_text():
    entries = _raw_string_entries("f1", 5, _with_len("Battery"), {})

    assert len(entries) == 1
    entry = entries[0]
    assert entry.original == "Battery"
    assert entry.status == "pending"
    assert entry.meta["confidence"] == "high"
    assert entry.meta["role"] == "display"
    assert entry.meta["disposition"] == "translate"
    assert entry.meta["reason"] == "single_visible_string"


def test_resources_asset_single_identifier_requires_display_evidence():
    entry = _raw_string_entries(
        "resources.assets", 5, _with_len("Enum"), {}, "resources.assets",
    )[0]

    assert entry.status == "skipped"
    assert entry.meta["confidence"] == "low"
    assert entry.meta["role"] == "structural"
    assert entry.meta["disposition"] == "structural"
    assert entry.meta["reason"] == "resource_identifier_without_display_evidence"


def test_single_input_binding_names_are_low_confidence_structure():
    for text in ("Move", "WASD", "Fire", "Look"):
        entries = _raw_string_entries("f1", 5, _with_len(text), {})
        assert len(entries) == 1
        entry = entries[0]
        assert entry.status == "skipped"
        assert entry.meta["confidence"] == "low"
        assert entry.meta["role"] == "structural"
        assert entry.meta["reason"] == "input_binding"

    battery = _raw_string_entries("f1", 6, _with_len("Battery"), {})[0]
    assert battery.status == "pending"
    assert battery.meta["confidence"] == "high"
    assert battery.meta["role"] == "display"


@pytest.mark.parametrize("text", [
    "right click", "Right Click", "RIGHT CLICK",
    "Square Button", "square button", "X Button", "x button", "Y Button",
    "Square/X/Y Button",
])
def test_bare_semantic_inputs_remain_low_confidence_bindings(text):
    assert not is_interaction_prompt(text)
    assert not has_display_text_evidence(text)

    entry = _raw_string_entries("f1", 6, _with_len(text), {})[0]
    assert entry.status == "skipped"
    assert entry.meta["confidence"] == "low"
    assert entry.meta["role"] == "structural"
    assert entry.meta["reason"] == "input_binding"


@pytest.mark.parametrize("text", [
    "Ctrl_Delete", "Ctrl-Delete", "D-Pad Up",
])
def test_physical_binding_identifiers_remain_structural_in_raw_entries(text):
    assert _structural_reason(text) == "input_binding"

    entry = _raw_string_entries("f1", 10, _with_len(text), {})[0]
    assert entry.status == "skipped"
    assert entry.meta["confidence"] == "low"
    assert entry.meta["role"] == "structural"
    assert entry.meta["reason"] == "input_binding"


@pytest.mark.parametrize("text", [
    "Press Ctrl_Delete to remove",
    "Press Ctrl-Delete to remove",
])
def test_raw_interaction_with_physical_binding_chord_is_display(text):
    entry = _raw_string_entries("f1", 11, _with_len(text), {})[0]

    assert entry.status == "pending"
    assert entry.meta["confidence"] == "high"
    assert entry.meta["role"] == "display"
    assert entry.meta["reason"] == "interaction_prompt"


def test_natural_hyphenated_phrase_is_not_a_physical_binding_identifier():
    assert _structural_reason("Long-term plan") is None


@pytest.mark.parametrize("text", [
    "Player/Move", "Player/Fire1", "Menu/dPadHoriz", "Debug/Warp 0",
    "Forward/Back Tilt", "Pause/Unpause", "Save/Load", "Menu/Escape",
    "battle/spr_damage_numbers", "CameraRig/MainCamera",
])
def test_input_action_paths_remain_structural_in_raw_entries(text):
    """InputSystem action 路径：翻译后按键查找失败 → 必须跳过。
    真实语料：ivor Player/* 323 条、doubleshake Menu/* 48 条曾被误标 display。"""
    assert _structural_reason(text) == "input_action_path"

    entry = _raw_string_entries("f1", 12, _with_len(text), {})[0]
    assert entry.status == "skipped"
    assert entry.meta["reason"] == "input_action_path"


@pytest.mark.parametrize("text", [
    "Failed to parse server key/certificate",
    "Private/public key mismatch",
    "Sprite Assets/Default Sprite Asset",
])
def test_sentence_shaped_slashes_are_not_input_action_paths(text):
    """词数超限的句子（真实语料：IL2CPP metadata 错误消息）不得判为 action 路径。"""
    assert _structural_reason(text) is None


def test_controller_prompt_with_slashes_survives_raw_string_filtering():
    entries = _raw_string_entries(
        "f1", 7, _with_len("Square/X/Y Button: Jump"), {})

    assert len(entries) == 1
    entry = entries[0]
    assert entry.status == "pending"
    assert entry.meta["confidence"] == "high"
    assert entry.meta["role"] == "display"
    assert entry.meta["reason"] == "interaction_prompt"


@pytest.mark.parametrize("text", [
    "Assets/right click/config",
    "Assets/Square Button/config",
    "Assets/right click to/config",
    "C:\\UI\\right click with Harpoon equipped",
    "Assets/Square/X/Y Button: Jump/config",
])
def test_semantic_input_words_inside_paths_remain_filtered(text):
    assert _raw_string_entries("f1", 9, _with_len(text), {}) == []


def test_code_heavy_object_keeps_sentence_and_marks_structure_skipped():
    raw = (_with_len("Play") + _with_len("set_clip")
           + _with_len("UnityEngine.AudioSource")
           + _with_len("Press E to interact"))
    entries = _raw_string_entries("f1", 5, raw, {})
    by_orig = {entry.original: entry for entry in entries}

    prompt = by_orig["Press E to interact"]
    assert prompt.status == "pending"
    assert prompt.meta["confidence"] == "high"
    assert prompt.meta["role"] == "display"
    assert prompt.meta["reason"] == "interaction_prompt"

    # 'Play' 是 DISPLAY_WORDS 白名单成员（UI 按钮文本）——code_heavy 对象中仍放行
    assert by_orig["Play"].status == "pending"
    assert by_orig["Play"].meta["reason"] == "code_heavy_display_word"
    assert by_orig["set_clip"].status == "skipped"
    assert by_orig["set_clip"].meta["reason"] == "method_name"
    assert by_orig["UnityEngine.AudioSource"].status == "skipped"
    assert by_orig["UnityEngine.AudioSource"].meta["reason"] == "type_reference"
    assert by_orig["Play"].meta["confidence"] == "medium"
    assert by_orig["Play"].meta["role"] == "display"
    assert all(by_orig[text].meta["confidence"] == "low"
               for text in ("set_clip", "UnityEngine.AudioSource"))
    assert all(by_orig[text].meta["role"] == "structural"
               for text in ("set_clip", "UnityEngine.AudioSource"))


def test_code_heavy_button_object_skips_control_state_names():
    # code_heavy 按钮对象（类型引用 + 控件状态 + Play）：Play/Instructions
    # 放行（code_heavy_display_word），但 Normal/Highlighted/Pressed/Disabled
    # 是 Unity VisualState 引擎文本，不得翻译（hotel-paradise 真实误伤）
    raw = (b"\x00" * 8) + b"".join(_with_len(text) for text in (
        "Normal", "Highlighted", "Pressed", "Disabled",
        "Play", "Instructions",
        "UnityEngine.UI.Button", "UnityEngine.UI.Image",
    ))
    entries = _raw_string_entries("mainData", 7, raw, {})
    by_orig = {entry.original: entry for entry in entries}

    assert by_orig["Play"].status == "pending"
    assert by_orig["Play"].meta["reason"] == "code_heavy_display_word"
    assert by_orig["Instructions"].status == "pending"
    assert by_orig["Instructions"].meta["reason"] == "code_heavy_display_word"
    assert all(by_orig[text].status == "skipped"
               and by_orig[text].meta["reason"] == "code_heavy_identifier"
               for text in ("Normal", "Highlighted", "Pressed", "Disabled"))


def test_general_qualified_types_and_lifecycle_methods_make_object_code_heavy():
    raw = (_with_len("Play") + _with_len("TMPro.TMP_Text")
           + _with_len("MyGame.Audio.Controller") + _with_len("Update")
           + _with_len("Press E to interact"))
    entries = _raw_string_entries("f1", 5, raw, {})
    by_orig = {entry.original: entry for entry in entries}

    prompt = by_orig["Press E to interact"]
    assert prompt.status == "pending"
    assert prompt.meta["confidence"] == "high"
    assert prompt.meta["role"] == "display"
    assert prompt.meta["reason"] == "interaction_prompt"

    expected_reasons = {
        "TMPro.TMP_Text": "type_reference",
        "MyGame.Audio.Controller": "type_reference",
        "Update": "lifecycle_method",
    }
    for text, reason in expected_reasons.items():
        entry = by_orig[text]
        assert entry.status == "skipped"
        assert entry.meta["confidence"] == "low"
        assert entry.meta["role"] == "structural"
        assert entry.meta["reason"] == reason

    # code-heavy 对象但有 UI 证据（交互提示）时，白名单显示词（Play）放行
    play = by_orig["Play"]
    assert play.status == "pending"
    assert play.meta["confidence"] == "medium"
    assert play.meta["role"] == "display"
    assert play.meta["reason"] == "code_heavy_display_word"

    single_start = _raw_string_entries("f1", 6, _with_len("Start"), {})[0]
    assert single_start.status == "skipped"
    assert single_start.meta["confidence"] == "low"
    assert single_start.meta["role"] == "structural"
    assert single_start.meta["reason"] == "lifecycle_method"


def test_assembly_reference_requires_a_complete_type_and_assembly_shape():
    welcome = _raw_string_entries(
        "f1", 5, _with_len("Welcome, Unity"), {})[0]
    assert welcome.status == "pending"
    assert welcome.meta["confidence"] in ("high", "medium")
    assert welcome.meta["role"] == "display"
    assert welcome.meta["reason"] != "type_reference"

    references = (
        "MenuButton, Assembly-CSharp",
        "TMPro.TMP_Text, Unity.TextMeshPro",
        ("OneBit, Assembly-CSharp, Version=0.0.0.0, Culture=neutral, "
         "PublicKeyToken=null"),
    )
    for text in references:
        entry = _raw_string_entries("f1", 6, _with_len(text), {})[0]
        assert entry.status == "skipped"
        assert entry.meta["confidence"] == "low"
        assert entry.meta["role"] == "structural"
        assert entry.meta["reason"] == "type_reference"


def test_raw_string_entries_skips_identifier_keys():
    # Localization 表键/标识符形态：ui_newGame、MENU_PLAY、UITable_en 绝不翻译
    raw = (b"\x00" * 8) + _with_len("ui_newGame") + _with_len("MENU_PLAY") \
        + _with_len("UITable_en") + _with_len("phone_call_01") + _with_len("NEW GAME")
    entries = _raw_string_entries("f1", 5, raw, {})
    orig = [e.original for e in entries]
    assert all(k not in orig for k in ("ui_newGame", "MENU_PLAY", "UITable_en", "phone_call_01"))
    assert "NEW GAME" in orig          # 含空格 → 显示文本


def test_raw_string_entries_key_list_object_all_skipped():
    # SharedTableData 键列表对象（≥85% 键风格标识符）：全部键被剔除
    raw = (b"\x00" * 8) + _with_len("ui_settings") + _with_len("ui_options") \
        + _with_len("ui_quit") + _with_len("ui_back") + _with_len("ui_language") \
        + _with_len("New Game")
    entries = _raw_string_entries("f1", 5, raw, {})
    by_orig = {e.original: e for e in entries}
    assert all(k not in by_orig for k in ("ui_settings", "ui_options", "ui_language"))
    assert by_orig["New Game"].status == "pending"        # 值形态文本保留


def test_raw_string_entries_marker_object_skips_identifiers():
    # 含 UnityEngine.Localization 标记的对象（SharedTableData）：单词式键也跳过
    raw = (b"\x00" * 8) + _with_len("Settings") + _with_len("Quit") \
        + _with_len("New Game") + _with_len("UnityEngine.Localization.Tables")
    entries = _raw_string_entries("f1", 5, raw, {})
    by_orig = {e.original: e for e in entries}
    assert by_orig["Settings"].status == "skipped"
    assert by_orig["Quit"].status == "skipped"
    assert by_orig["New Game"].status == "pending"     # 值形态文本保留


def test_raw_string_entries_word_values_translatable():
    # 值特征对象（含句子）：单词式写法（任意语言的 UI 标签）是显示值，可翻译
    raw = (b"\x00" * 8) + _with_len("CREDITOS") + _with_len("SENSIBILIDAD") \
        + _with_len("CONTINUAR") + _with_len("ui_newGame") \
        + _with_len("Press any key to continue.")
    entries = _raw_string_entries("f1", 5, raw, {})
    by_orig = {e.original: e for e in entries}
    assert by_orig["CREDITOS"].status == "pending"       # 西语 UI 标签 → 值
    assert by_orig["SENSIBILIDAD"].status == "pending"
    assert "ui_newGame" not in by_orig                   # 键风格 → 键，剔除


def test_core_menu_terms_require_ui_collection_evidence():
    menu_terms = ("Quit", "Controls", "Settings", "Resolution", "SFX", "Volume")
    menu_raw = (b"\x00" * 8) + b"".join(_with_len(text) for text in menu_terms)
    menu_entries = _raw_string_entries("menu", 5, menu_raw, {})
    by_menu = {entry.original: entry for entry in menu_entries}

    for text in menu_terms:
        assert by_menu[text].status == "pending"
        assert by_menu[text].meta["role"] == "display"
        assert by_menu[text].meta["disposition"] == "translate"
        assert by_menu[text].meta["reason"] == "core_menu_collection"

    code_raw = menu_raw + _with_len("Game.PlayerController") + _with_len("Update")
    code_entries = _raw_string_entries("code", 6, code_raw, {})
    by_code = {entry.original: entry for entry in code_entries}
    assert all(by_code[text].status == "skipped" for text in menu_terms)
    assert all(by_code[text].meta["role"] == "structural" for text in menu_terms)


def test_single_core_menu_term_uses_unity_control_state_evidence():
    raw = (b"\x00" * 8) + b"".join(_with_len(text) for text in (
        "Normal", "Highlighted", "Pressed", "Selected", "Disabled", "Quit",
        "UnityEngine.Object, UnityEngine",
    ))

    entries = _raw_string_entries("menu", 694, raw, {})
    by_original = {entry.original: entry for entry in entries}

    assert by_original["Quit"].status == "pending"
    assert by_original["Quit"].meta["confidence"] == "high"
    assert by_original["Quit"].meta["role"] == "display"
    assert by_original["Quit"].meta["reason"] == "core_menu_control"
    assert all(by_original[text].status == "skipped" for text in (
        "Normal", "Highlighted", "Pressed", "Selected", "Disabled",
    ))


def test_raw_string_entries_inputsystem_actions_skipped_in_map_object():
    # deadbeat obj 717 实证：InputSystem 对象（含 GameActions action map 名）
    # 里 Select/Cancel 是输入绑定名，翻译会破坏按键交互（#205 根因 e0ede8f
    # 只覆盖路径形态，单词形态 Select/Cancel 漏网）；Pause 等按钮文本不受影响
    raw = (_with_len("GameActions") + _with_len("Select") + _with_len("Cancel")
           + _with_len("Pause") + _with_len("Settings") + _with_len("Quit")
           + _with_len("Button") + _with_len("Open Settings Menu"))
    entries = _raw_string_entries("f1", 5, raw, {})
    by_orig = {e.original: e for e in entries}
    assert by_orig["Select"].status == "skipped"
    assert by_orig["Select"].meta.get("reason") == "input_system_object"
    assert by_orig["Select"].meta.get("obj_is_key_list") is True
    assert by_orig["Cancel"].status == "skipped"
    # InputSystem 配置对象内短词全部是运行时按名查找的键（morfosigame 实证），
    # 不再逐词白名单——Pause 等若为动作名翻译即破坏输入，宁可漏译不漏保护
    assert by_orig["Pause"].status == "skipped"
    assert by_orig["Settings"].status == "skipped"
    assert by_orig["Quit"].status == "skipped"
    # 强显示证据句子仍放行（配置对象里理论上不出现，保守防误伤）
    assert by_orig["Open Settings Menu"].status == "pending"


def test_raw_string_entries_inputsystem_binding_path_object_all_skipped():
    # morfosigame 实证根因：InputActionAsset 对象（map 名 'Normal' 是默认模板名，
    # 不在 GameActions 名单里）含绑定路径 <Keyboard>/z 与 interactions 串
    # Press(behavior=2) → 动作名 Proceed/Interact 全被翻译 → 点击对话/F 跳过
    # 无反应。绑定路径/interactions 是输入配置强信号，对象内全部短词串跳过。
    raw = ((b"\x00" * 12) + _with_len("Normal") + _with_len("Proceed")
           + _with_len("<Keyboard>/z") + _with_len("<Mouse>/position")
           + _with_len("<Gamepad>/leftStick") + _with_len("Press(behavior=2)")
           + _with_len("Interact") + _with_len("Action") + _with_len("Button")
           + _with_len("Controls") + _with_len("Arrow Keys"))
    entries = _raw_string_entries("sharedassets0.assets", 19, raw, {},
                                  "sharedassets0.assets")
    by_orig = {e.original: e for e in entries}
    # 绑定路径是结构串（skipped 保留标记，写回不会写），interactions 被引擎过滤
    for name in ("<Keyboard>/z", "<Mouse>/position", "<Gamepad>/leftStick"):
        assert by_orig[name].status == "skipped", name
    assert "Press(behavior=2)" not in by_orig
    # 动作名/绑定组名在输入配置对象内全部跳过
    for name in ("Normal", "Proceed", "Interact", "Action", "Button",
                 "Controls", "Arrow Keys"):
        assert by_orig[name].status == "skipped", name
        assert by_orig[name].meta.get("reason") == "input_system_object", name


def test_raw_string_entries_timeline_object_skipped():
    # morfosigame 实证：Timeline 轨道对象含 'Animation Track (1)'（带编号，旧正则
    # 只匹配不带编号形式而漏网，被拆成 '动画轨道'+' (1)' 结构错乱）与动画状态名
    # 'Player Idle' → 全部跳过；同形短词对象在 level 场景文件里仍是显示文本。
    raw = ((b"\x00" * 12) + _with_len("Animation Track (1)")
           + _with_len("Player Idle") + _with_len("Player Walk")
           + _with_len("Markers"))
    entries = _raw_string_entries("sharedassets4.assets", 23, raw, {},
                                  "sharedassets4.assets")
    by_orig = {e.original: e for e in entries}
    assert by_orig["Animation Track (1)"].status == "skipped"
    for name in ("Player Idle", "Player Walk", "Markers"):
        assert by_orig[name].status == "skipped", name
        assert by_orig[name].meta.get("reason") == "timeline_object", name


def test_raw_string_entries_shared_resource_small_config_skipped_but_level_kept():
    # 'Timothy' 在共享资源文件里是 Timeline 剪辑 displayName（morfosigame
    # sharedassets4 116 字节 ScriptableObject 实证）→ 跳过；同样内容在 level
    # 场景文件里是对话说话者名 → 保持 pending（真实语料：level5 136 个对话对象）。
    so = (b"\x00" * 12) + _with_len("Timothy")   # ScriptableObject 形态（无 GameObject）
    comp = (b"\x00\x00\x00\x00\x05\x00\x00\x00") + _with_len("Timothy")  # 场景组件形态
    shared = _raw_string_entries("sharedassets4.assets", 23, so, {},
                                 "sharedassets4.assets")
    shared_component = _raw_string_entries("sharedassets4.assets", 24, comp, {},
                                           "sharedassets4.assets")
    level = _raw_string_entries("level5", 54107, comp, {}, "level5")
    assert shared[0].status == "skipped"
    assert shared[0].meta.get("reason") == "shared_resource_config_object"
    assert shared_component[0].status == "pending"   # 组件形态不受影响
    assert level[0].status == "pending"              # 场景文件不受影响


def test_raw_string_entries_select_pending_without_inputsystem_signal():
    # 无 GameActions 信号的普通 UI 对象：SELECT 是按钮显示文本，保持 pending
    raw = (_with_len("SELECT") + _with_len("QUIT") + _with_len("PAUSE")
           + _with_len("Open Settings Menu"))
    entries = _raw_string_entries("f1", 5, raw, {})
    by_orig = {e.original: e for e in entries}
    assert by_orig["SELECT"].status == "pending"
    assert by_orig["QUIT"].status == "pending"


def test_raw_string_entries_word_identifiers_skipped_in_code_objects():
    # 无值特征对象（InputActionAsset / UI 样式等）：单词式是绑定名/枚举名/引擎名，
    # 翻译必破坏功能（输入失效）→ 全部降级为键
    raw = (b"\x00" * 8) + _with_len("WASD") + _with_len("Move") + _with_len("Fire") \
        + _with_len("Look") + _with_len("Bold") + _with_len("Unity")
    entries = _raw_string_entries("f1", 5, raw, {})
    by_orig = {e.original: e for e in entries}
    assert all(by_orig[k].status == "skipped"
               for k in ("WASD", "Move", "Fire", "Look", "Bold", "Unity"))
    assert by_orig["WASD"].meta.get("obj_is_key_list") is True


def test_raw_string_entries_display_words_skipped_in_code_objects():
    # InputActionAsset 场景：白名单词 down/left/right 作为绑定名也是键
    raw = (b"\x00" * 8) + _with_len("Player") + _with_len("Move") + _with_len("down") \
        + _with_len("left") + _with_len("right") + _with_len("Dpad")
    entries = _raw_string_entries("f1", 5, raw, {})
    by_orig = {e.original: e for e in entries}
    assert all(by_orig[k].status == "skipped"
               for k in ("Player", "Move", "down", "left", "right", "Dpad"))


def test_duplicate_display_strings_all_pending_without_marker():
    """非 Localization 对象里相同显示文本多次出现（按钮多状态 / 多处同一按钮），
    每次出现都是可译显示值——只有末条 pending 会导致游戏里只有一种 UI 状态
    被汉化（deadbeat 暂停菜单 Pause 按钮 ×3 实证 #206）。"""
    raw = (_with_len("NEW GAME") + _with_len("SETTINGS") + _with_len("NEW GAME")
           + _with_len("SETTINGS") + _with_len("Press any key to continue."))
    entries = _raw_string_entries("f1", 5, raw, {})
    by_status = {}
    for e in entries:
        by_status.setdefault(e.original, []).append(e.status)
    assert by_status["NEW GAME"] == ["pending", "pending"]
    assert by_status["SETTINGS"] == ["pending", "pending"]


def test_duplicate_strings_key_position_skipped_with_localization_marker():
    """Localization 键值对（含标记）：同一对象内重复字符串，第一次出现（键）
    标记 skipped，最后一次出现（值）为 pending；标识符形态（SETTINGS）在
    键列表对象中全降级。"""
    raw = (_with_len("UnityEngine.Localization")
           + _with_len("NEW GAME") + _with_len("SETTINGS") + _with_len("NEW GAME")
           + _with_len("SETTINGS") + _with_len("Press any key to continue."))
    entries = _raw_string_entries("f1", 5, raw, {})
    by_status = {}
    for e in entries:
        by_status.setdefault(e.original, []).append(e.status)
    assert by_status["NEW GAME"] == ["skipped", "pending"]
    assert by_status["SETTINGS"] == ["skipped", "skipped"]


def test_generic_strong_display_does_not_override_duplicate_position_with_marker():
    # marker 串本身带 type_reference 结构化原因（structural skipped 条目），
    # 随后的重复显示文本保持首键末值
    raw = (_with_len("UnityEngine.Localization")
           + _with_len("Open Settings Menu") * 2)

    entries = _raw_string_entries("f1", 5, raw, {})

    assert [entry.status for entry in entries] == ["skipped", "skipped", "pending"]
    assert entries[0].meta["role"] == "structural"
    assert entries[1].meta["reason"] == "duplicate_key_position"
    assert entries[2].meta["role"] == "display"


def test_repeated_high_frequency_interaction_positions_are_all_kept():
    raw = _with_len("Press E") * 3

    entries = _raw_string_entries("f1", 5, raw, {"Press E": 51})

    assert [entry.original for entry in entries] == ["Press E"] * 3
    assert all(entry.status == "pending" for entry in entries)
    assert all(entry.meta["role"] == "display" for entry in entries)
    assert len({entry.key_path for entry in entries}) == 3


def test_high_frequency_generic_strong_display_is_kept():
    entries = _raw_string_entries(
        "f1", 5, _with_len("Open Settings Menu"),
        {"Open Settings Menu": 50},
    )

    assert len(entries) == 1
    assert entries[0].status == "pending"
    assert entries[0].meta["role"] == "display"


def test_raw_string_entries_freq_filter():
    from hanhua.core.models import TextEntry
    raw = _with_len("SomeEngineThing") + _with_len("AnotherEngineThing")
    entries = _raw_string_entries("f1", 5, raw, {"SomeEngineThing": 50, "AnotherEngineThing": 50})
    assert entries == []


# ── #US 堆 ──
def test_find_dll_files_reuses_shared_fallback_application_rules(tmp_path):
    managed = tmp_path / "Example_Data" / "Managed"
    managed.mkdir(parents=True)
    names = (
        "Assembly-CSharp.dll",
        "Assembly-CSharp-firstpass.dll",
        "Assembly-CSharp.Custom.dll",
        "GameAnalytics.dll",
        "UnityEngine.CoreModule.dll",
    )
    for name in names:
        _write_cli_pe(managed / name)
    other_managed = tmp_path / "Other_Data" / "Managed"
    other_managed.mkdir(parents=True)
    _write_cli_pe(other_managed / "assembly-csharp.dll")

    assert [path.name for path in find_dll_files(tmp_path)] == [
        "Assembly-CSharp-firstpass.dll",
        "Assembly-CSharp.Custom.dll",
        "Assembly-CSharp.dll",
        "assembly-csharp.dll",
    ]


def test_find_dll_files_discovers_safe_manifest_user_assemblies(tmp_path):
    import json

    data_dir = tmp_path / "Example_Data"
    managed = data_dir / "Managed"
    managed.mkdir(parents=True)
    for name in (
        "Assembly-CSharp.dll", "Custom.Gameplay.dll",
        "UnityEngine.CoreModule.dll", "Escape.dll",
    ):
        _write_cli_pe(managed / name)
    (data_dir / "ScriptingAssemblies.json").write_text(json.dumps({
        "names": [
            "Custom.Gameplay.dll", "UnityEngine.CoreModule.dll",
            "Assembly-CSharp.dll",
        ],
        "types": [16, 2, 16],
    }), encoding="utf-8")

    assert [path.name for path in find_dll_files(tmp_path)] == [
        "Assembly-CSharp.dll", "Custom.Gameplay.dll",
    ]


@pytest.mark.parametrize(
    "reparse_name", ("Example_Data", "Managed", "Custom.Gameplay.dll"))
def test_find_dll_files_rejects_manifest_reparse_chain(
        tmp_path, monkeypatch, reparse_name):
    import json
    import hanhua.core.tooling.player_layout as player_layout

    data_dir = tmp_path / "Example_Data"
    managed = data_dir / "Managed"
    managed.mkdir(parents=True)
    _write_cli_pe(managed / "Custom.Gameplay.dll")
    (data_dir / "ScriptingAssemblies.json").write_text(json.dumps({
        "names": ["Custom.Gameplay.dll"],
        "types": [16],
    }), encoding="utf-8")
    monkeypatch.setattr(
        player_layout, "_is_reparse_point",
        lambda path: path.name == reparse_name,
    )

    assert find_dll_files(tmp_path) == []


def test_find_dll_files_fails_closed_on_duplicate_canonical_assemblies(
        tmp_path, monkeypatch):
    managed = tmp_path / "Example_Data" / "Managed"
    _write_cli_pe(managed / "Assembly-CSharp.dll")
    original_iterdir = type(tmp_path).iterdir

    def duplicate_assembly(path):
        entries = list(original_iterdir(path))
        if path == managed:
            entries.append(managed / "assembly-csharp.DLL")
        return iter(entries)

    monkeypatch.setattr(type(tmp_path), "iterdir", duplicate_assembly)

    assert find_dll_files(tmp_path) == []


def test_explicit_dll_extraction_accepts_nonstandard_assembly_name(
        tmp_path, monkeypatch):
    import dnfile

    text = "Hello from custom assembly"
    encoded = text.encode("utf-16-le") + b"\x01"
    heap = b"\x00" + bytes([len(encoded)]) + encoded

    class FakeUserStrings:
        def sizeof(self):
            return len(heap)

        def get_data_at_offset(self, offset, size):
            assert (offset, size) == (0, len(heap))
            return heap

        def get_file_offset(self, offset):
            assert offset == 0
            return 100

    fake_pe = type(
        "FakePE", (),
        {
            "net": type("FakeNet", (), {"user_strings": FakeUserStrings()})(),
            "close": lambda self: None,
        },
    )()
    monkeypatch.setattr(dnfile, "dnPE", lambda _path: fake_pe)

    parsed = extract_dll_user_strings(tmp_path / "Custom.Game.dll")

    assert [entry.original for entry in parsed.entries] == [text]


def test_dll_extraction_strips_any_ecma335_user_string_flag(
        tmp_path, monkeypatch):
    import dnfile

    text = "Phase 1"
    encoded = text.encode("utf-16-le") + b"\x00"  # legal ASCII flag=0
    heap = b"\x00" + bytes([len(encoded)]) + encoded

    class FakeUserStrings:
        def sizeof(self): return len(heap)
        def get_data_at_offset(self, offset, size): return heap
        def get_file_offset(self, offset): return 100

    fake_pe = SimpleNamespace(
        net=SimpleNamespace(
            user_strings=FakeUserStrings(),
            mdtables=SimpleNamespace(
                MemberRef=SimpleNamespace(rows=[]),
                MethodDef=SimpleNamespace(rows=[]),
            ),
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(dnfile, "dnPE", lambda _path: fake_pe)

    parsed = extract_dll_user_strings(tmp_path / "FlagZero.dll")

    assert [entry.original for entry in parsed.entries] == [text]
    assert parsed.entries[0].meta["utf16_len"] == len(text.encode("utf-16-le"))


def test_mono_strong_interaction_promotes_without_setter(
        tmp_path, monkeypatch):
    import dnfile

    prompts = (
        "Press E to Open",
        "Press E to Close",
        "Press E to take battery",
        "Testing inputs. When done, press the Enter key.",
        "Press the Enter key to continue",
    )
    structural = (
        "Pressed", "Move", "Fire",
        "Game.PlayerController", "Assets/UI/Menu.prefab",
    )
    debug_rows = (
        "'0x{0:X}': {1}",
        "[FLIP] - constrained edge done",
        "AddPath: Open paths must be subject.",
        "Debug: Press E state observed",
        "Failed to press the Enter key in simulation",
        "Press inventoryManager to open",
        "Press E state observed",
        "Press the Enter key state observed",
        "Debug. Failed to press the Enter key in simulation. Aborting.",
        "Trace. Failed to press the Enter key in simulation. Aborting.",
        "Assertion failed. Could not press the Enter key. Aborting.",
    )
    heap = bytearray(b"\x00")
    for text in prompts + structural + debug_rows:
        raw = text.encode("utf-16-le") + b"\x00"
        heap.extend((len(raw),))
        heap.extend(raw)

    class FakeUserStrings:
        def sizeof(self): return len(heap)
        def get_data_at_offset(self, offset, size): return bytes(heap)
        def get_file_offset(self, offset): return 100

    fake_pe = SimpleNamespace(
        net=SimpleNamespace(
            user_strings=FakeUserStrings(),
            mdtables=SimpleNamespace(
                MemberRef=SimpleNamespace(rows=[]),
                MethodDef=SimpleNamespace(rows=[]),
            ),
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(dnfile, "dnPE", lambda _path: fake_pe)

    parsed = extract_dll_user_strings(tmp_path / "Assembly-CSharp.dll")
    by_original = {entry.original: entry for entry in parsed.entries}

    for text in prompts:
        entry = by_original[text]
        assert entry.status == "pending"
        assert entry.meta["confidence"] == "high"
        assert entry.meta["role"] == "display"
        assert entry.meta["disposition"] == "translate"
        assert entry.meta["reason"] == "interaction_prompt"
    assert not set(structural) & by_original.keys()
    for text in debug_rows:
        entry = by_original[text]
        if text == "[FLIP] - constrained edge done":
            # 全大写日志标签被 UI 启发式放行：翻译无害（仅日志），
            # 且能救回真实 UI 拼接文本（driftapocalypse）
            assert entry.status == "pending"
            assert entry.meta["reason"] == "user_string_uppercase_ui"
        else:
            assert entry.status == "skipped"
            assert entry.meta["role"] == "structural"
            assert entry.meta["reason"] == "unverified_user_string"


def test_dll_extraction_promotes_uppercase_ui_concatenated_strings(
        tmp_path, monkeypatch):
    """driftapocalypse 真实漏检：代码拼接的 UI 文本未进 ui setter 验证链，
    但含全大写强调词（BEST/LEFT/DRIFT）→ 放行翻译。诊断句仍保守跳过。"""
    import dnfile

    ui_rows = (
        "BEST SCORE: ",
        "SHOW ANUNCIO",
        "\n[     NOT ENOUGH COINS ]",
        "Hold LEFT or RIGHT to turn\n(",
        "Hold LEFT and RIGHT together to BOOST\n(",
        "Be CAREFUL with the FRONT of the car\nYour engine is FRAGILE!",
    )
    diagnostics = (
        "Internal diagnostic message",
        "Trace. Please press the Enter key message was not displayed. Aborting.",
        "Unrelated stack literal",
    )
    heap = bytearray(b"\x00")
    for text in ui_rows + diagnostics:
        raw = text.encode("utf-16-le") + b"\x00"
        # ECMA-335 压缩长度编码：≥128 需 2 字节（诊断句 utf-16 长度超 127）
        if len(raw) < 0x80:
            heap.extend((len(raw),))
        else:
            heap.extend((0x80 | (len(raw) >> 8), len(raw) & 0xFF))
        heap.extend(raw)

    class FakeUserStrings:
        def sizeof(self): return len(heap)
        def get_data_at_offset(self, offset, size): return bytes(heap)
        def get_file_offset(self, offset): return 100

    fake_pe = SimpleNamespace(
        net=SimpleNamespace(
            user_strings=FakeUserStrings(),
            mdtables=SimpleNamespace(
                MemberRef=SimpleNamespace(rows=[]),
                MethodDef=SimpleNamespace(rows=[]),
            ),
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(dnfile, "dnPE", lambda _path: fake_pe)

    parsed = extract_dll_user_strings(tmp_path / "Assembly-CSharp.dll")
    by_original = {entry.original: entry for entry in parsed.entries}

    for text in ui_rows:
        entry = by_original[text]
        assert entry.status == "pending"
        assert entry.meta["confidence"] == "medium"
        assert entry.meta["role"] == "display"
        assert entry.meta["disposition"] == "translate"
        assert entry.meta["reason"] == "user_string_uppercase_ui"
    for text in diagnostics:
        entry = by_original[text]
        assert entry.status == "skipped"
        assert entry.meta["role"] == "structural"
        assert entry.meta["reason"] == "unverified_user_string"


@pytest.mark.parametrize("text", [
    "Trace. Please press the Enter key message was not displayed. Aborting.",
    "Assertion. When testing the prompt, press the Enter key message was missing. Aborting.",
    "Press the Enter key to continue message was not displayed.",
    "Press the Enter key to continue instruction was not displayed.",
    "Press the Enter key to continue label was not shown.",
    "Press the Enter key to continue prompt could not be displayed.",
    "Press the Enter key to continue message did not appear.",
    "Press the Enter key to continue message was never shown.",
    "Press the Enter key to continue instruction disappeared.",
    "Press the Enter key to continue label vanished.",
    "Press the Enter key to continue notification timed out.",
    "Controller connected. Please press the Enter key to continue instruction disappeared.",
])
def test_strong_interaction_rejects_missing_prompt_diagnostics(text):
    assert is_strong_interaction_prompt(text) is False


@pytest.mark.parametrize("text", [
    ("Controller inputs are working. When you're done testing, "
     "press the enter key on your keyboard."),
    "Testing inputs. When done, press the Enter key to continue.",
    "Controller connected. Please press the Enter key to continue.",
    "Controller connected. Then press the Enter key to begin.",
])
def test_strong_interaction_accepts_positive_long_instructions(text):
    assert is_strong_interaction_prompt(text) is True


@pytest.mark.parametrize("text", [
    "Press E to take the oil can",
    "Press E to put the can down",
    "Press E to move the can",
    "Controller ready. Please press E to take the oil can.",
])
def test_strong_interaction_accepts_bounded_object_actions(text):
    assert is_strong_interaction_prompt(text) is True


@pytest.mark.parametrize("text", [
    "Press R to reload weapon",
    "Press Enter to confirm selection",
    "Press Esc to pause game",
    "Press Enter to continue playing",
    "Press Enter to begin the mission",
    "Press E to open locked door",
    "Press E to inspect ancient artifact",
    "Press E to talk to Bob",
    "Press E to drive to town",
    "Press E to move the can to the table",
])
def test_strong_interaction_accepts_common_action_complements(text):
    assert is_strong_interaction_prompt(text) is True


@pytest.mark.parametrize("text", [
    "Press E to take the oil can disappeared.",
    "Press E to open the door prompt vanished.",
    "Press E to open the notification timed out.",
    "Controller ready. Please press E to move the crate instruction disappeared.",
])
def test_strong_interaction_rejects_predicates_after_objects(text):
    assert is_strong_interaction_prompt(text) is False


@pytest.mark.parametrize("text", [
    "Press E to take the ring",
    "Press E to enter the building",
    "Press E to inspect the painting",
    "Press E to move the bed",
    "Press E to open the shed",
    "Press Enter to continue playing the game",
    "Press Enter to begin loading the level",
])
def test_strong_interaction_accepts_noun_suffixes_and_gerund_objects(text):
    assert is_strong_interaction_prompt(text) is True


@pytest.mark.parametrize("text", [
    "Press E to take the oil can fell.",
    "Press E to open the door broke.",
    "Press E to move the crate fell down.",
    "Press E to open the prompt fails.",
    "Controller ready. Please press E to open the door broke.",
    "Press E to open the door got stuck.",
    "Press E to open the door shut.",
    "Press E to open the door opens unexpectedly.",
    "Press E to open the prompt times out.",
])
def test_strong_interaction_rejects_irregular_finite_predicates(text):
    assert is_strong_interaction_prompt(text) is False


@pytest.mark.parametrize("text", [
    "Press E to take the fallen remains",
    "Press E to inspect the frozen remains",
    "Press E to read the system errors",
    "Press E to inspect the loose ends",
    "Press E to open the locked door",
    "Press E to read the collected works",
    "Press E to inspect the remains",
    "Press E to inspect tax returns",
    "Press E to read system errors",
    "Press E to inspect loose ends",
    "Press E to read collected works",
    "Press E to talk to May",
    "Press E to talk to Will",
    "Press E to read the will",
    "Press E to inspect May records",
])
def test_strong_interaction_accepts_determined_ambiguous_nouns(text):
    assert is_strong_interaction_prompt(text) is True


@pytest.mark.parametrize("text", [
    "Press E to open failed.",
    "Press E to open broke.",
    "Press E to continue crashes.",
    "Press E to open times out.",
    "Press E to open the door won't open.",
    "Press E to open the door can not open.",
    "Press E to open the door jams.",
    "Press E to open the prompt dies.",
    "Press E to open the door works.",
    "Press E to open the door remains stuck.",
    "Press E to open failed again.",
    "Press E to open broke again.",
    "Press E to continue crashes repeatedly.",
    "Press E to open times out repeatedly.",
    "Press E to open may fail.",
    "Press E to open did fail.",
    "Press E to open the door doesn't open.",
    "Press E to open the door didn't open.",
    "Press E to open the door isn't open.",
    "Press E to open the door wasn't open.",
    "Press E to open the door couldn't open.",
    "Press E to open the door wouldn't open.",
    "Press E to open timed out once.",
    "Press E to open crashed once.",
    "Press E to open aborted twice.",
    "Press E to open stopped today.",
    "Press E to open controls don't work.",
    "Controller ready. Please press E to open failed.",
])
def test_strong_interaction_rejects_terminal_and_modal_predicates(text):
    assert is_strong_interaction_prompt(text) is False


def test_dll_only_promotes_verified_ldstr_to_ui_setter(tmp_path, monkeypatch):
    import dnfile

    visible = (
        "Settings", "Quit", "Resolution",
        "InternalKey", "ScoreValue", "UITable_en",
    )
    formatted_visible = "{0}\n{1}kg\n£{2}"
    format_only = "Internal format {0}"
    consumed_before_format = "Internal diagnostic {0}"
    unrelated_below_format = "Unrelated stack literal"
    unverified_identifier = "InternalKey"
    hard_structural = ("https://example.com/menu", "Assets/UI/Menu.prefab")
    conservative = "Internal diagnostic message"
    heap = bytearray(b"\x00")
    tokens = []
    all_text = (
        *visible, formatted_visible, format_only, consumed_before_format,
        unrelated_below_format,
        unverified_identifier,
        *hard_structural, conservative,
    )
    for text in all_text:
        raw = text.encode("utf-16-le") + b"\x01"
        tokens.append(len(heap))
        heap.extend((len(raw),))
        heap.extend(raw)
    display_code = b"".join(
        b"\x72" + struct.pack("<I", 0x70000000 | token)
        + b"\x6f" + struct.pack("<I", 0x0A000001)
        for token in tokens[:6]
    ) + b"\x2a"
    formatted_display_code = (
        b"\x72" + struct.pack("<I", 0x70000000 | tokens[6])
        + b"\x16"
        + b"\x28" + struct.pack("<I", 0x0A000002)
        + b"\x6f" + struct.pack("<I", 0x0A000001)
        + b"\x2a"
    )
    format_only_code = (
        b"\x72" + struct.pack("<I", 0x70000000 | tokens[7])
        + b"\x16"
        + b"\x28" + struct.pack("<I", 0x0A000002)
        + b"\x26\x2a"
    )
    consumed_before_format_code = (
        b"\x72" + struct.pack("<I", 0x70000000 | tokens[8])
        + b"\x28" + struct.pack("<I", 0x0A000003)
        + b"\x16"
        + b"\x28" + struct.pack("<I", 0x0A000002)
        + b"\x6f" + struct.pack("<I", 0x0A000001)
        + b"\x2a"
    )
    unrelated_below_format_code = (
        b"\x72" + struct.pack("<I", 0x70000000 | tokens[9])
        + b"\x02"  # UI receiver
        + b"\x03"  # actual format string from an argument
        + b"\x04"  # formatting argument
        + b"\x28" + struct.pack("<I", 0x0A000002)
        + b"\x6f" + struct.pack("<I", 0x0A000001)
        + b"\x26\x2a"  # discard the unrelated literal after the setter
    )
    hard_structural_code = b"".join(
        b"\x72" + struct.pack("<I", 0x70000000 | token)
        + b"\x6f" + struct.pack("<I", 0x0A000001)
        for token in tokens[11:13]
    ) + b"\x2a"
    bodies = {
        0x2000: bytes(((len(display_code) << 2) | 2,)) + display_code,
        0x3000: bytes(((len(formatted_display_code) << 2) | 2,))
        + formatted_display_code,
        0x4000: bytes(((len(format_only_code) << 2) | 2,))
        + format_only_code,
        0x5000: bytes(((len(consumed_before_format_code) << 2) | 2,))
        + consumed_before_format_code,
        0x6000: bytes(((len(unrelated_below_format_code) << 2) | 2,))
        + unrelated_below_format_code,
        0x7000: bytes(((len(hard_structural_code) << 2) | 2,))
        + hard_structural_code,
    }

    class FakeUserStrings:
        def sizeof(self): return len(heap)
        def get_data_at_offset(self, offset, size): return bytes(heap)
        def get_file_offset(self, offset): return 100

    declaring_type = SimpleNamespace(TypeName="TMP_Text", TypeNamespace="TMPro")
    member_ref = SimpleNamespace(
        Name="set_text", Class=SimpleNamespace(row=declaring_type))
    string_type = SimpleNamespace(TypeName="String", TypeNamespace="System")
    format_ref = SimpleNamespace(
        Name="Format", Class=SimpleNamespace(row=string_type),
        Signature=SimpleNamespace(value=b"\x00\x02\x0e\x0e\x1c"))
    debug_type = SimpleNamespace(TypeName="Debug", TypeNamespace="UnityEngine")
    debug_ref = SimpleNamespace(
        Name="Log", Class=SimpleNamespace(row=debug_type))
    methods = [SimpleNamespace(Rva=rva) for rva in bodies]
    fake_pe = SimpleNamespace(
        net=SimpleNamespace(
            user_strings=FakeUserStrings(),
            mdtables=SimpleNamespace(
                MemberRef=SimpleNamespace(
                    rows=[member_ref, format_ref, debug_ref]),
                MethodDef=SimpleNamespace(rows=methods),
            ),
        ),
        get_data=lambda rva, size: bodies.get(rva, b"")[:size],
        close=lambda: None,
    )
    monkeypatch.setattr(dnfile, "dnPE", lambda _path: fake_pe)

    parsed = extract_dll_user_strings(tmp_path / "Custom.Game.dll")
    by_original = {entry.original: entry for entry in parsed.entries}

    for text in visible:
        assert by_original[text].status == "pending"
        assert by_original[text].meta["confidence"] == "high"
        assert by_original[text].meta["role"] == "display"
        assert by_original[text].meta["disposition"] == "translate"
        assert by_original[text].meta["reason"] == "mono_ui_setter"
    assert by_original[formatted_visible].status == "pending"
    assert by_original[formatted_visible].meta["reason"] == "mono_ui_setter"
    assert by_original[format_only].status == "skipped"
    assert by_original[format_only].meta["reason"] == "unverified_user_string"
    assert by_original[consumed_before_format].status == "skipped"
    assert by_original[consumed_before_format].meta["reason"] == (
        "unverified_user_string")
    assert by_original[unrelated_below_format].status == "skipped"
    assert by_original[unrelated_below_format].meta["reason"] == (
        "unverified_user_string")
    assert [entry.original for entry in parsed.entries].count(
        unverified_identifier) == 1
    assert not set(hard_structural) & by_original.keys()
    assert by_original[conservative].status == "skipped"
    assert by_original[conservative].meta["confidence"] == "low"
    assert by_original[conservative].meta["role"] == "structural"
    assert by_original[conservative].meta["disposition"] == "structural"
    assert by_original[conservative].meta["reason"] == "unverified_user_string"


def test_dll_extraction_closes_pe_on_success_empty_and_error(
        tmp_path, monkeypatch):
    import dnfile
    import pytest

    text = "Hello from managed code"
    encoded = text.encode("utf-16-le") + b"\x01"
    heap = b"\x00" + bytes([len(encoded)]) + encoded

    class FakeUserStrings:
        def sizeof(self):
            return len(heap)

        def get_data_at_offset(self, offset, size):
            return heap

        def get_file_offset(self, offset):
            return 100

    class FailingUserStrings:
        def sizeof(self):
            raise RuntimeError("broken #US heap")

        def get_data_at_offset(self, offset, size):
            raise AssertionError("sizeof must fail before heap data is read")

    class FakePE:
        def __init__(self, user_strings):
            self.net = type("FakeNet", (), {"user_strings": user_strings})()
            self.close_calls = 0

        def close(self):
            self.close_calls += 1

    pe_instances = [
        FakePE(FakeUserStrings()),
        FakePE(None),
        FakePE(FailingUserStrings()),
    ]
    pending = iter(pe_instances)
    monkeypatch.setattr(dnfile, "dnPE", lambda _path: next(pending))

    parsed = extract_dll_user_strings(tmp_path / "Success.dll")
    assert [entry.original for entry in parsed.entries] == [text]
    assert extract_dll_user_strings(tmp_path / "Empty.dll").entries == []
    with pytest.raises(RuntimeError, match="broken #US heap"):
        extract_dll_user_strings(tmp_path / "Broken.dll")

    assert [pe.close_calls for pe in pe_instances] == [1, 1, 1]


def test_us_heap_walk():
    heap = b"\x00"
    heap += bytes([0x0B]) + "Hello".encode("utf-16-le") + b"\x01"   # 11 = 10 字节 UTF-16 + 终结
    heap += bytes([0x05]) + "你好".encode("utf-16-le") + b"\x01"
    items = _walk_us_heap(heap)
    assert len(items) == 2
    assert items[0][0] == 2                    # 1 字节占位 + 1 字节长度头
    assert items[0][1][:-1].decode("utf-16-le") == "Hello"   # 末字节是 0x01 终结标记
    assert items[1][1][:-1].decode("utf-16-le") == "你好"


@pytest.mark.parametrize("heap", (
    b"\x00\xe0\x00\x00\x01A",  # ECMA-335 reserved 111xxxxx prefix
    b"\x00\x80\x01A",           # non-canonical two-byte encoding of 1
    b"\x00\xc0\x00\x00\x01A",  # non-canonical four-byte encoding of 1
    b"\x00\x80",                 # truncated two-byte prefix
    b"\x00\xc0\x00\x00",        # truncated four-byte prefix
    b"\x00\x02A",                # truncated record payload
))
def test_us_heap_walk_rejects_reserved_or_truncated_records(heap):
    # F5 鲁棒遍历：坏前缀/截断记录步进 1 继续（写回后残留区不可断链），
    # 损坏区残留的短前缀可能被解析为 ln=1 空记录；契约 = 不产出任何
    # 可解码的 UTF-16 文本记录（空记录由提取侧字符串级过滤淘汰，不会
    # 成为可译条目）。
    for _token, raw in _walk_us_heap(heap):
        text = raw[:-1].decode("utf-16-le", errors="replace")
        assert text == ""


# ── IL2CPP metadata ──
def _fake_metadata(literals: list[str] | None = None) -> bytes:
    if literals is None:
        literals = ["Hello player", "Press {key} to jump", "继续游戏"]
    data = b"".join(s.encode("utf-8") for s in literals)
    offsets = []
    pos = 0
    for s in literals:
        offsets.append((pos, len(s.encode("utf-8"))))
        pos += len(s.encode("utf-8"))
    header = bytearray(0x30)
    struct.pack_into("<II", header, 0, 0xFAB11BAF, 29)
    table_size = len(literals) * 8
    struct.pack_into("<II", header, 0x08, 0x100, table_size)         # stringLiteralOffset/byte size
    struct.pack_into("<II", header, 0x10, 0x200, len(data))          # stringLiteralData
    lit_arr = b"".join(struct.pack("<II", ln, off) for off, ln in offsets)
    buf = bytes(header) + b"\x00" * (0x100 - 0x30) + lit_arr
    buf += b"\x00" * (0x200 - len(buf)) + data
    return buf


def test_il2cpp_parse_and_extract():
    raw = _fake_metadata()
    lits = parse_string_literals(raw)
    assert lits == [(0, 12, 0x200), (12, 19, 0x20C), (31, 12, 0x21F)]
    from hanhua.core.unity.il2cpp import extract_metadata_strings
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "global-metadata.dat"
        p.write_bytes(raw)
        pf = extract_metadata_strings(p, "m.dat")
        orig = {e.key_path: e.original for e in pf.entries}
        assert orig["meta#0"] == "Hello player"
        assert orig["meta#12"] == "Press {key} to jump"   # data_index 语义
        assert orig["meta#31"] == "继续游戏"
        by_key = {e.key_path: e.meta["file_offset"] for e in pf.entries}
        assert by_key == {"meta#0": 0x200, "meta#12": 0x20C, "meta#31": 0x21F}


def test_il2cpp_rejects_non_divisible_literal_table_size():
    raw = bytearray(_fake_metadata())
    struct.pack_into("<I", raw, 0x0C, 25)

    assert parse_string_literals(bytes(raw)) == []


def test_il2cpp_rejects_literal_sections_that_overlap_metadata_header():
    raw = bytearray(100)
    struct.pack_into("<II", raw, 0, 0xFAB11BAF, 29)
    struct.pack_into("<II", raw, 0x08, 4, 8)
    struct.pack_into("<II", raw, 0x10, 64, 36)

    assert parse_string_literals(bytes(raw)) == []


def test_il2cpp_rejects_literal_data_index_or_length_out_of_range():
    oversized_length = bytearray(_fake_metadata())
    data_size = struct.unpack_from("<I", oversized_length, 0x14)[0]
    struct.pack_into("<II", oversized_length, 0x100, data_size + 1, 0)

    out_of_range_index = bytearray(_fake_metadata())
    struct.pack_into("<II", out_of_range_index, 0x100, 1, data_size)

    assert parse_string_literals(bytes(oversized_length)) == []
    assert parse_string_literals(bytes(out_of_range_index)) == []


def test_il2cpp_rejects_overlapping_literal_data_ranges():
    raw = bytearray(_fake_metadata())
    second_length = struct.unpack_from("<I", raw, 0x108)[0]
    struct.pack_into("<II", raw, 0x108, second_length, 1)

    assert parse_string_literals(bytes(raw)) == []


def test_il2cpp_skips_literal_that_is_not_valid_utf8():
    raw = bytearray(_fake_metadata())
    data_offset = struct.unpack_from("<I", raw, 0x10)[0]
    raw[data_offset] = 0xFF

    literals = parse_string_literals(bytes(raw))

    assert [(data_index, length) for data_index, length, _ in literals] == [
        (12, 19),
        (31, 12),
    ]


def test_il2cpp_extraction_rejects_illegal_controls_but_allows_tab_and_newlines(
        tmp_path):
    allowed = "First line\tlabel\nSecond line\rreturn"
    path = tmp_path / "global-metadata.dat"
    path.write_bytes(_fake_metadata([
        allowed,
        "Contains NUL\x00garbage",
        "Contains control\x01garbage",
        "Contains C1\x80garbage",
    ]))

    from hanhua.core.unity.il2cpp import extract_metadata_strings
    pending = [entry.original for entry in
               extract_metadata_strings(path).entries
               if entry.status == "pending"]

    assert pending == [allowed]


def test_il2cpp_rejects_overlapping_table_and_data_sections():
    raw = bytearray(_fake_metadata())
    data_size = struct.unpack_from("<I", raw, 0x14)[0]
    struct.pack_into("<II", raw, 0x10, 0x100, data_size)

    assert parse_string_literals(bytes(raw)) == []


def test_il2cpp_skips_zero_length_literal_record():
    raw = _fake_metadata(["", "Visible text"])

    literals = parse_string_literals(raw)

    assert [(data_index, length) for data_index, length, _ in literals] == [
        (0, len(b"Visible text")),
    ]


def test_il2cpp_rejects_wrong_magic_and_unsupported_versions():
    wrong_magic = bytearray(_fake_metadata())
    struct.pack_into("<I", wrong_magic, 0, 0xDEADBEEF)
    assert parse_string_literals(bytes(wrong_magic)) == []

    # v24/v27/v31/v39 已有真实语料验证的支持（见 test_v2_metadata_versions.py）；
    # 其余版本（包括 v30）必须拒绝，绝不猜 record 布局。
    for unsupported_version in (0, 30, 32, 33, 35, 40):
        raw = bytearray(_fake_metadata())
        struct.pack_into("<I", raw, 4, unsupported_version)
        assert parse_string_literals(bytes(raw)) == []


def test_il2cpp_rejects_table_or_data_section_out_of_file():
    table_out_of_file = bytearray(_fake_metadata())
    struct.pack_into("<II", table_out_of_file, 0x08,
                     len(table_out_of_file) - 4, 24)

    data_out_of_file = bytearray(_fake_metadata())
    data_size = struct.unpack_from("<I", data_out_of_file, 0x14)[0]
    struct.pack_into("<II", data_out_of_file, 0x10,
                     len(data_out_of_file) - 1, data_size)

    assert parse_string_literals(bytes(table_out_of_file)) == []
    assert parse_string_literals(bytes(data_out_of_file)) == []


def _v24_metadata(*literals: bytes) -> bytes:
    """构造 IL2CPP v24 metadata：magic + version + 8 字节 <length, dataIndex>
    显式记录 + data 区。布局 off: litOff@0x08 litSize@0x0C dataOff@0x10
    dataSize@0x14（与 hanhua.core.unity.il2cpp._LAYOUTS[24] 一致）。"""
    header = bytearray(0x30)
    struct.pack_into("<II", header, 0, 0xFAB11BAF, 24)
    data = b"".join(literals)
    table = b"".join(
        struct.pack("<II", len(lit), offset)
        for lit, offset in _cumulative(literals))
    struct.pack_into("<IIII", header, 0x08, 0x30, len(table),
                     0x30 + len(table), len(data))
    return bytes(header) + table + data


def _cumulative(literals: list[bytes]):
    offset = 0
    for lit in literals:
        yield lit, offset
        offset += len(lit)


def test_il2cpp_extract_filters_engine_noise_and_classifies():
    from hanhua.core.unity.il2cpp import extract_metadata_strings
    raw = _v24_metadata(
        b"Press E to interact",           # 交互提示 → display/medium
        b"A buffer must be provided",     # 引擎句子 → display/low 留档
        b"back_to_menu",                  # 标识符 → 不产生条目（代码池严格键）
        b"{0} bytes processed by {1}",    # 格式串 → 丢弃
        b"  .locals ",                    # 前导多空白调试 → 丢弃
        b"\t\n\r'(),-0123456789ABCDEF",   # 控制符开头字符表 → 丢弃
    )
    path = Path(tempfile.mkdtemp()) / "global-metadata.dat"
    path.write_bytes(raw)

    parsed = extract_metadata_strings(path, "meta.dat")

    by_orig = {e.original: e for e in parsed.entries}
    assert set(by_orig) == {"Press E to interact", "A buffer must be provided"}
    prompt = by_orig["Press E to interact"]
    assert (prompt.status, prompt.meta["confidence"], prompt.meta["role"]) == (
        "pending", "medium", "display")
    sentence = by_orig["A buffer must be provided"]
    assert (sentence.status, sentence.meta["confidence"]) == ("pending", "low")
