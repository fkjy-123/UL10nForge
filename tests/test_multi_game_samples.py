"""Environment-gated, read-only checks against the local multi-game sample set."""
from __future__ import annotations

from collections import Counter
import hashlib
import os
from pathlib import Path
import re

import pytest

from hanhua.core.unity.extractor import extract_asset_file, find_asset_files
from hanhua.core.unity.il2cpp import (extract_metadata_strings,
                                      find_metadata_file,
                                      parse_string_literals)
from hanhua.core.unity.mono_dll import (extract_dll_user_strings,
                                        find_dll_files)
from hanhua.core.tooling.fingerprint import fingerprint_game
from hanhua.core.tooling.planner import plan_backends, plan_is_unblocked
from hanhua.core.corpus.inventory import build_inventory
from hanhua.core.paths import _is_reparse_point


_LEVEL_SCENE = re.compile(r"^level\d+$")
_GAME_LEVEL_COUNTS = {
    "BFNS Remastered 1.4.7_Windows": 19,
    "Flabby Pizza": 10,
    "Forrgotten": 3,
    "seijunDROP - version 1.21": 7,
    "SEWER CALL": 5,
    "The Last Debug": 2,
    "What-Lives-Below-Demo-Windows": 3,
}

_GAME_FINGERPRINTS = {
    "BFNS Remastered 1.4.7_Windows": ("mono", "2021.3.1f1"),
    "Flabby Pizza": ("mono", "6000.4.3f1"),
    "Forrgotten": ("mono", "2022.3.34f1"),
    "seijunDROP - version 1.21": ("il2cpp", "2022.3.11f1"),
    "SEWER CALL": ("mono", "6000.3.10f1"),
    "The Last Debug": ("mono", "2021.3.30f1"),
    "What-Lives-Below-Demo-Windows": ("mono", "2019.4.19f1"),
}


def _games_root() -> Path:
    configured = os.environ.get("HANHUA_GAMES_DIR")
    if not configured:
        pytest.skip("set HANHUA_GAMES_DIR to run real multi-game sample checks")
    root = Path(configured)
    if not root.is_dir():
        pytest.fail(f"HANHUA_GAMES_DIR is not a directory: {root}")
    return root


def _corpus_root() -> Path:
    configured = os.environ.get("HANHUA_CORPUS_DIR")
    if not configured:
        pytest.skip("set HANHUA_CORPUS_DIR to run the real corpus gate")
    root = Path(configured)
    if not root.is_dir():
        pytest.fail(f"HANHUA_CORPUS_DIR is not a directory: {root}")
    return root


def _tree_metadata_manifest(root: Path) -> dict[str, tuple[int, int]]:
    manifest: dict[str, tuple[int, int]] = {}
    pending = [root]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                path = Path(entry.path)
                if _is_reparse_point(path):
                    continue
                stat = entry.stat(follow_symlinks=False)
                relative = path.relative_to(root).as_posix()
                manifest[relative] = (stat.st_size, stat.st_mtime_ns)
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
    return manifest


def _has_strong_unity_layout(game_root: Path) -> bool:
    files: list[Path] = []
    directories: list[Path] = []
    pending = [game_root]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                path = Path(entry.path)
                if _is_reparse_point(path):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    directories.append(path)
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    files.append(path)

    player_executables = [
        path for path in files
        if path.suffix.casefold() == ".exe"
        and "crashhandler" not in path.name.casefold()
    ]
    has_player_pair = (
        len(player_executables) == 1
        and any(path.name.casefold() in {
            "unityplayer.dll", "globalgamemanagers", "maindata",
        } for path in files)
    )
    global_manager_parents = {
        path.parent for path in files
        if path.name.casefold() == "globalgamemanagers"
    }
    has_canonical_data = any(
        directory.name.casefold().endswith("_data")
        and directory in global_manager_parents
        for directory in directories
    )
    return has_player_pair or has_canonical_data


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_real_corpus_inventory_represents_every_direct_directory_read_only():
    root = _corpus_root().resolve()
    direct_directories = {
        path.name for path in root.iterdir()
        if path.is_dir() and not _is_reparse_point(path)
    }
    before = _tree_metadata_manifest(root)

    inventory = build_inventory(root)

    after = _tree_metadata_manifest(root)
    assert len(inventory.games) == len(direct_directories)
    assert {game.game_id for game in inventory.games} == direct_directories
    games_without_strong_marker = [
        game.game_id for game in inventory.games
        if not _has_strong_unity_layout(game.source_path)
    ]
    assert games_without_strong_marker == []
    runtime_counts = Counter(game.runtime for game in inventory.games)
    assert runtime_counts["mono"] >= 1
    assert runtime_counts["il2cpp"] >= 1
    unknown_count = runtime_counts["unknown"]
    assert unknown_count >= 0
    assert sum(runtime_counts.values()) == len(inventory.games)
    print(
        "corpus runtime distribution: "
        f"mono={runtime_counts['mono']} il2cpp={runtime_counts['il2cpp']} "
        f"unknown={unknown_count}")
    assert before == after


def test_games_root_fails_when_configured_directory_is_missing(
        tmp_path, monkeypatch):
    class FailCalled(Exception):
        pass

    def unexpected_skip(reason):
        raise AssertionError(f"unexpected skip: {reason}")

    def expected_fail(reason):
        raise FailCalled(reason)

    missing = tmp_path / "missing-games"
    monkeypatch.setenv("HANHUA_GAMES_DIR", str(missing))
    monkeypatch.setattr(pytest, "skip", unexpected_skip)
    monkeypatch.setattr(pytest, "fail", expected_fail)

    with pytest.raises(FailCalled, match="not a directory"):
        _games_root()


def test_all_physical_level_scenes_are_discovered_read_only():
    root = _games_root()
    physical_levels: set[Path] = set()
    discovered_assets: set[Path] = set()
    for game_name, expected_count in _GAME_LEVEL_COUNTS.items():
        game_dir = root / game_name
        assert game_dir.is_dir()
        game_levels = {
            path for path in game_dir.rglob("*")
            if path.is_file() and _LEVEL_SCENE.fullmatch(path.name)
        }
        assert len(game_levels) == expected_count
        physical_levels.update(game_levels)
        discovered_assets.update(find_asset_files(game_dir))

    discovered_extensionless = {
        path for path in discovered_assets if path.suffix == ""
    }

    # The former 58-file audit counted non-source artifacts. The seven named,
    # original game roots currently contain exactly 49 extensionless scenes.
    assert len(physical_levels) == 49
    assert discovered_extensionless == physical_levels
    assert all(path.suffix.lower() != ".ress" for path in discovered_assets)


def test_all_games_have_deterministic_read_only_fingerprint_and_route():
    root = _games_root()
    for game_name, (runtime, unity_version) in _GAME_FINGERPRINTS.items():
        game_dir = root / game_name
        before = {
            path.relative_to(game_dir).as_posix(): _sha256_file(path)
            for path in game_dir.rglob("*") if path.is_file()
        }
        fingerprint = fingerprint_game(game_dir)
        repeated = fingerprint_game(game_dir)
        plan = plan_backends(
            fingerprint, {"il2cpp_dumper": "verified", "bmfont": "verified"})
        after = {
            path.relative_to(game_dir).as_posix(): _sha256_file(path)
            for path in game_dir.rglob("*") if path.is_file()
        }

        assert fingerprint.runtime == runtime
        assert fingerprint.unity_version == unity_version
        assert fingerprint.executable is not None
        assert fingerprint.data_dir is not None
        assert repeated == fingerprint
        assert plan_is_unblocked(plan)
        assert before == after


def test_representative_scene_text_is_not_duplicated_by_object_aliases():
    root = _games_root()
    scene = (
        root / "BFNS Remastered 1.4.7_Windows"
        / "BFNS Remastered_Data" / "level11"
    )

    parsed = extract_asset_file(scene, scene.relative_to(root).as_posix())
    originals = Counter(entry.original for entry in parsed.entries)
    key_paths = [entry.key_path for entry in parsed.entries]

    assert originals["CONGRATULATIONS!"] == 1
    assert originals["YOU  HAVE  WON"] == 1
    assert len(key_paths) == len(set(key_paths))


def test_bfns_slash_rich_text_and_long_description_anchors_are_read_only():
    root = _games_root()
    data_dir = (
        root / "BFNS Remastered 1.4.7_Windows" / "BFNS Remastered_Data"
    )
    scenes = [data_dir / "level1", data_dir / "level7"]
    before = {scene.name: _sha256_file(scene) for scene in scenes}

    level1 = extract_asset_file(scenes[0], scenes[0].relative_to(root).as_posix())
    level7 = extract_asset_file(scenes[1], scenes[1].relative_to(root).as_posix())

    assert Counter((entry.status, entry.meta["role"])
                   for entry in level1.entries) == {
        ("pending", "display"): 144,
        # 88 条增量来自 method_name（set_sprite/set_fontSize 等引擎 setter）
        # 与更多 type_reference 精确归类——显示文本 144 条零变化
        ("skipped", "structural"): 327,
    }
    settings_anchor = [
        entry for entry in level1.entries
        if entry.original == "Click/Tap Me To Go To The Settings Screen."
    ]
    assert len(settings_anchor) == 1
    assert settings_anchor[0].status == "pending"
    assert settings_anchor[0].meta["role"] == "display"
    assert sum(
        entry.status == "pending" and entry.meta["role"] == "display"
        for entry in level1.entries if "</" in entry.original
    ) == 29

    long_descriptions = [
        entry for entry in level7.entries
        if len(entry.original.encode("utf-8")) == 651
    ]
    assert len(long_descriptions) == 1
    assert long_descriptions[0].status == "pending"
    assert long_descriptions[0].meta["role"] == "display"
    assert before == {scene.name: _sha256_file(scene) for scene in scenes}


def test_manifest_assemblies_and_tree_locale_routing_are_read_only():
    root = _games_root()
    bfns = root / "BFNS Remastered 1.4.7_Windows"
    manifest = bfns / "BFNS Remastered_Data" / "ScriptingAssemblies.json"
    before_manifest = _sha256_file(manifest)

    assemblies = find_dll_files(bfns)

    assert len(assemblies) == 26
    assert {path.name for path in assemblies} >= {
        "Assembly-CSharp.dll", "GameJoltRuntime.dll",
        "Platforms_Source.dll", "WordFilter.dll",
    }
    assert all(path.parent.name == "Managed" for path in assemblies)
    assert before_manifest == _sha256_file(manifest)

    assembly_csharp = next(
        path for path in assemblies if path.name == "Assembly-CSharp.dll")
    before_assembly = _sha256_file(assembly_csharp)
    parsed = extract_dll_user_strings(
        assembly_csharp, assembly_csharp.relative_to(root).as_posix())
    roles = Counter((entry.status, entry.meta["role"], entry.meta["reason"])
                    for entry in parsed.entries)
    assert roles == {
        ("pending", "display", "mono_ui_setter"): 133,
        ("pending", "display", "interaction_prompt"): 1,
        ("pending", "display", "user_string_uppercase_ui"): 12,
        ("skipped", "structural", "unverified_user_string"): 170,
    }
    assert {entry.original for entry in parsed.entries if entry.status == "pending"} >= {
        "Good Job!",
        "Tap On An Achievement Below To View It!",
        "Show FPS?\n<color=green>Yes</color>",
    }
    assert before_assembly == _sha256_file(assembly_csharp)

    sewer = root / "SEWER CALL"
    localization = [
        path for path in find_asset_files(sewer)
        if path.name.startswith("localization-string-tables-")
    ]
    assert [path.name for path in localization] == [
        "localization-string-tables-english(en)_assets_all.bundle",
    ]


def test_reported_flabby_prompts_and_keeper_quit_are_actionable_read_only():
    root = _games_root()
    flabby = root / "Flabby Pizza"
    keeper = root / "the-keeper-windows-new"
    flabby_assembly = next(
        path for path in find_dll_files(flabby)
        if path.name == "Assembly-CSharp.dll")
    before_assembly = _sha256_file(flabby_assembly)
    prompts = {
        entry.original: entry
        for entry in extract_dll_user_strings(
            flabby_assembly,
            flabby_assembly.relative_to(root).as_posix()).entries
        if entry.original.casefold().startswith("press e to")
    }
    expected_prompts = {
        "Press E to Open",
        "Press E to Close",
        "Press E to take battery",
        "Press E to insert battery",
        "Press E to Break Board",
        "Press E to Move ",
        "Press E to put box in fridge",
    }

    assert set(prompts) == expected_prompts
    assert all(
        entry.status == "pending"
        and entry.meta["confidence"] == "high"
        and entry.meta["role"] == "display"
        and entry.meta["disposition"] == "translate"
        and entry.meta["reason"] == "interaction_prompt"
        for entry in prompts.values()
    )
    assert before_assembly == _sha256_file(flabby_assembly)

    keeper_quit = []
    keeper_hashes = {}
    for asset in find_asset_files(keeper):
        keeper_hashes[asset] = _sha256_file(asset)
        keeper_quit.extend(
            entry for entry in extract_asset_file(
                asset, asset.relative_to(root).as_posix()).entries
            if entry.original == "Quit")
    assert len(keeper_quit) == 2
    assert all(
        entry.status == "pending"
        and entry.meta["confidence"] == "high"
        and entry.meta["role"] == "display"
        and entry.meta["disposition"] == "translate"
        and entry.meta["reason"] == "core_menu_control"
        for entry in keeper_quit
    )
    assert keeper_hashes == {
        asset: _sha256_file(asset) for asset in keeper_hashes}


def test_what_lives_below_formatted_shop_text_has_ui_provenance_read_only():
    root = _games_root()
    assembly = (
        root / "What-Lives-Below-Demo-Windows"
        / "What Lives Below Demo_Data" / "Managed" / "Assembly-CSharp.dll"
    )
    before = _sha256_file(assembly)

    parsed = extract_dll_user_strings(
        assembly, assembly.relative_to(root).as_posix())
    formatted = next(
        entry for entry in parsed.entries if entry.key_path == "us#58197")

    assert formatted.original == "{0}\n{1}kg\n£{2}"
    assert formatted.status == "pending"
    assert formatted.meta["role"] == "display"
    assert formatted.meta["disposition"] == "translate"
    assert formatted.meta["reason"] == "mono_ui_setter"
    assert before == _sha256_file(assembly)


def test_seijundrop_v29_metadata_literals_are_strict_and_read_only():
    root = _games_root()
    game_dir = root / "seijunDROP - version 1.21"
    metadata_path = find_metadata_file(game_dir)
    assert metadata_path is not None

    raw = metadata_path.read_bytes()
    before_sha256 = hashlib.sha256(raw).hexdigest().upper()
    assert int.from_bytes(raw[4:8], "little") == 29
    literals = parse_string_literals(raw)
    decoded = [raw[data_pos:data_pos + length].decode("utf-8")
               for _, length, data_pos in literals]

    assert len(literals) == 5725
    assert "[PICK UP]" in decoded

    parsed = extract_metadata_strings(
        metadata_path, metadata_path.relative_to(root).as_posix())
    pending = [entry.original for entry in parsed.entries
               if entry.status == "pending"]
    assert pending
    assert all(
        all((ord(ch) >= 0x20 or ch in "\t\n\r")
            and not 0x7F <= ord(ch) <= 0x9F
            for ch in text)
        for text in pending
    )
    after_sha256 = hashlib.sha256(metadata_path.read_bytes()).hexdigest().upper()
    assert before_sha256 == after_sha256
    assert after_sha256 == "6E522747F36F500D382B6E4FBCC9C9400B427B438AC043AC4519C85B418929AD"


def test_all_games_keep_representative_display_text_and_skip_structural_noise():
    root = _games_root()
    display_samples = {
        "BFNS Remastered 1.4.7_Windows": ("level0", "View Controls"),
        "Flabby Pizza": ("level0", "Master Volume"),
        "Forrgotten": ("level0", "Start game"),
        "seijunDROP - version 1.21": ("level0", "NEW GAME"),
        "SEWER CALL": ("level0", "SELECT LANGUAGE"),
        "The Last Debug": ("level0", "Press any key to continue"),
        "What-Lives-Below-Demo-Windows": ("level0", "Press Any Key"),
    }
    parsed_by_game: dict[str, list] = {}
    for game_name, (asset_name, expected_text) in display_samples.items():
        game_dir = root / game_name
        matches = [path for path in find_asset_files(game_dir)
                   if path.name == asset_name]
        assert len(matches) == 1
        parsed = extract_asset_file(
            matches[0], matches[0].relative_to(root).as_posix())
        parsed_by_game[game_name] = parsed.entries
        candidates = [entry for entry in parsed.entries
                      if entry.original == expected_text]
        assert candidates
        assert all(entry.status == "pending" for entry in candidates)
        assert all(entry.meta["confidence"] in ("high", "medium")
                   and entry.meta["role"] == "display"
                   for entry in candidates)

    last_debug = root / "The Last Debug"
    last_debug_level1 = next(
        path for path in find_asset_files(last_debug) if path.name == "level1")
    new_text_entries = [
        entry for entry in extract_asset_file(
            last_debug_level1, last_debug_level1.relative_to(root).as_posix()).entries
        if entry.original == "New Text"
    ]
    assert new_text_entries
    assert all(entry.status == "skipped"
               and entry.meta["reason"] == "default_placeholder"
               for entry in new_text_entries)

    flabby = root / "Flabby Pizza"
    timeline_asset = next(
        path for path in find_asset_files(flabby)
        if path.name == "sharedassets3.assets")
    timeline_entries = [
        entry for entry in extract_asset_file(
            timeline_asset, timeline_asset.relative_to(root).as_posix()).entries
        if entry.original in {
            "Animation Track", "Activation Track", "Signal Track", "Audio Track",
        }
    ]
    assert {entry.original for entry in timeline_entries} == {
        "Animation Track", "Activation Track", "Signal Track", "Audio Track",
    }
    assert all(entry.status == "skipped"
               and entry.meta["reason"] == "timeline_track"
               for entry in timeline_entries)

    forrgotten = root / "Forrgotten"
    forrgotten_resources = next(
        path for path in find_asset_files(forrgotten)
        if path.name == "resources.assets")
    forrgotten_type_refs = [
        entry for entry in extract_asset_file(
            forrgotten_resources,
            forrgotten_resources.relative_to(root).as_posix()).entries
        if entry.original == (
            "UnityEngine.Rendering.UI.DebugUIHandlerButton, "
            "Unity.RenderPipelines.Core.Runtime")
    ]
    assert forrgotten_type_refs
    assert all(entry.status == "skipped"
               and entry.meta["confidence"] == "low"
               and entry.meta["role"] == "structural"
               and entry.meta["reason"] == "type_reference"
               for entry in forrgotten_type_refs)

    seijun_entries = parsed_by_game["seijunDROP - version 1.21"]
    seijun_assembly_refs = [
        entry for entry in seijun_entries
        if entry.original == "Katsuai.Menu.MainMenu, Assembly-CSharp"
    ]
    assert seijun_assembly_refs
    assert all(entry.status == "skipped"
               and entry.meta["confidence"] == "low"
               and entry.meta["role"] == "structural"
               and entry.meta["reason"] == "type_reference"
               for entry in seijun_assembly_refs)

    sewer_entries = parsed_by_game["SEWER CALL"]
    sewer_assembly_refs = [
        entry for entry in sewer_entries
        if entry.original == "MenuButton, Assembly-CSharp"
    ]
    assert sewer_assembly_refs
    assert all(entry.status == "skipped"
               and entry.meta["confidence"] == "low"
               and entry.meta["role"] == "structural"
               and entry.meta["reason"] == "type_reference"
               for entry in sewer_assembly_refs)

    what_lives_below = root / "What-Lives-Below-Demo-Windows"
    what_lives_below_level1 = next(
        path for path in find_asset_files(what_lives_below)
        if path.name == "level1")
    what_lives_below_assembly_refs = [
        entry for entry in extract_asset_file(
            what_lives_below_level1,
            what_lives_below_level1.relative_to(root).as_posix()).entries
        if entry.original == (
            "OneBit, Assembly-CSharp, Version=0.0.0.0, Culture=neutral, "
            "PublicKeyToken=null")
    ]
    assert what_lives_below_assembly_refs
    assert all(entry.status == "skipped"
               and entry.meta["confidence"] == "low"
               and entry.meta["role"] == "structural"
               and entry.meta["reason"] == "type_reference"
               for entry in what_lives_below_assembly_refs)

    bfns_entries = parsed_by_game["BFNS Remastered 1.4.7_Windows"]
    structural_refs = [
        entry for entry in bfns_entries
        if ("Assembly-CSharp" in entry.original
            or "UnityEngine." in entry.original
            or ", Unity.TextMeshPro" in entry.original)
    ]
    assert structural_refs
    assert all(entry.status == "skipped"
               and entry.meta["confidence"] == "low"
               and entry.meta["role"] == "structural"
               and entry.meta["reason"] == "type_reference"
               for entry in structural_refs)
