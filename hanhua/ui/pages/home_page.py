"""首页：游戏接入任务入口（拖放/选择）、五步状态轨道与游戏档案。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import (QColor, QDragEnterEvent, QDropEvent, QPainter,
                           QPen)
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QProgressBar, QPushButton, QVBoxLayout,
                               QWidget)

from hanhua.core.project import Project
from hanhua.ui.app_state import AppState
from hanhua.ui.icons import LineIcon
from hanhua.ui.widgets import (MetricChip, PageHeader, StatusRail, Toast,
                               Worker)


class _DirectoryDropZone(QFrame):
    """拖放区：任务轨道网格背景 + 五种状态（empty/drag-active/
    scanning/ready/blocked）。"""

    directoryDropped = Signal(object)
    activeChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.setProperty("state", "empty")
        self.setMinimumHeight(150)

    @staticmethod
    def local_directory(mime_data) -> Path | None:
        if not mime_data.hasUrls():
            return None
        urls = mime_data.urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        return path.resolve() if path.is_dir() else None

    def set_state(self, state: str):
        """empty / drag-active / scanning / ready / blocked。"""
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        # 任务轨道网格：24px 间距、1px 线、低对比度品牌色
        painter = QPainter(self)
        pen = QPen(Qt.GlobalColor.transparent)
        pen.setColor(QColor(101, 168, 255, 9))
        pen.setWidth(1)
        painter.setPen(pen)
        spacing = 24
        for x in range(0, self.width(), spacing):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), spacing):
            painter.drawLine(0, y, self.width(), y)
        painter.end()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self.local_directory(event.mimeData()) is not None:
            event.acceptProposedAction()
            self.activeChanged.emit(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.activeChanged.emit(False)
        event.accept()

    def dropEvent(self, event: QDropEvent):
        self.activeChanged.emit(False)
        path = self.local_directory(event.mimeData())
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.directoryDropped.emit(path)


class HomePage(QWidget):
    def __init__(self, state: AppState, window):
        super().__init__()
        self.state = state
        self.window = window
        self._scanning = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 18)
        outer.setSpacing(14)
        col = QVBoxLayout()
        col.setSpacing(14)
        outer.addLayout(col)

        # ── 页面抬头 ──
        col.addWidget(PageHeader(
            "游戏接入",
            "拖入游戏文件夹，检测、提取、工具交叉验证、翻译质量与安全写回，一条龙完成",
        ))

        # ── 拖放区（任务入口） ──
        self.drop_zone = _DirectoryDropZone()
        dz = QVBoxLayout(self.drop_zone)
        dz.setSpacing(8)
        dz.addStretch(1)
        icon_row = QHBoxLayout()
        icon_row.addStretch(1)
        icon_row.addWidget(LineIcon("brand", 26, "#58F0C6"))
        icon_row.addSpacing(10)
        self.dz_icon = LineIcon("folder", 42)
        icon_row.addWidget(self.dz_icon)
        icon_row.addStretch(1)
        self.dz_title = QLabel("将游戏文件夹拖到此处")
        self.dz_title.setAlignment(Qt.AlignCenter)
        self.dz_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.dz_hint = QLabel("检测 Unity 布局、提取文本、工具交叉验证、翻译与安全写回")
        self.dz_hint.setAlignment(Qt.AlignCenter)
        self.dz_hint.setProperty("class", "subtitle")
        self.pick_btn = QPushButton("选择文件夹…")
        self.pick_btn.setProperty("primary", True)
        self.pick_btn.setFixedWidth(160)
        self.pick_btn.setMinimumHeight(48)
        self.pick_btn.setAccessibleName("选择 Unity 游戏文件夹")
        self.pick_btn.setAccessibleDescription("选择包含游戏可执行文件和 Data 目录的文件夹")
        self.pick_btn.setCursor(Qt.PointingHandCursor)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.pick_btn)
        btn_row.addStretch(1)
        self.scan_bar = QProgressBar()
        self.scan_bar.setRange(0, 0)
        self.scan_bar.setVisible(False)
        dz.addLayout(icon_row)
        dz.addWidget(self.dz_title)
        dz.addWidget(self.dz_hint)
        dz.addLayout(btn_row)
        dz.addWidget(self.scan_bar)
        dz.addStretch(1)
        col.addWidget(self.drop_zone)

        # ── 运行时概要（工具状态/缓存等细节并入状态轨道与审校页） ──
        self.runtime_strip = QFrame()
        self.runtime_strip.setObjectName("card")
        runtime_row = QHBoxLayout(self.runtime_strip)
        runtime_row.setContentsMargins(14, 12, 14, 12)
        runtime_row.setSpacing(10)
        self.runtime_value = MetricChip("运行时", "未检测")
        self.tool_value = MetricChip("自动工具", "待校验")
        runtime_row.addWidget(self.runtime_value)
        runtime_row.addWidget(self.tool_value)
        runtime_row.addStretch(1)
        col.addWidget(self.runtime_strip)

        # ── 五步任务状态轨道（横向节点 + 连接线） ──
        rail_head = QHBoxLayout()
        rail_title = QLabel("任务流水线")
        rail_title.setProperty("class", "pageTitle")
        rail_head.addWidget(rail_title)
        rail_head.addStretch(1)
        col.addLayout(rail_head)
        definitions = (
            ("detection", "1 游戏检测", "scan"),
            ("text_scan", "2 文本扫描", "folder"),
            ("tool_analysis", "3 自动工具分析", "tool"),
            ("translation_quality", "4 翻译质量", "translate"),
            ("writeback", "5 写回验证", "shield"),
        )
        self.pipeline_rail = StatusRail(definitions)
        # 兼容既有测试：pipeline_cards 指向节点列表（每项含 step_id）
        self.pipeline_cards = self.pipeline_rail.nodes
        col.addWidget(self.pipeline_rail)

        # ── 游戏档案（带左侧黄色标记的编辑区，不套大卡片） ──
        self.profile_card = QFrame()
        self.profile_card.setObjectName("profileCard")
        self.profile_card.setFixedHeight(64)
        pc = QHBoxLayout(self.profile_card)
        pc.setContentsMargins(16, 10, 16, 10)
        pc.setSpacing(10)
        pc_title = QLabel("游戏档案")
        pc_title.setProperty("class", "pageTitle")
        self.profile_edit_btn = QPushButton("编辑档案")
        self.profile_edit_btn.setProperty("ghost", True)
        self.profile_edit_btn.setMinimumHeight(44)
        self.profile_edit_btn.setAccessibleName("编辑当前游戏档案")
        self.profile_summary = QLabel("尚未填写。填写后翻译将贴合本游戏的世界观与文风。")
        self.profile_summary.setProperty("class", "subtitle")
        self.profile_summary.setWordWrap(True)
        pc.addWidget(pc_title)
        pc.addWidget(self.profile_summary, 1)
        pc.addWidget(self.profile_edit_btn)
        self.profile_card.setHidden(True)
        col.addWidget(self.profile_card)

        self.profile_edit_btn.clicked.connect(self._edit_profile)
        self.pick_btn.clicked.connect(self._pick_dir)
        self.drop_zone.directoryDropped.connect(self.open_dir)
        self.drop_zone.activeChanged.connect(self._set_drop_active)

    # ── 拖放 ──
    def _set_drop_active(self, active: bool):
        if self._scanning:
            return
        self.drop_zone.set_state("drag-active" if active else "empty")
        self.dz_title.setText(
            "松开以打开游戏" if active else "将游戏文件夹拖到此处")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self.drop_zone.local_directory(event.mimeData()) is not None:
            event.acceptProposedAction()
            self._set_drop_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drop_active(False)

    def dropEvent(self, event: QDropEvent):
        self._set_drop_active(False)
        path = self.drop_zone.local_directory(event.mimeData())
        if path is not None:
            event.acceptProposedAction()
            self.open_dir(path)
        else:
            event.ignore()

    def _pick_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择游戏文件夹")
        if path:
            self.open_dir(path)

    # ── 打开项目 ──
    def open_dir(self, path: Path):
        if self._scanning:
            return
        path = Path(path)
        if not path.is_dir():
            Toast.show(self, "请选择有效的文件夹", "warning")
            return
        self._set_busy(True)
        worker = Worker(
            self._scan_worker, str(path), str(self.state.app_dir)
        )
        worker.signals.finished.connect(self._on_scan_done)
        worker.signals.error.connect(self._on_scan_error)
        QThreadPool.globalInstance().start(worker)

    @staticmethod
    def _scan_worker(path_str: str, app_dir: str):
        proj = Project.open_game_dir(path_str, app_dir)
        report = proj.scan_all()
        return proj, report

    def _on_scan_done(self, result):
        proj, report = result
        self._set_busy(False)
        self.state.switch_project(proj, report)
        self._render_report(report)
        self._refresh_profile_card()
        self.window.updateProjectCard(proj)
        summary = f"{report.text_files} 个文本文件 · {report.v2_files} 个二进制资源"
        if report.unblocked:
            self.drop_zone.set_state("ready")
            Toast.show(self, f"分析通过：{summary}", "success")
            self.window.navigate("review")
        else:
            self.drop_zone.set_state("blocked")
            Toast.show(self, f"分析受限：{summary}，请查看阻断步骤", "warning")

    def _on_scan_error(self, err: str):
        self._set_busy(False)
        self.pipeline_rail.set_node_state(
            "detection", "failed", err[:80], "置信度 low")
        Toast.show(self, f"扫描失败：{err}", "error")

    def _set_busy(self, busy: bool):
        self._scanning = busy
        self.scan_bar.setVisible(busy)
        self.pick_btn.setEnabled(not busy)
        self.drop_zone.set_state("scanning" if busy else "empty")
        self.dz_title.setText(
            "正在扫描文本与二进制资源…" if busy else "将游戏文件夹拖到此处")
        if busy:
            self.pipeline_rail.set_node_state(
                "detection", "running", "正在读取 Unity 布局证据", "置信度 —")

    def _render_report(self, report):
        fingerprint = report.fingerprint
        self.runtime_value.setValue(
            f"{fingerprint.runtime.upper()} · Unity {fingerprint.unity_version}")
        status_text = " · ".join(
            f"{item.tool_id} {item.state}" for item in report.tool_statuses)
        self.tool_value.setValue(status_text)
        tool_by_id = {item.tool_id: item for item in report.tool_results}
        route = {step.step_id: step for step in report.route}
        for node in self.pipeline_rail.nodes:
            if node.step_id == "writeback":
                step = route.get("writeback")
                font_block = next((item for item in report.route
                                   if item.required and item.status in {"blocked", "failed"}
                                   and item.step_id in {"font", "font_injection"}), None)
                if font_block is not None:
                    step = font_block
            else:
                step = route.get(node.step_id)
            if step is None:
                continue
            tool = tool_by_id.get(step.backend)
            cache = ("命中" if tool.cache_hit is True
                     else "未命中" if tool.cache_hit is False else "—")
            elapsed = f"{tool.elapsed_ms} ms" if tool and tool.elapsed_ms else "—"
            metrics = f"置信度 {step.confidence} · 缓存 {cache} · 耗时 {elapsed}"
            self.pipeline_rail.set_node_state(
                node.step_id, step.status, step.reason, metrics)

    def _refresh_profile_card(self):
        self.profile_card.setHidden(False)
        p = self.state.project.profile
        if p.game_name or p.world_setting or p.tone_notes:
            parts = [p.game_name + (f"（{p.genre}）" if p.genre else "")]
            if p.world_setting:
                parts.append(f"世界观：{p.world_setting[:60]}{'…' if len(p.world_setting) > 60 else ''}")
            if p.tone_notes:
                parts.append(f"文风：{p.tone_notes[:60]}{'…' if len(p.tone_notes) > 60 else ''}")
            self.profile_summary.setText("　".join(parts))
        else:
            self.profile_summary.setText("尚未填写。填写后翻译将贴合本游戏的世界观与文风。")

    def _edit_profile(self):
        from hanhua.ui.profile_dialog import ProfileDialog
        dialog = ProfileDialog(self.state.project.profile, self)
        if dialog.exec():
            self.state.project.save_profile(dialog.result_profile())
            self._refresh_profile_card()
            Toast.show(self, "游戏档案已保存（仅当前项目生效）", "success")
