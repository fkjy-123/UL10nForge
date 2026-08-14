"""「翻译」页（#11）测试：轻量翻译应用——模型信息、可编辑提示词、
后台翻译、历史落盘回填、长文本分块、导航接入。"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from hanhua.core.agent_memory import AgentMemory
from hanhua.core.glossary import GlossaryStore
from hanhua.core.knowledge import KnowledgeBase
from hanhua.core.settings import SettingsStore
from hanhua.ui.app_state import AppState
from hanhua.ui.main_window import MainWindow, PAGES
from hanhua.ui.pages.translate_tool_page import (
    TranslateToolPage,
    _BLOCK_CHARS,
)
from conftest import await_reload


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Window:
    def navigate(self, _page):
        pass


def _state(tmp_path: Path) -> AppState:
    settings = SettingsStore(tmp_path / "settings.json")
    settings.load()
    return AppState(tmp_path, settings)


class _FakeClient:
    """假翻译客户端：译文 = 原文前缀「译：」。"""

    def __init__(self, config=None):
        self.config = config
        self.calls = []

    def chat(self, system, messages):
        self.calls.append((system, messages))
        return "译：" + (messages[0]["content"] or ""), None


def _fake_client_factory(client):
    def factory(config, transport_factory=None):
        client.config = config
        return client
    return factory


def _run_until_idle(page, timeout_ms=8000):
    deadline = time.monotonic() + timeout_ms / 1000.0
    while page._running and time.monotonic() < deadline:
        QTest.qWait(10)
    assert not page._running, "翻译超时"


def test_tool_page_model_label_and_history_disabled(qapp, tmp_path):
    """未配置模型：提示去设置；无历史：下拉禁用。"""
    page = TranslateToolPage(_state(tmp_path), _Window())
    assert "未配置" in page.model_label.text()
    assert not page.history_combo.isEnabled()
    assert page.dst_edit.isReadOnly()
    # 默认提示词是游戏本地化角色（#10 精简版头部）
    assert "游戏本地化" in page.prompt_edit.toPlainText()


def test_tool_page_translate_and_history_persist(qapp, tmp_path, monkeypatch):
    """翻译 → 译文显示 + 历史落盘 json + 下拉可回填。"""
    client = _FakeClient()
    monkeypatch.setattr("hanhua.ui.pages.translate_tool_page.create_client",
                        _fake_client_factory(client))
    state = _state(tmp_path)
    state.settings.api.mode = "api"
    state.settings.api.base_url = "http://x"
    state.settings.api.api_key = "k"
    state.settings.api.model = "test-model"
    page = TranslateToolPage(state, _Window())
    page.src_edit.setPlainText("Hello world\nSecond line")
    page.translate_btn.click()
    _run_until_idle(page)
    await_reload(page)
    assert page.dst_edit.toPlainText() == "译：Hello world\nSecond line"
    assert client.calls, "必须调用翻译客户端"
    # 落盘
    history_path = Path(state.app_dir) / "quick_translate_history.json"
    data = json.loads(history_path.read_text(encoding="utf-8"))
    assert data[0]["src"] == "Hello world\nSecond line"
    assert data[0]["model"] == "test-model"
    assert page.history_combo.isEnabled()
    # 回填
    page.src_edit.clear()
    page.dst_edit.clear()
    page.history_combo.setCurrentIndex(0)
    page.history_combo.activated.emit(0)
    assert page.src_edit.toPlainText() == "Hello world\nSecond line"
    assert page.dst_edit.toPlainText() == "译：Hello world\nSecond line"


def test_tool_page_unconfigured_api_blocked(qapp, tmp_path, monkeypatch):
    """API 模式未配置 → 点翻译只提示，不调客户端。"""
    calls = []
    monkeypatch.setattr("hanhua.ui.pages.translate_tool_page.create_client",
                        lambda config, transport_factory=None: calls.append(1))
    page = TranslateToolPage(_state(tmp_path), _Window())
    page.src_edit.setPlainText("Hello")
    page.translate_btn.click()
    _run_until_idle(page)
    assert calls == []
    assert page.dst_edit.toPlainText() == ""
    assert "失败" not in page.status_label.text()


def test_tool_page_local_model_starts_service(qapp, tmp_path, monkeypatch):
    """本地模式：worker 先 ensure_running 再翻译（配置透传 endpoint）。"""
    class _FakeLocalModel:
        def ensure_running(self, config, cancellation_event=None):
            return type("Runtime", (), {
                "endpoint": "http://127.0.0.1:9999",
                "api_key": "local-key",
                "model": "local-model",
            })()

    client = _FakeClient()
    monkeypatch.setattr("hanhua.ui.pages.translate_tool_page.create_client",
                        _fake_client_factory(client))
    state = _state(tmp_path)
    state.settings.api.mode = "local"
    state.settings.api.local_model_path = "D:/models/hy-mt2.gguf"
    page = TranslateToolPage(state, _Window())
    page.src_edit.setPlainText("Hello")
    # 直接测后台函数（等价 worker 内路径）
    blocks = TranslateToolPage._split_blocks("Hello")
    out = TranslateToolPage._run_blocks(
        state.settings.api, page.prompt_edit.toPlainText(), blocks,
        _FakeLocalModel(), Path(tmp_path))
    assert out == ["译：Hello"]
    assert client.config.base_url == "http://127.0.0.1:9999"
    assert client.config.model == "local-model"


def test_tool_page_local_auto_discover_model(qapp, tmp_path, monkeypatch):
    """本地模式自动发现：settings 不存模型路径也能翻译（模型已启动场景）。"""
    import struct

    models_dir = tmp_path / "models"
    models_dir.mkdir()
    header = b"GGUF" + struct.pack("<IQQ", 3, 1, 1)
    (models_dir / "Hy-MT2-1.8B-Q6_K.gguf").write_bytes(
        header + b"\x00" * (1024 * 1024 - len(header)))

    class _FakeLocalModel:
        def ensure_running(self, config, cancellation_event=None):
            return type("Runtime", (), {
                "endpoint": "http://127.0.0.1:9999",
                "api_key": "local-key",
                "model": "Hy-MT2-1.8B-Q6_K",
            })()

    client = _FakeClient()
    monkeypatch.setattr("hanhua.ui.pages.translate_tool_page.create_client",
                        _fake_client_factory(client))
    state = _state(tmp_path)
    state.settings.api.mode = "local"        # local_model_path 保持空
    state.local_model = _FakeLocalModel()
    page = TranslateToolPage(state, _Window())
    # 标签按自动发现显示模型名，不再误报「未配置」
    assert "Hy-MT2-1.8B" in page.model_label.text()
    page.src_edit.setPlainText("Hello")
    page.translate_btn.click()
    _run_until_idle(page)
    await_reload(page)
    assert page.dst_edit.toPlainText() == "译：Hello"
    assert client.calls, "必须调用翻译客户端"
    history_path = Path(state.app_dir) / "quick_translate_history.json"
    data = json.loads(history_path.read_text(encoding="utf-8"))
    assert data[0]["model"] == "Hy-MT2-1.8B-Q6_K"


def test_tool_page_warning_dedup_on_repeated_click(qapp, tmp_path, monkeypatch):
    """连点翻译：失败提示只弹一条，不叠加多条消息。"""
    from hanhua.ui.widgets import Toast
    calls = []
    monkeypatch.setattr("hanhua.ui.pages.translate_tool_page.create_client",
                        lambda config, transport_factory=None: calls.append(1))
    page = TranslateToolPage(_state(tmp_path), _Window())
    page.src_edit.setPlainText("Hello")
    base = len(Toast._stack)
    page.translate_btn.click()
    QTest.qWait(50)
    page.translate_btn.click()
    QTest.qWait(50)
    assert len(Toast._stack) - base == 1, "连点应只弹一条提示"
    assert calls == []


def test_tool_page_split_blocks_keeps_lines():
    """长文本按行分块（行不拆分，块 ≤ _BLOCK_CHARS）。"""
    lines = ["x" * 500 + str(i) for i in range(20)]
    text = "\n".join(lines)
    assert len(text) > _BLOCK_CHARS * 3
    blocks = TranslateToolPage._split_blocks(text)
    assert len(blocks) > 1
    assert "\n".join(blocks) == text  # 行不拆分，块间换行拼接 = 原文本
    for block in blocks:
        assert len(block) <= _BLOCK_CHARS
    # 短文本不分块
    assert TranslateToolPage._split_blocks("short") == ["short"]


def test_tool_page_reset_prompt_uses_project_profile(qapp, tmp_path):
    """「使用当前游戏档案提示词」按档案（游戏名/个性化要求）生成。"""
    state = _state(tmp_path)
    page = TranslateToolPage(state, _Window())
    page.prompt_edit.setPlainText("自定义")
    # 无项目 → 档案为空，重置为默认角色提示词
    page._reset_prompt()
    assert "游戏本地化" in page.prompt_edit.toPlainText()
    # 模拟项目档案带游戏名与个性化要求
    profile = type("Profile", (), {
        "game_name": "DemoGame", "genre": "RPG",
        "world_setting": "赛博朋克", "tone_notes": "",
        "style_guide": "", "prompt_style": "专名音译",
        "source_lang": "en", "target_lang": "zh-CN",
    })()
    state.project = type("Project", (), {"profile": profile})()
    page._reset_prompt()
    text = page.prompt_edit.toPlainText()
    assert "DemoGame" in text
    assert "专名音译" in text


def test_main_window_has_translate_tool_page(qapp, tmp_path):
    """导航 5 项：翻译页可程序化进入。"""
    window = MainWindow(_state(tmp_path))
    assert "translate_tool" in PAGES
    assert window.pages["translate_tool"] is not None
    window.navigate("translate_tool")
    assert window.current_page() == "translate_tool"


# ── #38/#39（2026-08-14 用户实证）：工具页默认提示词注入 ──────────

def test_default_prompt_injects_glossary_knowledge_memory(qapp, tmp_path):
    """工具页默认提示词与批量翻译同源注入术语库/知识库/经验记忆。

    2026-08-14 用户实证（play 仍译「播放」、hello/hi 回显原文）：
    此前 _default_prompt 只注入档案（build_system_prompt(profile, [])），
    沉淀词对在工具页完全不生效。现注入 GlossaryStore + KnowledgeBase
    + AgentMemory.reference_pairs，并追加问候语必须译中文的补充规则。
    """
    # 种数据：play→开始（术语库）、text 域规则（知识库）、
    # Start game→开始游戏（经验记忆，evidence 2 达 ACTIVE_MIN_EVIDENCE
    # 晋升 active；组合词——单字词 hello 在 _PROTECTED_SINGLE_WORDS
    # 被过滤是 play 污染事故后的设计行为，问候语由补充规则兜底）
    glossary = GlossaryStore(tmp_path / "glossary.db")
    glossary.init_schema()
    glossary.add("play", "开始", category="术语")
    glossary.close()
    knowledge = KnowledgeBase(tmp_path / "knowledge.db")
    knowledge.store.upsert(domain="text", kind="规则", pattern="play",
                           map_to="开始", source="manual", confidence=1.0)
    knowledge.close()
    agent = AgentMemory(tmp_path / "agent_memory.db")
    agent.init_schema()
    agent.propose("Start game", "开始游戏", game="t", type_="phrase")
    agent.propose("Start game", "开始游戏", game="t", type_="phrase")
    agent.close()

    page = TranslateToolPage(_state(tmp_path), _Window())
    prompt = page._default_prompt()
    # 术语注入（play→开始 是用户实证的污染词对）
    assert "play" in prompt
    assert "开始" in prompt
    # 知识库规则行（map_to 有值才注入）
    assert "应译为" in prompt
    # 经验记忆参考对（→ 分隔行）
    assert "Start game → 开始游戏" in prompt
    # 问候语必须译中文（#39：hello/hi 回显原文的兜底指令）
    assert "问候语" in prompt
    assert "你好/嗨/嘿" in prompt
    # 参考译例优先级说明（与术语表冲突时以术语表为准）
    assert "与术语表冲突时" in prompt


def test_default_prompt_greeting_rule_always_present(qapp, tmp_path):
    """空库（无任何沉淀）时补充规则与参考译例说明仍恒在。"""
    page = TranslateToolPage(_state(tmp_path), _Window())
    prompt = page._default_prompt()
    assert "问候语" in prompt
    assert "禁止原样回显英文" in prompt


def test_default_prompt_token_budget_limits_injection(qapp, tmp_path):
    """#42（2026-08-14 用户实证「19987 token 超过上下文限制」）：全量
    注入跨游戏积累的词对会撑爆 llama-server ctx——限量 + 预算兜底后
    任意库规模下 prompt 估算不超预算，且只注入最近词对。"""
    from hanhua.ui.pages.translate_tool_page import (
        _SYSTEM_TOKEN_BUDGET, _estimate_prompt_tokens)
    # 大库：300 术语 + 200 记忆（evidence 2 晋升 active）
    glossary = GlossaryStore(tmp_path / "glossary.db")
    glossary.init_schema()
    for i in range(300):
        glossary.add(f"term{i}", f"译名{i}")
    glossary.close()
    agent = AgentMemory(tmp_path / "agent_memory.db")
    agent.init_schema()
    for i in range(200):
        agent.propose(f"phrase {i}", f"译句{i}", game="t")
        agent.propose(f"phrase {i}", f"译句{i}", game="t")
    agent.close()
    page = TranslateToolPage(_state(tmp_path), _Window())
    prompt = page._default_prompt()
    assert _estimate_prompt_tokens(prompt) <= _SYSTEM_TOKEN_BUDGET
    # 限量生效：最近词对（term299）在，最早（term0）不在
    assert "term299 → 译名299" in prompt
    assert "term0 → 译名0" not in prompt
    # 记忆参考对同样限量注入（≤40 条；hits 排序无 tiebreak，
    # 只断言数量不断言具体条目）
    assert prompt.count("phrase ") <= 40
    assert prompt.count("phrase ") >= 30
