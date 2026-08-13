"""「翻译」页（#11）：集成轻量翻译应用——本地/API 模型即时翻译。

独立于批量翻译流程：原文 → 译文单轮对话，提示词可自由编辑（默认
按当前游戏档案生成游戏本地化角色提示词，见 prompts.build_system_prompt），
历史记录保存在 app_dir/quick_translate_history.json（最近 50 条）。
长文本按行分块（每块 ≤2000 字符）逐块翻译，结果保持原文换行结构。
"""
from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QSplitter,
                               QVBoxLayout, QWidget)

from hanhua.core.prompts import build_system_prompt
from hanhua.core.translator import create_client
from hanhua.ui.app_state import AppState
from hanhua.ui.design_system import TOKENS
from hanhua.ui.widgets import PageHeader, Toast, Worker

_HISTORY_FILENAME = "quick_translate_history.json"
_HISTORY_LIMIT = 50          # 落盘上限
_HISTORY_SHOWN = 20          # 下拉展示条数
_BLOCK_CHARS = 2000          # 长文本单块字符上限（行不拆分）


class TranslateToolPage(QWidget):
    """轻量翻译应用页：模型信息 + 可编辑提示词 + 原文/译文 + 历史。"""

    def __init__(self, state: AppState, window):
        super().__init__()
        self.state = state
        self.window = window
        self._worker: Worker | None = None
        self._running = False
        self._history: list[dict] = []
        self._history_path = Path(state.app_dir) / _HISTORY_FILENAME
        self._load_history()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 18)
        lay.setSpacing(12)

        header = PageHeader(
            "翻译", "本地模型即时翻译：粘贴文本、调整提示词、一键翻译")
        self.settings_btn = QPushButton("模型设置 →")
        self.settings_btn.setMinimumHeight(TOKENS.control_height)
        self.settings_btn.clicked.connect(
            lambda: self.window.navigate("settings"))
        header.set_actions([self.settings_btn])
        lay.addWidget(header)

        # ── 模型信息 + 历史 ──
        info_row = QHBoxLayout()
        info_row.setSpacing(10)
        self.model_label = QLabel("")
        self.model_label.setProperty("class", "subtitle")
        info_row.addWidget(self.model_label)
        info_row.addStretch(1)
        self.history_combo = QComboBox()
        self.history_combo.setMinimumWidth(260)
        self.history_combo.setPlaceholderText("历史翻译…")
        self.history_combo.setMinimumHeight(TOKENS.control_height)
        self.history_combo.activated.connect(self._restore_history)
        info_row.addWidget(self.history_combo)
        lay.addLayout(info_row)

        # ── 提示词（可编辑；默认游戏本地化角色） ──
        lay.addWidget(self._section_label("提示词（可编辑，自定义翻译要求）"))
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setObjectName("promptEdit")
        self.prompt_edit.setFixedHeight(96)
        self.prompt_edit.setPlainText(self._default_prompt())
        self.prompt_edit.textChanged.connect(self._prompt_changed_hint)
        lay.addWidget(self.prompt_edit)
        prompt_row = QHBoxLayout()
        prompt_row.setSpacing(8)
        self.reset_prompt_btn = QPushButton("使用当前游戏档案提示词")
        self.reset_prompt_btn.setMinimumHeight(TOKENS.control_height)
        self.reset_prompt_btn.setToolTip(
            "按当前游戏档案（游戏名/世界观/文风/个性化要求）重新生成")
        self.reset_prompt_btn.clicked.connect(self._reset_prompt)
        prompt_row.addWidget(self.reset_prompt_btn)
        prompt_row.addStretch(1)
        lay.addLayout(prompt_row)

        # ── 原文 / 译文 ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        src_panel = QWidget()
        src_lay = QVBoxLayout(src_panel)
        src_lay.setContentsMargins(0, 0, 0, 0)
        src_lay.setSpacing(6)
        src_lay.addWidget(self._section_label("原文"))
        self.src_edit = QPlainTextEdit()
        self.src_edit.setObjectName("srcEdit")
        self.src_edit.setPlaceholderText("粘贴要翻译的文本（支持多行）…")
        src_lay.addWidget(self.src_edit, 1)
        splitter.addWidget(src_panel)
        dst_panel = QWidget()
        dst_lay = QVBoxLayout(dst_panel)
        dst_lay.setContentsMargins(0, 0, 0, 0)
        dst_lay.setSpacing(6)
        dst_lay.addWidget(self._section_label("译文"))
        self.dst_edit = QPlainTextEdit()
        self.dst_edit.setObjectName("dstEdit")
        self.dst_edit.setReadOnly(True)
        self.dst_edit.setPlaceholderText("翻译结果将显示在这里…")
        dst_lay.addWidget(self.dst_edit, 1)
        splitter.addWidget(dst_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([480, 480])
        lay.addWidget(splitter, 1)

        # ── 操作行 ──
        ops = QHBoxLayout()
        ops.setSpacing(8)
        self.translate_btn = QPushButton("翻译")
        self.translate_btn.setProperty("primary", True)
        self.translate_btn.setMinimumHeight(TOKENS.control_height + 8)
        self.translate_btn.setAccessibleName("开始翻译")
        self.translate_btn.clicked.connect(self._translate)
        ops.addWidget(self.translate_btn)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setMinimumHeight(TOKENS.control_height)
        self.clear_btn.clicked.connect(self._clear_all)
        ops.addWidget(self.clear_btn)
        self.copy_btn = QPushButton("复制译文")
        self.copy_btn.setMinimumHeight(TOKENS.control_height)
        self.copy_btn.clicked.connect(self._copy_dst)
        ops.addWidget(self.copy_btn)
        self.status_label = QLabel("")
        self.status_label.setProperty("class", "subtitle")
        ops.addWidget(self.status_label, 1)
        lay.addLayout(ops)

        self._refresh_model_label()
        self._refresh_history_combo()

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("detailSection")
        return label

    # ── 提示词 ───────────────────────────────────────────────
    def _default_prompt(self) -> str:
        """按当前游戏档案生成游戏本地化角色提示词（#10 个性化入口）。"""
        return build_system_prompt(self.state.profile, [])

    def _reset_prompt(self):
        self.prompt_edit.setPlainText(self._default_prompt())
        Toast.show(self, "已按当前游戏档案重新生成提示词", "success")

    def _prompt_changed_hint(self):
        """用户手动编辑提示词后：静默——提示词本就允许自由编辑。"""
        return

    # ── 模型信息 ─────────────────────────────────────────────
    def _refresh_model_label(self):
        api = self.state.api
        if api.mode == "local":
            name = Path(api.local_model_path).name if api.local_model_path else "未配置"
            self.model_label.setText(f"本地模型：{name}")
        elif api.base_url and api.api_key and api.model:
            self.model_label.setText(f"API 模型：{api.model}")
        else:
            self.model_label.setText("模型未配置（点击右上角「模型设置」）")

    # ── 翻译执行（后台 worker，长文本分块） ──────────────────
    def _translate(self):
        text = self.src_edit.toPlainText().strip()
        if not text:
            Toast.show(self, "请输入要翻译的文本", "warning")
            return
        if self._running:
            return
        api = self.state.api
        if api.mode == "api" and not (api.base_url and api.api_key and api.model):
            Toast.show(self, "请先在设置中配置 API 模型", "warning")
            return
        if api.mode == "local" and not api.local_model_path:
            Toast.show(self, "请先在设置中配置本地模型", "warning")
            return
        system = self.prompt_edit.toPlainText().strip() \
            or self._default_prompt()
        blocks = self._split_blocks(text)
        self._running = True
        self.translate_btn.setEnabled(False)
        self.translate_btn.setText(
            f"翻译中…（0/{len(blocks)} 段）")
        self.status_label.setText(
            "正在翻译…" + ("（首次本地模型启动约 30-120 秒）"
                        if api.mode == "local" else ""))
        worker = Worker(self._run_blocks, api, system, blocks,
                        self.state.local_model, self.state.resource_dir)
        # 引用必须保存：worker 局部变量会丢 wrapper（同各页 _worker 模式）
        self._worker = worker
        worker.signals.finished.connect(
            lambda out: self._on_done(out, blocks))
        worker.signals.error.connect(self._on_error)
        QThreadPool.globalInstance().start(worker)

    @staticmethod
    def _run_blocks(api, system: str, blocks: list[str],
                    local_model, resource_dir: Path):
        """后台线程：本地模式先确保服务运行，然后逐块翻译。"""
        if api.mode == "local":
            runtime = local_model.ensure_running(api)
            api = replace(api, base_url=runtime.endpoint,
                          api_key=runtime.api_key, model=runtime.model)
        client = create_client(api)
        parts = []
        for block in blocks:
            text, _usage = client.chat(
                system, [{"role": "user", "content": block}])
            parts.append(text.strip())
        return parts

    @staticmethod
    def _split_blocks(text: str) -> list[str]:
        """长文本按行分块（≤_BLOCK_CHARS，行不拆分，保留换行结构）。"""
        if len(text) <= _BLOCK_CHARS:
            return [text]
        blocks: list[str] = []
        current: list[str] = []
        size = 0
        for line in text.split("\n"):
            if size + len(line) + 1 > _BLOCK_CHARS and current:
                blocks.append("\n".join(current))
                current, size = [], 0
            current.append(line)
            size += len(line) + 1
        if current:
            blocks.append("\n".join(current))
        return blocks

    def _on_done(self, parts: list[str], blocks: list[str]):
        self._running = False
        self.translate_btn.setEnabled(True)
        self.translate_btn.setText("翻译")
        self.dst_edit.setPlainText("\n".join(parts))
        self.status_label.setText(f"完成 · {len(parts)} 段")
        api = self.state.api
        model = (Path(api.local_model_path).name if api.mode == "local"
                 else api.model or "")
        self._append_history(
            self.src_edit.toPlainText().strip(),
            "\n".join(parts),
            model,
            self.prompt_edit.toPlainText().strip())
        self._refresh_history_combo()

    def _on_error(self, err: str):
        self._running = False
        self.translate_btn.setEnabled(True)
        self.translate_btn.setText("翻译")
        self.status_label.setText("翻译失败")
        Toast.show(self, f"翻译失败：{err}", "error")

    # ── 历史（落盘 json，最近 50 条） ────────────────────────
    def _load_history(self):
        try:
            if not self._history_path.is_file():
                return
            data = json.loads(self._history_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._history = [d for d in data
                                 if isinstance(d, dict)][:_HISTORY_LIMIT]
        except (OSError, ValueError):
            self._history = []

    def _append_history(self, src: str, dst: str, model: str, prompt: str):
        record = {
            "ts": time.strftime("%Y-%m-%d %H:%M"),
            "src": src[:2000], "dst": dst[:4000],
            "model": model, "prompt": prompt[:2000],
        }
        self._history.insert(0, record)
        del self._history[_HISTORY_LIMIT:]
        try:
            self._history_path.write_text(
                json.dumps(self._history, ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass

    def _refresh_history_combo(self):
        self.history_combo.clear()
        for record in self._history[:_HISTORY_SHOWN]:
            first_line = record.get("src", "").strip().splitlines()
            summary = (first_line[0] if first_line else "")[:24]
            label = f"{record.get('ts', '')} · {summary}"
            self.history_combo.addItem(label, record)
        self.history_combo.setEnabled(
            self.history_combo.count() > 0)

    def _restore_history(self, index: int):
        record = self.history_combo.itemData(index)
        if not isinstance(record, dict):
            return
        self.src_edit.setPlainText(record.get("src", ""))
        self.dst_edit.setPlainText(record.get("dst", ""))
        if record.get("prompt"):
            self.prompt_edit.setPlainText(record["prompt"])
        self.status_label.setText(f"已载入历史 · {record.get('ts', '')}")

    # ── 小操作 ───────────────────────────────────────────────
    def _clear_all(self):
        self.src_edit.clear()
        self.dst_edit.clear()
        self.status_label.setText("")

    def _copy_dst(self):
        from PySide6.QtWidgets import QApplication
        text = self.dst_edit.toPlainText()
        if not text:
            Toast.show(self, "译文为空", "warning")
            return
        QApplication.clipboard().setText(text)
        Toast.show(self, "译文已复制", "success")
