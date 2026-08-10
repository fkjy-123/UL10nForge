import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from hanhua.core.font_support import FontInstallResult
from hanhua.core.models import FontConfig
from hanhua.core.project import Project
from hanhua.core.settings import SettingsStore
from hanhua.ui.app_state import AppState
from hanhua.ui.design_system import TOKENS
from hanhua.ui.pages.home_page import HomePage
from hanhua.ui.pages.settings_page import SettingsPage
from hanhua.ui.pages.translate_page import TranslatePage


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Window:
    def navigate(self, _page):
        pass


def _state(tmp_path: Path) -> AppState:
    settings = SettingsStore(tmp_path / "settings.json")
    settings.load()
    return AppState(tmp_path, settings)


def test_workbench_tokens_night_flight_palette():
    """夜航工作台：薄荷青主色、柠檬黄提示、珊瑚红错误，既有 token 全部保留。"""
    assert TOKENS.primary == "#58F0C6"
    assert TOKENS.warning == "#FFD166"
    assert TOKENS.error == "#FF6F7D"
    assert TOKENS.background == "#0C1424"
    assert TOKENS.gradient_end == "#65A8FF"
    for name in (
            "background", "panel", "surface", "surface_hover", "border",
            "border_strong", "primary", "primary_hover", "primary_pressed",
            "primary_muted", "accent2", "gradient_start", "gradient_end",
            "sidebar_bg", "glass_edge", "text", "text_secondary",
            "text_disabled", "success", "warning", "error", "info",
            "radius", "radius_card", "control_height", "primary_height",
            "focus_width", "space_1", "space_2", "space_3", "space_4",
            "space_6", "space_8",
            "status_idle", "status_locked", "surface_raised", "logger_bg",
            "overlay_scrim", "shadow_key"):
        assert hasattr(TOKENS, name), f"token 缺失: {name}"


def test_app_state_owns_local_model_manager(tmp_path):
    settings = SettingsStore(tmp_path / "settings.json")
    resource_dir = tmp_path / "read-only-install"
    state = AppState(tmp_path, settings, resource_dir=resource_dir)

    assert state.local_model.app_dir == resource_dir.resolve()
    assert state.local_model.state_dir == tmp_path.resolve()


def test_font_settings_ui_removed_and_default_config_intact(
        qapp, tmp_path, monkeypatch):
    """中文字体设置已从设置页移除；默认配置仍启用思源黑体，写回时自动生效。"""
    state = _state(tmp_path)
    page = SettingsPage(state, _Window())

    assert page.tabs.count() == 3
    assert [page.tabs.tabText(i) for i in range(3)] == [
        "翻译后端", "高级设置", "术语表"]
    assert not hasattr(page, "font_enabled")
    assert not hasattr(page, "font_save_btn")

    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.font.enabled is True
    assert loaded.font.filename == "SimplifiedChinese/SourceHanSansSC-Regular.otf"


def test_advanced_local_settings_visible_only_in_local_mode_and_refresh_vram(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    page = SettingsPage(state, _Window())

    # API 模式：高级设置独立 Tab 可见但置灰
    assert page.tabs.indexOf(page.advanced_tab) == 1
    assert page.local_concurrency.isEnabled() is False
    assert not page.advanced_mode_hint.isHidden()   # API 模式显示"仅本地生效"提示
    # 初始值来自配置（默认 local_concurrency=0 自动 / 4096 / 8）
    assert page.local_concurrency.currentData() == 0
    assert page.local_ctx.currentData() == 4096
    assert page.local_batch.currentData() == 8
    # 只能点选预设档位，不能直接输入（QComboBox 不可编辑）
    assert page.local_concurrency.isEditable() is False
    assert page.local_ctx.isEditable() is False
    assert page.local_batch.isEditable() is False

    monkeypatch.setattr(
        "hanhua.ui.pages.settings_page.gpu_memory_info",
        lambda: (12.0, 10.0),
    )
    search_roots = []
    monkeypatch.setattr(
        "hanhua.ui.pages.settings_page.discover_model",
        lambda _explicit, app_dir: (
            search_roots.append(Path(app_dir).resolve())
            or tmp_path / "Hy-MT2-1.8B-Q6_K.gguf"),
    )
    monkeypatch.setattr(
        "hanhua.ui.pages.settings_page.estimate_vram",
        lambda _model, context_size=4096, slots=1: SimpleNamespace(
            model_gb=1.5, kv_gb=0.28 * slots, kv_per_slot_gb=0.28,
            compute_gb=1.0, total_gb=1.5 + 0.28 * slots + 1.0),
    )

    page.backend_mode.setCurrentIndex(page.backend_mode.findData("local"))
    assert page.local_concurrency.isEnabled() is True
    assert page.advanced_mode_hint.isHidden()       # 本地模式提示消失
    page._refresh_vram()
    # 模型必须按程序目录（resource_dir）搜索 —— 模型放在 models/ 下而非用户数据目录
    assert search_roots and search_roots[-1] == state.resource_dir.resolve()
    assert "可用 10.00G" in page.vram_label.text()
    assert "× 1" in page.vram_label.text()
    assert "40 条/分" in page.speed_label.text()   # 单槽基线

    page.local_concurrency.setCurrentIndex(page.local_concurrency.findData(4))
    assert "× 4" in page.vram_label.text()   # 槽位联动 → KV 翻 4 倍
    assert "3.62G" in page.vram_label.text()  # 1.5 + 0.28×4 + 1.0
    assert "70 条/分" in page.speed_label.text()   # 40 × (1 + 0.25×3)

    # 保存 → 持久化高级参数
    page._save_api()
    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.api.local_concurrency == 4
    assert loaded.api.local_context_size == 4096


def test_settings_can_select_and_persist_local_backend_without_api_key(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    page = SettingsPage(state, _Window())
    toasts = []
    monkeypatch.setattr(
        "hanhua.ui.pages.settings_page.Toast.show",
        lambda _parent, message, kind="info": toasts.append((message, kind)),
    )

    page.backend_mode.setCurrentIndex(page.backend_mode.findData("local"))
    assert not page.api_url.isEnabled()
    assert not page.api_key.isEnabled()
    assert page.stop_local_btn.isEnabled()

    page._save_api()

    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.api.mode == "local"
    assert loaded.api.api_key == ""
    assert toasts[-1][1] == "success"


def test_local_connection_test_does_not_require_api_credentials(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    page = SettingsPage(state, _Window())
    queued = []
    toasts = []
    page._pool = SimpleNamespace(start=lambda worker: queued.append(worker))
    monkeypatch.setattr(
        "hanhua.ui.pages.settings_page.Toast.show",
        lambda _parent, message, kind="info": toasts.append((message, kind)),
    )

    page.backend_mode.setCurrentIndex(page.backend_mode.findData("local"))
    page.test_connection()

    assert len(queued) == 1
    assert toasts == []
    assert page.test_btn.text() == "启动中…"


def test_successful_local_test_persists_validated_config_for_translation(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    state.api.mode = "api"
    state.api.provider = "anthropic"
    state.api.base_url = "http://127.0.0.1:1234/v1/messages"
    state.api.model = "stale-model"
    state.settings.save()
    page = SettingsPage(state, _Window())
    queued = []
    page._pool = SimpleNamespace(start=lambda worker: queued.append(worker))
    monkeypatch.setattr(
        "hanhua.ui.pages.settings_page.Toast.show",
        lambda _parent, _message, kind="info": None,
    )
    page.backend_mode.setCurrentIndex(page.backend_mode.findData("local"))

    page.test_connection()
    assert len(queued) == 1
    page._on_test_ok({
        "reply": "正常",
        "runtime": SimpleNamespace(backend="cpu", port=18080),
    })

    assert state.api.mode == "local"
    assert state.api.base_url == "http://127.0.0.1:1234/v1/messages"
    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.api.mode == "local"


def test_settings_stop_local_service_runs_off_ui_thread(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    page = SettingsPage(state, _Window())
    queued = []
    stopped = []
    page._pool = SimpleNamespace(start=lambda worker: queued.append(worker))
    monkeypatch.setattr(state.local_model, "stop", lambda: stopped.append(True))
    monkeypatch.setattr(
        "hanhua.ui.pages.settings_page.Toast.show",
        lambda _parent, _message, kind="info": None,
    )
    page.backend_mode.setCurrentIndex(page.backend_mode.findData("local"))

    page._stop_local()

    assert len(queued) == 1
    assert stopped == []
    assert page.stop_local_btn.isEnabled() is False
    assert "正在停止" in page.local_status.text()

    queued[0].fn()
    page._on_local_stopped(None)
    assert stopped == [True]
    assert page.stop_local_btn.isEnabled() is True


def test_translate_page_local_mode_starts_without_api_credentials(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    state.api.mode = "local"
    page = TranslatePage(state, _Window())
    state.project = SimpleNamespace()
    queued = []
    toasts = []
    page._pool = SimpleNamespace(start=lambda worker: queued.append(worker))
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show",
        lambda _parent, message, kind="info": toasts.append((message, kind)),
    )

    page.start()

    assert len(queued) == 1
    assert toasts == []
    assert page._running is True


def test_translate_stop_cancels_local_model_during_startup(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    state.api.mode = "local"
    page = TranslatePage(state, _Window())
    state.project = SimpleNamespace()
    page._pool = SimpleNamespace(start=lambda _worker: None)
    cancelled = []
    monkeypatch.setattr(
        state.local_model, "cancel_start", lambda: cancelled.append(True))
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show",
        lambda _parent, _message, kind="info": None,
    )

    page.start()
    page.stop()

    assert cancelled == [True]
    assert "正在停止" in page.log_view.toPlainText()


def test_local_translation_cleanup_uses_run_snapshot_when_settings_change(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    state.api.mode = "local"
    state.api.local_keep_alive = False
    page = TranslatePage(state, _Window())
    state.project = SimpleNamespace(profile=None, store=SimpleNamespace())
    queued = []
    page._pool = SimpleNamespace(start=lambda worker: queued.append(worker))
    stopped = []
    runtime = SimpleNamespace(
        endpoint="http://127.0.0.1:1234/v1", api_key="runtime-key",
        model="Hy-MT2", backend="gpu", port=1234,
    )

    class FakeGlossary:
        def __init__(self, _path):
            pass

        def init_schema(self):
            pass

        def list_all(self):
            return []

        def format_for_prompt(self):
            return ""

        def close(self):
            pass

    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.GlossaryStore", FakeGlossary)
    monkeypatch.setattr(
        state.local_model, "ensure_running", lambda *_args, **_kwargs: runtime)
    monkeypatch.setattr(state.local_model, "stop", lambda: stopped.append(True))
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.create_client",
        lambda _api: (_ for _ in ()).throw(RuntimeError("simulated failure")),
    )
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show",
        lambda _parent, _message, kind="info": None,
    )

    page.start()
    state.api.mode = "api"
    state.api.local_keep_alive = True
    with pytest.raises(RuntimeError, match="simulated failure"):
        queued[0].fn()

    assert stopped == [True]


def test_translation_worker_receives_immutable_run_snapshots(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    state.api.mode = "api"
    state.api.base_url = "https://example.invalid/v1/chat/completions"
    state.api.api_key = "original-key"
    state.api.model = "original-model"
    page = TranslatePage(state, _Window())
    state.project = SimpleNamespace(profile=None)
    queued = []
    captured = []
    page._pool = SimpleNamespace(start=lambda worker: queued.append(worker))
    monkeypatch.setattr(
        page,
        "_translate_worker",
        lambda run, signals: captured.append(run),
    )

    page.start()
    original_run = page._active_run
    state.api.api_key = "mutated-key"
    state.api.model = "mutated-model"

    queued[0].fn()

    assert len(captured) == 1
    assert captured[0] is original_run
    assert captured[0].project is state.project
    assert captured[0].api.api_key == "original-key"
    assert captured[0].api.model == "original-model"
    assert captured[0].cancel is original_run.cancel


def test_home_scan_does_not_freeze_font_settings_before_write(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path / "app")
    state.settings.font = FontConfig(
        enabled=False, filename="DingTalk JinBuTi.ttf"
    )
    page = HomePage(state, _Window())
    queued = []

    class _Signal:
        def connect(self, _slot):
            pass

    class _Worker:
        def __init__(self, fn, *args):
            self.fn = fn
            self.args = args
            self.signals = type(
                "Signals", (), {"finished": _Signal(), "error": _Signal()}
            )()

    class _Pool:
        @staticmethod
        def globalInstance():
            return _Pool()

        def start(self, worker):
            queued.append(worker)

    monkeypatch.setattr("hanhua.ui.pages.home_page.Worker", _Worker)
    monkeypatch.setattr("hanhua.ui.pages.home_page.QThreadPool", _Pool)
    report = SimpleNamespace(text_files=4, v2_files=7)
    monkeypatch.setattr(Project, "scan_all", lambda _self: report)

    game_dir = tmp_path / "game"
    game_dir.mkdir()
    page.open_dir(game_dir)

    assert len(queued) == 1
    assert queued[0].args == (str(game_dir), str(state.app_dir))

    state.settings.font.enabled = True
    state.settings.font.filename = "联想小新黑体 常规.ttf"

    project, scan_report = queued[0].fn(*queued[0].args)
    assert project.font_config == FontConfig(enabled=False)
    assert project.font_config is not state.settings.font
    assert scan_report is report


def test_write_result_reports_installed_font_only(qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    page = TranslatePage(state, _Window())
    state.project = type("Project", (), {"out_dir": tmp_path / "game_汉化"})()
    state.analysis_report = SimpleNamespace(
        unblocked=True, completable=False, route=())
    toasts = []
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show",
        lambda _parent, message, kind="info": toasts.append((message, kind)),
    )

    page._on_written(
        {
            "text_files": 2,
            "font": FontInstallResult(
                True, "联想小新黑体 常规.ttf", "Lenovo-XiaoxinHeiGB"
            ),
            "verification": {
                "input_protected": True,
                "reopen_verified": True,
                "changed_files": 5,
                "written_translations": 12,
                "font_level": "runtime_fallback",
                "warnings": [],
                "overall": "PASS",
                "gates": {
                    "file": {"status": "PASS", "detail": ""},
                    "container": {"status": "PASS", "detail": ""},
                    "object": {"status": "PASS", "detail": ""},
                    "runtime": {"status": "PASS", "detail": ""},
                },
            },
            "analysis_report": SimpleNamespace(completable=True, route=()),
        }
    )
    log = page.log_view.toPlainText()
    assert "中文字体 Lenovo-XiaoxinHeiGB" in log
    assert "变更文件 5" in log
    assert "实际写入译文 12" in log
    assert "原游戏输入哈希 已保护" in log
    assert "输出重开验证 已通过" in log
    assert "四态闸门" in log

    page.log_view.clear()
    page._on_written({
        "text_files": 2,
        "font": FontInstallResult(False),
        "verification": {
            "input_protected": False,
            "reopen_verified": False,
            "changed_files": 0,
            "written_translations": 0,
            "font_level": "unavailable",
            "warnings": ["字体注入未验证"],
        },
        "analysis_report": SimpleNamespace(completable=True, route=()),
    })
    assert "写回未通过验证" in page.log_view.toPlainText()
    assert "字体注入未验证" in page.log_view.toPlainText()
    assert toasts[0] == (
        "写回已验证 · 5 个变更文件 · 12 条译文 · 四态闸门 PASS"
        " · 中文字体 Lenovo-XiaoxinHeiGB",
        "success",
    )
    assert toasts[1][1] == "error"
    assert "写回未通过验证" in toasts[1][0]


def test_write_result_never_reports_success_when_required_route_is_blocked(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    page = TranslatePage(state, _Window())
    state.project = type("Project", (), {"out_dir": tmp_path / "game_汉化"})()
    state.analysis_report = SimpleNamespace(unblocked=True, completable=False, route=(
        SimpleNamespace(required=True, status="blocked", reason="字体注入不可验证"),
    ))
    toasts = []
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show",
        lambda _parent, message, kind="info": toasts.append((message, kind)),
    )

    page._on_written({
        "text_files": 1,
        "font": FontInstallResult(True, "font.ttf", "Test Font"),
        "verification": {
            "input_protected": True,
            "reopen_verified": True,
            "changed_files": 1,
            "written_translations": 1,
            "font_level": "runtime_fallback",
            "warnings": [],
        },
        "analysis_report": SimpleNamespace(completable=False, route=(
            SimpleNamespace(
                required=True, status="blocked", reason="字体注入不可验证"),
        )),
    })

    assert toasts == [("写回未通过验证 · 必需能力仍被阻断", "error")]
    assert page.reveal_btn.isHidden()


def test_write_result_never_reports_success_when_final_route_is_pending(
        qapp, tmp_path, monkeypatch):
    state = _state(tmp_path)
    page = TranslatePage(state, _Window())
    state.project = type("Project", (), {"out_dir": tmp_path / "game_汉化"})()
    state.analysis_report = SimpleNamespace(
        unblocked=True, completable=True, route=())
    toasts = []
    monkeypatch.setattr(
        "hanhua.ui.pages.translate_page.Toast.show",
        lambda _parent, message, kind="info": toasts.append((message, kind)),
    )

    page._on_written({
        "text_files": 1,
        "font": FontInstallResult(True, "font.ttf", "Test Font"),
        "verification": {
            "input_protected": True,
            "reopen_verified": True,
            "changed_files": 1,
            "written_translations": 1,
            "font_level": "runtime_fallback",
            "warnings": [],
        },
        "analysis_report": SimpleNamespace(completable=False, route=(
            SimpleNamespace(required=True, status="pending", reason="等待验证"),
        )),
    })

    assert toasts == [("写回未通过验证 · 必需步骤尚未完成", "error")]
    assert page.reveal_btn.isHidden()
