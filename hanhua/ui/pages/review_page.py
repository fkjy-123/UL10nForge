"""审校页：搜索/筛选、行内编辑、锁定、右键菜单、批量翻译入口。"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMenu, QPushButton, QStackedLayout,
                               QStyledItemDelegate, QTableView, QVBoxLayout, QWidget)

from hanhua.ui.app_state import AppState
from hanhua.ui import theme
from hanhua.ui.widgets import (STATUS_COLOR, STATUS_TEXT, EmptyState,
                               PageHeader, Toast)


def _row_meta(row: dict) -> dict:
    raw = row.get("meta", {})
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


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
        if self.status and r["status"] != self.status:
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

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 18)
        lay.setSpacing(12)

        # ── 页面抬头（操作按钮放入右上角动作区） ──
        header = PageHeader("文本审校", "搜索、筛选、行内编辑、锁定与批量翻译")
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
        self.status_combo.addItems(["全部状态", "待翻译", "已翻译", "失败", "跳过"])
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

        # ── 表格（空数据时切换为占位页，保留工具栏） ──
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
        header.resizeSection(0, 90)
        for column, width in ((1, 150), (4, 150), (5, 60)):
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
        lay.addLayout(self._stack, 1)

        self.search_box.textChanged.connect(self._apply_filters)
        self.status_combo.currentTextChanged.connect(self._apply_filters)
        self.file_combo.currentTextChanged.connect(self._apply_filters)
        self.locked_check.toggled.connect(self._apply_filters)
        self.translate_btn.clicked.connect(lambda: self.window.navigate("translate"))
        # Ctrl+F 聚焦搜索框（搜索框 placeholder 已提示）
        _search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        _search_shortcut.activated.connect(self._focus_search)

        self.state.projectOpened.connect(lambda _p: self.reload())
        self.state.entriesChanged.connect(self.reload)
        self.reload()

    def _focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def _apply_filters(self):
        if self._loading:
            return
        status = self.status_combo.currentText()
        mapping = {"待翻译": "pending", "已翻译": "translated", "失败": "failed", "跳过": "skipped"}
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
        for row in rows:
            self.state.project.store.set_status(
                row["file_id"], row["key_path"], "pending")
        self.state.entriesChanged.emit()
        Toast.show(self, f"已标记 {len(rows)} 条为待翻译")

    def _copy(self, text: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        Toast.show(self, "已复制到剪贴板")
