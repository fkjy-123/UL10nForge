"""翻译完成后失败记录自动导出（游戏名 + fail record，docs/fail record）。"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from hanhua.core.fail_export import export_fail_record


def _project(tmp_path, game_name="Bloody Battle"):
    store = SimpleNamespace(
        get_entries=lambda status=None: [{
            "file_id": "f1", "key_path": "menu/start",
            "original": "Press START to begin",
            "translation": "", "status": "failed", "locked": 0,
            "meta": json.dumps({
                "source": "game/Data/text_en.json",
                "quality_reasons": ["request_error"],
                "request_error_detail": json.dumps({
                    "status": 502, "message": "service unavailable",
                }, ensure_ascii=False),
            }, ensure_ascii=False),
        }, {
            "file_id": "f1", "key_path": "menu/quit",
            "original": "Quit to desktop",
            "translation": "退到桌面", "status": "failed", "locked": 0,
            "meta": json.dumps({
                "source": "game/Data/text_en.json",
                "quality_reasons": ["untranslated_text", "line_content_mismatch"],
            }, ensure_ascii=False),
        }],
    )
    profile = SimpleNamespace(game_name=game_name)
    return SimpleNamespace(store=store, profile=profile)


def test_export_writes_game_named_file_with_all_fields(tmp_path):
    """文件命名含游戏名 + fail record，内容含来源/原文/译文/原因。"""
    out_dir = tmp_path / "docs" / "fail record"
    path = export_fail_record(_project(tmp_path), out_dir)

    assert path is not None
    assert "Bloody Battle" in path.name and "fail record" in path.name
    text = path.read_text(encoding="utf-8")
    assert "game/Data/text_en.json" in text          # 来源完整路径
    assert "menu/start" in text                      # key_path
    assert "Press START to begin" in text            # 原文
    assert "退到桌面" in text                          # 译文
    assert "request_error" in text                   # 失败原因
    assert "untranslated_text" in text
    assert "service unavailable" in text             # 错误详情


def test_export_skips_when_no_failed_entries(tmp_path):
    project = _project(tmp_path)
    project.store.get_entries = lambda status=None: []
    out_dir = tmp_path / "docs" / "fail record"

    assert export_fail_record(project, out_dir) is None
    assert not out_dir.exists()


def test_export_falls_back_when_game_name_empty(tmp_path):
    path = export_fail_record(_project(tmp_path, game_name=""), tmp_path)

    assert path is not None
    assert "fail record" in path.name


def test_export_creates_output_directory(tmp_path):
    out_dir = tmp_path / "a" / "b" / "c"
    path = export_fail_record(_project(tmp_path), out_dir)

    assert path is not None and path.exists()
    assert out_dir.is_dir()


def test_export_keeps_history_with_timestamp(tmp_path):
    out_dir = tmp_path / "docs"
    first = export_fail_record(_project(tmp_path), out_dir)
    second = export_fail_record(_project(tmp_path), out_dir)

    assert first is not None and second is not None
    assert first != second                       # 每次汉化独立成档，不覆盖


def test_export_handles_missing_meta_gracefully(tmp_path):
    store = SimpleNamespace(get_entries=lambda status=None: [{
        "file_id": "f9", "key_path": "k", "original": "raw",
        "translation": "", "status": "failed", "locked": 0,
        "meta": "not-json",
    }])
    project = SimpleNamespace(
        store=store, profile=SimpleNamespace(game_name="No Meta"))

    path = export_fail_record(project, tmp_path)

    assert path is not None
    assert "raw" in path.read_text(encoding="utf-8")


def test_export_with_attach_error_writes_error_block(tmp_path):
    """写回失败等非条目级错误 → 附加错误段落盘（所有失败都导出）。"""
    store = SimpleNamespace(get_entries=lambda status=None: [])
    project = SimpleNamespace(
        store=store, profile=SimpleNamespace(game_name="Ghost"))

    path = export_fail_record(
        project, tmp_path,
        error_title="写回失败",
        error_detail="Unity Mono 游戏结构不完整：需要同名 *_Data/Managed/UnityEngine.CoreModule.dll")

    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert "附加错误：写回失败" in text
    assert "UnityEngine.CoreModule.dll" in text
    assert "失败条目：0 条" in text


def test_export_without_entries_or_error_returns_none(tmp_path):
    store = SimpleNamespace(get_entries=lambda status=None: [])
    project = SimpleNamespace(
        store=store, profile=SimpleNamespace(game_name="Quiet"))

    assert export_fail_record(project, tmp_path) is None


def test_export_lock_error_appends_actionable_hint(tmp_path):
    """F9：文件锁定类写回错误（WinError 5）追加可操作提示。"""
    store = SimpleNamespace(get_entries=lambda status=None: [])
    project = SimpleNamespace(
        store=store, profile=SimpleNamespace(game_name="Locked"))
    path = export_fail_record(
        project, tmp_path,
        error_title="写回失败",
        error_detail="文件被占用无法写回（可能原因：游戏仍在运行、杀毒软件/"
        "Windows Defender 正在扫描）：Assembly-CSharp.dll")
    text = path.read_text(encoding="utf-8")
    assert "附加错误：写回失败" in text
    assert "提示：文件正被占用导致写回失败" in text
    assert "白名单" in text


def test_export_non_lock_error_has_no_hint(tmp_path):
    store = SimpleNamespace(get_entries=lambda status=None: [])
    project = SimpleNamespace(
        store=store, profile=SimpleNamespace(game_name="Other"))
    path = export_fail_record(
        project, tmp_path,
        error_title="写回失败",
        error_detail="Unity Mono 游戏结构不完整：需要同名 *_Data 目录")
    text = path.read_text(encoding="utf-8")
    assert "附加错误：写回失败" in text
    assert "提示：" not in text
