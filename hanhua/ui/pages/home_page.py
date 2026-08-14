"""首页 v3（Aurora Forge §16~18）：欢迎态 / 项目态双容器。

- 欢迎态 `welcome_panel`：大拖放区 + 运行时概要（未打开项目时的接入入口）。
- 项目态 `project_panel`：英雄区（项目名 + 主行动）、数据带（四指标）、
  健康度 + 下一步推荐、五步任务轨道、游戏档案。
打开项目后不保留大拖放框（spec：不长期保留大拖放区域）。
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import (QColor, QDragEnterEvent, QDropEvent, QPainter,
                           QPen)
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QProgressBar, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from hanhua.core.models import (TextEntry, entry_from_row,
                                is_actionable_translation)
from hanhua.core.project import Project
from hanhua.ui.app_state import AppState
from hanhua.ui.design_system import TOKENS
from hanhua.ui.icons import LineIcon
from hanhua.ui.widgets import (MetricChip, PageHeader, StatCard, StatusRail,
                               Toast, Worker)


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
            "概览",
            "项目状态总览——拖入游戏文件夹开始，或打开项目掌握进度",
        ))

        # ── 双态容器（欢迎 / 项目） ──
        self._panels = QStackedWidget()
        self.welcome_panel = QWidget()
        self.project_panel = QWidget()
        self._panels.addWidget(self.welcome_panel)
        self._panels.addWidget(self.project_panel)
        col.addWidget(self._panels, 1)
        self.welcome_panel.setVisible(True)
        self.project_panel.setVisible(False)

        self._build_welcome_panel()
        self._build_project_panel()

        self.profile_edit_btn.clicked.connect(self._edit_profile)
        self.pick_btn.clicked.connect(self._pick_dir)
        # #2：数据带统计后台化竞态防护——每次刷新递增 token，worker
        # 完成时 token 不符（项目已切换/更新刷新已发出）则丢弃。
        self._dashboard_token = 0
        self._dashboard_worker = None
        self._dashboard_loading = False
        self.drop_zone.directoryDropped.connect(self.open_dir)
        self.drop_zone.activeChanged.connect(self._set_drop_active)
        self.hero_btn.clicked.connect(lambda: self.window.navigate("translate"))
        # 双态刷新：打开项目与条目变化（翻译/审校后）都要更新
        state.projectOpened.connect(lambda _p: self._refresh_dashboard())
        state.entriesChanged.connect(self._refresh_dashboard)
        # 流水线 rail 实时刷新（#15）：扫描阶段事件 + 翻译/审核/写回阶段
        # 广播——此前 rail 只在 _render_report（扫描完成）更新一次，扫描
        # 与翻译全程 rail 卡在「游戏检测」节点。
        state.pipelinePhase.connect(self._on_pipeline_phase)

    # ── 欢迎态（§15 大拖放区） ────────────────────────────
    def _build_welcome_panel(self):
        lay = QVBoxLayout(self.welcome_panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # 拖放区（任务入口）
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
        lay.addWidget(self.drop_zone)

        # 运行时概要
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
        lay.addWidget(self.runtime_strip)

    # ── 项目态（§16~18 英雄区 / 数据带 / 健康度+推荐 / 轨道 / 档案） ──
    def _build_project_panel(self):
        lay = QVBoxLayout(self.project_panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # 英雄区（§16）：项目名 + 副题 + 主行动
        self.project_hero = QFrame()
        self.project_hero.setObjectName("heroCard")
        hero = QHBoxLayout(self.project_hero)
        hero.setContentsMargins(22, 18, 22, 18)
        hero.setSpacing(14)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(4)
        self.hero_title = QLabel("项目已就绪")
        self.hero_title.setObjectName("heroTitle")
        self.hero_sub = QLabel("正在准备项目摘要…")
        self.hero_sub.setObjectName("heroSub")
        hero_text.addWidget(self.hero_title)
        hero_text.addWidget(self.hero_sub)
        hero.addLayout(hero_text, 1)
        self.hero_btn = QPushButton("开始翻译")
        self.hero_btn.setProperty("primary", True)
        self.hero_btn.setMinimumHeight(TOKENS.primary_height)
        self.hero_btn.setAccessibleName("前往运行页开始翻译")
        hero.addWidget(self.hero_btn)
        lay.addWidget(self.project_hero)

        # 数据带（§17）：四指标一排
        self.data_strip = QFrame()
        self.data_strip.setObjectName("dataStrip")
        strip = QHBoxLayout(self.data_strip)
        strip.setContentsMargins(16, 14, 16, 14)
        strip.setSpacing(10)
        self.stat_total = StatCard("文本总数", 0)
        self.stat_translated = StatCard("已翻译", 0)
        self.stat_review = StatCard("待审核", 0)
        self.stat_high_risk = StatCard("高风险", 0)
        for card in (self.stat_total, self.stat_translated,
                     self.stat_review, self.stat_high_risk):
            strip.addWidget(card, 1)
        lay.addWidget(self.data_strip)

        # 五步任务状态轨道（横向节点 + 连接线）
        rail_head = QHBoxLayout()
        rail_title = QLabel("任务流水线")
        rail_title.setProperty("class", "pageTitle")
        rail_head.addWidget(rail_title)
        rail_head.addStretch(1)
        lay.addLayout(rail_head)
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
        lay.addWidget(self.pipeline_rail)

        # 游戏档案（带左侧黄色标记的编辑区，不套大卡片）
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
        lay.addWidget(self.profile_card)

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
        # 扫描事件经 Worker 信号转发（M1：event_cb 此前未接线，rail 的
        # 检测/扫描/工具分析节点全程卡在首个 running）
        signals_holder = {}

        def run_scan():
            return self._scan_worker(
                str(path), str(self.state.app_dir),
                event_cb=signals_holder["signals"].progress.emit)

        worker = Worker(run_scan)
        signals_holder["signals"] = worker.signals
        worker.signals.progress.connect(self._on_scan_progress)
        worker.signals.finished.connect(self._on_scan_done)
        worker.signals.error.connect(self._on_scan_error)
        QThreadPool.globalInstance().start(worker)

    @staticmethod
    def _scan_worker(path_str: str, app_dir: str,
                     event_cb=None):
        proj = Project.open_game_dir(path_str, app_dir)
        report = proj.scan_all(event_cb=event_cb)
        return proj, report

    def _on_scan_progress(self, event) -> None:
        """扫描阶段事件 → rail 实时更新（检测/文本扫描/工具分析）。"""
        phase = getattr(event, "phase", "") or ""
        status = getattr(event, "status", "") or ""
        message = getattr(event, "message", "") or ""
        if not phase or not status:
            return
        step_id = phase if phase in {
            "detection", "text_scan", "tool_analysis", "binary_scan",
        } else None
        if step_id is None:
            return
        self.pipeline_rail.set_node_state(
            step_id, status, message, "")

    def _on_pipeline_phase(self, step_id: str, status: str,
                           detail: str, metrics: str) -> None:
        """翻译/审核/写回阶段广播 → rail 节点实时更新（#15）。"""
        self.pipeline_rail.set_node_state(
            step_id, status, detail, metrics)

    def _on_scan_done(self, result):
        proj, report = result
        self._set_busy(False)
        self.state.switch_project(proj, report)
        self._render_report(report)
        self._refresh_profile_card()
        self.window.updateProjectCard(proj)
        summary = f"{report.text_files} 个文本文件 · {report.v2_files} 个二进制资源"
        morph_warnings = [w for w in getattr(report, "warnings", ())
                          if w.startswith("未知文本形态")]
        if morph_warnings:
            Toast.show(self, "\n".join(morph_warnings), "warning")
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
            # tool_results 的 tool_id 与 route.backend 非同一命名空间
            # （检测= native_fingerprint / 质量门= quality_gate / 写回=
            # native_atomic_writer），Mono 游戏 tool_results 甚至为空——
            # 必须判空，否则扫描完成必崩（C1）
            cache = ("命中" if tool is not None and tool.cache_hit is True
                     else "未命中" if tool is not None
                     and tool.cache_hit is False else "—")
            elapsed = f"{tool.elapsed_ms} ms" if tool and tool.elapsed_ms else "—"
            metrics = f"置信度 {step.confidence} · 缓存 {cache} · 耗时 {elapsed}"
            self.pipeline_rail.set_node_state(
                node.step_id, step.status, step.reason, metrics)

    @staticmethod
    def _entry_from_row(row: dict) -> TextEntry:
        """与翻译页同源（统一口径见 models.entry_from_row）。"""
        return entry_from_row(row)

    # ── 双态切换（§16：项目打开后隐藏大拖放框） ─────────────
    def _refresh_dashboard(self):
        """有项目 → 项目态；无项目 → 欢迎态。"""
        project = self.state.project
        has_project = project is not None and project.store is not None
        self._panels.setCurrentIndex(0 if not has_project else 1)
        self.welcome_panel.setVisible(not has_project)
        self.project_panel.setVisible(has_project)
        if not has_project:
            return
        self._refresh_project_state()

    def _refresh_project_state(self):
        """数据带 + 健康度 + 推荐 + 英雄区（#2：全量统计后台线程）。"""
        project = self.state.project
        store = project.store
        self._dashboard_token += 1
        self._dashboard_loading = True
        token = self._dashboard_token
        worker = Worker(self._collect_dashboard_stats, store)
        # 引用必须保存（局部 worker 函数返回后 wrapper 引用丢失，
        # finished 连接失效——同 review_page #2 实证）。
        self._dashboard_worker = worker
        worker.signals.finished.connect(
            lambda stats: self._on_dashboard_stats(token, stats))
        worker.signals.error.connect(
            lambda err: self._on_dashboard_error(token, err))
        QThreadPool.globalInstance().start(worker)

    @staticmethod
    def _collect_dashboard_stats(store) -> tuple:
        """后台线程统计：#19 口径单循环（total/translated/actionable/
        pending_review/flagged/failed），一次 get_entries 算完。
        """
        rows = store.get_entries()
        total = len(rows)
        translated = 0
        actionable = 0
        reviewed = 0
        flagged = 0
        failed = 0
        for row in rows:
            entry = HomePage._entry_from_row(row)
            if entry.status == "translated":
                translated += 1
                # 待审核：已翻译但未过质量门（meta.quality_passed 非 True）
                meta = entry.meta
                if meta.get("quality_passed") is True:
                    reviewed += 1
                if meta.get("quality_passed") is False \
                        or meta.get("review_status") in {"flagged", "suspicious"}:
                    flagged += 1
            elif entry.status == "failed":
                # failed 算翻译失败数，同时保持原口径：failed 条目若
                # 引擎会翻（is_actionable）仍计入待翻译分母（不永久卡死）
                failed += 1
                if is_actionable_translation(entry):
                    actionable += 1
            elif is_actionable_translation(entry):
                actionable += 1
        return (total, translated, actionable,
                max(0, translated - reviewed), flagged, failed)

    def _on_dashboard_stats(self, token: int, stats: tuple) -> None:
        """后台统计完成：渲染数据带与英雄区（主线程）。"""
        if token != self._dashboard_token:
            return
        self._dashboard_loading = False
        total, translated, actionable, pending_review, flagged, failed = stats
        self.stat_total.setValue(total)
        self.stat_translated.setValue(translated)
        self.stat_review.setValue(pending_review)
        self.stat_high_risk.setValue(flagged + failed)

        # 英雄区（测试桩可能无 profile/game_dir，容错显示纯统计）
        project = self.state.project
        profile = getattr(project, "profile", None)
        game_dir = getattr(project, "game_dir", None)
        name = getattr(game_dir, "name", None) or "Unity 项目"
        if profile is not None:
            src = getattr(profile, "source_lang", "") or "—"
            dst = getattr(profile, "target_lang", "") or "—"
            lang = f"{src} → {dst} · "
        else:
            lang = ""
        translate_pct = (100.0 * translated / (translated + actionable)
                         if (translated + actionable) else 0.0)
        self.hero_title.setText(name)
        self.hero_sub.setText(
            f"{lang}共 {total} 条文本 · "
            f"{translated} 已翻译（{translate_pct:.0f}%）")

    def _on_dashboard_error(self, token: int, err: str) -> None:
        if token != self._dashboard_token:
            return
        self._dashboard_loading = False
        self.hero_sub.setText(f"统计数据读取失败：{err[:60]}")

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
