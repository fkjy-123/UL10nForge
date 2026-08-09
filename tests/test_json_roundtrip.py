import json

import pytest

from hanhua.core.formats.json_format import (
    apply_json,
    detect_indent,
    extract_json,
    extract_json_text,
)
from hanhua.core.models import STATUS_SKIPPED

FIXTURE = "tests/fixtures/game.json"


JSONC_SOURCE = (
    '\ufeff{\r\n'
    '  // 中文注释 "not a value"\r\n'
    '  "url": "https://host/a",\r\n'
    '  "literal": "literal // text",\r\n'
    '  "escaped": "escaped \\" quote",\r\n'
    '  /* 块注释 "also not a value" */ "rich": "<c=red>Text</c>",\r\n'
    '  "a/b": "slash value",\r\n'
    '  "a~b": "tilde",\r\n'
    '  "a": {"b": "nested",},\r\n'
    '  "items": ["first", {"text": "second",},],\r\n'
    '}\r\n'
)


def test_extract_jsonc_values_with_rfc6901_paths():
    entries = extract_json_text(JSONC_SOURCE, "localization.json")

    values = {entry.key_path: entry.original for entry in entries}

    assert values == {
        "url": "https://host/a",
        "literal": "literal // text",
        "escaped": 'escaped " quote',
        "rich": "<c=red>Text</c>",
        "a~1b": "slash value",
        "a~0b": "tilde",
        "a/b": "nested",
        "items/0": "first",
        "items/1/text": "second",
    }


def test_apply_jsonc_replaces_only_selected_value_span():
    entries = extract_json_text(JSONC_SOURCE, "localization.json")
    by_path = {entry.key_path: entry for entry in entries}
    by_path["a~1b"].translation = "斜线"

    out = apply_json(entries, JSONC_SOURCE)

    assert out == JSONC_SOURCE.replace('"slash value"', '"斜线"')
    assert out.startswith("\ufeff{")
    assert '// 中文注释 "not a value"\r\n' in out
    assert '/* 块注释 "also not a value" */' in out
    assert '"a": {"b": "nested",}' in out
    assert out.endswith("}\r\n")


@pytest.mark.parametrize(
    "source",
    [
        '{"missing" "colon"}',
        '{"unterminated": "string}',
        '{"comment": "value" /* unterminated}',
        '{"not": \ufeff"leading"}',
        '{// \ufeff not leading\n"text": "value"}',
        '\ufeff\ufeff{"two": "markers"}',
    ],
)
def test_jsonc_fallback_keeps_invalid_documents_invalid(source):
    with pytest.raises((json.JSONDecodeError, ValueError)):
        extract_json_text(source, "invalid.json")


@pytest.mark.parametrize(
    "source",
    [
        '{"text": "first phrase", "text": "last phrase"}',
        '{"text": "first phrase", /* keep */ "text": "last phrase",}',
    ],
)
def test_duplicate_object_keys_extract_only_last_value(source):
    entries = extract_json_text(source, "duplicate.json")

    assert [(entry.key_path, entry.original) for entry in entries] == [
        ("text", "last phrase")
    ]


def test_duplicate_object_keys_write_only_last_value_span():
    source = '{"text": "first phrase", /* keep */ "text": "last phrase",}'
    entries = extract_json_text(source, "duplicate.json")
    entries[0].translation = "最终译文"

    out = apply_json(entries, source)

    assert out == '{"text": "first phrase", /* keep */ "text": "最终译文",}'


def test_shadowed_duplicate_subtree_is_not_extracted_or_written():
    source = (
        '{"node": {"text": "shadowed phrase"}, '
        '"node": {"text": "effective phrase"}}'
    )
    entries = extract_json_text(source, "duplicate-subtree.json")
    assert [(entry.key_path, entry.original) for entry in entries] == [
        ("node/text", "effective phrase")
    ]
    entries[0].translation = "有效译文"

    out = apply_json(entries, source)

    assert out == (
        '{"node": {"text": "shadowed phrase"}, '
        '"node": {"text": "有效译文"}}'
    )


@pytest.mark.parametrize(
    ("source", "expected_path", "expected_original", "expected_output"),
    [
        (
            '{"node": "shadowed phrase", "node": {"text": "effective phrase"}}',
            "node/text",
            "effective phrase",
            '{"node": "shadowed phrase", "node": {"text": "有效译文"}}',
        ),
        (
            '{"node": {"text": "shadowed phrase"}, "node": "effective phrase"}',
            "node",
            "effective phrase",
            '{"node": {"text": "shadowed phrase"}, "node": "有效译文"}',
        ),
    ],
)
def test_duplicate_type_change_keeps_only_last_occurrence_subtree(
    source, expected_path, expected_original, expected_output
):
    entries = extract_json_text(source, "duplicate-type-change.json")
    assert [(entry.key_path, entry.original) for entry in entries] == [
        (expected_path, expected_original)
    ]
    entries[0].translation = "有效译文"

    out = apply_json(entries, source)

    assert out == expected_output


def test_numeric_object_key_remains_distinct_from_array_index():
    source = '{"0": "object value", "items": ["array value"]}'
    entries = extract_json_text(source, "numeric.json")
    by_path = {entry.key_path: entry for entry in entries}
    by_path["0"].translation = "对象值"
    by_path["items/0"].translation = "数组值"

    out = apply_json(entries, source)

    assert json.loads(out) == {"0": "对象值", "items": ["数组值"]}


def test_apply_json_honors_ensure_ascii_without_reformatting():
    source = '{"text": "English phrase", /* keep */ "other": "untouched",}'
    entries = extract_json_text(source, "ascii.json")
    entries[0].translation = "中文"

    out = apply_json(entries, source, ensure_ascii=True)

    assert out == '{"text": "\\u4e2d\\u6587", /* keep */ "other": "untouched",}'


def test_extract_json():
    entries = extract_json(FIXTURE)
    assert len(entries) == 9
    orig = {e.key_path: e.original for e in entries}
    assert orig["title"] == "Echoes of the Vale"
    assert orig["dialogue/1/text"] == "We must not linger here."
    assert orig["dialogue/0/choices/0"] == "Follow the light"
    assert orig["hint"] == "{0} more steps remaining"
    # 数字不是字符串，不应提取
    assert "settings/volume" not in orig
    assert "quest" not in orig


def test_apply_json_roundtrip():
    entries = extract_json(FIXTURE)
    source = open(FIXTURE, encoding="utf-8").read()
    for e in entries:
        if e.original == "Echoes of the Vale":
            e.translation = "谷之回响"
        if e.original == "{0} more steps remaining":
            e.translation = "还剩 {0} 步"
    data = apply_json(entries, source)
    obj = json.loads(data)
    assert obj["title"] == "谷之回响"
    assert obj["hint"] == "还剩 {0} 步"
    assert obj["settings"]["volume"] == 80
    assert obj["dialogue"][1]["text"] == "We must not linger here."
    assert obj["dialogue"][0]["choices"] == ["Follow the light", "Leave"]


def test_apply_preserves_indent_and_newline():
    source = open(FIXTURE, encoding="utf-8").read()
    assert detect_indent(source) == 2
    out = apply_json([], source)
    assert out == source  # 无译文时完全不变


def test_detect_indent_compact():
    assert detect_indent('{"a": 1}') is None


def test_extract_json_skips_structural_values():
    # Addressables catalog 真实结构：m_AssemblyName 值、m_InternalId 路径都不该进翻译池
    source = json.dumps({
        "m_ObjectType": {
            "m_AssemblyName": "Unity.ResourceManager, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null",
        },
        "m_InternalId": "file:///C:/Game/Assets/Bundles/menu.bundle",
        "m_Address": "Assets/Scenes/Main.unity",
        "m_InternalIds": [
            "Fonts & Materials/LiberationSans SDF - Drop Shadow",
            "Shaders/TMP_Bitmap",
        ],
        "m_BucketDataString": "TwAAAAQAAAABAAAAAAAAAFsAAAABAAAAAQAAAK0AAAABAAAAAgAAAAQBAAAB",
        "title": "My Game",
    })
    entries = extract_json_text(source, "catalog.json")
    by_path = {e.key_path: e for e in entries}
    assert by_path["m_ObjectType/m_AssemblyName"].status == STATUS_SKIPPED
    assert by_path["m_InternalId"].status == STATUS_SKIPPED
    assert by_path["m_Address"].status == STATUS_SKIPPED
    assert by_path["m_InternalIds/0"].status == STATUS_SKIPPED
    assert by_path["m_InternalIds/1"].status == STATUS_SKIPPED
    assert by_path["m_BucketDataString"].status == STATUS_SKIPPED
    assert by_path["title"].status != STATUS_SKIPPED
    assert by_path["title"].original == "My Game"


def test_apply_json_unicode_escape_fallback_applies_translation():
    source = '{"title":"\\u0048\\u0065\\u006c\\u006c\\u006f"}\n'
    entries = [entry for entry in __import__(
        "hanhua.core.formats.json_format", fromlist=["extract_json_text"]
    ).extract_json_text(source, "fixture.json")]
    entries[0].translation = "你好"

    out = apply_json(entries, source)

    assert json.loads(out)["title"] == "你好"
    assert out.endswith("\n")
