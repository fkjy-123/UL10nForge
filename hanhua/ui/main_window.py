"""主窗口：左侧导航 + 页面栈。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QStackedWidget, QStatusBar,
                               QVBoxLayout, QWidget)

from hanhua.core.project import Project
from hanhua.ui.app_state import AppState
from hanhua.ui.design_system import TOKENS
from hanhua.ui.icons import LineIcon

PAGES = ["home", "review", "translate", "settings"]
NAV_ENTRIES = (
    ("首页", "home"),
    ("文本审校", "review"),
    ("翻译", "translate"),
    ("设置", "settings"),
)


class MainWindow(QMainWindow):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setWindowTitle("汉化助手 0.9.0 — Unity 游戏智能汉化工具")
        self.resize(1180, 740)
        self.setMinimumSize(1000, 660)

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root_lay = QHBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── 侧边栏 ──
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        side_lay = QVBoxLayout(sidebar)
        side_lay.setContentsMargins(0, 22, 0, 14)
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
        sub = QLabel("Unity 游戏智能汉化工具 v0.9.0")
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
        side_lay.addSpacing(20)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        for name, icon_name in NAV_ENTRIES:
            item = QListWidgetItem(name)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            item.setIcon(QIcon(LineIcon.pixmap(icon_name, 18)))
            item.setData(Qt.UserRole, icon_name)
            self.nav.addItem(item)
        self.nav.setCurrentRow(0)
        self.nav.setIconSize(self.nav.iconSize().expandedTo(
            self.nav.iconSize()))
        self.nav.setSpacing(2)
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

        root_lay.addWidget(sidebar)

        # ── 页面栈 ──
        self.stack = QStackedWidget()
        root_lay.addWidget(self.stack, 1)

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

    def _on_project_opened(self, project):
        """项目打开：更新侧边栏卡片并同步状态栏项目名。"""
        self.updateProjectCard(project)
        self._refresh_statusbar()

    def _on_nav_changed(self, row: int):
        if 0 <= row < len(PAGES):
            self.stack.setCurrentIndex(row)
            self._refresh_nav_icons(row)
            self._animate_nav_indicator(row)
            self._fade_in_page(row)
            self._refresh_statusbar()

    def _refresh_nav_icons(self, selected_row: int):
        """选中项图标用品牌青色，其余用中性色。"""
        for row in range(self.nav.count()):
            item = self.nav.item(row)
            icon_name = item.data(Qt.UserRole) or "home"
            color = TOKENS.primary if row == selected_row else TOKENS.text_disabled
            item.setIcon(QIcon(LineIcon.pixmap(icon_name, 18, color)))

    def _position_nav_indicator(self, animate: bool):
        """指示条定位到当前项；animate=True 时 180ms 滑动。"""
        row = self.nav.currentRow()
        item = self.nav.item(row) if 0 <= row else None
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

    def _animate_nav_indicator(self, row: int):
        self._position_nav_indicator(True)

    def _fade_in_page(self, row: int):
        """页面切换：150ms 淡入（QSS 无法做动画，用 opacity effect）。"""
        page = self.stack.widget(row)
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
        anim.setDuration(150)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(lambda p=page: p.setGraphicsEffect(None))
        self._page_fade_anim = anim
        anim.start()

    def navigate(self, name: str):
        if name in PAGES:
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(PAGES.index(name))
            self.nav.blockSignals(False)
            self.stack.setCurrentIndex(PAGES.index(name))
            self._refresh_nav_icons(PAGES.index(name))
            self._animate_nav_indicator(PAGES.index(name))
            self._fade_in_page(PAGES.index(name))

    def showEvent(self, event):
        super().showEvent(event)
        self._position_nav_indicator(False)

    def current_page(self) -> str:
        return PAGES[self.stack.currentIndex()]

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
