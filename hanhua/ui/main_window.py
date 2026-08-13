"""主窗口 v3（Aurora Forge，2026-08-13）：Top Bar + 四项导航 + 页面栈。

布局（spec §5）：
┌────────────────────────────────────────┐
│ TopBar（项目 · 语言 · 切换项目 · Ctrl+K · 通知 · 设置）│
├─────────┬──────────────────────────────┤
│ Sidebar  │  页面栈（180ms 淡入 + 12px 上移）│
│ 四项导航  │                              │
└─────────┴──────────────────────────────┘
Ctrl+K 命令面板浮层覆盖在中央（§51）。导航指示器 200ms 平滑滑动。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect,
                            Qt, QVariantAnimation)
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QStackedWidget, QStatusBar,
                               QVBoxLayout, QWidget)

from hanhua.core.project import Project
from hanhua.ui.app_state import AppState
from hanhua.ui.design_system import TOKENS, motion_enabled
from hanhua.ui.icons import LineIcon
from hanhua.ui.widgets import TopBar

PAGES = ["home", "review", "translate", "translate_tool", "settings"]
# 五项任务导航（spec §3：概览/审校/运行/翻译/设置，图标 + 短标签）
NAV_ITEMS = (
    ("概览", "home", "home"),
    ("审校", "review", "pen"),
    ("运行", "translate", "rocket"),
    ("翻译", "translate_tool", "translate"),
    ("设置", "settings", "gear"),
)
# nav row → PAGES 索引（五项一一对应，无分组标题行）
_NAV_PAGE_ROWS: dict[int, int] = {row: index for index, row in enumerate(range(5))}
# 页面进入动效的上移距离（px，spec §7：12px 上移 + 180ms 淡入）
_PAGE_RISE_PX = 12


class MainWindow(QMainWindow):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setWindowTitle("UL10nForge — Unity 游戏智能汉化工具")
        self.resize(1280, 800)
        self.setMinimumSize(1000, 660)

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root_lay = QVBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── Top Bar（§5：项目上下文 + 命令入口 + 通知 + 设置） ──
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
        sidebar.setFixedWidth(176)
        side_lay = QVBoxLayout(sidebar)
        side_lay.setContentsMargins(0, 18, 0, 14)
        side_lay.setSpacing(0)
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(20, 0, 20, 0)
        brand_row.setSpacing(10)
        brand_icon = LineIcon("brand", 24, TOKENS.accent)
        brand_icon.setAccessibleName("UL10nForge")
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        title = QLabel("UL10nForge")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignLeft)
        sub = QLabel("unity")
        sub.setObjectName("appSub")
        sub.setAlignment(Qt.AlignLeft)
        brand_text.addWidget(title)
        brand_text.addWidget(sub)
        brand_row.addWidget(brand_icon)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        side_lay.addLayout(brand_row)
        side_lay.addSpacing(16)

        # 四项导航（图标 + 短标签；选中指示器 200ms 滑动）
        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        for title, kind, icon_name in NAV_ITEMS:
            item = QListWidgetItem(title)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            item.setIcon(QIcon(LineIcon.pixmap(icon_name, 18)))
            item.setData(Qt.UserRole, kind)
            self.nav.addItem(item)
        self.nav.setSpacing(2)
        self.nav.setCurrentRow(0)
        self._refresh_nav_icons(0)
        side_lay.addWidget(self.nav, 1)
        # 导航指示条：叠在列表视口上，切换时 200ms 滑到目标项
        self.nav_indicator = QFrame(self.nav.viewport())
        self.nav_indicator.setObjectName("navIndicator")
        self.nav_indicator.setFixedWidth(3)
        self.nav_indicator.hide()
        side_lay.addStretch(1)

        body_lay.addWidget(sidebar)

        # ── 页面栈 ──
        self.stack = QStackedWidget()
        body_lay.addWidget(self.stack, 1)

        from hanhua.ui.pages.home_page import HomePage
        from hanhua.ui.pages.review_page import ReviewPage
        from hanhua.ui.pages.settings_page import SettingsPage
        from hanhua.ui.pages.translate_page import TranslatePage
        from hanhua.ui.pages.translate_tool_page import TranslateToolPage
        self.pages = {
            "home": HomePage(state, self),
            "review": ReviewPage(state, self),
            "translate": TranslatePage(state, self),
            "translate_tool": TranslateToolPage(state, self),
            "settings": SettingsPage(state, self),
        }
        for name in PAGES:
            self.stack.addWidget(self.pages[name])

        self.nav.currentRowChanged.connect(self._on_nav_changed)
        self.setStatusBar(QStatusBar())
        self._refresh_statusbar()
        state.settingsChanged.connect(self._refresh_statusbar)
        state.projectOpened.connect(self._on_project_opened)
        # 顶部栏「切换项目」→ 首页打开项目对话框（spec §3：项目切换进顶部栏）
        self.top_bar.switch_btn.clicked.connect(self._switch_project)

    def _switch_project(self):
        self.pages["home"]._pick_dir()

    # ── 导航 ───────────────────────────────────────────────
    def _page_row(self) -> int:
        """当前选中 page 对应的 nav row（四项一一对应）。"""
        return self.stack.currentIndex()

    def _on_nav_changed(self, row: int):
        index = _NAV_PAGE_ROWS[row]
        self.stack.setCurrentIndex(index)
        self._refresh_nav_icons(index)
        self._animate_nav_indicator(index)
        self._fade_in_page(index)
        self._refresh_statusbar()

    def _refresh_nav_icons(self, selected_index: int):
        """选中项图标用薄荷青，其余用中性色。"""
        for row, index in _NAV_PAGE_ROWS.items():
            item = self.nav.item(row)
            icon_name = item.data(Qt.UserRole) or "home"
            color = TOKENS.accent if index == selected_index else TOKENS.text_disabled
            item.setIcon(QIcon(LineIcon.pixmap(icon_name, 18, color)))

    def _position_nav_indicator(self, animate: bool):
        """指示条定位到当前项；animate=True 时 200ms 滑动。"""
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
        if not animate or not self.nav_indicator.isVisible() \
                or not motion_enabled():
            self.nav_indicator.setGeometry(target)
            self.nav_indicator.show()
            return
        anim = QPropertyAnimation(self.nav_indicator, b"geometry", self)
        anim.setDuration(TOKENS.nav_indicator_ms)
        anim.setStartValue(self.nav_indicator.geometry())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._nav_anim = anim
        anim.start()

    def _animate_nav_indicator(self, index: int):
        self._position_nav_indicator(True)

    def _fade_in_page(self, index: int):
        """页面切换：180ms 淡入 + 12px 上移（spec §7；reduced-motion 时直切）。

        H1 修复（两次）：①位移改由 QGraphicsOpacityEffect.offset 承担，
        避免直接动画 widget pos 与 QStackedWidget 布局冲突；②PySide6
        6.11 未暴露 QGraphicsEffect.setOffset（Qt 6.8+ 绑定缺失），位移
        改由 QVariantAnimation 驱动 move。残留防护：进入即复位 (0,0)、
        finished 复位、快速重入由下一次调用的复位兜底，effect 随
        setGraphicsEffect(None) 整体移除。
        """
        page = self.stack.widget(index)
        if page is None:
            return
        for attr in ("_page_fade_anim", "_page_rise_anim"):
            old = getattr(self, attr, None)
            if old is not None:
                old.stop()
                old.deleteLater()
        if page.graphicsEffect() is not None:
            page.setGraphicsEffect(None)
        page.move(0, 0)
        if not motion_enabled():
            return
        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)
        page.move(0, _PAGE_RISE_PX)
        fade = QPropertyAnimation(effect, b"opacity", self)
        fade.setDuration(TOKENS.page_enter_ms)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        rise = QVariantAnimation(self)
        rise.setDuration(TOKENS.page_enter_ms)
        rise.setStartValue(float(_PAGE_RISE_PX))
        rise.setEndValue(0.0)
        rise.setEasingCurve(QEasingCurve.OutCubic)
        rise.valueChanged.connect(lambda v: page.move(0, int(v)))
        fade.finished.connect(lambda p=page: p.setGraphicsEffect(None))
        rise.finished.connect(lambda p=page: p.move(0, 0))
        self._page_fade_anim = fade
        self._page_rise_anim = rise
        fade.start()
        rise.start()

    def navigate(self, name: str):
        if name in PAGES:
            index = PAGES.index(name)
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(index)
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

    # ── 项目上下文 / 状态栏 ─────────────────────────────────
    def _on_project_opened(self, project):
        """项目打开：更新顶部栏上下文并同步状态栏。"""
        self.updateProjectCard(project)
        self._refresh_statusbar()

    def updateProjectCard(self, project: Project):
        """兼容入口：侧栏项目卡已移除，项目上下文统一在顶部栏显示。"""
        self.top_bar._on_project(project)

    def _refresh_statusbar(self):
        """状态栏：后端模型 + 项目名（不含端口/硬件调试信息，运行细节
        进入「运行」页模型状态区）。"""
        api = self.state.api
        if api.mode == "local":
            runtime = self.state.local_model.runtime
            if runtime:
                text = f"本地：{runtime.model} · {runtime.backend.upper()}"
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
