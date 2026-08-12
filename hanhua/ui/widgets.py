"""通用控件：页面抬头、状态徽章/轨道、数据舱、空态、Toast、后台 Worker。"""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QObject, QPropertyAnimation,
                            QRunnable, Qt, QTimer, Signal)
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)

from hanhua.ui import theme
from hanhua.ui.design_system import TOKENS
from hanhua.ui.icons import LineIcon

STATUS_TEXT = {
    "pending": "待翻译",
    "translated": "已翻译",
    "failed": "失败",
    "skipped": "跳过",
    "idle": "空闲",
    "running": "运行中",
    "succeeded": "通过",
    "warning": "待确认",
    "locked": "锁定",
    "blocked": "受限",
}
STATUS_COLOR = {
    "pending": theme.TEXT_DISABLED,
    "translated": theme.SUCCESS,
    "failed": theme.ERROR,
    "skipped": theme.STATUS_IDLE,
    "locked": theme.STATUS_LOCKED,
    "idle": theme.STATUS_IDLE,
    "running": theme.ACCENT,
    "succeeded": theme.SUCCESS,
    "warning": theme.WARNING,
    "blocked": theme.WARNING,
}


class PageHeader(QWidget):
    """统一页面抬头：左侧标题 + 任务说明，右侧动作插槽。

    只处理布局，不连接业务信号；动作按钮由页面自行连接。
    """

    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setProperty("class", "pageTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setProperty("class", "subtitle")
        left.addWidget(self.title_label)
        left.addWidget(self.subtitle_label)
        lay.addLayout(left)
        lay.addStretch(1)
        self.actions_box = QHBoxLayout()
        self.actions_box.setSpacing(10)
        lay.addLayout(self.actions_box)
        self.primary_slot: QPushButton | None = None

    def set_actions(self, buttons: list[QPushButton]) -> None:
        """右侧动作：第一个按钮标记为主按钮，其余为次按钮。"""
        for index, button in enumerate(buttons):
            if index == 0:
                button.setProperty("primary", True)
                self.primary_slot = button
            button.setMinimumHeight(TOKENS.control_height)
            self.actions_box.addWidget(button)


class StatusBadge(QWidget):
    """状态徽章：6px 语义色圆点 + 文字，由 QSS 动态属性驱动。

    状态：idle / running / succeeded / warning / failed / locked /
    pending / translated / skipped / blocked。
    """

    def __init__(self, status: str = "pending", parent=None):
        super().__init__(parent)
        self._status = status
        self.setFixedHeight(22)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.dot = QLabel()
        self.dot.setObjectName("statusNodeDot")
        self.text_label = QLabel()
        self.text_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 8.5pt;")
        lay.addWidget(self.dot)
        lay.addWidget(self.text_label)
        self._apply_status()

    def setStatus(self, status: str):
        self._status = status
        self._apply_status()

    def status(self) -> str:
        return self._status

    def _apply_status(self):
        self.setProperty("status", self._status)
        self.dot.setProperty("status", self._status)
        for widget in (self, self.dot):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.text_label.setText(STATUS_TEXT.get(self._status, self._status))


class StatusNode(QFrame):
    """状态轨道上的一个节点：状态灯 + 标题 + 细节 + 指标。"""

    def __init__(self, step_id: str, title: str, icon_name: str,
                 parent=None):
        super().__init__(parent)
        self.step_id = step_id
        self.setObjectName("statusNode")
        self.setProperty("status", "idle")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(7)
        self.dot = QLabel()
        self.dot.setObjectName("statusNodeDot")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("statusNodeTitle")
        head.addWidget(self.dot)
        head.addWidget(self.title_label)
        head.addStretch(1)
        self.detail_label = QLabel("等待")
        self.detail_label.setObjectName("statusNodeDetail")
        self.metrics_label = QLabel("")
        self.metrics_label.setObjectName("statusNodeMetrics")
        lay.addLayout(head)
        lay.addWidget(self.detail_label)
        lay.addWidget(self.metrics_label)
        self._pulse_anim = None

    def start_pulse(self):
        """运行态：状态灯 900ms 呼吸（0.35 ↔ 1.0，循环）。"""
        if self._pulse_anim is not None:
            return
        effect = QGraphicsOpacityEffect(self.dot)
        self.dot.setGraphicsEffect(effect)
        self._pulse_anim = QPropertyAnimation(effect, b"opacity", self.dot)
        self._pulse_anim.setDuration(900)
        self._pulse_anim.setStartValue(0.35)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.start()

    def stop_pulse(self):
        """离开运行态：停止呼吸并还原状态灯（不留残影）。"""
        if self._pulse_anim is None:
            return
        self._pulse_anim.stop()
        self._pulse_anim.deleteLater()
        self._pulse_anim = None
        self.dot.setGraphicsEffect(None)


class StatusRail(QWidget):
    """横向状态轨道：节点 + 细连接线，贯穿四页的产品记忆点。"""

    def __init__(self, nodes: list[tuple[str, str, str]], parent=None):
        super().__init__(parent)
        self.nodes: list[StatusNode] = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        for index, (step_id, title, icon_name) in enumerate(nodes):
            if index:
                rail = QFrame()
                rail.setObjectName("brandRail")
                rail.setFixedHeight(2)
                lay.addWidget(rail, 1)
            node = StatusNode(step_id, title, icon_name)
            lay.addWidget(node, 3)
            self.nodes.append(node)

    def set_node_state(self, step_id: str, status: str, detail: str,
                       metrics: str = "", *, progress: bool = False):
        """更新节点状态；status ∈ idle/running/succeeded/failed/warning。"""
        node = next((n for n in self.nodes if n.step_id == step_id), None)
        if node is None:
            return
        node.setProperty("status", status)
        node.dot.setProperty("status", status)
        for widget in (node, node.dot):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        node.detail_label.setText(detail)
        node.metrics_label.setText(metrics)
        # 运行态呼吸动画只作用于状态灯，绝不触碰表格/日志/滚动条
        if status == "running":
            node.start_pulse()
        else:
            node.stop_pulse()
        if progress:
            rail = node.parentWidget().findChild(QFrame, "brandRail")
            if rail is not None:
                rail.setProperty("progress", True)
                rail.style().unpolish(rail)
                rail.style().polish(rail)


class MetricStrip(QFrame):
    """数据舱：panel 底 + 左侧 2px 语义色条 + 数值/标签。"""

    def __init__(self, label: str, value: str = "—",
                 accent: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("metricStrip")
        if accent:
            self.setProperty("accent", accent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(0)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricStripValue")
        self.label = QLabel(label)
        self.label.setObjectName("metricStripLabel")
        lay.addWidget(self.value_label)
        lay.addWidget(self.label)

    def setValue(self, value) -> None:
        self.value_label.setText(str(value))


class EmptyState(QWidget):
    """空态：居中图标 + 标题 + 提示，页面无数据时的引导。"""

    def __init__(self, icon_name: str, title: str, hint: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        icon_row = QHBoxLayout()
        icon_row.addStretch(1)
        icon_row.addWidget(LineIcon(icon_name, 42))
        icon_row.addStretch(1)
        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {theme.TEXT};")
        self.hint = QLabel(hint)
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setProperty("class", "subtitle")
        lay.addStretch(1)
        lay.addLayout(icon_row)
        lay.addWidget(self.title)
        lay.addWidget(self.hint)
        lay.addStretch(1)


class StatCard(QFrame):
    """大数字 + 标签的统计卡片。"""

    def __init__(self, label: str, value: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(2)
        self.value_label = QLabel(str(value))
        self.value_label.setProperty("class", "statValue")
        self.label = QLabel(label)
        self.label.setProperty("class", "statLabel")
        lay.addWidget(self.value_label)
        lay.addWidget(self.label)

    def setValue(self, value):
        self.value_label.setText(str(value))


class MetricChip(QFrame):
    def __init__(self, label: str, value: str = "—", parent=None):
        super().__init__(parent)
        self.setObjectName("metricChip")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 7, 12, 7)
        lay.setSpacing(7)
        caption = QLabel(label)
        caption.setProperty("class", "metricLabel")
        self.value_label = QLabel(value)
        self.value_label.setProperty("class", "metricValue")
        lay.addWidget(caption)
        lay.addWidget(self.value_label)

    def setValue(self, value) -> None:
        self.value_label.setText(str(value))


class CapabilityBadge(QLabel):
    def __init__(self, text: str = "等待", status: str = "pending", parent=None):
        super().__init__(text, parent)
        self.setObjectName("capabilityBadge")
        self.setAlignment(Qt.AlignCenter)
        self.setStatus(status)

    def setStatus(self, status: str) -> None:
        self.setProperty("status", status)
        self.style().unpolish(self)
        self.style().polish(self)


class PipelineStepCard(QFrame):
    def __init__(self, step_id: str, title: str, icon_name: str, parent=None):
        super().__init__(parent)
        self.step_id = step_id
        self.setObjectName("pipelineStep")
        self.setProperty("status", "pending")
        self.setMinimumHeight(112)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 13, 14, 12)
        lay.setSpacing(7)
        head = QHBoxLayout()
        self.icon = LineIcon(icon_name, 26)
        self.title_label = QLabel(title)
        self.title_label.setProperty("class", "stepTitle")
        self.status_badge = CapabilityBadge("等待", "pending")
        head.addWidget(self.icon)
        head.addWidget(self.title_label)
        head.addStretch(1)
        head.addWidget(self.status_badge)
        self.detail_label = QLabel("等待项目分析")
        self.detail_label.setProperty("class", "stepDetail")
        self.detail_label.setWordWrap(True)
        self.metrics_label = QLabel("置信度 — · 缓存 — · 耗时 —")
        self.metrics_label.setProperty("class", "stepMetrics")
        lay.addLayout(head)
        lay.addWidget(self.detail_label)
        lay.addWidget(self.metrics_label)

    def setState(self, status: str, detail: str, confidence: str = "—",
                 cache_hit: bool | None = None, elapsed_ms: int = 0) -> None:
        labels = {
            "pending": "等待", "running": "运行中", "succeeded": "通过",
            "failed": "失败", "blocked": "受限", "skipped": "跳过",
        }
        self.setProperty("status", status)
        self.style().unpolish(self); self.style().polish(self)
        self.status_badge.setText(labels.get(status, status))
        self.status_badge.setStatus(status)
        self.detail_label.setText(detail)
        cache = "命中" if cache_hit is True else ("未命中" if cache_hit is False else "—")
        elapsed = f"{elapsed_ms} ms" if elapsed_ms else "—"
        self.metrics_label.setText(f"置信度 {confidence} · 缓存 {cache} · 耗时 {elapsed}")


class Toast:
    """右上角浮动通知，自动淡出。"""

    _stack: list[QFrame] = []

    @staticmethod
    def show(parent: QWidget, message: str, kind: str = "info", duration_ms: int = 3000):
        frame = QFrame(parent)
        frame.setObjectName("toast")
        if kind == "success":
            frame.setProperty("success", True)
        elif kind == "error":
            frame.setProperty("error", True)
        elif kind == "warning":
            frame.setProperty("warning", True)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(14, 10, 14, 10)
        prefix = {"success": "成功 · ", "error": "错误 · ",
                  "warning": "警告 · "}.get(kind, "")
        label = QLabel(prefix + message)
        lay.addWidget(label)
        frame.adjustSize()
        # 右上角堆叠
        x = parent.width() - frame.width() - 24
        y = 24 + 8 * len(Toast._stack)
        frame.move(x, y)
        frame.show()
        Toast._stack.append(frame)
        effect = QGraphicsOpacityEffect(frame)
        frame.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", frame)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        frame._toast_anim = anim  # noqa: SLF001 防 GC

        def close_toast():
            fade = QPropertyAnimation(effect, b"opacity", frame)
            fade.setDuration(180)
            fade.setStartValue(1.0)
            fade.setEndValue(0.0)

            def cleanup():
                frame.deleteLater()
                if frame in Toast._stack:
                    Toast._stack.remove(frame)
                for i, other in enumerate(Toast._stack):
                    other.move(parent.width() - other.width() - 24, 24 + 8 * i)

            fade.finished.connect(cleanup)
            fade.start()

        QTimer.singleShot(duration_ms, close_toast)


class AIPulseDot(QLabel):
    """AI 状态点（§59/§62）：紫色微弱呼吸，AI 正在分析时的唯一动效。

    克制：900ms 呼吸 0.45↔1.0，不发光不闪烁；仅状态为 running 时循环。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiDot")
        self._anim = None

    def setActive(self, active: bool):
        if active and self._anim is None:
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
            self._anim = QPropertyAnimation(effect, b"opacity", self)
            self._anim.setDuration(900)
            self._anim.setStartValue(0.45)
            self._anim.setEndValue(1.0)
            self._anim.setEasingCurve(QEasingCurve.InOutSine)
            self._anim.setLoopCount(-1)
            self._anim.start()
        elif not active and self._anim is not None:
            self._anim.stop()
            self._anim.deleteLater()
            self._anim = None
            self.setGraphicsEffect(None)


class AIReviewPanel(QFrame):
    """AI 审核面板（§27/§28/§29）：紫色语义区，展示 AI 判断与候选。

    显示：AI 分数（x/100 + 通过/建议/强制）+ 游戏语境 + 候选词（含
    概率与最佳标记）+ AI 判断原因 + 风险 + 采用建议按钮。数据经
    update_review(dict) 注入；无数据时显示空态引导。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiPanel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.dot = AIPulseDot()
        title = QLabel("AI 审核")
        title.setObjectName("aiPanelTitle")
        head.addWidget(self.dot)
        head.addWidget(title)
        head.addStretch(1)
        self.state_label = QLabel("等待审核")
        self.state_label.setObjectName("aiSectionTitle")
        head.addWidget(self.state_label)
        lay.addLayout(head)

        # 语义准确度：大分数 + 判定
        score_row = QHBoxLayout()
        score_row.setSpacing(10)
        self.score_label = QLabel("—")
        self.score_label.setObjectName("aiScore")
        self.verdict_label = QLabel("")
        self.verdict_label.setObjectName("aiSectionTitle")
        score_row.addWidget(self.score_label)
        score_row.addWidget(self.verdict_label)
        score_row.addStretch(1)
        lay.addLayout(score_row)

        # 游戏语境
        self.context_label = QLabel("")
        self.context_label.setObjectName("aiSectionTitle")
        self.context_label.setWordWrap(True)
        lay.addWidget(self.context_label)

        # 候选词列表（含概率）
        self.candidates_box = QVBoxLayout()
        self.candidates_box.setSpacing(4)
        lay.addLayout(self.candidates_box)

        # AI 判断原因
        self.reason_label = QLabel("")
        self.reason_label.setObjectName("aiReason")
        self.reason_label.setWordWrap(True)
        lay.addWidget(self.reason_label)

        # 风险
        self.risk_label = QLabel("")
        self.risk_label.setObjectName("aiSectionTitle")
        self.risk_label.setWordWrap(True)
        lay.addWidget(self.risk_label)

        self.apply_btn = QPushButton("采用 AI 建议")
        self.apply_btn.setAccessibleName("采用 AI 建议")
        self.apply_btn.setMinimumHeight(TOKENS.control_height)
        self.apply_btn.setVisible(False)
        lay.addWidget(self.apply_btn)

        self._candidate_views: list[tuple[QLabel, str]] = []
        self._current_candidates: list[str] = []

    def set_active(self, active: bool, status_text: str = "AI 正在分析"):
        """AI 工作中：紫色呼吸 + 状态文字；结束后停止呼吸。"""
        self.dot.setActive(active)
        self.state_label.setText(status_text)

    def update_review(self, *, score: float | None = None,
                      verdict: str = "", context: str = "",
                      candidates: list[tuple[str, float]] | None = None,
                      reason: str = "", risk: str = "") -> None:
        """注入 AI 审核结果。candidates: [(译文, 概率%)]。"""
        if score is None:
            self.score_label.setText("—")
            self.verdict_label.setText("")
            self.set_active(False, "等待审核")
        else:
            self.score_label.setText(f"{score:.0f} / 100")
            self.verdict_label.setText(verdict)
        self.context_label.setText(context or "")
        self.reason_label.setText(reason or "")
        self.risk_label.setText(("风险：" + risk) if risk else "")
        self._render_candidates(candidates or [])
        self.apply_btn.setVisible(bool(candidates))

    def _render_candidates(self, candidates: list[tuple[str, float]]) -> None:
        for label, _ in self._candidate_views:
            label.deleteLater()
        self._candidate_views.clear()
        self._current_candidates = []
        for text, prob in candidates:
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(f"{text}  {prob:.0f}%")
            label.setObjectName("aiCandidate")
            label.setProperty("best", text == candidates[0][0])
            label.setMinimumHeight(30)
            row.addWidget(label)
            row.addStretch(1)
            self.candidates_box.addLayout(row)
            self._candidate_views.append((label, text))
            self._current_candidates.append(text)

    def best_candidate(self) -> str | None:
        return self._current_candidates[0] if self._current_candidates else None


class CommandPalette(QFrame):
    """Ctrl+K 命令面板（§51）：浮层 + 过滤 + 回车执行。

    命令表 [(标题, 描述, 回调)]；输入过滤匹配标题/描述（不区分大小写），
    Enter 执行选中项，Esc 关闭。浮层覆盖在主窗口中央，微玻璃深底。
    """

    def __init__(self, parent: QWidget, commands: list[tuple[str, str, callable]],
                 *, on_close: callable | None = None):
        super().__init__(parent)
        self._commands = commands
        self._on_close = on_close
        self.setObjectName("commandPalette")
        self.setFixedWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(10)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索操作…（Ctrl+K 打开 / Esc 关闭）")
        self.search.setAccessibleName("命令面板搜索")
        self.search.setMinimumHeight(TOKENS.control_height)
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("commandList")
        self.list_widget.setFixedHeight(260)
        self.list_widget.itemActivated.connect(self._execute)
        lay.addWidget(self.list_widget)

        self._populate(self._commands)
        self.setVisible(False)

    def _populate(self, commands):
        self.list_widget.clear()
        for title, desc, _cb in commands:
            item = QListWidgetItem(f"{title}" + (f"　— {desc}" if desc else ""))
            item.setData(Qt.UserRole, title)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _filter(self, text: str):
        needle = text.strip().casefold()
        hits = [c for c in self._commands if not needle
                or needle in c[0].casefold()
                or needle in c[1].casefold()]
        self._populate(hits)

    def open(self):  # noqa: A003（父类 open 被 QFrame 占用名）
        self.raise_()
        self.setVisible(True)
        self.search.clear()
        self.search.setFocus()
        # 浮层居中 + 200ms 淡入（§59 Dialog 动效）
        parent = self.parentWidget()
        if parent is not None:
            x = (parent.width() - self.width()) // 2
            y = max(60, (parent.height() - self.height()) // 3)
            self.move(x, y)
        self._fade(0.0, 1.0, 200)

    def closeEvent(self, event):  # noqa: N802
        if self._on_close is not None:
            self._on_close()
        super().closeEvent(event)

    def _execute(self, item):
        title = item.data(Qt.UserRole)
        for cmd_title, _desc, cb in self._commands:
            if cmd_title == title:
                self.setVisible(False)
                if self._on_close is not None:
                    self._on_close()
                cb()
                return

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.setVisible(False)
            if self._on_close is not None:
                self._on_close()
            return
        super().keyPressEvent(event)

    def _fade(self, start: float, end: float, duration: int):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        effect.setOpacity(start)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.finished.connect(
            lambda: self.setGraphicsEffect(None) if end >= 1.0 else None)
        self._palette_anim = anim  # noqa: SLF001 防 GC
        anim.start()


class TopBar(QWidget):
    """§14 顶部条：当前项目 + 搜索入口（Ctrl+K）+ 通知 + 设置。"""

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self._state = state
        self.setObjectName("topBar")
        self.setFixedHeight(56)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 18, 0)
        lay.setSpacing(12)

        left = QHBoxLayout()
        left.setSpacing(8)
        self.project_name = QLabel("尚未打开项目")
        self.project_name.setObjectName("topBarProject")
        self.project_sub = QLabel("选择 Unity 游戏文件夹开始")
        self.project_sub.setObjectName("topBarProjectSub")
        left.addWidget(self.project_name)
        left.addWidget(self.project_sub)
        lay.addLayout(left)
        lay.addStretch(1)

        self.search_label = QLabel("搜索操作  Ctrl+K")
        self.search_label.setObjectName("topBarSearch")
        self.search_label.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.search_label)

        self.notify_btn = QPushButton()
        self.notify_btn.setAccessibleName("通知")
        self.notify_btn.setProperty("ghost", True)
        self.notify_btn.setMinimumHeight(TOKENS.control_height)
        lay.addWidget(self.notify_btn)

        self.settings_btn = QPushButton()
        self.settings_btn.setAccessibleName("设置")
        self.settings_btn.setProperty("ghost", True)
        self.settings_btn.setMinimumHeight(TOKENS.control_height)
        lay.addWidget(self.settings_btn)

        self._install_icons()
        state.projectOpened.connect(self._on_project)

    def _install_icons(self):
        self.notify_btn.setIcon(QIcon(LineIcon.pixmap("alert", 18)))
        self.settings_btn.setIcon(QIcon(LineIcon.pixmap("gear", 18)))

    def _on_project(self, project):
        self.project_name.setText(project.game_dir.name)
        self.project_sub.setText(
            "Unity · 翻译记忆已就绪" if getattr(project, "store", None) else "Unity")


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(object)
    log = Signal(str)


class Worker(QRunnable):
    """后台任务：fn 在池线程执行，结果经信号回到主线程。"""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # noqa: BLE001
            self.signals.error.emit(str(e))
        else:
            self.signals.finished.emit(result)
