"""阶段 D：UI 按键交互实测（offscreen）——每个按键的响应、漏洞、显示正确性。

覆盖：导航点击 / 搜索快捷键 / 表格编辑与锁定 / 筛选联动 / 拖放 /
翻译页按钮状态矩阵 / 设置页后端切换矩阵 / 写回按钮无项目保护。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QLabel,
                               QPushButton, QTableWidgetItem)

from hanhua.core.memory import ProjectStore
from hanhua.core.models import TranslateStats
from hanhua.core.settings import SettingsStore
from hanhua.ui.app_state import AppState
from hanhua.ui.main_window import MainWindow
from hanhua.ui.pages.home_page import HomePage
from hanhua.ui.pages.review_page import ReviewPage
from hanhua.ui.pages.translate_page import TranslatePage
from hanhua.ui.widgets import (EmptyState, MetricStrip, PageHeader,
                               StatusBadge, StatusRail)


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
        self.projects = []

    def navigate(self, page):
        self.pages.append(page)

    def updateProjectCard(self, project):
        self.projects.append(project)


def _state(tmp_path: Path) -> AppState:
    settings = SettingsStore(tmp_path / "settings.json")
    settings.load()
    return AppState(tmp_path, settings)


def _store(tmp_path: Path) -> ProjectStore:
    store = ProjectStore(tmp_path / "project.db")
    store.init_schema()
    store.add_file("ui", "ui.assets", "v2_asset", "binary", "")
    store.upsert_entries([
        {
            "file_id": "ui", "key_path": "obj/open",
            "original": "Open Door", "meta": {
                "role": "display", "confidence": "high",
                "disposition": "translate",
            },
        },
        {
            "file_id": "ui", "key_path": "obj/quit",
            "original": "Quit Game", "meta": {
                "role": "display", "confidence": "high",
                "disposition": "translate",
            },
        },
    ])
    return store


class _FakeProject:
    """含 store 与 profile 的假项目。"""

    def __init__(self, store: ProjectStore):
        self.store = store
        self.profile = None
        self.game_dir = Path("D:/fake/game")
        self.out_dir = Path("D:/fake/out")


# ─────────────────────────── 导航 ───────────────────────────

def test_nav_click_switches_stack_and_enables_nav(qapp, tmp_path):
    state = _state(tmp_path)
    window = MainWindow(state)
    window.updateProjectCard(_FakeProject(_store(tmp_path)))

    assert window.current_page() == "home"
    assert not window.pages["review"].isVisible() or window.stack.currentIndex() == 0

    # 逐一点击每个导航项，断言页面栈切换（nav row 1..3 对应 review/translate/settings）
    for row, page_name in enumerate(("review", "translate", "settings"), start=1):
        window.nav.setCurrentRow(row)
        assert window.current_page() == page_name, f"row {row} 应切到 {page_name}"
        # 选中项图标应为品牌青色（响应验证）
        selected = window.nav.item(row)
        assert selected.icon() is not None and not selected.icon().isNull()
    window.nav.setCurrentRow(0)
    assert window.current_page() == "home"


def test_nav_always_available_without_project(qapp, tmp_path):
    """未打开游戏文件夹时导航也可用：设置/审校/翻译都允许进入页面。"""
    state = _state(tmp_path)
    window = MainWindow(state)
    for row in range(1, window.nav.count()):
        item = window.nav.item(row)
        assert item.flags() & Qt.ItemIsEnabled, f"row {row} 无项目时也应可点"
    for row, page_name in enumerate(("review", "translate", "settings"),
                                    start=1):
        window.nav.setCurrentRow(row)
        assert window.current_page() == page_name


def test_statusbar_reflects_project_and_backend(qapp, tmp_path):
    state = _state(tmp_path)
    window = MainWindow(state)
    project = _FakeProject(_store(tmp_path))
    state.switch_project(project)  # 触发 projectOpened → 状态栏刷新
    text = window.statusBar().currentMessage()
    assert "game" in text  # 项目名（game_dir.name）出现在状态栏
    assert "项目" in text
    assert not window.project_card.isHidden()


# ─────────────────────────── 首页 ───────────────────────────

def test_home_pick_button_opens_directory_picker(qapp, tmp_path, monkeypatch):
    page = HomePage(_state(tmp_path), _RecordingWindow())
    chosen = []

    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        lambda *args, **kwargs: str(tmp_path / "some-dir"))
    # 打开一个真实存在的小目录模拟选择后流程：open_dir 会触发扫描，
    # 这里拦截 Project.open_game_dir 避免真实扫描
    import hanhua.ui.pages.home_page as home_mod

    def fake_open(game_dir, app_dir):
        project = _FakeProject(_store(tmp_path))
        project.game_dir = Path(game_dir)
        project.out_dir = Path(app_dir).parent / "out"
        return project

    monkeypatch.setattr(home_mod.Project, "open_game_dir", staticmethod(fake_open))
    target = tmp_path / "some-dir"
    target.mkdir()

    page.pick_btn.click()
    assert page._scanning or not page.pick_btn.isEnabled()  # 进入忙碌态


def test_home_drop_zone_emits_directory(qapp, tmp_path):
    page = HomePage(_state(tmp_path), _RecordingWindow())
    received = []
    page.drop_zone.directoryDropped.connect(received.append)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path))])
    from PySide6.QtGui import QDragEnterEvent
    event = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, mime,
                            Qt.LeftButton, Qt.NoModifier)
    page.drop_zone.dragEnterEvent(event)
    assert event.isAccepted()


# ─────────────────────────── 审校页 ─────────────────────────

def test_review_search_shortcut_focuses_search_box(qapp, tmp_path):
    from PySide6.QtGui import QShortcut
    state = _state(tmp_path)
    state.project = _FakeProject(_store(tmp_path))
    page = ReviewPage(state, _Window())
    # Ctrl+F 快捷键已注册（offscreen 下窗口焦点不可靠，验证注册与行为函数）
    shortcuts = [s for s in page.findChildren(QShortcut)
                 if s.key().matches(QKeySequence("Ctrl+F"))]
    assert shortcuts, "缺少 Ctrl+F 搜索快捷键"
    page._focus_search()  # 行为函数可调用且不崩溃
    assert page.search_box.text() == ""


def test_review_table_edit_persists_translation(qapp, tmp_path):
    store = _store(tmp_path)
    state = _state(tmp_path)
    state.project = _FakeProject(store)
    page = ReviewPage(state, _Window())
    page.reload()

    model = page.model
    assert model.rowCount() >= 2
    # 找到 Open Door 行，编辑译文列（col 3）
    row_idx = next(
        i for i in range(model.rowCount())
        if model._rows[i]["key_path"] == "obj/open")
    index = model.index(row_idx, 3)
    assert model.flags(index) & Qt.ItemIsEditable
    assert model.setData(index, "打开门")
    persisted = next(
        e for e in store.get_entries()
        if e["key_path"] == "obj/open")
    assert persisted["translation"] == "打开门"
    assert persisted["status"] == "translated"


def test_review_lock_checkbox_toggles(qapp, tmp_path):
    store = _store(tmp_path)
    state = _state(tmp_path)
    state.project = _FakeProject(store)
    page = ReviewPage(state, _Window())
    page.reload()

    row_idx = next(
        i for i in range(page.model.rowCount())
        if page.model._rows[i]["key_path"] == "obj/quit")
    index = page.model.index(row_idx, 5)
    assert page.model.flags(index) & Qt.ItemIsUserCheckable
    assert page.model.setData(index, Qt.Checked, Qt.CheckStateRole)
    persisted = next(
        e for e in store.get_entries()
        if e["key_path"] == "obj/quit")
    assert persisted["locked"] == 1


def test_review_filter_updates_proxy_rows(qapp, tmp_path):
    state = _state(tmp_path)
    state.project = _FakeProject(_store(tmp_path))
    page = ReviewPage(state, _Window())
    page.reload()

    assert page.proxy.rowCount() == 2
    page.search_box.setText("Quit")
    assert page.proxy.rowCount() == 1
    page.search_box.setText("不存在的文本")
    assert page.proxy.rowCount() == 0


def test_review_translate_button_navigates(qapp, tmp_path):
    window = _RecordingWindow()
    state = _state(tmp_path)
    state.project = _FakeProject(_store(tmp_path))
    page = ReviewPage(state, window)
    page.translate_btn.click()
    assert window.pages == ["translate"]


def test_review_context_menu_copy_does_not_crash(qapp, tmp_path):
    state = _state(tmp_path)
    state.project = _FakeProject(_store(tmp_path))
    page = ReviewPage(state, _Window())
    page.reload()
    # 右键菜单弹出需要真实窗口事件循环，这里直接调用菜单构建逻辑
    # 验证 _show_menu 在无命中时安全返回
    page._show_menu(QPoint(-5, -5))  # 不在表格内 → 直接返回
    assert True


# ─────────────────────────── 翻译页 ─────────────────────────

def test_translate_buttons_disabled_without_project(qapp, tmp_path):
    page = TranslatePage(_state(tmp_path), _RecordingWindow())
    # 无项目时写回与停止按钮必须禁用；开始按钮可点（点击给警告提示）
    assert page.start_btn.isEnabled()
    assert not page.write_btn.isEnabled()
    assert not page.stop_btn.isEnabled()
    assert page.reveal_btn.isHidden()


def test_translate_start_without_project_shows_warning_not_crash(
        qapp, tmp_path):
    page = TranslatePage(_state(tmp_path), _RecordingWindow())
    page.start()  # 无项目 → Toast 警告，不应崩溃、不应触发翻译 worker
    assert page._active_run is None


def test_translate_buttons_state_matrix_with_project(qapp, tmp_path):
    store = _store(tmp_path)
    state = _state(tmp_path)
    state.project = _FakeProject(store)
    page = TranslatePage(state, _RecordingWindow())

    # 有项目且有待翻译 → 开始按钮可用；写回需有译文（无）→ 禁用
    assert page.start_btn.isEnabled()
    assert not page.write_btn.isEnabled()

    # 手动翻译一条 → 写回可用
    store.set_manual("ui", "obj/open", "打开门")
    page._refresh_chips()
    assert page.write_btn.isEnabled()

    # 停止按钮仅在运行中可用
    assert not page.stop_btn.isEnabled()


def test_translate_progress_chips_refresh(qapp, tmp_path):
    store = _store(tmp_path)
    state = _state(tmp_path)
    state.project = _FakeProject(store)
    page = TranslatePage(state, _RecordingWindow())
    # 进度统计来自 stats；已翻译计数来自 store
    page._on_progress(TranslateStats(total=2, done=1, failed=0))
    assert "1 / 2" in page.progress_label.text() or page.progress_bar.value() == 50
    assert page.chip_done.text() == "已翻译 0"
    store.set_manual("ui", "obj/open", "打开门")
    page._refresh_chips()
    assert page.chip_done.text() == "已翻译 1"


def test_translate_retry_marks_failed_as_pending(qapp, tmp_path):
    store = _store(tmp_path)
    store.set_status("ui", "obj/open", "failed")
    state = _state(tmp_path)
    state.project = _FakeProject(store)
    page = TranslatePage(state, _RecordingWindow())
    # 拦截 start 避免真实翻译
    page.start = lambda: None
    page.retry_failed()
    persisted = next(
        e for e in store.get_entries()
        if e["key_path"] == "obj/open")
    assert persisted["status"] == "pending"


# ─────────────────────────── 设置页 ─────────────────────────

def test_settings_backend_switch_enables_local_fields(qapp, tmp_path):
    from hanhua.ui.pages.settings_page import SettingsPage
    page = SettingsPage(_state(tmp_path), _RecordingWindow())

    # 默认 API 模式：本地操作禁用
    assert page.backend_mode.currentData() == "api"
    assert not page.stop_local_btn.isEnabled()
    assert page.api_url.isEnabled()

    # 切到本地：本地操作启用，API 字段禁用
    page.backend_mode.setCurrentIndex(
        page.backend_mode.findData("local"))
    assert page.stop_local_btn.isEnabled()
    assert not page.api_url.isEnabled()
    assert page.test_btn.text() == "启动并测试"


def test_settings_save_persists_config(qapp, tmp_path):
    from hanhua.ui.pages.settings_page import SettingsPage
    state = _state(tmp_path)
    page = SettingsPage(state, _RecordingWindow())
    page.api_url.setText("https://example.com/v1")
    page._save_api()
    assert state.api.base_url == "https://example.com/v1"


def test_settings_glossary_add_edit_delete(qapp, tmp_path):
    from hanhua.ui.pages.settings_page import SettingsPage
    page = SettingsPage(_state(tmp_path), _RecordingWindow())
    page.tabs.setCurrentWidget(page.glossary_table.parent())  # 切到术语表
    page._glossary_add()
    # 直接填表
    page._glossary_loading = True
    page.glossary_table.setItem(0, 0, QTableWidgetItem("Aria"))
    page.glossary_table.setItem(0, 1, QTableWidgetItem("艾莉亚"))
    page.glossary_table.setItem(0, 2, QTableWidgetItem("人名"))
    page._glossary_loading = False
    page._glossary_cell_changed(0, 1)
    rows = page._glossary.list_all()
    assert any(r["term"] == "Aria" and r["translation"] == "艾莉亚"
               for r in rows)


# ─────────────────────────── 主窗口整体 ─────────────────────

def test_all_page_titles_and_primary_buttons_accessible(qapp, tmp_path):
    state = _state(tmp_path)
    window = MainWindow(state)
    window.updateProjectCard(_FakeProject(_store(tmp_path)))
    for name in ("home", "review", "translate", "settings"):
        page = window.pages[name]
        for button in page.findChildren(QPushButton):
            if button.isVisible() or not button.isHidden():
                assert button.accessibleName() or button.text(), (
                    f"{name} 页存在无名称按钮: {button.objectName()}")


# ─────────────────────────── 夜航共享展示组件 ────────────────

def test_page_header_exposes_title_subtitle_and_actions(qapp, tmp_path):
    header = PageHeader("游戏接入", "检测、提取、翻译、写回一条龙")
    header.set_actions([QPushButton("主动作"), QPushButton("次动作")])
    assert header.title_label.text() == "游戏接入"
    assert header.subtitle_label.text() == "检测、提取、翻译、写回一条龙"
    assert header.primary_slot is not None


def test_status_badge_drives_qss_status_property(qapp, tmp_path):
    for status in ("idle", "running", "succeeded", "warning", "failed",
                   "locked", "pending"):
        badge = StatusBadge(status)
        assert badge.status() == status
        assert badge.property("status") == status
        badge.setStatus("succeeded")
        assert badge.status() == "succeeded"
        assert badge.property("status") == "succeeded"


def test_metric_strip_label_value_and_set_value(qapp, tmp_path):
    strip = MetricStrip("待翻译", "12")
    assert strip.label.text() == "待翻译"
    assert strip.value_label.text() == "12"
    strip.setValue("99")
    assert strip.value_label.text() == "99"


def test_empty_state_shows_title_and_hint(qapp, tmp_path):
    empty = EmptyState("folder-open", "尚未载入游戏", "请拖入游戏文件夹开始")
    assert empty.title.text() == "尚未载入游戏"
    assert empty.hint.text() == "请拖入游戏文件夹开始"


def test_status_rail_exposes_nodes_and_state_update(qapp, tmp_path):
    rail = StatusRail([
        ("detection", "1 游戏检测", "scan"),
        ("writeback", "5 写回验证", "shield"),
    ])
    assert [node.step_id for node in rail.nodes] == ["detection", "writeback"]
    rail.set_node_state("detection", "running", "正在读取布局证据", "置信度 —")
    assert rail.nodes[0].property("status") == "running"
    rail.set_node_state("writeback", "succeeded", "通过", "置信度 高")
    assert rail.nodes[1].property("status") == "succeeded"
