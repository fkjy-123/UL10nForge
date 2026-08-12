"""主窗口 v2：Top Bar + 分组可折叠 Sidebar + 页面栈 + 状态栏（任务二）。

布局（§11/§12/§13/§14）：
┌───────────────────────────────────────┐
│ TopBar（当前项目 · Ctrl+K 搜索 · 通知 · 设置）│
├───────────┬───────────────────────────┤
│ Sidebar   │   页面栈（淡入切换）         │
│ 分组导航    │                           │
├───────────┴───────────────────────────┤
│ StatusBar（本地模型/项目）              │
└───────────────────────────────────────┘
Ctrl+K 命令面板浮层覆盖在中央（§51）。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QStackedWidget, QStatusBar,
                               QVBoxLayout, QWidget)

from hanhua.core.project import Project
from hanhua.ui.app_state import AppState
from hanhua.ui.design_system import TOKENS
from hanhua.ui.icons import LineIcon
from hanhua.ui.widgets import CommandPalette, TopBar

PAGES = ["home", "review", "translate", "settings"]
# 分组导航（§12：kind="group" 为不可选中标题行，其余为页面项）
NAV_ENTRIES = (
    ("文本中心", "group", ""),
    ("首页", "home", "home"),
    ("文本审校", "review", "database"),
    ("翻译", "translate", "translate"),
    ("系统", "group", ""),
    ("设置", "settings", "gear"),
)
# nav row → PAGES 索引（跳过 group 行；元组为 (标题, kind, 图标)）
_NAV_PAGE_ROWS: dict[int, int] = {}
_page_index = 0
for _row, (_title, _kind, _icon) in enumerate(NAV_ENTRIES):
    if _kind == "group":
        continue
    _NAV_PAGE_ROWS[_row] = _page_index
    _page_index += 1


class MainWindow(QMainWindow):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setWindowTitle("汉化助手 — Unity 游戏智能汉化工具")
        self.resize(1280, 800)
        self.setMinimumSize(1000, 660)

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root_lay = QVBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── Top Bar（§14） ──
        self.top_bar = TopBar(state)
        root_lay.addWidget(self.top_bar)

        # ── 中部：Sidebar + 页面栈 ──
        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)
        root_lay.addWidget(body, 1)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        side_lay = QVBoxLayout(sidebar)
        side_lay.setContentsMargins(0, 18, 0, 14)
        side_lay.setSpacing(0)
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(20, 0, 20, 0)
        brand_row.setSpacing(10)
        brand_icon = LineIcon("brand", 24, TOKENS.primary)
        brand_icon.setAccessibleName("汉化助手")
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        title = QLabel("汉化助手")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignLeft)
        sub = QLabel("Unity 游戏智能汉化工具")
        sub.setObjectName("appSub")
        sub.setAlignment(Qt.AlignLeft)
        brand_text.addWidget(title)
        brand_text.addWidget(sub)
        brand_row.addWidget(brand_icon)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        side_lay.addLayout(brand_row)
        brand_bar = QFrame()
        brand_bar.setObjectName("brandBar")
        brand_bar.setFixedHeight(3)
        side_lay.addWidget(brand_bar)
        side_lay.addSpacing(12)

        # 分组导航（§12/§13：图标+文字；group 行为不可选标题）
        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        for title, kind, icon_name in NAV_ENTRIES:
            item = QListWidgetItem(title)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            if kind == "group":
                item.setFlags(Qt.NoItemFlags)
                item.setData(Qt.UserRole, None)
            else:
                item.setIcon(QIcon(LineIcon.pixmap(icon_name, 18)))
                item.setData(Qt.UserRole, kind)
            self.nav.addItem(item)
        self.nav.setIconSize(self.nav.iconSize().expandedTo(
            self.nav.iconSize()))
        self.nav.setSpacing(2)
        self.nav.setCurrentRow(0)
        self._refresh_nav_icons(0)
        side_lay.addWidget(self.nav, 1)
        # 导航指示条：叠在列表视口上，切换时 180ms 滑到目标项
        self.nav_indicator = QFrame(self.nav.viewport())
        self.nav_indicator.setObjectName("navIndicator")
        self.nav_indicator.setFixedWidth(3)
        self.nav_indicator.hide()

        # 底部项目卡片：无项目时显示占位引导，不隐藏
        self.project_card = QFrame()
        self.project_card.setObjectName("card")
        self.project_card.setFixedHeight(64)
        pc_lay = QVBoxLayout(self.project_card)
        pc_lay.setContentsMargins(14, 10, 14, 10)
        pc_lay.setSpacing(2)
        self.pc_name = QLabel("尚未载入游戏")
        self.pc_name.setObjectName("projectCardName")
        self.pc_path = QLabel("在首页拖入游戏文件夹开始")
        self.pc_path.setObjectName("projectCardPath")
        pc_lay.addWidget(self.pc_name)
        pc_lay.addWidget(self.pc_path)
        side_lay.addWidget(self.project_card)
        side_lay.addSpacing(14)

        body_lay.addWidget(sidebar)

        # ── 页面栈 ──
        self.stack = QStackedWidget()
        body_lay.addWidget(self.stack, 1)

        from hanhua.ui.pages.home_page import HomePage
        from hanhua.ui.pages.review_page import ReviewPage
        from hanhua.ui.pages.settings_page import SettingsPage
        from hanhua.ui.pages.translate_page import TranslatePage
        self.pages = {
            "home": HomePage(state, self),
            "review": ReviewPage(state, self),
            "translate": TranslatePage(state, self),
            "settings": SettingsPage(state, self),
        }
        for name in PAGES:
            self.stack.addWidget(self.pages[name])

        self.nav.currentRowChanged.connect(self._on_nav_changed)
        self.setStatusBar(QStatusBar())
        self._refresh_statusbar()
        state.settingsChanged.connect(self._refresh_statusbar)
        state.projectOpened.connect(self._on_project_opened)

        # ── Ctrl+K 命令面板（§51） ──
        self.palette: CommandPalette | None = None
        shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        shortcut.activated.connect(self._toggle_palette)
        # TopBar 搜索入口点击打开命令面板
        self.top_bar.search_label.mousePressEvent = lambda _e: (
            self._toggle_palette())  # noqa: SLF001（测试环境无 signal 依赖）
        self.top_bar.settings_btn.clicked.connect(
            lambda: self.navigate("settings"))
        self.top_bar.notify_btn.clicked.connect(self._show_notifications)

    # ── 导航 ───────────────────────────────────────────────
    def _page_row(self) -> int:
        """当前选中 page 对应的 nav row。"""
        for row, index in _NAV_PAGE_ROWS.items():
            if index == self.stack.currentIndex():
                return row
        return 0

    def _on_nav_changed(self, row: int):
        if row in _NAV_PAGE_ROWS:
            index = _NAV_PAGE_ROWS[row]
            self.stack.setCurrentIndex(index)
            self._refresh_nav_icons(index)
            self._animate_nav_indicator(index)
            self._fade_in_page(index)
            self._refresh_statusbar()
        else:
            # 误选中 group 标题行：回退到当前页面
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(self._page_row())
            self.nav.blockSignals(False)

    def _refresh_nav_icons(self, selected_index: int):
        """选中项图标用品牌青色，其余用中性色（group 行无图标）。"""
        for row, index in _NAV_PAGE_ROWS.items():
            item = self.nav.item(row)
            icon_name = item.data(Qt.UserRole) or "home"
            color = TOKENS.primary if index == selected_index else TOKENS.text_disabled
            item.setIcon(QIcon(LineIcon.pixmap(icon_name, 18, color)))

    def _position_nav_indicator(self, animate: bool):
        """指示条定位到当前项；animate=True 时 180ms 滑动。"""
        row = self._page_row()
        item = self.nav.item(row) if 0 <= row < self.nav.count() else None
        if item is None:
            return
        rect = self.nav.visualItemRect(item)
        if rect.isNull() or rect.width() <= 0:
            return
        target = QRect(rect.left(), rect.top(), 3, rect.height())
        old = getattr(self, "_nav_anim", None)
        if old is not None:
            old.stop()
        if not animate or not self.nav_indicator.isVisible():
            self.nav_indicator.setGeometry(target)
            self.nav_indicator.show()
            return
        anim = QPropertyAnimation(self.nav_indicator, b"geometry", self)
        anim.setDuration(180)
        anim.setStartValue(self.nav_indicator.geometry())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._nav_anim = anim
        anim.start()

    def _animate_nav_indicator(self, index: int):
        self._position_nav_indicator(True)

    def _fade_in_page(self, index: int):
        """页面切换：200ms 淡入（§59 Page 动效；QSS 无法做动画）。"""
        page = self.stack.widget(index)
        if page is None:
            return
        old = getattr(self, "_page_fade_anim", None)
        if old is not None:
            old.stop()
            old.deleteLater()
        if page.graphicsEffect() is not None:
            page.setGraphicsEffect(None)
        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(lambda p=page: p.setGraphicsEffect(None))
        self._page_fade_anim = anim
        anim.start()

    def navigate(self, name: str):
        if name in PAGES:
            index = PAGES.index(name)
            self.nav.blockSignals(True)
            # _NAV_PAGE_ROWS 键是 nav 行号（group 行无键）——按值反查
            self.nav.setCurrentRow(next((row for row, i in _NAV_PAGE_ROWS.items()
                                         if i == index), index))
            self.nav.blockSignals(False)
            self.stack.setCurrentIndex(index)
            self._refresh_nav_icons(index)
            self._animate_nav_indicator(index)
            self._fade_in_page(index)

    def showEvent(self, event):
        super().showEvent(event)
        self._position_nav_indicator(False)

    def current_page(self) -> str:
        return PAGES[self.stack.currentIndex()]

    # ── Ctrl+K 命令面板（§51） ─────────────────────────────
    def _toggle_palette(self):
        if self.palette is not None and self.palette.isVisible():
            self.palette.setVisible(False)
            return
        self._open_palette()

    def _open_palette(self):
        if self.palette is None:
            commands = [
                ("打开首页", "回到工作台", lambda: self.navigate("home")),
                ("打开文本审校", "查看全部文本", lambda: self.navigate("review")),
                ("打开 AI 翻译", "开始/查看翻译进度", lambda: self.navigate("translate")),
                ("打开设置", "模型/审核/项目配置", lambda: self.navigate("settings")),
            ]
            self.palette = CommandPalette(self.centralWidget(), commands)
        self.palette.open()

    # ── 通知（§53：Toast 汇总） ────────────────────────────
    def _show_notifications(self):
        from hanhua.ui.widgets import Toast
        page = self.pages.get(self.current_page())
        if page is not None and self.state.project is not None:
            Toast.show(page, "项目已载入 · 本地模型可用时即可开始翻译", "info")
        else:
            Toast.show(page or self, "暂无通知 · 打开项目后开始本地化流程", "info")

    # ── 项目卡 / 状态栏（护栏测试断言：本地：Hy-MT2 · 未启动） ──
    def _on_project_opened(self, project):
        """项目打开：更新侧边栏卡片并同步状态栏项目名。"""
        self.updateProjectCard(project)
        self._refresh_statusbar()

    def updateProjectCard(self, project: Project):
        """项目卡两行紧凑摘要：项目名 + 缩略路径。"""
        self.pc_name.setText(project.game_dir.name)
        parts = project.game_dir.parts
        if len(parts) > 3:
            self.pc_path.setText(
                f"…{project.game_dir.parent.name}/{project.game_dir.name}")
        else:
            self.pc_path.setText(str(project.game_dir))
        self.project_card.setHidden(False)

    def _refresh_statusbar(self):
        """状态栏只保留运行后端与项目名（1px 顶部分隔见 QSS）。"""
        api = self.state.api
        if api.mode == "local":
            runtime = self.state.local_model.runtime
            if runtime:
                text = (f"本地：{runtime.model} · {runtime.backend.upper()} "
                        f"· 端口 {runtime.port}")
            else:
                model = (Path(api.local_model_path).stem
                         if api.local_model_path else "")
                text = f"本地：{model} · 未启动" if model else "本地：未启动"
        elif api.base_url and api.api_key and api.model:
            tag = "OpenAI 兼容" if api.provider == "openai" else "Anthropic"
            text = f"API：{tag} · {api.model}"
        else:
            text = "API：未配置（请到设置中填写）"
        if self.state.project is not None:
            text += f"　|　项目：{self.state.project.game_dir.name}"
        self.statusBar().showMessage(text)
