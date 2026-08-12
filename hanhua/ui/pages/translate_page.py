"""翻译页：批量深度翻译（进度/日志/停止/重试失败）+ 写回。"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import os
import subprocess
import threading

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QPlainTextEdit, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from hanhua.core.batch_translator import BatchTranslator
from hanhua.core.glossary import GlossaryStore
from hanhua.core.knowledge import KnowledgeBase
from hanhua.core.local_model import LocalModelError, sanitize_exception
from hanhua.core.models import (GameProfile, TextEntry,
                                is_actionable_translation)
from hanhua.core.prompts import build_system_prompt, collect_known_names
from hanhua.core.quality import is_write_ready
from hanhua.core.translator import create_client
from hanhua.ui.app_state import AppState
from hanhua.ui.widgets import MetricStrip, PageHeader, Toast, Worker

@dataclass(eq=False)
class _TranslationRun:
    project: object
    generation: int
    api: object
    profile: GameProfile
    cancel: threading.Event
    stop_local_after_run: bool
    secrets: list[str]
    translator: BatchTranslator | None = None
    local_started: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock)

    def attach_translator(self, translator: BatchTranslator) -> None:
        with self.lock:
            self.translator = translator
            cancelled = self.cancel.is_set()
        if cancelled:
            translator.stop()

    def detach_translator(self) -> None:
        with self.lock:
            self.translator = None

    def request_stop(self, local_model) -> None:
        self.cancel.set()
        if self.api.mode == "local":
            local_model.cancel_start()
        with self.lock:
            translator = self.translator
        if translator is not None:
            translator.stop()


MAX_LOCAL_RECOVERIES = 2  # 单次翻译运行允许的服务故障恢复次数


def _critical_local_failures(store) -> bool:
    """失败条目中是否存在服务坏状态（HTTP 502，CUDA OOM 后 llama-server
    持续返回 502）→ 需要重启服务恢复。质量失败（无 502）不触发恢复。"""
    for row in store.get_entries(status="failed"):
        meta = row.get("meta", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                continue
        if not isinstance(meta, dict):
            continue
        detail = meta.get("request_error_detail")
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(detail, dict) and detail.get("status") == 502:
            return True
    return False


def _write_ready_count(store) -> int:
    return sum(
        is_write_ready(
            row.get("status", ""), row.get("translation", ""),
            row.get("meta", "{}"),
        )
        for row in store.get_entries()
    )


class TranslatePage(QWidget):
    def __init__(self, state: AppState, window):
        super().__init__()
        self.state = state
        self.window = window
        self._worker: Worker | None = None
        self._write_worker_task: Worker | None = None
        self._active_run: _TranslationRun | None = None
        self._running = False
        self._write_running = False
        self._write_terminal_message = ""
        self._last_stats = None
        self._pool = QThreadPool.globalInstance()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 18)
        lay.setSpacing(12)

        # ── 页面抬头 ──
        lay.addWidget(PageHeader(
            "翻译",
            "批量深度翻译 · 记忆命中复用 · 质量门拦截 · 安全写回",
        ))

        # ── 任务摘要条（细长：进度 + 即时文本，不套大卡片） ──
        strip = QFrame()
        strip_row = QHBoxLayout(strip)
        strip_row.setContentsMargins(0, 0, 0, 0)
        strip_row.setSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_label = QLabel("尚未开始")
        self.progress_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        strip_row.addWidget(self.progress_bar, 1)
        strip_row.addWidget(self.progress_label)
        lay.addWidget(strip)

        # ── 次级行：剩余量 + 轻量状态计数（跳过项默认隐藏） ──
        sub_row = QHBoxLayout()
        sub_row.setSpacing(14)
        self.progress_sub = QLabel("在开始前，请确认设置页的 API 与游戏档案已配置")
        self.progress_sub.setProperty("class", "subtitle")
        self.chip_pending = QLabel("待翻译 —")
        self.chip_done = QLabel("已翻译 —")
        self.chip_failed = QLabel("失败 —")
        self.chip_skipped = QLabel("跳过 —")
        self.chip_skipped.setHidden(True)
        for chip in (self.chip_pending, self.chip_done, self.chip_failed,
                     self.chip_skipped):
            chip.setProperty("class", "subtitle")
        sub_row.addWidget(self.progress_sub)
        sub_row.addStretch(1)
        sub_row.addWidget(self.chip_pending)
        sub_row.addWidget(self.chip_done)
        sub_row.addWidget(self.chip_failed)
        sub_row.addWidget(self.chip_skipped)
        lay.addLayout(sub_row)

        # ── 数据舱：待翻译 / tokens ──
        self.metric_pending = MetricStrip("待翻译", "—")
        self.metric_tokens = MetricStrip("tokens", "—")
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(10)
        for metric in (self.metric_pending, self.metric_tokens):
            metrics_row.addWidget(metric, 1)
        lay.addLayout(metrics_row)

        self.quality_reason_label = QLabel("质量门失败原因：无")
        self.quality_reason_label.setProperty("class", "subtitle")
        self.quality_reason_label.setWordWrap(True)
        self.quality_reason_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.quality_reason_label)

        # ── 运行记录（标题 + 复制/清空） ──
        log_head = QHBoxLayout()
        log_title = QLabel("运行记录")
        log_title.setProperty("class", "pageTitle")
        self.copy_log_btn = QPushButton("复制")
        self.clear_log_btn = QPushButton("清空")
        for button in (self.copy_log_btn, self.clear_log_btn):
            button.setProperty("ghost", True)
            button.setMinimumHeight(32)
            button.setCursor(Qt.PointingHandCursor)
        log_head.addWidget(log_title)
        log_head.addStretch(1)
        log_head.addWidget(self.copy_log_btn)
        log_head.addWidget(self.clear_log_btn)
        lay.addLayout(log_head)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        lay.addWidget(self.log_view, 1)

        # ── 底部固定操作区（任一时刻只有一个主按钮） ──
        ctl = QHBoxLayout()
        ctl.setSpacing(10)
        self.start_btn = QPushButton("开始翻译")
        self.start_btn.setProperty("primary", True)
        self.stop_btn = QPushButton("停止")
        self.retry_btn = QPushButton("重试失败")
        self.write_btn = QPushButton("写回游戏")
        self.play_btn = QPushButton("开始游戏")
        self.reveal_btn = QPushButton("在文件夹中显示")
        self.reveal_btn.setProperty("ghost", True)
        for button, name in (
            (self.start_btn, "开始自动翻译"), (self.stop_btn, "停止自动翻译"),
            (self.retry_btn, "重试失败译文"), (self.write_btn, "安全写回游戏副本"),
            (self.play_btn, "启动汉化副本进入游戏"), (self.reveal_btn, "打开汉化输出目录"),
        ):
            button.setMinimumHeight(44)
            button.setAccessibleName(name)
        self.play_btn.setToolTip(
            "写回验证通过后亮起，点击直接启动汉化副本进入游戏")
        self.partial_check = QCheckBox("允许部分写入")
        self.partial_check.setChecked(False)
        self.partial_check.setToolTip(
            "存在拒绝/截断条目时强制发布（默认阻断，不勾选）")
        self.partial_check.setAccessibleName("允许部分写入并发布")
        self.stop_btn.setEnabled(False)
        self.retry_btn.setEnabled(False)
        self.write_btn.setEnabled(False)
        self.play_btn.setEnabled(False)
        self.reveal_btn.setHidden(True)
        ctl.addWidget(self.start_btn)
        ctl.addWidget(self.stop_btn)
        ctl.addWidget(self.retry_btn)
        ctl.addStretch(1)
        ctl.addWidget(self.partial_check)
        ctl.addWidget(self.reveal_btn)
        ctl.addWidget(self.write_btn)
        ctl.addWidget(self.play_btn)
        lay.addLayout(ctl)

        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.retry_btn.clicked.connect(self.retry_failed)
        self.write_btn.clicked.connect(self.write_back)
        self.play_btn.clicked.connect(self.launch_game)
        self.reveal_btn.clicked.connect(self.reveal_output)
        self.copy_log_btn.clicked.connect(self._copy_log)
        self.clear_log_btn.clicked.connect(self._clear_log)
        self.state.projectOpened.connect(self._on_project)
        self.state.projectAboutToChange.connect(self._on_project_changing)
        self.state.settingsChanged.connect(lambda: self._refresh_chips())
        self._set_primary(self.start_btn)
        self._on_project(None)

    def _set_primary(self, primary_btn):
        """任一时刻只有一个主按钮：开始翻译 ⇄ 写回游戏。"""
        for button in (self.start_btn, self.write_btn):
            is_primary = button is primary_btn
            if button.property("primary") != is_primary:
                button.setProperty("primary", is_primary)
                button.style().unpolish(button)
                button.style().polish(button)

    def _copy_log(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.log_view.toPlainText())
        Toast.show(self, "运行记录已复制到剪贴板")

    def _clear_log(self):
        self.log_view.clear()

    # ── 开始 ──
    def start(self):
        if self.state.project is None:
            Toast.show(self, "请先在首页打开游戏文件夹", "warning")
            return
        if self._active_run is not None:
            Toast.show(self, "上一个翻译任务仍在停止，请稍候", "warning")
            return
        api = replace(self.state.api)
        if (api.mode != "local"
                and not (api.base_url and api.api_key and api.model)):
            Toast.show(self, "请先在设置中配置 API", "warning")
            self.window.navigate("settings")
            return
        project = self.state.project
        generation = self.state.project_generation
        project_profile = getattr(project, "profile", None)
        run = _TranslationRun(
            project=project,
            generation=generation,
            api=replace(api),
            profile=(replace(project_profile)
                     if project_profile is not None else GameProfile()),
            cancel=threading.Event(),
            stop_local_after_run=(
                api.mode == "local" and not api.local_keep_alive),
            secrets=[api.api_key],
        )
        self._active_run = run
        self.log_view.clear()
        self._running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.retry_btn.setEnabled(False)
        self.write_btn.setEnabled(False)
        self.progress_label.setText("正在请求模型…（第一批可能需要一点时间）")
        self.progress_bar.setRange(0, 0)          # 第一批返回前为忙碌动画
        signals_holder = {}

        def run_translation():
            return self._translate_worker(run, signals_holder["signals"])

        worker = Worker(run_translation)
        signals_holder["signals"] = worker.signals
        worker.signals.progress.connect(
            lambda stats, p=project, g=generation:
            self._on_progress(stats)
            if self.state.is_current_project(p, g) else None)
        worker.signals.log.connect(
            lambda line, p=project, g=generation:
            self.log_view.appendPlainText(line)
            if self.state.is_current_project(p, g) else None)
        worker.signals.finished.connect(
            lambda stats, p=project, g=generation:
            self._on_finished(stats)
            if stats is not None and self.state.is_current_project(p, g)
            else None)
        worker.signals.error.connect(
            lambda error, p=project, g=generation, r=run:
            self._on_error(error, tuple(r.secrets))
            if self.state.is_current_project(p, g) else None)
        worker.signals.finished.connect(
            lambda _result, r=run: self._on_run_drained(r))
        worker.signals.error.connect(
            lambda _error, r=run: self._on_run_drained(r))
        self._worker = worker
        self._pool.start(worker)

    def _translate_worker(self, run: _TranslationRun, signals):
        project = run.project
        generation = run.generation
        with self.state.project_lease(project, generation) as acquired:
            if not acquired:
                return None
            return self._translate_with_lease(run, signals)

    def _translate_with_lease(self, run: _TranslationRun, signals):
        project = run.project
        generation = run.generation

        def on_progress(stats):
            signals.progress.emit(stats)     # Qt 信号自动排队回主线程

        def on_log(line: str):
            signals.log.emit(line)

        api = replace(run.api)
        profile = replace(run.profile)
        cancel = run.cancel
        store = project.store
        runtime = None
        try:
            glossary = GlossaryStore(self.state.app_dir / "glossary.db")
            glossary.init_schema()
            glossary_rows = glossary.list_all()
            glossary_prompt = glossary.format_for_prompt()
            # 知识库：跨游戏沉淀的特殊情况规则（「该翻未翻」模式 + 处置策略）。
            # 译例并入 glossary——native 降级重试（Hy-MT2 无 system prompt）
            # 靠 references 的 terms 机制带出译例
            knowledge = KnowledgeBase(self.state.app_dir / "knowledge.db")
            knowledge_prompt = knowledge.format_for_prompt()
            knowledge_pairs = knowledge.format_reference_pairs()
            knowledge.close()
            # 专名注入：当前项目收集的专名 + 全局术语库积累的专名（跨游戏复用）
            entries0 = [self._entry_from_row(r) for r in store.get_entries()]
            collected_names = collect_known_names(
                [str(e.original or "") for e in entries0])
            known_names = glossary.known_names_for(collected_names)
            glossary.close()
            if api.mode == "local":
                on_log("正在启动本地 Hy-MT2 模型服务…")
                if cancel.is_set():
                    raise RuntimeError("translation cancelled")
                runtime = self.state.local_model.ensure_running(
                    api, cancellation_event=cancel)
                run.local_started = True
                if not self.state.is_current_project(project, generation):
                    return None
                api = replace(
                    api, base_url=runtime.endpoint, api_key=runtime.api_key,
                    model=runtime.model,
                )
                run.secrets.append(runtime.api_key)
                on_log(
                    f"本地服务已就绪：{runtime.backend.upper()} · 端口 {runtime.port}")
            system = build_system_prompt(
                profile, glossary_prompt, known_names=known_names,
                knowledge_lines=knowledge_prompt)
            if cancel.is_set():
                raise RuntimeError("translation cancelled")
            if not self.state.is_current_project(project, generation):
                return None
            recoveries = 0
            while True:
                if cancel.is_set():
                    raise RuntimeError("translation cancelled")
                if not self.state.is_current_project(project, generation):
                    return None
                client = create_client(api)
                lang = (f"{profile.source_lang or 'auto'}→"
                        f"{profile.target_lang or 'zh-CN'}")
                concurrency = (runtime.parallel if api.mode == "local"
                               else api.concurrency)
                batch_size = (max(1, int(api.local_batch_size))
                              if api.mode == "local" else api.batch_size)
                translator = BatchTranslator(
                    client, batch_size=batch_size, concurrency=concurrency,
                    memory=store, model=api.model, lang=lang,
                    system_prompt=system,
                    glossary=[(row["term"], row["translation"])
                              for row in glossary_rows] + knowledge_pairs,
                    cancellation_event=cancel)
                run.attach_translator(translator)
                entries = [self._entry_from_row(r) for r in store.get_entries()]
                total_pending = sum(
                    is_actionable_translation(entry) for entry in entries)
                on_log(f"开始翻译：共 {len(entries)} 条，待翻译 {total_pending} 条")
                if total_pending == 0:
                    low_pending = sum(
                        1 for e in entries
                        if e.status == "pending"
                        and e.meta.get("confidence") == "low")
                    if low_pending:
                        on_log(f"没有可翻译条目；另有 {low_pending} 条低置信度"
                               f"条目（引擎消息/疑似噪音）留档，可在文本审校"
                               f"按「低置信度」筛选查看")
                    else:
                        on_log("没有待翻译条目（全部已翻译或已锁定），"
                               "可直接点击写回游戏")
                on_log(f"模型：{api.model} · 并发 {concurrency} · 每批 {batch_size} 条")
                on_log(f"请求地址：{client.url}")
                stats = translator.run(entries, progress_cb=on_progress)
                run.detach_translator()
                if (api.mode != "local" or stats.failed == 0
                        or recoveries >= MAX_LOCAL_RECOVERIES
                        or not _critical_local_failures(store)):
                    break
                recoveries += 1
                on_log(f"检测到本地服务故障（HTTP 502），正在以保守模式重启服务"
                       f"（第 {recoveries}/{MAX_LOCAL_RECOVERIES} 次）…")
                try:
                    runtime = self.state.local_model.restart_conservative(
                        cancellation_event=cancel)
                except LocalModelError as exc:
                    on_log(f"保守模式重启失败：{exc}")
                    break
                if runtime is None:
                    break
                on_log(f"服务已重启：CPU 模式 · 单槽 · 端口 {runtime.port}")
                reset = 0
                for row in store.get_entries(status="failed"):
                    store.set_status(row["file_id"], row["key_path"], "pending")
                    reset += 1
                on_log(f"已将 {reset} 条失败重置为待翻译，继续…")
            on_log(f"翻译完成：{stats.done} 条已翻译"
                   f"（记忆命中 {stats.from_memory}），失败 {stats.failed} 条，"
                   f"请求 {stats.requests} 次")
            if entries:
                learn_g = GlossaryStore(self.state.app_dir / "glossary.db")
                learn_g.init_schema()
                learned = learn_g.learn_proper_names(
                    entries, collected_names, str(profile.game_name or ""))
                learn_g.close()
                if learned:
                    on_log(f"术语库学习：新增 {learned} 条专名"
                           f"（跨游戏复用）")
                # 知识库学习：从「该翻未翻」回显条目沉淀特殊情况模式
                learn_kb = KnowledgeBase(self.state.app_dir / "knowledge.db")
                learned_kb, hits_kb = learn_kb.learn(
                    entries, str(profile.game_name or ""),
                    names=set(collected_names))
                learn_kb.close()
                if learned_kb or hits_kb:
                    on_log(f"知识库学习：新增 {learned_kb} 条规则"
                           f" · 累计命中 {hits_kb} 条"
                           f"（特殊情况模式沉淀，后续游戏自动复用）")
            if stats.elapsed > 0:
                on_log(
                    f"耗时 {stats.elapsed:.1f} 秒"
                    f" · 吞吐 {stats.rate_per_minute:.0f} 条/分"
                    f" · 输入 {stats.input_tokens} tokens"
                    f" · 输出 {stats.output_tokens} tokens")
            return stats
        finally:
            run.detach_translator()
            if run.stop_local_after_run and run.local_started:
                self.state.local_model.stop()

    @staticmethod
    def _entry_from_row(row: dict) -> TextEntry:
        raw_meta = row.get("meta", {})
        if isinstance(raw_meta, str):
            try:
                meta = json.loads(raw_meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        else:
            meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
        reasons = meta.get("quality_reasons", [])
        return TextEntry(
            file_id=row["file_id"], key_path=row["key_path"],
            original=row["original"], translation=row.get("translation", ""),
            status=row.get("status", "pending"), locked=bool(row.get("locked", 0)),
            id=row.get("id"), meta=meta,
            confidence=str(meta.get("confidence", "medium")),
            quality_reasons=tuple(str(reason) for reason in reasons)
            if isinstance(reasons, list) else (),
        )

    def _on_progress(self, stats):
        self._last_stats = stats
        self._refresh_chips()

    def _on_finished(self, stats):
        self._running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.retry_btn.setEnabled(stats.failed > 0)
        self._last_stats = stats
        self._refresh_chips()
        self._set_primary(self.write_btn)
        self.state.entriesChanged.emit()
        if stats.failed:
            export_path = self._export_fail_record()
            Toast.show(
                self,
                f"完成，{stats.failed} 条失败可重试"
                + (f" · 失败记录已导出：{export_path}" if export_path else ""),
                "warning")
        else:
            Toast.show(self, "翻译完成", "success")

    def _export_fail_record(self, error_title: str = "", error_detail: str = ""):
        """本次汉化失败条目（及附加错误）落盘到 docs/fail record。

        所有失败路径都经过这里：翻译失败条目、写回失败、写回未通过验证、
        翻译出错——保证失败日志不丢失。
        """
        if self.state.project is None:
            return None
        from hanhua.core.fail_export import export_fail_record
        out_dir = self.state.resource_dir / "docs" / "fail record"
        try:
            return export_fail_record(
                self.state.project, out_dir,
                error_title=error_title, error_detail=error_detail)
        except OSError as exc:
            Toast.show(self, f"失败记录导出失败：{exc}", "error")
            return None

    def _export_records(self, write_result=None,
                        error_title: str = "",
                        error_detail: str = "") -> Path | None:
        """写回后自动生成完整记录文档（docs/all record/游戏名/）。

        与 runner 闭环同一文档结构；成功与失败路径都落盘，保证手动
        汉化每次写回都有记录依据（用户实测问题可复盘）。
        """
        if self.state.project is None:
            return None
        from hanhua.core.record_writer import export_records
        out_root = self.state.resource_dir / "docs" / "all record"
        api = getattr(self.state, "api", None)
        model_name = str(getattr(api, "model", "") or "")
        try:
            return export_records(
                self.state.project, out_root,
                write_result=write_result,
                error_title=error_title, error_detail=error_detail,
                model_name=model_name)
        except Exception as exc:  # noqa: BLE001 记录导出不阻断写回主流程
            Toast.show(self, f"记录导出失败：{exc}", "error")
            return None

    def _on_error(self, err: str, secrets=()):
        self._running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._refresh_chips()
        self._set_primary(self.write_btn)
        self.progress_label.setText("翻译出错")
        diagnostic = sanitize_exception(RuntimeError(str(err)), secrets)
        Toast.show(self, f"翻译出错：{json.dumps(diagnostic, ensure_ascii=False)}", "error")
        export_path = self._export_fail_record(
            "翻译出错", json.dumps(diagnostic, ensure_ascii=False))
        if export_path:
            self.log_view.appendPlainText(f"失败记录已导出：{export_path}")

    def _on_run_drained(self, run: _TranslationRun):
        if self._active_run is run:
            self._active_run = None
            self.start_btn.setEnabled(self.state.project is not None)
            self.stop_btn.setEnabled(False)

    # ── 停止 / 重试 ──
    def stop(self):
        run = self._active_run
        requested = run is not None
        if run is not None:
            run.request_stop(self.state.local_model)
        if requested:
            self.stop_btn.setEnabled(False)
            self.log_view.appendPlainText("正在停止…未完成条目保留为待翻译，可随时继续")

    def retry_failed(self):
        store = self.state.project.store
        for r in store.get_entries(status="failed"):
            store.set_status(r["file_id"], r["key_path"], "pending")
        self.state.entriesChanged.emit()
        self.log_view.appendPlainText("已标记失败条目为待翻译")
        self.start()

    # ── 写回 ──
    def write_back(self):
        if self._write_running:
            self.log_view.appendPlainText("写回正在进行，请等待当前任务完成")
            return
        report = self.state.analysis_report
        if report is None or not report.unblocked:
            blocked = [step.reason for step in (report.route if report else ())
                       if step.required and step.status in {"blocked", "failed"}]
            detail = blocked[0] if blocked else "分析报告尚未满足写回条件"
            self.log_view.appendPlainText(f"写回已阻断：{detail}")
            Toast.show(self, f"写回已阻断：{detail}", "warning")
            return
        if _write_ready_count(self.state.project.store) <= 0:
            detail = "没有通过质量门的可写译文"
            self.log_view.appendPlainText(f"写回已阻断：{detail}")
            Toast.show(self, f"写回已阻断：{detail}", "warning")
            return
        project = self.state.project
        generation = self.state.project_generation
        font_config = replace(self.state.settings.font)
        signals_holder = {}

        def run_write():
            return self._write_worker(
                project, generation, font_config, signals_holder["signals"],
                allow_partial=self.partial_check.isChecked())

        worker = Worker(run_write)
        signals_holder["signals"] = worker.signals
        worker.signals.progress.connect(
            lambda stage, p=project, g=generation:
            self._on_write_stage(stage)
            if self.state.is_current_project(p, g) else None)
        worker.signals.finished.connect(
            lambda result, p=project, g=generation:
            self._on_written(result)
            if result is not None and self.state.is_current_project(p, g)
            else None)
        worker.signals.error.connect(
            lambda error, p=project, g=generation:
            self._on_write_error(error)
            if self.state.is_current_project(p, g) else None)
        worker.signals.log.connect(
            lambda line, p=project, g=generation:
            self.log_view.appendPlainText(line)
            if self.state.is_current_project(p, g) else None)
        worker.signals.finished.connect(
            lambda _result, w=worker: self._on_write_drained(w))
        worker.signals.error.connect(
            lambda _error, w=worker: self._on_write_drained(w))
        self._write_running = True
        self._write_terminal_message = ""
        self._write_worker_task = worker
        self.write_btn.setEnabled(False)
        self.log_view.appendPlainText("正在写回…")
        self._pool.start(worker)

    def _on_write_error(self, err: str):
        message = f"写回失败：{err}"
        self._write_terminal_message = message
        self.log_view.appendPlainText(message)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText(message)
        Toast.show(self, message, "error")
        export_path = self._export_fail_record("写回失败", err)
        if export_path:
            self.log_view.appendPlainText(f"失败记录已导出：{export_path}")
        record_path = self._export_records(
            error_title="写回失败", error_detail=err)
        if record_path:
            self.log_view.appendPlainText(f"完整记录已导出：{record_path}")

    def _write_worker(self, project, generation: int, font_config,
                      signals=None, *, allow_partial: bool = False):
        with self.state.project_lease(project, generation) as acquired:
            if not acquired:
                return None
            if signals is None:
                return project.write_all(
                    font_config=font_config,
                    allow_partial=allow_partial)
            return project.write_all(
                font_config=font_config,
                stage_cb=signals.progress.emit,
                allow_partial=allow_partial,
            )

    def _on_write_stage(self, stage) -> None:
        message = str(getattr(stage, "message", "") or "")
        phase = str(getattr(stage, "phase", "") or "")
        if message:
            self.log_view.appendPlainText(message)
            self.progress_label.setText(message)
        phases = {
            "preflight": 5,
            "copying": 20,
            "patching": 45,
            "runtime_payload": 65,
            "verifying": 80,
            "publishing": 95,
            "published": 100,
        }
        if phase in phases:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(phases[phase])

    def _on_write_drained(self, worker: Worker) -> None:
        if self._write_worker_task is not worker:
            return
        self._write_worker_task = None
        self._write_running = False
        self._refresh_chips()
        if self._write_terminal_message:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_label.setText(self._write_terminal_message)

    def _on_written(self, result):
        out = self.state.project.out_dir
        v2 = result.get("v2")
        font = result.get("font")
        verification = result.get("verification") or {}
        input_protected = verification.get("input_protected") is True
        reopen_verified = verification.get("reopen_verified") is True
        changed_files = int(verification.get("changed_files", 0) or 0)
        written_translations = int(
            verification.get("written_translations", 0) or 0)
        font_level = str(verification.get("font_level", "unavailable"))
        warnings = list(verification.get("warnings") or [])
        final_report = result.get("analysis_report")
        if final_report is not None:
            self.state.set_analysis_report(final_report)
        final_route = final_report.route if final_report is not None else ()
        route_blocked = any(
            step.required and step.status in {"blocked", "failed"}
            for step in final_route
        )
        route_complete = bool(
            final_report is not None and final_report.completable)
        gates = verification.get("gates") or {}
        overall = str(verification.get("overall") or "")
        verified = (input_protected and reopen_verified and route_complete
                    and overall in {"PASS", "WARN"})

        parts = [f"文本 {result.get('text_files', 0)} 个文件"]
        if v2 is not None:
            parts.append(
                f"二进制资源 {getattr(v2, 'files', 0)} 个文件、"
                f"{getattr(v2, 'entries', 0)} 条候选")
            if getattr(v2, "truncated", 0):
                parts.append(
                    f"（{v2.truncated} 条因 DLL/IL2CPP 长度限制截断）")
        if (font_level == "runtime_fallback" and font is not None
                and font.installed):
            parts.append(f"中文字体 {font.family}")
        result_label = "写回验证通过" if verified else "写回未通过验证"
        self.log_view.appendPlainText(f"{result_label}：{'，'.join(parts)} → {out}")
        self.log_view.appendPlainText(
            f"验证摘要：变更文件 {changed_files} · 实际写入译文 "
            f"{written_translations} · 原游戏输入哈希 "
            f"{'已保护' if input_protected else '发生变化'} · 输出重开验证 "
            f"{'已通过' if reopen_verified else '未通过'}")
        font_labels = {
            "runtime_fallback": "运行时中文回退",
            "disabled": "未启用",
            "unavailable": "不可验证",
        }
        self.log_view.appendPlainText(
            f"字体层级：{font_labels.get(font_level, font_level)}")
        if gates:
            gate_parts = [
                f"{name}={item.get('status', 'N/A')}"
                for name, item in gates.items()
                if name != "overall"]
            self.log_view.appendPlainText(
                f"四态闸门：{' · '.join(gate_parts)}"
                f"（overall={overall}）")
            for name, item in gates.items():
                if name != "overall" and item.get("detail"):
                    self.log_view.appendPlainText(
                        f"  {name}: {item['detail']}")
        for warning in getattr(v2, "warnings", ()) if v2 else ():
            if warning not in warnings:
                warnings.append(warning)
        for warning in warnings:
            self.log_view.appendPlainText(f"警告：{warning}")
        rejected_entries = verification.get("rejected_entries") or []
        truncated_entries = verification.get("truncated_entries") or []
        if rejected_entries:
            self.log_view.appendPlainText(
                f"— 拒绝条目 {len(rejected_entries)} 条（默认阻断发布，"
                "需勾选“允许部分写入”后重试）—")
            for item in rejected_entries[:10]:
                self.log_view.appendPlainText(
                    f"  拒绝 {item.get('locator', '?')}: {item.get('reason', '?')}")
            if len(rejected_entries) > 10:
                self.log_view.appendPlainText(
                    f"  … 其余 {len(rejected_entries) - 10} 条")
        if truncated_entries:
            self.log_view.appendPlainText(
                f"— 截断条目 {len(truncated_entries)} 条"
                "（仅 DLL/IL2CPP 固定容量限制，Bundle/Assets 无影响）—")
            for item in truncated_entries[:10]:
                self.log_view.appendPlainText(f"  {item}")
            if len(truncated_entries) > 10:
                self.log_view.appendPlainText(
                    f"  … 其余 {len(truncated_entries) - 10} 条")
        manifest_name = verification.get("manifest")
        if manifest_name:
            self.log_view.appendPlainText(
                f"发布清单：{out / manifest_name}（全量文件 hash，含未修改文件）")
        self.reveal_btn.setHidden(not verified)
        staged_exe = self._staged_executable()
        self.play_btn.setEnabled(
            verified and staged_exe is not None and staged_exe.exists())
        if route_blocked or not route_complete or not verified:
            detail = (
                "必需能力仍被阻断" if route_blocked
                else "必需步骤尚未完成" if not route_complete
                else f"请检查输入保护与重开验证（overall={overall}）")
            export_path = self._export_fail_record("写回未通过验证", detail)
            if export_path:
                self.log_view.appendPlainText(f"失败记录已导出：{export_path}")
        if route_blocked:
            Toast.show(self, "写回未通过验证 · 必需能力仍被阻断", "error")
        elif not route_complete:
            Toast.show(self, "写回未通过验证 · 必需步骤尚未完成", "error")
        elif not verified:
            Toast.show(self, "写回未通过验证 · 请检查输入保护与重开验证", "error")
        else:
            toast = (f"写回已验证 · {changed_files} 个变更文件 · "
                     f"{written_translations} 条译文 · "
                     f"四态闸门 {overall}")
            if (font_level == "runtime_fallback" and font is not None
                    and font.installed):
                toast += f" · 中文字体 {font.family}"
            Toast.show(self, toast, "warning" if warnings else "success")
        record_path = self._export_records(write_result=result)
        if record_path:
            self.log_view.appendPlainText(f"完整记录已导出：{record_path}")

    def reveal_output(self):
        out = str(self.state.project.out_dir)
        if os.path.exists(out):
            if os.name == "nt":
                os.startfile(out)  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", out])

    def _staged_executable(self):
        """汉化副本 exe 的绝对路径；无法定位时返回 None。

        汉化副本与原游戏布局一致，exe 相对位置取自 fingerprint，
        拼到 out_dir 上即为发布后的可执行文件。
        """
        project = self.state.project
        if project is None:
            return None
        fingerprint = getattr(project, "_fingerprint", None)
        if not callable(fingerprint):
            return None
        try:
            info = fingerprint()
        except Exception:  # noqa: BLE001 定位不到 exe 就不亮起按钮
            return None
        exe = getattr(info, "executable", None)
        if exe is None:
            return None
        try:
            return project.out_dir / exe.relative_to(project.game_dir)
        except ValueError:
            return None

    def launch_game(self):
        """启动已发布的汉化副本 exe（写回验证通过后按钮亮起）。"""
        exe = self._staged_executable()
        if exe is None or not exe.exists():
            Toast.show(self, "找不到汉化副本可执行文件", "warning")
            return
        try:
            # cwd 指向 exe 所在目录：Unity 游戏常见相对路径资源加载
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
            Toast.show(self, f"已启动汉化副本：{exe.name}", "success")
        except OSError as exc:
            Toast.show(self, f"启动失败：{exc}", "error")

    # ── 状态刷新 ──
    def _refresh_chips(self):
        if self.state.project is None:
            return
        store = self.state.project.store
        s = self._last_stats
        rows = store.get_entries()
        # 待翻译 = 引擎实际会翻的条目（is_actionable_translation），与翻译引擎
        # 同源。此前用 store.count('pending') 裸计数：IL2CPP 低置信度引擎消息
        # 留档（pending/low，不可自动翻译）被计入 → 显示虚高且永不减少，
        # 「翻译已完成但待翻译不变」的真实案例（526 条引擎异常消息留档）。
        actionable = low_pending = 0
        for row in rows:
            entry = self._entry_from_row(row)
            if is_actionable_translation(entry):
                actionable += 1
            elif (row.get("status") == "pending"
                    and entry.meta.get("confidence") == "low"):
                low_pending += 1
        self.chip_pending.setText(f"待翻译 {actionable}")
        self.chip_pending.setToolTip(
            f"另有 {low_pending} 条低置信度条目（引擎消息/疑似噪音）留档，"
            "可在文本审校按「低置信度」筛选查看" if low_pending else "")
        self.chip_done.setText(f"已翻译 {store.count('translated')}")
        self.chip_failed.setText(f"失败 {store.count('failed')}")
        self.chip_skipped.setText(f"跳过 {store.count('skipped')}")
        self.metric_pending.setValue(f"{actionable} 条")
        reasons: dict[str, int] = {}
        for row in rows:
            try:
                meta = json.loads(row.get("meta") or "{}")
            except (json.JSONDecodeError, TypeError):
                meta = {}
            for reason in meta.get("quality_reasons", []):
                reasons[str(reason)] = reasons.get(str(reason), 0) + 1
        if reasons:
            summary = " · ".join(f"{reason} {count}" for reason, count in sorted(reasons.items()))
            self.quality_reason_label.setText(f"质量门失败原因：{summary}")
        else:
            self.quality_reason_label.setText("质量门失败原因：无")
        if s is None:
            n_total = actionable
            n_done = 0
            n_failed = 0
        else:
            n_total = s.total
            n_done = s.done + s.failed
            n_failed = s.failed
        if self.progress_bar.maximum() == 0:
            self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(
            int(n_done / n_total * 100) if n_total else 0)
        self.progress_label.setText(f"{n_done} / {n_total} 条")
        self.progress_sub.setText(
            f"剩余 {max(0, n_total - n_done)} 条 · 失败 {n_failed} 条")
        # 写回可用性与核心质量门同源，翻译/写回进行中禁用。
        self.write_btn.setEnabled(
            not self._running and not self._write_running
            and _write_ready_count(store) > 0)
        if s is None:
            self.metric_tokens.setValue("—")
            return
        self.metric_tokens.setValue(f"{s.input_tokens}↑ / {s.output_tokens}↓"
                                    f" · 请求 {s.requests}")

    def _on_project(self, _proj):
        if self.state.project is None:
            return
        self._running = False
        self._write_terminal_message = ""
        self._worker = None
        self._last_stats = None
        self.start_btn.setEnabled(self._active_run is None)
        self.stop_btn.setEnabled(False)
        self.retry_btn.setEnabled(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText("尚未开始")
        self.log_view.clear()
        self._refresh_chips()
        self._set_primary(self.start_btn)
        self.reveal_btn.setHidden(True)
        self.play_btn.setEnabled(False)

    def _on_project_changing(self, _project):
        self.stop()
