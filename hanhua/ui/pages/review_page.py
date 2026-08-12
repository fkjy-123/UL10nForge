"""审校页 v2：三栏工作区（§21-28）——文本列表 25% / 翻译工作区 50% / AI 审核 25%。

左栏列表沿用表格模型（EntryTableModel 六列 + 筛选 + 右键菜单，护栏
契约不变，列宽适配窄栏）；中栏展示选中条目的原文、译文编辑与上下文
（§24 Context 区域）；右栏 AIReviewPanel 展示已落盘的审核结果
（review_level → AI 分数换算）。选中联动：表格 selectionChanged →
中栏/右栏同步刷新；保存/锁定后恢复选中，避免 reload 丢焦点。
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import (QAbstractTableModel, QModelIndex,
                            QSortFilterProxyModel, Qt)
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMenu,
                               QPlainTextEdit, QPushButton, QSplitter,
                               QStackedLayout, QStyledItemDelegate, QTableView,
                               QVBoxLayout, QWidget)

from hanhua.ui.app_state import AppState
from hanhua.ui import theme
from hanhua.ui.design_system import TOKENS
from hanhua.ui.widgets import (AIReviewPanel, STATUS_COLOR, STATUS_TEXT,
                               EmptyState, PageHeader, StatusBadge, Toast)

# 审核流程落盘的 review_level → AI 分数 / 判定文案（§27 语义换算）
_REVIEW_LEVEL_SCORE = {
    "PASS": 92, "MINOR": 72, "MAJOR": 50, "CRITICAL": 25, "RETRANSLATED": 40,
}
_REVIEW_LEVEL_TEXT = {
    "PASS": "通过", "MINOR": "轻微建议", "MAJOR": "较大问题",
    "CRITICAL": "严重问题", "RETRANSLATED": "已重译",
}


def _row_meta(row: dict) -> dict:
    raw = row.get("meta", {})
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _is_sample_row(row: dict) -> bool:
    """留档样本行（识别 L1/R5）：meta 含 skipped_count（提取器限量
    样本标志，回写后仍保留）。样本无 file_offset/定位键，写回永远
    失败；人工翻译还会污染跳过统计与导出——审校页禁止编辑。"""
    return "skipped_count" in _row_meta(row)


class StatusDelegate(QStyledItemDelegate):
    """状态列：6px 语义色圆点 + 文字。"""

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        status = index.data(Qt.DisplayRole) or "pending"
        color = QColor(STATUS_COLOR.get(status, theme.TEXT_DISABLED))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(option.rect.left() + 14, option.rect.center().y() - 3, 6, 6)
        painter.setPen(QPen(QColor(theme.TEXT_SECONDARY)))
        painter.drawText(option.rect.adjusted(28, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft,
                         STATUS_TEXT.get(status, status))
        painter.restore()


class ReasonDelegate(QStyledItemDelegate):
    """失败原因列：仅失败行显示珊瑚色原因，其余显示占位符。"""

    def paint(self, painter: QPainter, option, index):
        painter.save()
        source = index.model().mapToSource(index)
        row = source.model()._rows[source.row()]
        failed = row.get("status") == "failed"
        reason = index.data(Qt.DisplayRole) or ""
        if failed and reason:
            painter.setPen(QPen(QColor(theme.ERROR)))
        else:
            painter.setPen(QPen(QColor(theme.TEXT_DISABLED)))
            reason = reason or "—"
        painter.drawText(option.rect.adjusted(10, 0, -6, 0),
                         Qt.AlignVCenter | Qt.AlignLeft, reason)
        painter.restore()


class ColumnDividerDelegate(QStyledItemDelegate):
    """在指定列右缘画 1px 分隔轨（原文/译文对照带）。"""

    def paint(self, painter: QPainter, option, index):
        super().paint(painter, option, index)
        painter.save()
        painter.setPen(QPen(QColor(theme.BORDER)))
        painter.drawLine(option.rect.right(), option.rect.top(),
                         option.rect.right(), option.rect.bottom())
        painter.restore()


class EntryTableModel(QAbstractTableModel):
    """审校表格：状态 / 来源 / 原文 / 译文 / 失败原因 / 锁定。

    置信度、角色等识别元数据对普通用户不可操作，已从表格移除（仍保留在
    meta 中供筛选与写回判断使用）。
    """
    COLS = ["状态", "来源", "原文", "译文", "失败原因", "锁定"]

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._rows: list[dict] = []

    def setEntries(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        meta = _row_meta(row)
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return row["status"]
            if col == 1:
                # 来源列显示短路径，完整路径放 tooltip
                source = meta.get("source", row["file_id"])
                if isinstance(source, str) and source:
                    return Path(source).name
                return source
            if col == 2:
                return row["original"]
            if col == 3:
                return row["translation"]
            if col == 4:
                reasons = meta.get("quality_reasons", [])
                if isinstance(reasons, list):
                    return "、".join(str(reason) for reason in reasons)
                return str(reasons) if reasons else ""
        if role == Qt.EditRole and col == 3:
            return row["translation"]
        if role == Qt.CheckStateRole and col == 5:
            return Qt.Checked if row["locked"] else Qt.Unchecked
        if role == Qt.ToolTipRole and col == 1:
            return meta.get("source", row["file_id"])
        if role == Qt.ToolTipRole and col == 2:
            return row["original"]
        if role == Qt.ToolTipRole and col == 4:
            reasons = meta.get("quality_reasons", [])
            return "\n".join(str(reason) for reason in reasons) if isinstance(reasons, list) else str(reasons or "")
        return None

    def setData(self, index, value, role=Qt.EditRole):
        row = self._rows[index.row()]
        col = index.column()
        if role == Qt.EditRole and col == 3:
            # 留档样本行禁止人工翻译（无定位键写回失败 + 污染跳过统计）
            if _is_sample_row(row):
                return False
            text = str(value).strip()
            if text == row["translation"]:
                return False
            self.state.project.store.set_manual(row["file_id"], row["key_path"], text)
            persisted = next(
                item for item in self.state.project.store.get_entries()
                if item["file_id"] == row["file_id"]
                and item["key_path"] == row["key_path"]
            )
            for field in ("translation", "status", "meta"):
                row[field] = persisted[field]
            self.dataChanged.emit(
                self.index(index.row(), 0), self.index(index.row(), 4))
            self.state.entriesChanged.emit()
            return True
        if role == Qt.CheckStateRole and col == 5:
            locked = value == Qt.Checked
            self.state.project.store.set_locked(row["file_id"], row["key_path"], locked)
            row["locked"] = locked
            self.dataChanged.emit(index, index)
            return True
        return False

    def flags(self, index):
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 3:
            # 留档样本行（meta 含 skipped_count）不可编辑：无定位键写回
            # 永远失败，人工翻译污染跳过统计与导出
            if not _is_sample_row(self._rows[index.row()]):
                f |= Qt.ItemIsEditable
        if index.column() == 5:
            f |= Qt.ItemIsUserCheckable
        return f


class EntryFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search = ""
        self.status = ""
        self.file_id = ""
        self.locked_only = False

    def setFilters(self, search="", status="", file_id="", locked_only=False):
        self.search = search.lower()
        self.status = status
        self.file_id = file_id
        self.locked_only = locked_only
        self.beginFilterChange()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, row, parent):
        model: EntryTableModel = self.sourceModel()
        r = model._rows[row]
        if self.search and self.search not in r["original"].lower() \
                and self.search not in (r["translation"] or "").lower():
            return False
        if self.status == "needs_review":
            # 翻译 C6：语义审核不合格条目（meta 有 review_issue）按
            # 「需要优化」筛选，与 store 状态无关
            if not _row_meta(r).get("review_issue"):
                return False
        elif self.status and r["status"] != self.status:
            return False
        if self.file_id and r["file_id"] != self.file_id:
            return False
        if self.locked_only and not r["locked"]:
            return False
        return True


class ReviewPage(QWidget):
    def __init__(self, state: AppState, window):
        super().__init__()
        self.state = state
        self.window = window
        self._loading = True
        self._current_row: int | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 18)
        lay.setSpacing(12)

        # ── 页面抬头（操作按钮放入右上角动作区） ──
        header = PageHeader("文本审校", "三栏工作区：筛选文本、精修译文、查看 AI 审核")
        self.translate_btn = QPushButton("开始翻译 →")
        self.translate_btn.setProperty("primary", True)
        self.translate_btn.setMinimumHeight(48)
        self.translate_btn.setAccessibleName("进入自动翻译")
        self.translate_btn.setCursor(Qt.PointingHandCursor)
        header.set_actions([self.translate_btn])
        lay.addWidget(header)

        # ── 工具栏（搜索占剩余宽度；状态/文件/锁定筛选 + 结果计数） ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索原文或译文…（Ctrl+F）")
        self.search_box.setClearButtonEnabled(True)
        self.status_combo = QComboBox()
        self.status_combo.addItems(
            ["全部状态", "待翻译", "已翻译", "失败", "跳过", "需要优化"])
        self.status_combo.setFixedWidth(110)
        self.file_combo = QComboBox()
        self.file_combo.setMinimumWidth(200)
        self.locked_check = QCheckBox("只看锁定")
        self.summary_label = QLabel("")
        self.summary_label.setProperty("class", "subtitle")
        for control, name in (
            (self.search_box, "搜索原文或译文"),
            (self.status_combo, "按翻译状态筛选"),
            (self.file_combo, "按来源文件筛选"),
        ):
            control.setMinimumHeight(44)
            control.setAccessibleName(name)
        toolbar.addWidget(self.search_box, 1)
        toolbar.addWidget(self.status_combo)
        toolbar.addWidget(self.file_combo)
        toolbar.addWidget(self.locked_check)
        toolbar.addSpacing(8)
        toolbar.addWidget(self.summary_label)
        lay.addLayout(toolbar)

        # ── 三栏工作区（§21：25% / 50% / 25%） ──
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        lay.addWidget(self.splitter, 1)

        # ── 左栏：文本列表（表格模型 + 筛选 + 右键菜单，契约不变） ──
        self.model = EntryTableModel(state)
        self.proxy = EntryFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, 74)
        for column, width in ((1, 110), (4, 100), (5, 44)):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
            header.resizeSection(column, width)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setItemDelegateForColumn(0, StatusDelegate(self.table))
        # 原文列右缘画 1px 分隔轨，与译文列形成对照带
        self.table.setItemDelegateForColumn(2, ColumnDividerDelegate(self.table))
        self.table.setItemDelegateForColumn(4, ReasonDelegate(self.table))
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_menu)
        self.empty_state = EmptyState(
            "database", "暂无文本条目", "接入游戏后，识别出的原文与译文会出现在这里")
        self._stack = QStackedLayout()
        self._stack.addWidget(self.table)
        self._stack.addWidget(self.empty_state)
        self._stack.setCurrentWidget(self.table)
        self._stack_host = QWidget()
        self._stack_host.setLayout(self._stack)
        self.splitter.addWidget(self._stack_host)

        # ── 中栏：翻译工作区（原文 / 译文编辑 / 上下文 / 质量门） ──
        self._detail_stack = QStackedLayout()
        self.detail_panel = self._build_detail_panel()
        self.detail_empty = EmptyState(
            "database", "选择条目查看详情",
            "在左侧列表选中一条文本，这里展示原文、译文与上下文")
        self._detail_stack.addWidget(self.detail_panel)
        self._detail_stack.addWidget(self.detail_empty)
        self._detail_stack.setCurrentWidget(self.detail_empty)
        self._detail_host = QWidget()
        self._detail_host.setLayout(self._detail_stack)
        self.splitter.addWidget(self._detail_host)

        # ── 右栏：AI 审核面板（§27-29 紫色语义区） ──
        self.ai_panel = AIReviewPanel()
        self.splitter.addWidget(self.ai_panel)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes([300, 540, 260])

        self.search_box.textChanged.connect(self._apply_filters)
        self.status_combo.currentTextChanged.connect(self._apply_filters)
        self.file_combo.currentTextChanged.connect(self._apply_filters)
        self.locked_check.toggled.connect(self._apply_filters)
        self.translate_btn.clicked.connect(lambda: self.window.navigate("translate"))
        # Ctrl+F 聚焦搜索框（搜索框 placeholder 已提示）
        _search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        _search_shortcut.activated.connect(self._focus_search)
        # 选中联动：左栏选中 → 中栏/右栏刷新
        self.table.selectionModel().selectionChanged.connect(
            self._on_selection_changed)

        self.state.projectOpened.connect(lambda _p: self.reload())
        self.state.entriesChanged.connect(self.reload)
        self.reload()

    # ── 中栏构建 ───────────────────────────────────────────
    def _build_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("detailPanel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.detail_badge = StatusBadge("pending")
        self.detail_source = QLabel("")
        self.detail_source.setObjectName("detailSection")
        head.addWidget(self.detail_badge)
        head.addWidget(self.detail_source, 1)
        lay.addLayout(head)

        lay.addWidget(self._section_label("原文"))
        self.detail_original = QLabel("")
        self.detail_original.setObjectName("detailOriginal")
        self.detail_original.setWordWrap(True)
        self.detail_original.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.detail_original)

        lay.addWidget(self._section_label("译文"))
        self.detail_edit = QPlainTextEdit()
        self.detail_edit.setObjectName("detailEdit")
        self.detail_edit.setPlaceholderText("在此输入或修改译文…")
        self.detail_edit.setFixedHeight(96)
        lay.addWidget(self.detail_edit)

        ops = QHBoxLayout()
        ops.setSpacing(8)
        self.save_btn = QPushButton("保存译文")
        self.save_btn.setMinimumHeight(TOKENS.control_height)
        self.save_btn.clicked.connect(self._save_detail)
        self.copy_src_btn = QPushButton("复制原文")
        self.copy_src_btn.setMinimumHeight(TOKENS.control_height)
        self.copy_src_btn.clicked.connect(
            lambda: self._copy(self.detail_original.text()))
        self.copy_tr_btn = QPushButton("复制译文")
        self.copy_tr_btn.setMinimumHeight(TOKENS.control_height)
        self.copy_tr_btn.clicked.connect(
            lambda: self._copy(self.detail_edit.toPlainText()))
        self.lock_check = QCheckBox("锁定（不翻译）")
        self.lock_check.setMinimumHeight(TOKENS.control_height)
        self.lock_check.toggled.connect(self._toggle_detail_lock)
        for w in (self.save_btn, self.copy_src_btn, self.copy_tr_btn,
                  self.lock_check):
            ops.addWidget(w)
        lay.addLayout(ops)

        lay.addWidget(self._section_label("上下文"))
        self.detail_context = QLabel("")
        self.detail_context.setObjectName("detailContext")
        self.detail_context.setWordWrap(True)
        lay.addWidget(self.detail_context)

        lay.addWidget(self._section_label("质量门"))
        self.detail_reason = QLabel("")
        self.detail_reason.setObjectName("detailReason")
        self.detail_reason.setWordWrap(True)
        lay.addWidget(self.detail_reason)
        lay.addStretch(1)
        return panel

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("detailSection")
        return label

    # ── 选中联动 ───────────────────────────────────────────
    def _on_selection_changed(self, selected, _deselected):
        indexes = selected.indexes()
        if not indexes:
            self._current_row = None
            self._detail_stack.setCurrentWidget(self.detail_empty)
            return
        src = self.proxy.mapToSource(self.model.index(indexes[0].row(), 0))
        self._current_row = src.row()
        self._fill_detail(self.model._rows[self._current_row])

    def _fill_detail(self, row: dict):
        meta = _row_meta(row)
        self.detail_badge.setStatus(row["status"])
        source = meta.get("source", row["file_id"])
        name = Path(source).name if isinstance(source, str) and source else str(source)
        self.detail_source.setText(name)
        self.detail_original.setText(row["original"])
        self.detail_edit.setPlainText(row["translation"] or "")
        self.lock_check.blockSignals(True)
        self.lock_check.setChecked(bool(row["locked"]))
        self.lock_check.blockSignals(False)
        self.detail_context.setText(self._context_text(meta))
        self.detail_reason.setText(self._quality_text(row, meta))
        self._detail_stack.setCurrentWidget(self.detail_panel)
        self._update_ai_panel(meta)

    def _context_text(self, meta: dict) -> str:
        """§24 Context 区域：文件/类型/场景/前文/后文。"""
        lines = []
        for label, key in (("场景", "scene"), ("位置", "ui_position"),
                           ("类型", "text_type")):
            value = meta.get(key)
            if value:
                lines.append(f"{label}：{value}")
        if meta.get("ctx_before"):
            lines.append(f"前文：{meta['ctx_before']}")
        if meta.get("ctx_after"):
            lines.append(f"后文：{meta['ctx_after']}")
        return "\n".join(lines) or "—"

    def _quality_text(self, row: dict, meta: dict) -> str:
        """质量门 + 审核判定摘要（来自翻译/审核流程落盘字段）。"""
        parts = []
        reasons = meta.get("quality_reasons") or []
        if row["status"] == "failed":
            parts.append("✗ 翻译失败（右键可标记重试）")
        elif meta.get("quality_passed"):
            parts.append("✓ 已通过质量门")
        if reasons:
            parts.append("未通过：" + "、".join(str(r) for r in reasons))
        level = meta.get("review_level")
        if level in _REVIEW_LEVEL_TEXT:
            text = f"AI 审核：{_REVIEW_LEVEL_TEXT[level]}"
            if meta.get("review_reason"):
                text += f" · {meta['review_reason']}"
            parts.append(text)
        if meta.get("review_blocked"):
            parts.append("⚠ 审核阻断：多轮未通过")
        return "\n".join(parts) if parts else "—"

    def _update_ai_panel(self, meta: dict):
        """右栏 AI 审核面板：review_level → 分数/判定（候选译文不落盘，
        candidates 传 None，采用按钮保持隐藏）。"""
        level = meta.get("review_level")
        if level in _REVIEW_LEVEL_SCORE:
            reason = meta.get("review_reason", "") or ""
            suggestion = meta.get("review_suggestion", "")
            if suggestion:
                reason = f"{reason}\n建议：{suggestion}".strip("\n")
            self.ai_panel.update_review(
                score=_REVIEW_LEVEL_SCORE[level],
                verdict=_REVIEW_LEVEL_TEXT[level],
                context=self._context_text(meta),
                candidates=None,
                reason=reason or "—",
                risk="审核阻断：多轮未通过" if meta.get("review_blocked") else "")
            self.ai_panel.set_active(False, "审核完成")
        else:
            self.ai_panel.update_review(score=None)
            self.ai_panel.set_active(False, "等待审核")

    # ── 中栏操作（复用 model.setData 持久化路径） ────────────
    def _save_detail(self):
        if self._current_row is None:
            return
        row = self.model._rows[self._current_row]
        fid, key = row["file_id"], row["key_path"]
        if self.model.setData(self.model.index(self._current_row, 3),
                              self.detail_edit.toPlainText()):
            Toast.show(self, "已保存译文")
        else:
            Toast.show(self, "译文未变化或该行为留档样本")
            self._fill_detail(row)
        self._restore_selection(fid, key)

    def _toggle_detail_lock(self, checked: bool):
        if self._current_row is None:
            return
        row = self.model._rows[self._current_row]
        fid, key = row["file_id"], row["key_path"]
        self.state.project.store.set_locked(fid, key, checked)
        row["locked"] = checked
        self.state.entriesChanged.emit()
        self._restore_selection(fid, key)

    def _restore_selection(self, file_id: str, key_path: str):
        """reload 重建模型后按主键找回行并重新选中（保持中栏焦点）。"""
        for row_idx, row in enumerate(self.model._rows):
            if row["file_id"] == file_id and row["key_path"] == key_path:
                src = self.proxy.mapFromSource(self.model.index(row_idx, 0))
                self.table.selectRow(src.row())
                break

    # ── 既有逻辑（护栏契约不变） ────────────────────────────
    def _focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def _apply_filters(self):
        if self._loading:
            return
        status = self.status_combo.currentText()
        mapping = {"待翻译": "pending", "已翻译": "translated", "失败": "failed",
                   "跳过": "skipped", "需要优化": "needs_review"}
        file_id = "" if self.file_combo.currentIndex() <= 0 else self.file_combo.currentData()
        self.proxy.setFilters(
            search=self.search_box.text(),
            status=mapping.get(status, ""),
            file_id=file_id,
            locked_only=self.locked_check.isChecked())
        self._refresh_summary()

    def reload(self):
        if self.state.project is None:
            self._loading = False
            self.model.setEntries([])
            self._stack.setCurrentWidget(self.empty_state)
            self._detail_stack.setCurrentWidget(self.detail_empty)
            self._refresh_summary()
            return
        store = self.state.project.store
        self._loading = True
        rows = store.get_entries()
        self.model.setEntries(rows)
        self._stack.setCurrentWidget(
            self.table if rows else self.empty_state)
        # 文件筛选下拉
        current = self.file_combo.currentData()
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        self.file_combo.addItem("全部文件", None)
        for f in store.get_files():
            self.file_combo.addItem(f["rel_path"], f["id"])
        if current is not None:
            idx = self.file_combo.findData(current)
            if idx >= 0:
                self.file_combo.setCurrentIndex(idx)
        self.file_combo.blockSignals(False)
        self._loading = False
        self._apply_filters()
        self._refresh_summary()

    def _refresh_summary(self):
        """结果计数：总数显示筛选后行数，其余统计来自 store。"""
        if self.state.project is None:
            self.summary_label.setText("共 0 条")
            return
        store = self.state.project.store
        failed = store.count("failed")
        failed_s = f" · 失败 {failed}" if failed else ""
        self.summary_label.setText(
            f"共 {self.proxy.rowCount()} 条 · 待翻译 {store.count('pending')} · "
            f"已翻译 {store.count('translated')}{failed_s} · "
            f"跳过 {store.count('skipped')}")

    # ── 右键菜单（多选批量生效） ──
    def _show_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        rows = self._selected_rows()
        if not rows:
            return
        menu = QMenu(self)
        if len(rows) == 1:
            row = rows[0]
            if row["locked"]:
                menu.addAction("解锁", lambda: self._toggle_lock(rows, False))
            else:
                menu.addAction("锁定（不翻译）", lambda: self._toggle_lock(rows, True))
            menu.addSeparator()
            menu.addAction("复制原文", lambda: self._copy(row["original"]))
            menu.addAction("复制译文", lambda: self._copy(row["translation"] or ""))
            if row["status"] == "failed":
                menu.addSeparator()
                menu.addAction("标记为待翻译（重新翻译）",
                               lambda: self._mark_pending(rows))
        else:
            menu.addAction(f"锁定选中 {len(rows)} 条（不翻译）",
                           lambda: self._toggle_lock(rows, True))
            menu.addAction(f"解锁选中 {len(rows)} 条",
                           lambda: self._toggle_lock(rows, False))
            menu.addSeparator()
            menu.addAction(f"标记选中 {len(rows)} 条为待翻译",
                           lambda: self._mark_pending(rows))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _selected_rows(self) -> list[dict]:
        """当前选中行（含右键点击所在行），转为原始模型行。"""
        selected = {self.proxy.mapToSource(i).row()
                    for i in self.table.selectionModel().selectedRows()}
        index = self.table.indexAt(self.table.viewport().mapFromGlobal(
            self.table.viewport().cursor().pos()))
        if index.isValid():
            selected.add(self.proxy.mapToSource(index).row())
        return [self.model._rows[row] for row in sorted(selected)]

    def _toggle_lock(self, rows: list[dict], locked: bool):
        for row in rows:
            self.state.project.store.set_locked(
                row["file_id"], row["key_path"], locked)
        self.state.entriesChanged.emit()
        Toast.show(self,
                   f"已锁定 {len(rows)} 条，翻译时跳过" if locked
                   else f"已解锁 {len(rows)} 条")

    def _mark_pending(self, rows: list[dict]):
        targets = [row for row in rows if not _is_sample_row(row)]
        if not targets:
            Toast.show(self, "留档样本行仅审计用，不可标记翻译")
            return
        for row in targets:
            self.state.project.store.set_status(
                row["file_id"], row["key_path"], "pending")
        self.state.entriesChanged.emit()
        Toast.show(self, f"已标记 {len(targets)} 条为待翻译")

    def _copy(self, text: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        Toast.show(self, "已复制到剪贴板")
