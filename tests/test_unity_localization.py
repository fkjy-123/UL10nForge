"""Unity Localization 结构化提取与源语言选择测试。"""
import json
import os
from pathlib import Path

import pytest

from hanhua.core.unity.extractor import (
    _localization_entries_from_tree,
    _prefer_source_locale_bundles,
    extract_asset_file,
    find_asset_files,
)


def test_localization_tree_extracts_values_but_not_shared_keys():
    string_tree = {
        "m_Name": "UITable_en",
        "m_LocaleId": {"m_Code": "en"},
        "m_TableData": [
            {"m_Id": 1, "m_Localized": "VOLUME"},
            {"m_Id": 2, "m_Localized": "FULLSCREEN"},
        ],
    }
    shared_tree = {
        "m_Name": "UITable Shared Data",
        "m_Entries": [{"m_Id": 1, "m_Key": "ui_volume"}],
    }

    entries = _localization_entries_from_tree("table.bundle", 7, string_tree)

    assert [entry.original for entry in entries] == ["VOLUME", "FULLSCREEN"]
    assert entries[0].key_path == "asset#7/loc/1"
    assert entries[0].meta == {
            "kind": "localization",
            "obj": 7,
            "entry_id": 1,
            "locale": "en",
            "table": "UITable_en",
            "role": "display",
            "confidence": "high",
            "reason": "localization_table_value",
            "disposition": "translate",
        }
    assert _localization_entries_from_tree("shared.bundle", 8, shared_tree) == []


def test_localization_tree_drops_structural_plural_templates_and_json():
    # I2 复数模板（{0:p:mine|mines}）与 JSON 序列化值是结构数据：
    # 模型必失败回显（minato 真实样本），且翻译会破坏 plural/JSON 语法
    string_tree = {
        "m_Name": "GameplayTable_en",
        "m_LocaleId": {"m_Code": "en"},
        "m_TableData": [
            {"m_Id": 1, "m_Localized": "Reveals {0} random {0:p:column|columns}."},
            {"m_Id": 2, "m_Localized": "Restores {0} <b>{0:p:heart|hearts}</b>."},
            {"m_Id": 3, "m_Localized": "{\"nest\":{\"source\":\"Macro\",\"macro\":0}}"},
            {"m_Id": 4, "m_Localized": "Pick {0} {0:p:item|items}"},
            {"m_Id": 5, "m_Localized": "VOLUME"},
        ],
    }

    entries = _localization_entries_from_tree("table.bundle", 7, string_tree)

    assert [entry.original for entry in entries] == ["VOLUME"]


def test_localization_tree_keeps_sentence_that_merely_contains_p():
    string_tree = {
        "m_Name": "HelpTable_en",
        "m_LocaleId": {"m_Code": "en"},
        "m_TableData": [
            {"m_Id": 1, "m_Localized": "Press P to pause"},
            {"m_Id": 2, "m_Localized": "Howdy, partner!"},
        ],
    }

    entries = _localization_entries_from_tree("table.bundle", 7, string_tree)

    assert [entry.original for entry in entries] == [
        "Press P to pause", "Howdy, partner!"]


def test_prefer_english_localization_bundle_only():
    ordinary = Path("gameplay.bundle")
    russian = Path("localization-string-tables-russian(ru)_assets_all.bundle")
    english = Path("localization-string-tables-english(en)_assets_all.bundle")
    spanish = Path("localization-string-tables-spanish(es)_assets_all.bundle")

    selected = _prefer_source_locale_bundles([ordinary, russian, english, spanish])

    assert selected == [ordinary, english]


def test_keep_all_localization_bundles_when_english_is_absent():
    russian = Path("localization-string-tables-russian(ru)_assets_all.bundle")
    spanish = Path("localization-string-tables-spanish(es)_assets_all.bundle")

    assert _prefer_source_locale_bundles([russian, spanish]) == [russian, spanish]


@pytest.mark.skipif(not os.getenv("HANHUA_SEWER_CALL_DIR"), reason="需要本机 SEWER CALL 样本")
def test_sewer_call_extracts_each_english_localization_value_once():
    game_dir = Path(os.environ["HANHUA_SEWER_CALL_DIR"])
    assets = find_asset_files(game_dir)
    localization = [p for p in assets if p.name.startswith("localization-string-tables-")]

    assert [p.name for p in localization] == [
        "localization-string-tables-english(en)_assets_all.bundle"
    ]

    parsed = extract_asset_file(localization[0], "english.bundle")
    originals = [entry.original for entry in parsed.entries if entry.status == "pending"]

    assert len(originals) == 38
    assert len(originals) == len(set(entry.key_path for entry in parsed.entries))
    assert {"VOLUME", "FULLSCREEN", "V-SYNC"} <= set(originals)


@pytest.mark.skipif(not os.getenv("HANHUA_SEWER_CALL_DIR"), reason="需要本机 SEWER CALL 样本")
def test_sewer_call_fallback_keeps_prompt_and_rejects_false_positive():
    game_dir = Path(os.environ["HANHUA_SEWER_CALL_DIR"])
    parsed = extract_asset_file(
        game_dir / "SEWER CALL_Data/sharedassets1.assets",
        "sharedassets1.assets",
    )

    originals = [entry.original for entry in parsed.entries if entry.status == "pending"]

    assert originals == ["Pick up flashlight"]
    assert "`\tB" not in originals


@pytest.mark.skipif(not os.getenv("HANHUA_SEWER_CALL_DIR"), reason="需要本机 SEWER CALL 样本")
def test_sewer_call_project_scan_keeps_exact_translation_scope(tmp_path):
    from hanhua.core.project import Project

    project = Project.open_game_dir(
        Path(os.environ["HANHUA_SEWER_CALL_DIR"]),
        tmp_path / "app-data",
    )

    kept_files = project.scan_v2()
    entries = project.store.get_entries()
    pending = [entry for entry in entries if entry["status"] == "pending"]

    assert kept_files == 8
    assert len(entries) == 734
    assert len(pending) == 91
    assert sum(entry["status"] == "skipped" for entry in entries) == 643
    assert {entry["original"] for entry in pending} >= {
        "SELECT LANGUAGE", "CREDITS", "SETTINGS", "VOLUME",
        "FULLSCREEN", "V-SYNC", "Pick up flashlight",
        "A <#0080ff>simple</color> line of text.",
    }
    for entry in pending:
        meta = json.loads(entry["meta"] or "{}")
        assert meta.get("role", "display") == "display"
        assert meta.get("confidence", "medium") in {"high", "medium"}
    assert not any(
        entry["file_id"].endswith("resources.assets") for entry in entries)
    assert any(
        entry["file_id"].endswith("Managed/Assembly-CSharp.dll")
        and entry["original"].startswith("Camera Control")
        for entry in pending)
