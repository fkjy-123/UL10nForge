"""设置页：API 配置（含测试连接）/ 游戏档案 / 术语表。"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QBrush, QColor, QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QRadioButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)

from hanhua.ui.icons import LineIcon
from hanhua.ui.design_system import TOKENS
from hanhua.core.glossary import GlossaryStore
from hanhua.core.local_model import LocalModelError, discover_model
from hanhua.core.model_registry import ModelRegistry
from hanhua.core.translator import create_client
from hanhua.core.vram import estimate_vram, gpu_memory_info
from hanhua.ui.app_state import AppState
from hanhua.ui.widgets import PageHeader, Toast, Worker

CATEGORIES = ["术语", "人名", "地名", "专名"]

# 估算速度基线：单槽短条约 1.5 秒 → 40 条/分（Hy-MT2 1.8B 本地经验值）
_ESTIMATED_RATE_PER_SLOT = 40.0


class SettingsPage(QWidget):
    def __init__(self, state: AppState, window):
        super().__init__()
        self.state = state
        self.window = window
        self._pool = QThreadPool.globalInstance()
        self._glossary: GlossaryStore | None = None
        self._glossary_loading = False
        self._pending_test_config = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 18)
        lay.setSpacing(12)

        lay.addWidget(PageHeader(
            "设置",
            "分类设置中心 · 环境设置 / 字体设置 / 模型与性能 / AI 审核 / 术语库 / 关于",
        ))

        # 构建顺序：高级 tab 先建（API tab 的 _load_api_ui/_sync_backend_mode
        # 引用其控件），再按显示顺序 addTab
        advanced_tab = self._build_advanced_tab()
        env_tab = self._build_env_tab()
        font_tab = self._build_font_tab()
        glossary_tab = self._build_glossary_tab()
        review_tab = self._build_review_tab()
        about_tab = self._build_about_tab()
        self.tabs = QTabWidget()
        self.tabs.addTab(env_tab, "环境设置")
        self.tabs.addTab(font_tab, "字体设置")
        self.tabs.addTab(advanced_tab, "模型与性能")
        self.tabs.addTab(glossary_tab, "术语库")
        self.tabs.addTab(review_tab, "AI 审核")
        self.tabs.addTab(about_tab, "关于")
        for index, icon_name in enumerate(
                ("rocket", "pen", "tool", "database", "shield", "brand")):
            self.tabs.setTabIcon(index, QIcon(LineIcon.pixmap(icon_name, 16)))
        self.tabs.tabBar().setVisible(False)  # §66：左侧分类导航切换
        # 切回环境设置页时刷新四模型状态（端口探测；tabs 在此才创建完成）
        self.tabs.currentChanged.connect(self._on_env_tab_shown)
        self._refresh_model_states()

        # ── 左侧分类导航（§6.4：分类设置中心，不把所有设置堆一页） ──
        body = QHBoxLayout()
        body.setSpacing(16)
        self.settings_nav = QListWidget()
        self.settings_nav.setObjectName("settingsNav")
        self.settings_nav.setFixedWidth(180)
        for title, tab_index, icon_name in (
                ("环境设置", 0, "rocket"),
                ("字体设置", 1, "pen"),
                ("模型与性能", 2, "tool"),
                ("AI 审核", 4, "shield"),
                ("术语库", 3, "database"),
                ("关于", 5, "brand")):
            item = QListWidgetItem(
                QIcon(LineIcon.pixmap(icon_name, 16)), title)
            item.setData(Qt.UserRole, tab_index)
            self.settings_nav.addItem(item)
        self.settings_nav.currentRowChanged.connect(self._on_settings_nav)
        self.settings_nav.setCurrentRow(0)
        body.addWidget(self.settings_nav)
        # §6.4 中央表单 640–760px 可读宽度：居中列限制 tabs 宽度
        center = QWidget()
        center_lay = QHBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        self.tabs.setMaximumWidth(760)
        center_lay.addStretch(1)
        center_lay.addWidget(self.tabs)
        center_lay.addStretch(1)
        body.addWidget(center, 1)
        # §6.4 右侧实时状态卡：服务 / 模型 / 显存 / 测试结果
        body.addWidget(self._build_status_card())
        lay.addLayout(body, 1)
        state.settingsChanged.connect(self._refresh_status_card)
        state.settingsChanged.connect(self._refresh_vram_estimates)
        self._refresh_status_card()

    # ── 右侧实时状态卡（§6.4） ────────────────────────────
    def _build_status_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("statusCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        title = QLabel("实时状态")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)
        self.status_service = QLabel("未配置")
        self.status_model = QLabel("—")
        self.status_vram = QLabel("—")
        self.status_test = QLabel("尚未测试连接")
        for name, label in (
                ("服务", self.status_service), ("模型", self.status_model),
                ("显存", self.status_vram), ("测试", self.status_test)):
            row = QHBoxLayout()
            row.setSpacing(8)
            tag = QLabel(name)
            tag.setProperty("class", "metricLabel")
            row.addWidget(tag)
            row.addStretch(1)
            row.addWidget(label)
            lay.addLayout(row)
        lay.addStretch(1)
        card.setFixedWidth(220)
        return card

    def _refresh_status_card(self):
        api = self.state.api
        if api.mode == "local":
            self.status_service.setText("本地 llama.cpp")
            self.status_model.setText(
                Path(api.local_model_path).stem
                if api.local_model_path else "未配置模型")
        elif api.base_url and api.api_key and api.model:
            self.status_service.setText("在线 API")
            self.status_model.setText(api.model)
        else:
            self.status_service.setText("未配置")
            self.status_model.setText("—")
        try:
            total, free = gpu_memory_info()
            self.status_vram.setText(f"{free:.1f} / {total:.1f} GB 可用")
        except Exception:  # noqa: BLE001 无 GPU 信息时显示占位
            self.status_vram.setText("—")

    # ── 左侧分类导航（§66） ──
    def _on_settings_nav(self, row: int):
        item = self.settings_nav.item(row)
        if item is not None:
            self.tabs.setCurrentIndex(item.data(Qt.UserRole))

    # ── AI 审核设置（§68 开关与策略 / §69 阈值说明） ──
    def _build_review_tab(self) -> QWidget:
        tab = QWidget()
        root = QHBoxLayout(tab)
        root.setContentsMargins(28, 24, 28, 18)
        root.setSpacing(24)

        left = QWidget()
        form = QFormLayout(left)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(14)
        self.review_enabled = QCheckBox("翻译完成后自动进行 AI 语义审核")
        self.review_enabled.setMinimumHeight(44)
        strategy_box = QWidget()
        s_lay = QVBoxLayout(strategy_box)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(8)
        self.review_fast = QRadioButton("快速 —— 约 5% 最高风险文本送审")
        self.review_balanced = QRadioButton("平衡（推荐）—— 约 15% 最高风险文本送审")
        self.review_strict = QRadioButton("严格 —— 约 30% 最高风险文本送审")
        for r in (self.review_fast, self.review_balanced, self.review_strict):
            r.setMinimumHeight(34)
            s_lay.addWidget(r)
        form.addRow("自动审核", self.review_enabled)
        form.addRow("审核策略", strategy_box)
        self.review_save_btn = QPushButton("保存 AI 审核设置")
        self.review_save_btn.setProperty("primary", True)
        self.review_save_btn.setMinimumHeight(44)
        form.addRow("", self.review_save_btn)
        root.addWidget(left, 4)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(10)
        head = QLabel("语义审核说明")
        head.setProperty("class", "pageTitle")
        hint = QLabel(
            "翻译完成后，本地审核模型按风险评分对最可疑的译文做四级判定"
            "（通过 / 轻微 / 较大问题 / 严重）：\n\n"
            "· 严重问题 —— 自动重译并再次复核（最多 2 轮收敛）；\n"
            "· 较大问题 —— 按审核建议修正后放行；\n"
            "· 审核不通过的条目在「文本审校」页标为「需要优化」，"
            "审核词对经语境门禁沉淀后跨游戏复用。\n\n"
            "审核全程本地运行（llama.cpp · Qwen3.5-4B 审核模型），"
            "数据不出本机。送审率是硬约束上限：只对分流器挑出的最高"
            "风险条目送审，宁缺毋滥。")
        hint.setProperty("class", "subtitle")
        hint.setWordWrap(True)
        right_lay.addWidget(head)
        right_lay.addWidget(hint)
        right_lay.addStretch(1)
        root.addWidget(right, 6)

        self._load_review_ui()
        self.review_save_btn.clicked.connect(self._save_review)
        return tab

    def _load_review_ui(self):
        api = self.state.api
        self.review_enabled.setChecked(api.ai_review_enabled)
        strategy = getattr(api, "ai_review_strategy", "balanced")
        self.review_fast.setChecked(strategy == "fast")
        self.review_balanced.setChecked(strategy == "balanced")
        self.review_strict.setChecked(strategy == "strict")
        if not (self.review_fast.isChecked() or self.review_balanced.isChecked()
                or self.review_strict.isChecked()):
            self.review_balanced.setChecked(True)

    def _save_review(self):
        cfg = replace(self.state.api)
        cfg.ai_review_enabled = self.review_enabled.isChecked()
        if self.review_fast.isChecked():
            cfg.ai_review_strategy = "fast"
        elif self.review_strict.isChecked():
            cfg.ai_review_strategy = "strict"
        else:
            cfg.ai_review_strategy = "balanced"
        self._commit_api_config(cfg)
        Toast.show(self, "AI 审核设置已保存，下次翻译生效", "success")

    # ── 关于（版本 / 本地架构 / 隐私） ──
    def _build_about_tab(self) -> QWidget:
        from hanhua import VERSION
        tab = QWidget()
        root = QHBoxLayout(tab)
        root.setContentsMargins(28, 24, 28, 18)
        root.setSpacing(24)

        left = QWidget()
        lay = QVBoxLayout(left)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        icon = LineIcon("brand", 40, TOKENS.primary)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        name = QLabel("UL10nForge")
        name.setProperty("class", "pageTitle")
        ver = QLabel(f"v{VERSION} · Unity 游戏智能汉化工具")
        ver.setProperty("class", "subtitle")
        brand_text.addWidget(name)
        brand_text.addWidget(ver)
        brand_row.addWidget(icon)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        lay.addLayout(brand_row)
        lay.addSpacing(8)
        head = QLabel("本地推理架构")
        head.setProperty("class", "pageTitle")
        lay.addWidget(head)
        model_text = QLabel(
            "四模型全部本地运行（llama.cpp）：\n\n"
            "· Hy-MT2 1.8B —— 翻译主模型；\n"
            "· Qwen3.5-4B —— 语义审核（四级判定 + 反馈重译）；\n"
            "· Qwen3-Reranker 0.6B —— 语料相关度重排；\n"
            "· Qwen3-Embedding 0.6B —— 语境向量记忆检索。\n\n"
            "检测 / 提取 / 翻译 / 审核 / 写回全流程离线完成，"
            "数据不出本机。")
        model_text.setProperty("class", "subtitle")
        model_text.setWordWrap(True)
        lay.addWidget(model_text)
        lay.addStretch(1)
        root.addWidget(left, 5)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(10)
        head2 = QLabel("隐私与数据")
        head2.setProperty("class", "pageTitle")
        privacy = QLabel(
            "· 翻译、审核、记忆检索均在本机完成，不向任何云端服务发送"
            "文本内容；\n\n"
            "· 「在线 API」设置项仅为存在性保留，不作为开发验收通道；\n\n"
            "· 全局术语表、语境记忆与知识库存储于应用数据目录，"
            "跨游戏复用，可随时在术语表页维护。")
        privacy.setProperty("class", "subtitle")
        privacy.setWordWrap(True)
        right_lay.addWidget(head2)
        right_lay.addWidget(privacy)
        right_lay.addStretch(1)
        root.addWidget(right, 5)
        return tab

    # ── 环境设置（四模型管理 + 在线 API 切换，2026-08-14 重构） ────
    # 本地模式：四模型卡片（启动/停止 + GPU/CPU 选择 + 状态）；切换
    # 在线 API 才出现 Base URL / Key / 模型表单。选择持久化到
    # SettingsStore.model_runtime，启动时按 kind 应用。
    _MODEL_CARDS = (
        # (kind, 显示名, 端口, 模型线索, 描述)
        ("translate", "翻译模型", 8080, "hy-mt2", "Hy-MT2-1.8B —— 翻译主模型"),
        ("review", "语义审核", 8081, "qwen3.5-4b", "Qwen3.5-4B —— 四级判定 + 反馈重译"),
        ("rerank", "语境重排", 8082, "reranker", "Qwen3-Reranker-0.6B —— 语料相关度排序"),
        ("embed", "向量检索", 8083, "embedding", "Qwen3-Embedding-0.6B —— 语境记忆检索"),
    )
    _GPU_LAYERS_BY_CHOICE = {"auto": -1, "cpu": 0, "gpu": 999}

    def _build_env_tab(self) -> QWidget:
        tab = QWidget()
        root = QHBoxLayout(tab)
        root.setContentsMargins(28, 24, 28, 18)
        root.setSpacing(24)

        # 左 6：模式切换 + 在线表单 + 四模型卡片
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(14)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        mode_tag = QLabel("运行模式")
        mode_tag.setProperty("class", "metricLabel")
        mode_row.addWidget(mode_tag)
        self.backend_mode = QComboBox()
        self.backend_mode.addItem("本地 llama.cpp（四模型离线）", "local")
        self.backend_mode.addItem("在线 API", "api")
        self.backend_mode.setMinimumHeight(40)
        mode_row.addWidget(self.backend_mode, 1)
        left_lay.addLayout(mode_row)

        # 在线 API 表单（切换为在线 API 才显示）
        self.mode_api_widget = QWidget()
        api_form = QFormLayout(self.mode_api_widget)
        api_form.setContentsMargins(0, 6, 0, 0)
        api_form.setSpacing(14)
        self.api_provider = QComboBox()
        self.api_provider.addItem("OpenAI 兼容", "openai")
        self.api_provider.addItem("Anthropic 原生", "anthropic")
        self.api_url = QLineEdit()
        self.api_url.setPlaceholderText("https://api.openai.com/v1 或代理地址")
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("sk-…")
        self.api_model = QLineEdit()
        self.api_model.setPlaceholderText("如 gpt-4o / claude-sonnet-4 / deepseek-chat")
        for field in (self.api_provider, self.api_url, self.api_key,
                      self.api_model):
            field.setMinimumHeight(42)
        api_form.addRow("提供商", self.api_provider)
        api_form.addRow("Base URL", self.api_url)
        api_form.addRow("API Key", self.api_key)
        api_form.addRow("模型", self.api_model)
        api_btns = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setProperty("primary", True)
        self.save_btn = QPushButton("保存")
        api_btns.addWidget(self.test_btn)
        api_btns.addWidget(self.save_btn)
        api_btns.addStretch(1)
        api_form.addRow("", api_btns)
        left_lay.addWidget(self.mode_api_widget)

        # 本地模式：四模型卡片（启动/停止 + GPU/CPU 选择 + 状态）
        self.mode_local_widget = QWidget()
        local_lay = QVBoxLayout(self.mode_local_widget)
        local_lay.setContentsMargins(0, 4, 0, 0)
        local_lay.setSpacing(10)
        # 总览行：可用显存 / 系统内存（直观对照卡片占用）
        self.vram_overview = QLabel("可用显存 — · 内存 —")
        self.vram_overview.setProperty("class", "subtitle")
        self.vram_overview.setTextFormat(Qt.RichText)
        local_lay.addWidget(self.vram_overview)
        self.model_cards: dict[str, dict] = {}
        for kind, title, port, hint, desc in self._MODEL_CARDS:
            local_lay.addWidget(self._build_model_card(
                kind, title, port, hint, desc))
        local_lay.addStretch(1)
        left_lay.addWidget(self.mode_local_widget)
        left_lay.addStretch(1)
        root.addWidget(left, 6)

        # 右 4：连接状态与说明
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(10)
        status_head = QLabel("连接状态")
        status_head.setProperty("class", "pageTitle")
        self.local_status = QLabel("本地服务：未启动")
        self.local_status.setProperty("class", "subtitle")
        self.local_status.setWordWrap(True)
        self.stop_local_btn = QPushButton("停止全部本地模型")
        self.stop_local_btn.setProperty("danger", True)
        self.stop_local_btn.setMinimumHeight(44)
        self.env_hint = QLabel("")
        self.env_hint.setProperty("class", "subtitle")
        self.env_hint.setWordWrap(True)
        right_lay.addWidget(status_head)
        right_lay.addWidget(self.local_status)
        right_lay.addSpacing(4)
        right_lay.addWidget(self.stop_local_btn)
        right_lay.addSpacing(10)
        right_lay.addWidget(self.env_hint)
        right_lay.addStretch(1)
        root.addWidget(right, 4)

        self._load_api_ui()
        self.backend_mode.currentIndexChanged.connect(self._sync_backend_mode)
        self.stop_local_btn.clicked.connect(self._stop_all_models)
        self.test_btn.clicked.connect(self.test_connection)
        self.save_btn.clicked.connect(self._save_api)
        self._sync_backend_mode()
        self._refresh_vram_estimates()
        return tab

    def _build_model_card(self, kind: str, title: str, port: int,
                          hint: str, desc: str) -> QWidget:
        """单个模型的管理卡片：名称 / 模型文件 / 端口 / 运行方式 / 状态 /
        启动停止按钮。rerank/embed 固定 CPU（fixed_cpu 硬约束）不可改。"""
        card = QFrame()
        card.setObjectName("modelCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(8)
        name = QLabel(title)
        name.setProperty("class", "cardTitle")
        head.addWidget(name)
        model_label = QLabel(desc)
        model_label.setProperty("class", "subtitle")
        model_label.setToolTip(hint)
        head.addWidget(model_label, 1)
        self.model_cards[kind] = {
            "frame": card, "status": None, "btn": None, "combo": None,
            "port": port, "hint": hint,
        }
        head.addStretch(1)
        lay.addLayout(head)

        row = QHBoxLayout()
        row.setSpacing(10)
        port_label = QLabel(f"端口 {port}")
        port_label.setProperty("class", "metricLabel")
        row.addWidget(port_label)
        fixed_cpu = kind in ("rerank", "embed")
        combo = QComboBox()
        combo.setObjectName(f"modelRuntime_{kind}")
        if fixed_cpu:
            combo.addItem("固定 CPU", "auto")
            combo.setToolTip("轻量任务固定 CPU（0.6B 毫秒级，不上 GPU）")
        else:
            combo.addItem("自动（推荐）", "auto")
            combo.addItem("CPU", "cpu")
            combo.addItem("GPU", "gpu")
            combo.setToolTip(
                "自动：优先 GPU，显存放不下时把部分层分到 CPU；"
                "GPU：全层强制用显存；CPU：纯处理器运行")
        combo.setMinimumHeight(32)
        choice = self.state.settings.model_runtime_choice(kind)
        combo.setCurrentIndex(max(0, combo.findData(choice)))
        combo.currentIndexChanged.connect(
            lambda _i, k=kind: self._on_runtime_choice(k))
        combo.setEnabled(not fixed_cpu)
        self.model_cards[kind]["combo"] = combo
        row.addWidget(combo)
        # 预估占用：GPU 全层 / CPU 内存双值，当前选择高亮（直观调节）
        vram = QLabel("预估 —")
        vram.setProperty("class", "subtitle")
        vram.setTextFormat(Qt.RichText)
        row.addWidget(vram)
        row.addStretch(1)
        status = QLabel("状态：未启动")
        status.setProperty("class", "subtitle")
        row.addWidget(status)
        btn = QPushButton("启动")
        btn.setProperty("primary", True)
        btn.setMinimumHeight(32)
        btn.clicked.connect(lambda _c, k=kind: self._toggle_model(k))
        row.addWidget(btn)
        self.model_cards[kind]["status"] = status
        self.model_cards[kind]["btn"] = btn
        self.model_cards[kind]["vram"] = vram
        lay.addLayout(row)
        return card

    def _on_runtime_choice(self, kind: str) -> None:
        """运行方式选择持久化；运行中切换 → 下次重启生效（签名含
        gpu_layers，重新启动即按新选择运行）。"""
        card = self.model_cards[kind]
        choice = card["combo"].currentData()
        self.state.settings.set_model_runtime(kind, choice)
        self._refresh_vram_estimates()   # 高亮切换到当前选择
        if card["status"].text() != "状态：未启动":
            Toast.show(
                self, f"{self._model_title(kind)}：运行方式已保存，"
                      f"重新启动按 {choice} 运行", "success")

    @staticmethod
    def _model_title(kind: str) -> str:
        return {"translate": "翻译模型", "review": "语义审核",
                "rerank": "语境重排", "embed": "向量检索"}.get(kind, kind)

    def _model_port(self, kind: str) -> int:
        card = self.model_cards.get(kind)
        return card["port"] if card else 8080

    @staticmethod
    def _probe_port(port: int) -> bool:
        """探测本地模型端口（真实网络探测：反映包括外部进程的实例）。"""
        try:
            import httpx
            return httpx.get(
                f"http://127.0.0.1:{port}/health", timeout=1.5,
                trust_env=False, verify=False).status_code == 200
        except Exception:  # noqa: BLE001 - 未启动/探测失败 → 未运行
            return False

    def _refresh_model_states(self) -> None:
        for kind, card in self.model_cards.items():
            running = self._probe_port(card["port"])
            card["status"].setText(
                f"状态：运行中 · 端口 {card['port']}" if running
                else "状态：未启动")
            card["btn"].setText("停止" if running else "启动")
            card["btn"].setProperty(
                "danger", running)
            card["btn"].setProperty("primary", not running)

    def _on_env_tab_shown(self, index: int) -> None:
        """切回环境设置页时刷新四模型状态（index 0 恒为环境设置）。"""
        if index == 0:
            self._refresh_model_states()

    def _refresh_vram_estimates(self) -> None:
        """四卡片占用预估 + 顶部可用显存/内存总览（直观对照调节）。

        触发：combo 运行方式切换、模式切换、高级设置保存（ctx/并发
        变化）、设置页构建完成。
        """
        try:
            total, free = gpu_memory_info()
            overview = f"可用显存 <b>{free:.1f} / {total:.1f} GB</b>"
        except Exception:  # noqa: BLE001 - 无 GPU 信息显示占位
            overview = "可用显存 —"
        try:
            from hanhua.core.hardware_planner import probe_hardware
            ram = probe_hardware().ram_gb
            if ram:
                overview += f" · 内存 <b>{ram:.1f} GB</b>"
        except Exception:  # noqa: BLE001
            pass
        self.vram_overview.setText(overview)
        for kind in self.model_cards:
            self.model_cards[kind]["vram"].setText(
                self._vram_estimate_text(kind))

    def _vram_estimate_text(self, kind: str) -> str:
        """单卡预估：GPU 全层显存 / CPU 内存双值，当前选择加粗高亮。

        GPU 值 = 权重 + KV + 计算缓冲（llama.cpp 全层时 KV/计算都在
        显存）；CPU 值 = 权重 + KV（CPU 推理驻内存，无计算缓冲）。
        部分卸载（auto 中间态）介于两端之间，由 llama.cpp 实际分配。
        """
        card = self.model_cards.get(kind)
        if card is None:
            return "预估 —"
        try:
            spec = ModelRegistry(self.state.resource_dir).by_kind(kind)
            ctx = (int(self.state.api.local_context_size)
                   if kind == "translate" else spec.default_ctx)
            slots = (max(1, int(self.state.api.local_concurrency) or 1)
                     if kind == "translate" else 1)
            est = estimate_vram(spec.path, context_size=ctx, slots=slots)
        except (LocalModelError, OSError, ValueError, KeyError):
            return "预估 —"
        if not est:
            return "预估 —"
        if est.model_gb <= 0:
            return "预估 —（模型缺失）"
        gpu = est.total_gb
        cpu = est.model_gb + est.kv_gb
        choice = card["combo"].currentData() if card["combo"] else "auto"
        if choice == "cpu":
            gpu_html, cpu_html = f"{gpu:.1f}G", f"<b>{cpu:.1f}G</b>"
        else:
            gpu_html, cpu_html = f"<b>{gpu:.1f}G</b>", f"{cpu:.1f}G"
        return (f"预估 GPU <span style='color:{TOKENS.primary}'>"
                f"{gpu_html}</span>"
                f" / CPU <span style='color:#8b949e'>{cpu_html}</span>")

    def _toggle_model(self, kind: str) -> None:
        card = self.model_cards[kind]
        if self._probe_port(card["port"]):
            self._stop_model(kind)
        else:
            self._start_model(kind)

    def _start_model(self, kind: str) -> None:
        card = self.model_cards[kind]
        choice = card["combo"].currentData()
        card["status"].setText("状态：启动中…")
        card["btn"].setEnabled(False)
        worker = Worker(self._start_model_worker, kind, choice)
        worker.signals.finished.connect(self._on_model_started)
        worker.signals.error.connect(self._on_model_error)
        self._pool.start(worker)

    def _start_model_worker(self, kind: str, choice: str):
        """后台启动对应模型服务（与翻译/审核/重排/嵌入正式链路同源）。"""
        if kind == "translate":
            cfg = replace(self.state.api)
            cfg.mode = "local"
            cfg.local_gpu_layers = self._GPU_LAYERS_BY_CHOICE.get(choice, -1)
            runtime = self.state.local_model.ensure_running(cfg)
            return {"kind": kind, "port": runtime.port}
        if kind == "review":
            from hanhua.core.review_server import ReviewModelService
            svc = ReviewModelService(self.state.resource_dir)
            info = svc.ensure_running(gpu_choice=choice)
            return {"kind": kind, "port": int(info["port"])}
        if kind == "rerank":
            from hanhua.core.rerank_gate import RerankService
            svc = RerankService(self.state.resource_dir)
            info = svc.ensure_running()
            return {"kind": kind, "port": int(info["port"])}
        if kind == "embed":
            from hanhua.core.vector_store import EmbeddingService
            svc = EmbeddingService(self.state.resource_dir)
            info = svc.ensure_running()
            return {"kind": kind, "port": int(info["port"])}
        raise RuntimeError(f"未知模型：{kind}")

    def _on_model_started(self, result: dict):
        kind = result.get("kind", "") if isinstance(result, dict) else ""
        if not kind:
            return
        card = self.model_cards.get(kind)
        if card is None:
            return
        card["btn"].setEnabled(True)
        card["status"].setText(f"状态：运行中 · 端口 {card['port']}")
        card["btn"].setText("停止")
        card["btn"].setProperty("danger", True)
        self._refresh_env_status()
        Toast.show(self, f"{self._model_title(kind)} 已启动", "success")

    def _on_model_error(self, err: str):
        # Worker.error 信号不带 kind → 从启动中状态恢复（置灰按钮）
        for card in self.model_cards.values():
            if not card["btn"].isEnabled():
                card["btn"].setEnabled(True)
                card["status"].setText("状态：启动失败")
        self._refresh_env_status()
        Toast.show(self, f"模型启动失败：{err}", "error")

    def _stop_model(self, kind: str) -> None:
        card = self.model_cards[kind]
        card["status"].setText("状态：停止中…")
        card["btn"].setEnabled(False)
        worker = Worker(self._stop_model_worker, kind)
        worker.signals.finished.connect(self._on_model_stopped)
        worker.signals.error.connect(self._on_model_error)
        self._pool.start(worker)

    def _stop_model_worker(self, kind: str):
        from hanhua.core.runtime_coordinator import get_coordinator
        if kind == "translate":
            self.state.local_model.stop()
        elif kind == "review":
            from hanhua.core.review_server import ReviewModelService
            ReviewModelService(self.state.resource_dir).stop()
            get_coordinator(self.state.resource_dir).stop("review")
        elif kind == "rerank":
            from hanhua.core.rerank_gate import RerankService
            RerankService(self.state.resource_dir).stop()
        elif kind == "embed":
            from hanhua.core.vector_store import EmbeddingService
            EmbeddingService(self.state.resource_dir).stop()
        return {"kind": kind}

    def _on_model_stopped(self, result: dict):
        kind = result.get("kind", "")
        card = self.model_cards.get(kind)
        if card is not None:
            card["btn"].setEnabled(True)
            card["status"].setText("状态：未启动")
            card["btn"].setText("启动")
            card["btn"].setProperty("primary", True)
            card["btn"].setProperty("danger", False)
        self._refresh_env_status()
        if kind:
            Toast.show(self, f"{self._model_title(kind)} 已停止", "success")

    def _stop_all_models(self):
        self.stop_local_btn.setEnabled(False)
        self.local_status.setText("本地服务：正在停止全部模型…")
        worker = Worker(self._stop_all_worker)
        worker.signals.finished.connect(self._on_all_stopped)
        worker.signals.error.connect(self._on_local_stop_error)
        self._pool.start(worker)

    def _stop_all_worker(self):
        from hanhua.core.runtime_coordinator import stop_all_coordinators
        self.state.local_model.stop()
        return {"count": stop_all_coordinators()}

    def _on_all_stopped(self, _result):
        self.stop_local_btn.setEnabled(True)
        self.local_status.setText("本地服务：已全部停止")
        self._refresh_model_states()
        self.state.settingsChanged.emit()
        Toast.show(self, "全部本地模型已停止", "success")

    def _refresh_env_status(self):
        """右列连接状态卡：汇总四个模型运行数。"""
        running = [k for k in self.model_cards
                   if self._probe_port(self.model_cards[k]["port"])]
        if not running:
            self.local_status.setText("本地服务：未启动")
        else:
            names = "、".join(self._model_title(k) for k in running)
            self.local_status.setText(f"本地服务：运行中 · {names}")
        total, free = 0.0, 0.0
        try:
            total, free = gpu_memory_info()
            self.status_vram.setText(f"{free:.1f} / {total:.1f} GB 可用")
        except Exception:  # noqa: BLE001 无 GPU 信息时显示占位
            pass
        self.state.settingsChanged.emit()

    # ── 字体设置（2026-08-14 从翻译服务表单拆出独立页） ────────────
    def _build_font_tab(self) -> QWidget:
        tab = QWidget()
        root = QHBoxLayout(tab)
        root.setContentsMargins(28, 24, 28, 18)
        root.setSpacing(24)

        left = QWidget()
        lay = QVBoxLayout(left)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        font_group = QGroupBox("中文字体档位")
        f_lay = QVBoxLayout(font_group)
        f_lay.setContentsMargins(16, 14, 16, 14)
        f_lay.setSpacing(10)
        self.font_thin = QRadioButton("细")
        self.font_medium = QRadioButton("中（推荐）")
        self.font_heavy = QRadioButton("粗")
        for r in (self.font_thin, self.font_medium, self.font_heavy):
            r.setMinimumHeight(38)
            r.setMinimumWidth(200)
            f_lay.addWidget(r)
        hint = QLabel("写回时 TMP 字体按所选档位替换"
                      "（思源黑体 SDF：细 / 中 / 粗）")
        hint.setProperty("class", "subtitle")
        hint.setWordWrap(True)
        f_lay.addWidget(hint)
        self.font_save_btn = QPushButton("保存字体档位")
        self.font_save_btn.setProperty("primary", True)
        self.font_save_btn.setMinimumHeight(40)
        f_lay.addWidget(self.font_save_btn)
        lay.addWidget(font_group)
        lay.addStretch(1)
        root.addWidget(left, 4)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(10)
        head = QLabel("字体替换说明")
        head.setProperty("class", "pageTitle")
        font_hint = QLabel(
            "社区方案（XUnity）遇到的口口乱码，本工具走「替换字体 + "
            "完整性验证」链：写入游戏的字体需通过逐码点验证（所需字形"
            " → 字符表 → 字形表 → 图集 → 回退链），缺失码点如实报告"
            "而非静默替换——防止「汉化了但全是口口」的假成功。\n\n"
            "档位影响显示粗细：思源黑体细 / 中 / 粗三档 SDF，"
            "写回时按所选档位替换 TMP 字体。")
        font_hint.setProperty("class", "subtitle")
        font_hint.setWordWrap(True)
        right_lay.addWidget(head)
        right_lay.addWidget(font_hint)
        right_lay.addStretch(1)
        root.addWidget(right, 6)

        self._load_font_weight_ui()
        self.font_save_btn.clicked.connect(self._save_font_weight)
        return tab

    def _load_font_weight_ui(self):
        weight = getattr(self.state.settings.font, "weight", "medium")
        (self.font_thin if weight == "thin"
         else self.font_heavy if weight == "heavy"
         else self.font_medium).setChecked(True)

    def _save_font_weight(self):
        cfg = replace(self.state.settings.font)
        if self.font_thin.isChecked():
            cfg.weight = "thin"
        elif self.font_heavy.isChecked():
            cfg.weight = "heavy"
        else:
            cfg.weight = "medium"
        self.state.settings.font = cfg
        self.state.settings.save()
        self.state.settingsChanged.emit()
        Toast.show(self, "字体设置已保存，写回时按所选档位替换字体", "success")

    def _load_api_ui(self):
        api = self.state.api
        mode_idx = self.backend_mode.findData(api.mode)
        self.backend_mode.setCurrentIndex(max(0, mode_idx))
        idx = self.api_provider.findData(api.provider)
        self.api_provider.setCurrentIndex(max(0, idx))
        self.api_url.setText(api.base_url)
        self.api_key.setText(api.api_key)
        self.api_model.setText(api.model)
        self.local_concurrency.setCurrentIndex(max(
            0, self.local_concurrency.findData(int(api.local_concurrency))))
        self.local_ctx.setCurrentIndex(max(
            0, self.local_ctx.findData(int(api.local_context_size))))
        self.local_batch.setCurrentIndex(max(
            0, self.local_batch.findData(int(api.local_batch_size))))
        self._refresh_vram()

    def _sync_backend_mode(self):
        """模式切换：本地 → 显示四模型卡片，隐藏 API 表单；
        在线 API → 反之。高级设置独立 Tab 联动置灰。"""
        local = self.backend_mode.currentData() == "local"
        self.mode_local_widget.setVisible(local)
        self.mode_api_widget.setVisible(not local)
        self.stop_local_btn.setEnabled(local)
        # 高级设置独立 Tab：本地模式可调，API 模式置灰并提示
        for widget in (self.local_concurrency, self.local_ctx, self.local_batch,
                       self.advanced_save_btn):
            widget.setEnabled(local)
        self.advanced_mode_hint.setVisible(not local)
        self.test_btn.setText("启动并测试" if local else "测试连接")
        self.env_hint.setText(
            "本地模式：四模型全部离线运行，数据不出本机。"
            "「自动」优先 GPU，显存放不下时自动把部分层分到 CPU；"
            "「GPU」强制全层用显存，「CPU」则只走处理器。\n\n"
            "在线 API：填写 Base URL / Key / 模型后「测试连接」验证。"
            "切换回本地模式后，API 配置不参与运行。"
            if local else
            "在线 API 模式：翻译与审核走云端模型"
            "（OpenAI 兼容 / Anthropic 原生）。\n\n"
            "本地四模型卡片在切换回「本地 llama.cpp」后可用；"
            "在线模式下已启动的本地模型不会被自动停止。")
        self._refresh_vram()

    # ── 高级设置（本地模型） ──
    def _build_advanced_tab(self) -> QWidget:
        self.advanced_tab = QWidget()
        tab = self.advanced_tab
        root = QHBoxLayout(tab)
        root.setContentsMargins(28, 24, 28, 18)
        root.setSpacing(24)

        # 左 4：调节项表单（下拉选择，只能点选不能乱输）
        left = QWidget()
        form = QFormLayout(left)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(14)
        self.local_concurrency = QComboBox()
        for text, data in (("自动 · 单槽（推荐）", 0), ("1 槽", 1),
                           ("2 槽", 2), ("3 槽", 3), ("4 槽", 4)):
            self.local_concurrency.addItem(text, data)
        self.local_ctx = QComboBox()
        for tokens in (2048, 4096, 6144, 8192):
            self.local_ctx.addItem(f"{tokens} tokens", tokens)
        self.local_batch = QComboBox()
        for count in (1, 2, 4, 8, 16, 32):
            self.local_batch.addItem(f"{count} 条", count)
        for box in (self.local_concurrency, self.local_ctx, self.local_batch):
            box.setMinimumHeight(44)
        form.addRow("并发槽位", self.local_concurrency)
        form.addRow("上下文长度", self.local_ctx)
        form.addRow("每批条数", self.local_batch)
        form.addRow("", QLabel(""))
        self.vram_label = QLabel("显存预估：—")
        self.vram_label.setWordWrap(True)
        form.addRow("显存预估", self.vram_label)
        self.speed_label = QLabel("估算速度：—")
        self.speed_label.setWordWrap(True)
        form.addRow("估算速度", self.speed_label)
        row = QHBoxLayout()
        self.advanced_save_btn = QPushButton("保存高级设置")
        self.advanced_save_btn.setProperty("primary", True)
        self.advanced_save_btn.setMinimumHeight(44)
        row.addWidget(self.advanced_save_btn)
        row.addStretch(1)
        form.addRow("", row)
        root.addWidget(left, 4)

        # 右 6：说明
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(10)
        head = QLabel("说明")
        head.setProperty("class", "pageTitle")
        self.advanced_mode_hint = QLabel(
            "以下参数仅对「本地 Hy-MT2（llama.cpp）」后端生效，"
            "当前为在线 API 模式，调整将被忽略。")
        self.advanced_mode_hint.setProperty("class", "subtitle")
        self.advanced_mode_hint.setWordWrap(True)
        hint = QLabel(
            "并发槽位：同时开几条翻译线路。开得越多，占的显存越多；"
            "显卡一次只能干一件事，所以速度并不会成倍变快，"
            "反而容易把显存挤爆 —— 用「自动」最省心。\n\n"
            "上下文长度：模型一次能记住的文本量。太短了长句子"
            "记不住会翻译错，太长也没必要。\n\n"
            "每批条数：一次打包翻译多少条文本。打包多，每条分到的"
            "翻译空间就少，长文本容易出问题。\n\n"
            "显存预估是参考值，实际占用以运行时为准。")
        hint.setProperty("class", "subtitle")
        hint.setWordWrap(True)
        right_lay.addWidget(head)
        right_lay.addWidget(self.advanced_mode_hint)
        right_lay.addSpacing(4)
        right_lay.addWidget(hint)
        right_lay.addStretch(1)
        root.addWidget(right, 6)

        self.local_concurrency.currentIndexChanged.connect(self._refresh_vram)
        self.local_ctx.currentIndexChanged.connect(self._refresh_vram)
        self.advanced_save_btn.clicked.connect(self._save_advanced)
        return tab

    def _save_advanced(self):
        self._commit_api_config(self._config_from_form())
        Toast.show(self, "高级设置已保存，下次翻译启动生效", "success")

    def _refresh_vram(self):
        """按并发槽位/上下文重算显存预估并着色（<70% 绿 / <90% 黄 / ≥90% 红），
        同步刷新估算速度。速度模型：单槽基线约 40 条/分（短条约 1.5 秒），
        多槽只允许 prompt 流水线重叠（GPU 串行），提升递减。"""
        slots = int(self.local_concurrency.currentData() or 1)  # 0 = 自动 = 单槽
        rate = _ESTIMATED_RATE_PER_SLOT * (1 + 0.25 * (slots - 1))
        self.speed_label.setText(
            f"估算速度：约 <b>{rate:.0f} 条/分</b>"
            f"（{slots} 槽 · 每条约 {60 / rate:.1f} 秒，仅供参考）")
        try:
            # 与翻译启动（LocalModelManager）同一搜索根：模型在程序目录 models/
            model = discover_model(
                self.state.api.local_model_path, self.state.resource_dir)
        except LocalModelError as exc:
            self.vram_label.setText(f"显存预估：{exc}")
            self.vram_label.setStyleSheet("")
            return
        est = estimate_vram(
            model, context_size=int(self.local_ctx.currentData()), slots=slots)
        info = gpu_memory_info()
        kv_part = (f"＋ KV {est.kv_gb:.2f}G"
                   f"（{est.kv_per_slot_gb:.2f}G/槽 × {slots}）")
        head = f"模型 {est.model_gb:.2f}G {kv_part} ＋ 计算 {est.compute_gb:.2f}G"
        if info:
            _total, free = info
            ratio = est.total_gb / free
            color = ("#22c55e" if ratio < 0.7
                     else "#f59e0b" if ratio < 0.9 else "#ef4444")
            self.vram_label.setText(
                f"显存预估：{head} ≈ <b>{est.total_gb:.2f}G</b> / 可用 {free:.2f}G")
            self.vram_label.setStyleSheet(f"color: {color};")
        else:
            self.vram_label.setText(f"显存预估：{head} ≈ {est.total_gb:.2f}G")
            self.vram_label.setStyleSheet("")

    def _on_local_stop_error(self, err: str):
        self.stop_local_btn.setEnabled(True)
        self.local_status.setText("本地服务：停止失败")
        self._refresh_model_states()
        Toast.show(self, f"停止本地模型失败：{err}", "error")

    def _config_from_form(self):
        api = replace(self.state.api)
        api.mode = self.backend_mode.currentData()
        api.provider = self.api_provider.currentData()
        api.base_url = self.api_url.text().strip()
        api.api_key = self.api_key.text().strip()
        api.model = self.api_model.text().strip()
        api.local_concurrency = int(self.local_concurrency.currentData())
        api.local_context_size = int(self.local_ctx.currentData())
        api.local_batch_size = int(self.local_batch.currentData())
        return api

    def _commit_api_config(self, config) -> None:
        self.state.settings.api = replace(config)
        self.state.settings.save()
        self.state.settingsChanged.emit()

    def _save_api(self):
        self._commit_api_config(self._config_from_form())
        Toast.show(self, "翻译后端配置已保存", "success")

    def test_connection(self):
        local = self.backend_mode.currentData() == "local"
        if (not local and not (
                self.api_url.text().strip() and self.api_key.text().strip()
                and self.api_model.text().strip())):
            Toast.show(self, "请先填写 URL / Key / 模型", "warning")
            return
        self.test_btn.setEnabled(False)
        self.test_btn.setText("启动中…" if local else "测试中…")
        if local:
            self.save_btn.setEnabled(False)
        cfg = self._config_from_form()
        self._pending_test_config = cfg
        if local:
            worker = Worker(self._test_local_worker, cfg)
        else:
            worker = Worker(
                self._test_worker, cfg.provider, cfg.base_url,
                cfg.api_key, cfg.model)
        worker.signals.finished.connect(self._on_test_ok)
        worker.signals.error.connect(self._on_test_err)
        self._pool.start(worker)

    def _test_local_worker(self, config):
        runtime = self.state.local_model.ensure_running(config)
        runtime_config = replace(
            config, base_url=runtime.endpoint, api_key=runtime.api_key,
            model=runtime.model, max_tokens=64,
        )
        client = create_client(runtime_config)
        content, _ = client.chat(
            "你是翻译模型。",
            [{"role": "user", "content": (
                "将以下文本翻译为中文，注意只需要输出翻译后的结果，"
                "不要额外解释：\n\nHello") }],
        )
        return {"reply": content[:120], "runtime": runtime}

    @staticmethod
    def _test_worker(provider, base_url, api_key, model):
        from hanhua.core.models import ApiConfig
        cfg = ApiConfig(provider=provider, base_url=base_url, api_key=api_key,
                        model=model, max_tokens=16)
        client = create_client(cfg)
        content, _ = client.chat("你是连接测试助手", [{"role": "user", "content": "只回复两个字：正常"}])
        return content[:120]

    def _on_test_ok(self, reply):
        tested_config = self._pending_test_config
        self._pending_test_config = None
        if tested_config is not None:
            self._commit_api_config(tested_config)
        self.test_btn.setEnabled(True)
        local = isinstance(reply, dict)
        self.test_btn.setText("启动并测试" if local else "测试连接")
        if local:
            runtime = reply["runtime"]
            self.save_btn.setEnabled(True)
            self.local_status.setText(
                f"本地服务：已启动 · {runtime.backend.upper()} · 端口 {runtime.port}")
            reply_text = reply["reply"]
        else:
            reply_text = reply
        self.status_test.setText(f"成功 · {reply_text[:24]}…")
        Toast.show(self, f"连接成功 · 模型返回：{reply_text}", "success")

    def _on_test_err(self, err: str):
        self._pending_test_config = None
        self.test_btn.setEnabled(True)
        local = self.backend_mode.currentData() == "local"
        self.test_btn.setText("启动并测试" if local else "测试连接")
        if local:
            self.save_btn.setEnabled(True)
            self.local_status.setText("本地服务：启动失败")
        Toast.show(self, f"连接失败：{err}", "error")

    # ── 术语表（全局） ──
    def _build_glossary_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.addWidget(QLabel("术语表会注入翻译提示词，翻译时必须严格使用。"))
        head.addStretch(1)
        self.glossary_filter = QComboBox()
        self.glossary_filter.addItems(["全部"] + CATEGORIES)
        self.glossary_filter.setFixedWidth(110)
        self.add_btn = QPushButton("＋ 添加")
        self.del_btn = QPushButton("删除选中")
        self.del_btn.setProperty("danger", True)
        head.addWidget(self.glossary_filter)
        head.addWidget(self.add_btn)
        head.addWidget(self.del_btn)
        lay.addLayout(head)

        self.glossary_table = QTableWidget(0, 5)
        self.glossary_table.setHorizontalHeaderLabels(
            ["术语", "译文", "类别", "状态", "备注"])
        self.glossary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.glossary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.glossary_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.glossary_table.horizontalHeader().resizeSection(2, 90)
        self.glossary_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.glossary_table.horizontalHeader().resizeSection(3, 72)
        self.glossary_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.glossary_table.verticalHeader().setVisible(False)
        self.glossary_table.setSelectionBehavior(QTableWidget.SelectRows)
        lay.addWidget(self.glossary_table, 1)

        hint = QLabel("示例：Aria → 艾莉亚（人名）｜Vale → 幽谷（地名）。编辑后立即保存。")
        hint.setProperty("class", "subtitle")
        lay.addWidget(hint)

        self.add_btn.clicked.connect(self._glossary_add)
        self.del_btn.clicked.connect(self._glossary_delete)
        self.glossary_filter.currentTextChanged.connect(self._glossary_filter)
        self.glossary_table.cellChanged.connect(self._glossary_cell_changed)
        self.state.projectOpened.connect(lambda _p: self._ensure_glossary())
        self._ensure_glossary()
        return tab

    def _ensure_glossary(self):
        if self._glossary is None:
            self._glossary = GlossaryStore(self.state.app_dir / "glossary.db")
            self._glossary.init_schema()
        self._glossary_reload()

    def _glossary_reload(self):
        rows = self._glossary.list_all()
        self._glossary_loading = True
        self.glossary_table.setRowCount(0)
        for r in rows:
            self._glossary_row(r, CATEGORIES.index(r["category"]) if r["category"] in CATEGORIES else 0)
        self._glossary_loading = False

    def _glossary_row(self, data: dict, cat_idx: int):
        row = self.glossary_table.rowCount()
        self.glossary_table.insertRow(row)
        term = QTableWidgetItem(data["term"])
        translation = QTableWidgetItem(data["translation"])
        cat = QTableWidgetItem(data["category"])
        cat.setData(Qt.UserRole, data["term"])   # 记录原术语用于更新
        # 状态列：active=强制生效；candidate=候选（仅参考不强制，跨游戏
        # 复现才升级）。候选行置灰提示（术语表内容排查可见性，2026-08-13）
        status = QTableWidgetItem(
            "生效" if data.get("status", "active") == "active" else "候选")
        status.setFlags(Qt.ItemIsEnabled)         # 状态不可编辑
        note = QTableWidgetItem(data["note"])
        self.glossary_table.setItem(row, 0, term)
        self.glossary_table.setItem(row, 1, translation)
        self.glossary_table.setItem(row, 2, cat)
        self.glossary_table.setItem(row, 3, status)
        self.glossary_table.setItem(row, 4, note)
        if data.get("status", "active") != "active":
            for col in range(5):
                item = self.glossary_table.item(row, col)
                item.setForeground(QBrush(QColor("#999999")))
        return row

    def _glossary_add(self):
        if self._glossary is None:
            self._ensure_glossary()
        self._glossary_loading = True
        row = self._glossary_row({"term": "", "translation": "", "category": "术语", "note": ""}, 0)
        self._glossary_loading = False
        self.glossary_table.setCurrentCell(row, 0)
        self.glossary_table.editItem(self.glossary_table.item(row, 0))

    def _glossary_cell_changed(self, row: int, col: int):
        if self._glossary_loading or self._glossary is None:
            return
        term_item = self.glossary_table.item(row, 0)
        term = term_item.text().strip() if term_item else ""
        if not term:
            return
        translation = self.glossary_table.item(row, 1).text().strip() \
            if self.glossary_table.item(row, 1) else ""
        cat_item = self.glossary_table.item(row, 2)
        category = cat_item.text() if cat_item else "术语"
        note = self.glossary_table.item(row, 4).text() if self.glossary_table.item(row, 4) else ""
        old_term = cat_item.data(Qt.UserRole) if cat_item else None
        if old_term:
            self._glossary.update(term, translation, category, note)
        else:
            self._glossary.add(term, translation, category, note)
            self.glossary_table.item(row, 2).setData(Qt.UserRole, term)
        Toast.show(self, f"术语「{term}」已保存", "success")
        # P2：同源异译冲突检测——大小写/空白/标点变体同源但译名不同，
        # 会导致模型对同一原文无所适从（prompt 里出现两个译法）
        conflicts = self._glossary.detect_conflicts()
        for conflict in conflicts:
            group = " / ".join(
                f"「{r['term']}→{r['translation']}」" for r in conflict["rows"])
            Toast.show(
                self,
                f"术语冲突：{group} 同源但译名不同，请统一译名", "warning")

    def _glossary_delete(self):
        if self._glossary is None:
            return
        rows = sorted({i.row() for i in self.glossary_table.selectedIndexes()}, reverse=True)
        if not rows:
            Toast.show(self, "请先选中要删除的行", "warning")
            return
        for row in rows:
            term_item = self.glossary_table.item(row, 0)
            if term_item:
                self._glossary.delete(term_item.text().strip())
            self.glossary_table.removeRow(row)
        Toast.show(self, "已删除")

    def _glossary_filter(self, text: str):
        if self._glossary is None:
            return
        for row in range(self.glossary_table.rowCount()):
            cat = self.glossary_table.item(row, 2)
            self.glossary_table.setRowHidden(
                row, text != "全部" and (not cat or cat.text() != text))
