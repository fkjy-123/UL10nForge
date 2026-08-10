from __future__ import annotations

import os
import json
from pathlib import Path
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from hanhua.core.memory import ProjectStore
from hanhua.core.memory_lifecycle import (
    MemoryCleanupFailure,
    MemoryCleanupSummary,
)
from hanhua.core.models import FontConfig, TranslateStats
from hanhua.core.project import WritebackStage
from hanhua.core.settings import SettingsStore
from hanhua.ui.app_state import AppState
from hanhua.ui.design_system import TOKENS
from hanhua.ui.icons import LineIcon
from hanhua.ui.main_window import MainWindow
from hanhua.ui.pages.home_page import HomePage, _DirectoryDropZone
from hanhua.ui.pages.review_page import EntryFilterProxy, EntryTableModel, ReviewPage
from hanhua.ui.pages.translate_page import TranslatePage


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Window:
    def navigate(self, _page):
        pass

    def updateProjectCard(self, _project):
        pass


class _RecordingWindow(_Window):
    def __init__(self):
        self.pages = []

    def navigate(self, page):
        self.pages.append(page)


def _state(tmp_path: Path) -> AppState:
    settings = SettingsStore(tmp_path / "settings.json")
    settings.load()
    return AppState(tmp_path, settings)


def test_home_is_accessible_five_stage_workbench_without_emoji(qapp, tmp_path):
    page = HomePage(_state(tmp_path), _Window())

    assert TOKENS.control_height >= 44
    assert isinstance(page.dz_icon, LineIcon)
    assert [card.step_id for card in page.pipeline_cards] == [
        "detection", "text_scan", "tool_analysis",
        "translation_quality", "writeback",
    ]
    assert page.pick_btn.minimumHeight() >= 44
    assert page.pick_btn.accessibleName() == "选择 Unity 游戏文件夹"
    assert hasattr(page, "runtime_value")
    assert hasattr(page, "tool_value")
    assert not hasattr(page, "cache_value")         # 缓存/置信度并入流水线卡片
    assert not hasattr(page, "confidence_value")
    visible_text = " ".join(widget.text() for widget in (
        page.findChildren(QLabel) + page.findChildren(QPushButton)
    ))
    assert "📁" not in visible_text


def test_translate_page_exposes_actionable_stats_and_safe_writeback_state(
        qapp, tmp_path):
    page = TranslatePage(_state(tmp_path), _Window())

    assert hasattr(page, "chip_skipped")
    assert hasattr(page, "quality_reason_label")
    assert not hasattr(page, "metric_speed")        # 实时速度舱已移除（速度在设置页显示）
    assert not hasattr(page, "chip_high")           # 技术性置信/缓存/诊断已移除
    assert not hasattr(page, "scan_diagnostics_btn")
    for button in (page.start_btn, page.stop_btn, page.retry_btn, page.write_btn):
        assert button.minimumHeight() >= 44
        assert button.accessibleName()


def test_translate_progress_uses_actionable_scope_and_collapses_skips(
        qapp, tmp_path):
    rows = [
        {
            "file_id": "code", "key_path": f"skip/{index}",
            "original": f"Method{index}", "translation": "",
            "status": "skipped", "locked": 0,
            "meta": json.dumps({
                "role": "structural", "confidence": "low",
                "quality_reasons": ["structural_text"],
            }),
        }
        for index in range(1700)
    ]
    rows.extend({
        "file_id": "ui", "key_path": f"prompt/{index}",
        "original": f"Open door {index}", "translation": "",
        "status": "pending", "locked": 0,
        "meta": json.dumps({"role": "display", "confidence": "high"}),
    } for index in range(300))
    rows.append({
        "file_id": "ui", "key_path": "history/settings",
        "original": "Settings", "translation": "设置",
        "status": "translated", "locked": 0,
        "meta": json.dumps({"role": "display", "confidence": "high"}),
    })
    state = _state(tmp_path)
    state.project = type("Project", (), {"store": _StoreRows(rows)})()
    page = TranslatePage(state, _Window())

    page._refresh_chips()

    assert page.progress_label.text() == "0 / 300 条"
    assert page.progress_bar.value() == 0
    assert page.chip_done.text() == "已翻译 1"
    assert page.chip_skipped.isHidden()

    page._on_progress(TranslateStats(total=300, done=300))

    assert page.progress_label.text() == "300 / 300 条"
    assert page.progress_bar.value() == 100


def test_translation_start_log_uses_same_zero_actionable_scope(
        qapp, tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "project.db")
    store.init_schema()
    store.add_file("ui", "ui.assets", "v2_asset", "binary", "")
    store.upsert_entries([
        {
            "file_id": "ui", "key_path": "code/awake", "original": "Awake",
            "meta": {"role": "structural", "confidence": "high"},
        },
        {
            "file_id": "ui", "key_path": "uncertain/open",
            "original": "Open", "meta": {
                "role": "display", "confidence": "low",
            },
        },
    ])
    state = _state(tmp_path)
    state.api.mode = "api"
    state.api.base_url = "https://example.invalid/v1/chat/completions"
    state.api.api_key = "test-key"
    state.api.model = "test-model"
    state.project = type("Project", (), {"store": store, "profile": None})()
    page = TranslatePage(state, _Window())
    queued = []
    page._pool = type(
        "Pool", (), {"start": lambda _self, worker: queued.append(worker)})()

    class FakeGlossary:
        def __init__(self, _path):
            pass

        def init_schema(self):
            pass

        def list_all(self):
            return []

        def format_for_prompt(self):
            return ""

        def known_names_for(self, _collected=None):
            return []

        def learn_proper_names(self, *_args, **_kwargs):
            return 0

        def close(self):
            pass

    client = type("Client", (), {
        "url": "https://example.invalid/v1/chat/completions",
        "chat": lambda _self, *_args: pytest.fail(
            "zero actionable scope reached provider"),
    })()
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.GlossaryStore", FakeGlossary)
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.create_client", lambda _api: client)

    page.start()
    logs = []
    signals = type("Signals", (), {
        "progress": type("Signal", (), {"emit": lambda _self, _value: None})(),
        "log": type("Signal", (), {"emit": lambda _self, value: logs.append(value)})(),
    })()
    stats = page._translate_worker(page._active_run, signals)

    assert stats.total == 0
    assert any("待翻译 0 条" in line for line in logs)
    assert any("低置信度" in line for line in logs)   # 留档提示（uncertain/open 1 条）


def test_main_window_statusbar_reports_local_backend(qapp, tmp_path):
    state = _state(tmp_path)
    state.api.mode = "local"
    state.api.local_model_path = str(tmp_path / "models" / "Hy-MT2.gguf")

    window = MainWindow(state)

    status = window.statusBar().currentMessage()
    assert "本地" in status
    assert "Hy-MT2" in status
    assert "未启动" in status


def test_main_window_statusbar_omits_startup_cleanup_details(qapp, tmp_path):
    """状态栏不再展示启动内存清理诊断（开发者信息，普通用户不可操作）。"""
    settings = SettingsStore(tmp_path / "settings.json")
    settings.load()
    state = AppState(
        tmp_path,
        settings,
        memory_cleanup=MemoryCleanupSummary(
            discovered_databases=2,
            cleared_databases=2,
            cleared_entries=2,
            cleared_memory=1,
        ),
    )

    window = MainWindow(state)
    status = window.statusBar().currentMessage()

    assert "清理" not in status
    assert "翻译记忆" not in status


def test_review_page_filters_and_explains_recognition_evidence(qapp, tmp_path):
    state = _state(tmp_path)
    page = ReviewPage(state, _Window())

    assert EntryTableModel.COLS == [
        "状态", "来源", "原文", "译文", "失败原因", "锁定",
    ]
    for control in (
        page.search_box, page.status_combo, page.file_combo,
        page.translate_btn,
    ):
        assert control.minimumHeight() >= 44
        assert control.accessibleName()

    rows = [
        {
            "file_id": "ui.assets", "key_path": "obj/1", "original": "Continue",
            "translation": "继续", "status": "translated", "locked": 0,
            "meta": json.dumps({
                "confidence": "high", "role": "display", "quality_reasons": [],
            }),
        },
        {
            "file_id": "code.assets", "key_path": "obj/2", "original": "Awake",
            "translation": "", "status": "skipped", "locked": 0,
            "meta": json.dumps({
                "confidence": "low", "role": "structural",
                "quality_reasons": ["structural_text"],
            }),
        },
    ]
    model = EntryTableModel(state)
    model.setEntries(rows)
    proxy = EntryFilterProxy()
    proxy.setSourceModel(model)
    proxy.setFilters(status="skipped")

    assert proxy.rowCount() == 1
    assert proxy.index(0, 1).data() == "code.assets"
    assert proxy.index(0, 4).data() == "structural_text"


def test_review_context_menu_uses_table_coordinate_lookup(qapp, tmp_path):
    page = ReviewPage(_state(tmp_path), _Window())
    page._show_menu(QPoint(0, 0))


def test_review_table_can_unlock_a_checked_entry(qapp, tmp_path):
    recorded = []
    store = type("Store", (), {
        "set_locked": lambda _self, file_id, key_path, locked: recorded.append(
            (file_id, key_path, locked)),
    })()
    state = _state(tmp_path)
    state.project = type("Project", (), {"store": store})()
    model = EntryTableModel(state)
    row = {
        "file_id": "ui.assets", "key_path": "obj/1", "original": "Continue",
        "translation": "继续", "status": "translated", "locked": 1,
        "meta": "{}",
    }
    model.setEntries([row])

    assert model.setData(
        model.index(0, 5), Qt.Unchecked, Qt.CheckStateRole) is True
    assert recorded == [("ui.assets", "obj/1", False)]
    assert row["locked"] is False


def test_review_clearing_manual_translation_syncs_pending_quality_state(
        qapp, tmp_path):
    store = ProjectStore(tmp_path / "project.db")
    store.init_schema()
    store.add_file("ui.assets", "ui.assets", "v2_asset", "binary", "")
    store.upsert_entries([{
        "file_id": "ui.assets", "key_path": "obj/1",
        "original": "Continue", "meta": {"confidence": "high"},
    }])
    store.set_manual("ui.assets", "obj/1", "继续")
    state = _state(tmp_path)
    state.project = type("Project", (), {"store": store})()
    model = EntryTableModel(state)
    row = store.get_entries()[0]
    model.setEntries([row])

    assert model.setData(model.index(0, 3), "", Qt.EditRole) is True

    persisted = store.get_entries()[0]
    assert persisted["translation"] == ""
    assert persisted["status"] == "pending"
    assert json.loads(persisted["meta"])["quality_passed"] is False
    assert row["status"] == persisted["status"]
    assert row["meta"] == persisted["meta"]


def test_review_page_auto_reloads_on_construction_and_project_opened(
        qapp, tmp_path):
    """构造时自动 reload；projectOpened 信号触发 reload。
    回归：信号连接曾被误放进 _focus_search()，打开项目后表格空白。"""
    store = ProjectStore(tmp_path / "project.db")
    store.init_schema()
    store.add_file("ui.assets", "ui.assets", "v2_asset", "binary", "")
    store.upsert_entries([{
        "file_id": "ui.assets", "key_path": "obj/1",
        "original": "Continue", "meta": {"confidence": "high"},
    }])
    state = _state(tmp_path)
    page = ReviewPage(state, _Window())

    # 无项目时：构造即 reload，summary 显示 0 条，筛选未卡死
    assert "共 0 条" in page.summary_label.text()
    assert page._loading is False

    # 打开项目：projectOpened 信号自动触发 reload
    state.project = type("Project", (), {"store": store})()
    state.projectOpened.emit(state.project)
    assert page.model.rowCount() == 1
    assert "共 1 条" in page.summary_label.text()

    # 条目变化信号同样触发刷新
    state.entriesChanged.emit()
    assert page.model.rowCount() == 1


def test_home_enters_review_when_scan_is_unblocked_but_not_complete(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    window = _RecordingWindow()
    page = HomePage(state, window)
    monkeypatch.setattr(page, "_render_report", lambda _report: None)
    monkeypatch.setattr(page, "_refresh_profile_card", lambda: None)
    monkeypatch.setattr(
        "hanhua.ui.pages.home_page.Toast.show", lambda *args, **kwargs: None)
    report = type("Report", (), {
        "text_files": 1, "v2_files": 2,
        "unblocked": True, "completable": False,
    })()
    project = object()

    page._on_scan_done((project, report))

    assert window.pages == ["review"]


class _StoreRows:
    def __init__(self, rows):
        self.rows = rows

    def get_entries(self, status=None):
        if status is None:
            return self.rows
        return [row for row in self.rows if row["status"] == status]

    def count(self, status):
        return sum(row["status"] == status for row in self.rows)


def test_drop_zone_accepts_only_one_local_directory(qapp, tmp_path):
    directory = tmp_path / "game"
    directory.mkdir()
    file_path = tmp_path / "game.exe"
    file_path.write_bytes(b"MZ")
    zone = _DirectoryDropZone()

    valid = QMimeData()
    valid.setUrls([QUrl.fromLocalFile(str(directory))])
    file_drop = QMimeData()
    file_drop.setUrls([QUrl.fromLocalFile(str(file_path))])
    multiple = QMimeData()
    multiple.setUrls([
        QUrl.fromLocalFile(str(directory)),
        QUrl.fromLocalFile(str(tmp_path)),
    ])
    remote = QMimeData()
    remote.setUrls([QUrl("https://example.invalid/game")])

    assert zone.local_directory(valid) == directory.resolve()
    assert zone.local_directory(file_drop) is None
    assert zone.local_directory(multiple) is None
    assert zone.local_directory(remote) is None


def test_switch_project_closes_previous_store_and_advances_generation(
        qapp, tmp_path):
    state = _state(tmp_path)
    closed = []
    first = type("Project", (), {
        "store": type("Store", (), {
            "close": lambda _self: closed.append("first"),
        })(),
    })()
    second = type("Project", (), {
        "store": type("Store", (), {
            "close": lambda _self: closed.append("second"),
        })(),
    })()

    first_generation = state.switch_project(first)
    second_generation = state.switch_project(second)

    assert first_generation == 1
    assert second_generation == 2
    assert closed == ["first"]
    assert state.is_current_project(second, second_generation)
    assert not state.is_current_project(first, first_generation)


def test_active_project_lease_defers_store_close_until_worker_exits(
        qapp, tmp_path):
    state = _state(tmp_path)
    closed = []
    first = type("Project", (), {
        "store": type("Store", (), {
            "close": lambda _self: closed.append("first"),
        })(),
    })()
    second = type("Project", (), {
        "store": type("Store", (), {"close": lambda _self: None})(),
    })()
    generation = state.switch_project(first)

    with state.project_lease(first, generation) as acquired:
        assert acquired is True
        state.switch_project(second)
        assert closed == []

    assert closed == ["first"]


def test_app_close_defers_active_project_store_until_worker_exits(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    closed = []
    project = type("Project", (), {
        "store": type("Store", (), {
            "close": lambda _self: closed.append("project"),
        })(),
    })()
    generation = state.switch_project(project)
    monkeypatch.setattr(state.local_model, "stop", lambda: None)

    with state.project_lease(project, generation) as acquired:
        assert acquired is True
        state.close()
        assert closed == []

    assert closed == ["project"]


def test_reactivated_leased_project_is_not_closed_when_old_lease_exits(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    closed = []
    first = type("Project", (), {
        "store": type("Store", (), {
            "close": lambda _self: closed.append("first"),
        })(),
    })()
    second = type("Project", (), {
        "store": type("Store", (), {"close": lambda _self: None})(),
    })()
    generation = state.switch_project(first)
    monkeypatch.setattr(state.local_model, "stop", lambda: None)

    with state.project_lease(first, generation) as acquired:
        assert acquired is True
        state.switch_project(second)
        state.switch_project(first)

    assert closed == []
    state.close()
    assert closed == ["first"]


def test_stale_queued_write_never_targets_new_project_or_calls_back(
        qapp, tmp_path, monkeypatch):
    row = {
        "file_id": "ui.assets", "key_path": "obj/1", "original": "Continue",
        "translation": "继续", "status": "translated", "locked": 0,
        "meta": json.dumps({"quality_passed": True, "confidence": "high"}),
    }

    class Store(_StoreRows):
        def __init__(self):
            super().__init__([dict(row)])
            self.closed = False

        def close(self):
            self.closed = True

    calls = []

    class Project:
        def __init__(self, name):
            self.name = name
            self.store = Store()
            self.out_dir = tmp_path / f"{name}_汉化"

        def write_all(self, *, font_config=None, allow_partial=False):
            calls.append((self.name, font_config))
            return {"text_files": 1}

    state = _state(tmp_path)
    first = Project("A")
    second = Project("B")
    state.switch_project(first)
    state.analysis_report = _report(unblocked=True)
    page = TranslatePage(state, _Window())
    queued = []
    page._pool = type(
        "Pool", (), {"start": lambda _self, worker: queued.append(worker)})()
    callbacks = []
    monkeypatch.setattr(page, "_on_written", lambda result: callbacks.append(result))
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show", lambda *args, **kwargs: None)

    page.write_back()
    assert len(queued) == 1
    state.switch_project(second)
    queued[0].run()

    assert first.store.closed is True
    assert calls == []
    assert callbacks == []


def test_writeback_stage_progress_and_duplicate_run_guard(
        qapp, tmp_path, monkeypatch):
    row = {
        "file_id": "ui.assets", "key_path": "obj/1", "original": "Continue",
        "translation": "继续", "status": "translated", "locked": 0,
        "meta": json.dumps({"quality_passed": True, "confidence": "high"}),
    }

    class Project:
        def __init__(self):
            self.store = _StoreRows([row])
            self.out_dir = tmp_path / "game_汉化"

        def write_all(self, *, font_config=None, stage_cb=None,
                allow_partial=False):
            assert font_config is not None
            for phase, message in (
                    ("copying", "正在复制原游戏"),
                    ("verifying", "正在重开并验证汉化输出"),
                    ("published", "汉化游戏已发布")):
                stage_cb(WritebackStage(phase, message))
            report = _report(unblocked=True, completable=True)
            return {
                "text_files": 1,
                "verification": {
                    "input_protected": True,
                    "reopen_verified": True,
                    "changed_files": 1,
                    "written_translations": 1,
                    "font_level": "disabled",
                },
                "analysis_report": report,
            }

    state = _state(tmp_path)
    state.switch_project(Project())
    state.analysis_report = _report(unblocked=True)
    page = TranslatePage(state, _Window())
    queued = []
    page._pool = type(
        "Pool", (), {"start": lambda _self, worker: queued.append(worker)})()
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show", lambda *args, **kwargs: None)

    page.write_back()
    page.write_back()

    assert len(queued) == 1
    assert page.write_btn.isEnabled() is False
    queued[0].run()
    qapp.processEvents()

    log = page.log_view.toPlainText()
    assert "正在复制原游戏" in log
    assert "正在重开并验证汉化输出" in log
    assert "汉化游戏已发布" in log
    assert page.write_btn.isEnabled() is True


def test_project_switch_cannot_clear_active_write_guard(
        qapp, tmp_path, monkeypatch):
    row = {
        "file_id": "ui.assets", "key_path": "obj/1", "original": "Quit",
        "translation": "退出", "status": "translated", "locked": 0,
        "meta": json.dumps({"quality_passed": True, "confidence": "high"}),
    }

    class Store(_StoreRows):
        def close(self):
            pass

    class Project:
        def __init__(self, name):
            self.store = Store([row])
            self.out_dir = tmp_path / f"{name}_汉化"

        def write_all(self, *, font_config=None, stage_cb=None,
                allow_partial=False):
            return {"text_files": 1}

    first = Project("first")
    second = Project("second")
    state = _state(tmp_path)
    state.switch_project(first)
    state.analysis_report = _report(unblocked=True)
    page = TranslatePage(state, _Window())
    queued = []
    page._pool = type(
        "Pool", (), {"start": lambda _self, worker: queued.append(worker)})()
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show", lambda *args, **kwargs: None)

    page.write_back()
    state.switch_project(second)
    state.analysis_report = _report(unblocked=True)
    state.switch_project(first)
    state.analysis_report = _report(unblocked=True)
    page.write_back()

    assert len(queued) == 1
    assert page._write_running is True


def test_writeback_error_remains_visible_after_worker_drain(
        qapp, tmp_path, monkeypatch):
    row = {
        "file_id": "ui.assets", "key_path": "obj/1", "original": "Quit",
        "translation": "退出", "status": "translated", "locked": 0,
        "meta": json.dumps({"quality_passed": True, "confidence": "high"}),
    }
    project = type("Project", (), {
        "store": _StoreRows([row]),
        "out_dir": tmp_path / "failed_汉化",
        "write_all": lambda _self, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("disk unavailable")),
    })()
    state = _state(tmp_path)
    state.switch_project(project)
    state.analysis_report = _report(unblocked=True)
    page = TranslatePage(state, _Window())
    queued = []
    page._pool = type(
        "Pool", (), {"start": lambda _self, worker: queued.append(worker)})()
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show", lambda *args, **kwargs: None)

    page.write_back()
    queued[0].run()
    qapp.processEvents()

    assert "写回失败：disk unavailable" in page.log_view.toPlainText()
    assert page.progress_label.text() == "写回失败：disk unavailable"
    assert page.write_btn.isEnabled() is True


def test_active_write_holds_project_lease_across_switch(
        qapp, tmp_path):
    entered = threading.Event()
    release = threading.Event()

    class Store(_StoreRows):
        def __init__(self):
            super().__init__([])
            self.closed = False

        def close(self):
            self.closed = True

    class Project:
        def __init__(self):
            self.store = Store()

        def write_all(self, *, font_config=None, allow_partial=False):
            assert self.store.closed is False
            entered.set()
            assert release.wait(timeout=2)
            assert self.store.closed is False
            return {"text_files": 1}

    first = Project()
    second = Project()
    state = _state(tmp_path)
    generation = state.switch_project(first)
    page = TranslatePage(state, _Window())
    result = []
    worker = threading.Thread(
        target=lambda: result.append(page._write_worker(
            first, generation, FontConfig())))

    worker.start()
    assert entered.wait(timeout=2)
    state.switch_project(second)
    assert first.store.closed is False
    release.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert result == [{"text_files": 1}]
    assert first.store.closed is True


def test_write_task_captures_font_settings_at_queue_time(
        qapp, tmp_path, monkeypatch):
    row = {
        "file_id": "ui.assets", "key_path": "obj/1", "original": "Continue",
        "translation": "继续", "status": "translated", "locked": 0,
        "meta": json.dumps({"quality_passed": True, "confidence": "high"}),
    }
    captured = []
    store = _StoreRows([row])
    project = type("Project", (), {
        "store": store,
        "out_dir": tmp_path / "game_汉化",
        "write_all": lambda _self, *, font_config=None, stage_cb=None,
             allow_partial=False: captured.append(
            font_config) or {"text_files": 1},
    })()
    state = _state(tmp_path)
    state.settings.font = FontConfig(
        enabled=False, filename="DingTalk JinBuTi.ttf")
    state.switch_project(project)
    state.analysis_report = _report(unblocked=True)
    page = TranslatePage(state, _Window())
    queued = []
    page._pool = type(
        "Pool", (), {"start": lambda _self, worker: queued.append(worker)})()
    monkeypatch.setattr(page, "_on_written", lambda _result: None)
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show", lambda *args, **kwargs: None)

    page.write_back()
    state.settings.font.enabled = True
    state.settings.font.filename = "联想小新黑体 常规.ttf"
    queued[0].run()

    assert captured == [FontConfig(
        enabled=False, filename="DingTalk JinBuTi.ttf")]
    assert captured[0] is not state.settings.font


def test_stale_queued_translation_does_not_use_new_project_or_call_back(
        qapp, tmp_path, monkeypatch):
    class Store(_StoreRows):
        def __init__(self):
            super().__init__([])
            self.closed = False

        def close(self):
            self.closed = True

    first = type("Project", (), {
        "store": Store(), "profile": None,
    })()
    second = type("Project", (), {
        "store": Store(), "profile": None,
    })()
    state = _state(tmp_path)
    state.api.mode = "api"
    state.api.base_url = "https://example.invalid/v1/chat/completions"
    state.api.api_key = "test-key"
    state.api.model = "test-model"
    state.switch_project(first)
    page = TranslatePage(state, _Window())
    queued = []
    page._pool = type(
        "Pool", (), {"start": lambda _self, worker: queued.append(worker)})()
    callbacks = []
    monkeypatch.setattr(page, "_on_finished", lambda result: callbacks.append(result))
    monkeypatch.setattr(page, "_on_error", lambda error: callbacks.append(error))
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.create_client",
        lambda _api: pytest.fail("stale translation reached the API client"))
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show", lambda *args, **kwargs: None)

    page.start()
    state.switch_project(second)
    queued[0].run()

    assert first.store.closed is True
    assert callbacks == []


def test_project_switch_drains_old_translator_before_new_run_starts(
        qapp, tmp_path, monkeypatch):
    class Store(_StoreRows):
        def __init__(self):
            super().__init__([])

        def close(self):
            pass

    first = type("Project", (), {"store": Store(), "profile": None})()
    second = type("Project", (), {"store": Store(), "profile": None})()
    state = _state(tmp_path)
    state.api.mode = "api"
    state.api.base_url = "https://example.invalid/v1/chat/completions"
    state.api.api_key = "test-key"
    state.api.model = "test-model"
    state.switch_project(first)
    page = TranslatePage(state, _Window())
    queued = []
    toasts = []
    page._pool = type(
        "Pool", (), {"start": lambda _self, worker: queued.append(worker)})()
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show",
        lambda _parent, message, kind="info": toasts.append(message))

    page.start()
    old_run = page._active_run
    stopped = []
    old_run.attach_translator(type(
        "Translator", (), {"stop": lambda _self: stopped.append("old")})())

    state.switch_project(second)
    page.start()

    assert old_run.cancel.is_set()
    assert stopped == ["old"]
    assert len(queued) == 1
    assert any("仍在停止" in message for message in toasts)

    page._on_run_drained(old_run)
    page.start()

    assert len(queued) == 2
    assert page._active_run is not old_run


def test_active_translation_holds_project_lease_until_worker_finally(
        qapp, tmp_path, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    class Store(_StoreRows):
        def __init__(self):
            super().__init__([])
            self.closed = False

        def close(self):
            self.closed = True

    first = type("Project", (), {"store": Store(), "profile": None})()
    second = type("Project", (), {"store": Store(), "profile": None})()
    state = _state(tmp_path)
    state.api.mode = "api"
    state.api.base_url = "https://example.invalid/v1/chat/completions"
    state.api.api_key = "test-key"
    state.api.model = "test-model"
    state.switch_project(first)
    page = TranslatePage(state, _Window())
    queued = []
    page._pool = type(
        "Pool", (), {"start": lambda _self, worker: queued.append(worker)})()
    monkeypatch.setattr(
        page, "_translate_with_lease",
        lambda _run, _signals: (
            entered.set(), release.wait(timeout=2), first.store.closed)[2])

    page.start()
    result = []
    worker = threading.Thread(target=lambda: result.append(queued[0].fn()))
    worker.start()
    assert entered.wait(timeout=2)

    state.switch_project(second)
    assert first.store.closed is False
    release.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert result == [False]
    assert first.store.closed is True


def test_refresh_chips_pending_uses_actionable_count(qapp, tmp_path):
    """待翻译计数与翻译引擎同源（is_actionable_translation）：低置信度
    留档（pending/low，IL2CPP 引擎消息）不计入，只计入可翻译条目；
    留档条数进 tooltip 提示（真实案例：526 条引擎消息待翻译永不减少）。"""
    rows = [
        # 可翻译：high 置信度 pending
        {"file_id": "a", "key_path": "k1", "original": "Hello",
         "translation": "", "status": "pending", "locked": 0,
         "meta": json.dumps({"confidence": "high"})},
        # 留档：low 置信度 pending（IL2CPP 引擎消息，不可自动翻译）
        {"file_id": "b", "key_path": "k2",
         "original": "Address already in use",
         "translation": "", "status": "pending", "locked": 0,
         "meta": json.dumps({"confidence": "low",
                             "reason": "il2cpp_sentence"})},
        # 已翻译不计入；失败若置信度合格下次会重试 → 用 low 排除
        {"file_id": "a", "key_path": "k3", "original": "Bye",
         "translation": "再见", "status": "translated", "locked": 0,
         "meta": json.dumps({"confidence": "high"})},
        {"file_id": "a", "key_path": "k4", "original": "Oops",
         "translation": "", "status": "failed", "locked": 0,
         "meta": json.dumps({"confidence": "low"})},
    ]
    state = _state(tmp_path)
    state.project = type("Project", (), {
        "store": _StoreRows(rows), "out_dir": tmp_path / "game_汉化",
    })()
    state.analysis_report = _report()
    page = TranslatePage(state, _Window())
    page._last_stats = None
    page._refresh_chips()
    assert page.chip_pending.text() == "待翻译 1"
    assert page.metric_pending.value_label.text() == "1 条"
    assert "低置信度" in page.chip_pending.toolTip()
    assert "1" in page.chip_pending.toolTip()      # 留档 1 条
    # 进度条与计数同源（未运行时 done=0）：1 / 1
    assert page.progress_label.text() == "0 / 1 条"


def test_refresh_chips_pending_without_low_entries_has_no_tooltip(
        qapp, tmp_path):
    rows = [
        {"file_id": "a", "key_path": "k1", "original": "Hello",
         "translation": "", "status": "pending", "locked": 0,
         "meta": json.dumps({"confidence": "high"})},
    ]
    state = _state(tmp_path)
    state.project = type("Project", (), {
        "store": _StoreRows(rows), "out_dir": tmp_path / "game_汉化",
    })()
    state.analysis_report = _report()
    page = TranslatePage(state, _Window())
    page._last_stats = None
    page._refresh_chips()
    assert page.chip_pending.text() == "待翻译 1"
    assert page.chip_pending.toolTip() == ""


def _report(*, unblocked=True, completable=False, route=()):
    return type("Report", (), {
        "unblocked": unblocked,
        "completable": completable,
        "route": route,
        "tool_results": (),
    })()


def test_play_button_dark_until_verified_writeback_then_launches_staged_exe(
        qapp, tmp_path, monkeypatch):
    """开始游戏按钮：写回前禁用（黑），写回验证通过后亮起，
    点击启动汉化副本 exe（out_dir 下、与原游戏同相对位置）。"""
    row = {
        "file_id": "ui.assets", "key_path": "obj/1", "original": "Continue",
        "translation": "继续", "status": "translated", "locked": 0,
        "meta": json.dumps({"quality_passed": True, "confidence": "high"}),
    }
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    source_exe = game_dir / "Game.exe"
    source_exe.write_bytes(b"MZfake")
    out_dir = tmp_path / "game_汉化"
    out_dir.mkdir()
    (out_dir / "Game.exe").write_bytes(b"MZfake")

    class Store(_StoreRows):
        def close(self):
            pass

    class Project:
        def __init__(self):
            self.store = Store([row])
            self.game_dir = game_dir
            self.out_dir = out_dir

        def _fingerprint(self):
            return type("Fp", (), {"executable": source_exe})()

    state = _state(tmp_path)
    state.switch_project(Project())
    page = TranslatePage(state, _Window())
    assert page.play_btn.isEnabled() is False, "写回前按钮应禁用（黑）"

    launched = []
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.subprocess.Popen",
        lambda args, cwd=None: launched.append((list(args), cwd)))
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show", lambda *a, **k: None)

    result = {
        "text_files": 1,
        "verification": {
            "input_protected": True,
            "reopen_verified": True,
            "changed_files": 1,
            "written_translations": 1,
            "font_level": "disabled",
            "overall": "PASS",
        },
        "analysis_report": _report(unblocked=True, completable=True),
    }
    page._on_written(result)
    assert page.play_btn.isEnabled() is True, "写回成功后按钮应亮起"

    page.launch_game()
    assert launched == [([str(out_dir / "Game.exe")], str(out_dir))], \
        "必须启动汉化副本 exe，且 cwd 指向其所在目录"

    # 切换项目后恢复禁用
    class OtherStore(_StoreRows):
        def close(self):
            pass

    state.switch_project(type("Project", (), {
        "store": OtherStore([row]),
        "game_dir": game_dir,
        "out_dir": tmp_path / "other_汉化",
    })())
    assert page.play_btn.isEnabled() is False


def test_translate_write_uses_unblocked_route_and_real_write_ready_count(
        qapp, tmp_path, monkeypatch):
    row = {
        "file_id": "ui.assets", "key_path": "obj/1", "original": "Continue",
        "translation": "继续", "status": "translated", "locked": 0,
        "meta": json.dumps({"quality_passed": False, "confidence": "high"}),
    }
    state = _state(tmp_path)
    state.project = type("Project", (), {
        "store": _StoreRows([row]), "out_dir": tmp_path / "game_汉化",
    })()
    state.analysis_report = _report(route=(
        type("Step", (), {
            "required": True, "status": "pending", "reason": "等待写回",
        })(),
    ))
    page = TranslatePage(state, _Window())
    queued = []
    page._pool = type("Pool", (), {"start": lambda _self, worker: queued.append(worker)})()
    toasts = []
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show",
        lambda _parent, message, kind="info": toasts.append((message, kind)),
    )

    page._refresh_chips()
    assert not page.write_btn.isEnabled()
    page.write_back()
    assert not queued
    assert "可写译文" in toasts[-1][0]

    row["meta"] = json.dumps({"quality_passed": True, "confidence": "high"})
    page._refresh_chips()
    assert page.write_btn.isEnabled()
    page.write_back()
    assert len(queued) == 1


def test_translate_finish_exports_fail_record_automatically(
        qapp, tmp_path, monkeypatch):
    """翻译完成且存在失败 → 自动导出失败记录到 docs/fail record。"""
    state = _state(tmp_path)
    store = type("Store", (), {
        "get_entries": lambda _self, status=None: [{
            "file_id": "f1", "key_path": "k1",
            "original": "Hello world", "translation": "",
            "status": "failed", "locked": 0,
            "meta": json.dumps({"source": "game/a.txt",
                                "quality_reasons": ["request_error"]}),
        }],
        "count": lambda _self, status: 1 if status == "failed" else 0,
        "get_files": lambda _self: [],
        "get_entries_full": lambda _self: [],
    })()
    state.project = type("Project", (), {
        "store": store,
        "profile": type("Profile", (), {"game_name": "Bloody Battle"})(),
    })()
    page = TranslatePage(state, _Window())
    toasts = []
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show",
        lambda _parent, message, kind="info": toasts.append((message, kind)),
    )

    stats = TranslateStats(total=2, done=1, failed=1, requests=2)
    page._on_finished(stats)

    exported = list((state.resource_dir / "docs" / "fail record").glob(
        "Bloody Battle fail record *.txt"))
    assert len(exported) == 1
    text = exported[0].read_text(encoding="utf-8")
    assert "Hello world" in text and "request_error" in text
    assert "失败记录已导出" in toasts[-1][0]
