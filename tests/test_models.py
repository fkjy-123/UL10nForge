from hanhua.core.models import TextEntry, GameProfile, ApiConfig
from hanhua.core.settings import SettingsStore


def test_textentry_defaults():
    e = TextEntry(file_id="f1", key_path="a/b", original="Hello")
    assert e.status == "pending"
    assert e.translation == ""
    assert e.locked is False


def test_profile_and_api_defaults():
    p = GameProfile(game_name="Test")
    assert p.target_lang == "zh-CN"
    assert p.source_lang == "auto"
    c = ApiConfig(provider="openai", base_url="", api_key="", model="")
    assert c.concurrency == 6
    assert c.batch_size == 40


def test_local_model_config_defaults_and_roundtrip(tmp_path):
    config = ApiConfig()
    assert config.mode == "api"
    assert config.local_model_path == ""
    assert config.local_server_path == ""
    assert config.local_gpu_layers == -1
    assert config.local_context_size == 8192
    assert config.local_port == 0
    assert config.local_keep_alive is True

    store = SettingsStore(tmp_path / "settings.json")
    store.api.mode = "local"
    store.api.local_model_path = "models/test.gguf"
    store.api.local_server_path = "runtime/llama/llama-server.exe"
    store.api.local_gpu_layers = 0
    store.api.local_context_size = 8192
    store.api.local_port = 18080
    store.api.local_keep_alive = False
    store.save()

    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.api == store.api


# ── 四模型运行方式（环境设置页 model_runtime 持久化） ───────────

def test_model_runtime_choice_defaults_to_auto(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    for kind in ("translate", "review", "rerank", "embed"):
        assert store.model_runtime_choice(kind) == "auto"


def test_model_runtime_set_and_roundtrip(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.set_model_runtime("translate", "gpu")
    store.set_model_runtime("review", "cpu")
    store.save()

    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.model_runtime_choice("translate") == "gpu"
    assert loaded.model_runtime_choice("review") == "cpu"
    assert loaded.model_runtime_choice("embed") == "auto"


def test_model_runtime_auto_pops_entry(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.set_model_runtime("translate", "gpu")
    assert "translate" in store.model_runtime
    store.set_model_runtime("translate", "auto")
    assert "translate" not in store.model_runtime
    assert store.model_runtime_choice("translate") == "auto"


def test_model_runtime_fixed_cpu_kinds_ignored(tmp_path):
    """rerank/embed 固定 CPU（fixed_cpu 硬约束）：写入被忽略，恒为 auto。"""
    store = SettingsStore(tmp_path / "settings.json")
    store.set_model_runtime("rerank", "gpu")
    store.set_model_runtime("embed", "cpu")
    store.save()
    assert store.model_runtime == {}
    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.model_runtime_choice("rerank") == "auto"
    assert loaded.model_runtime_choice("embed") == "auto"


def test_model_runtime_ignores_unknown_kind_and_choice(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.set_model_runtime("nonsense", "gpu")     # 未知 kind 忽略
    store.set_model_runtime("translate", "turbo")  # 未知取值忽略
    assert store.model_runtime == {}
    # load 端同样过滤（手写脏 JSON）
    (tmp_path / "settings.json").write_text(
        '{"model_runtime": {"translate": "gpu", "review": "banana", '
        '"evil": "cpu"}}', encoding="utf-8")
    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.model_runtime_choice("translate") == "gpu"
    assert loaded.model_runtime_choice("review") == "auto"


# ── 在线 API per-kind 配置（2026-08-14：翻译/审核各自云端端点） ──

def test_api_configs_roundtrip_per_kind(tmp_path):
    """翻译与审核各自的 API 配置独立持久化、互不串扰。"""
    store = SettingsStore(tmp_path / "settings.json")
    store.api.mode = "api"
    store.set_api_config(
        "translate", provider="openai", base_url="https://a/v1",
        api_key="k-t", model="gpt-4o")
    store.set_api_config(
        "review", provider="anthropic", base_url="https://b",
        api_key="k-r", model="claude-sonnet-4")
    store.save()

    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.api_config("translate").base_url == "https://a/v1"
    assert loaded.api_config("translate").api_key == "k-t"
    assert loaded.api_config("review").provider == "anthropic"
    assert loaded.api_config("review").model == "claude-sonnet-4"
    # 互不串扰：改 review 不动 translate
    assert loaded.api_config("translate").model == "gpt-4o"


def test_api_configs_translate_aliases_self_api(tmp_path):
    """translate 配置与 self.api 恒同对象——翻译消费链零改动。"""
    store = SettingsStore(tmp_path / "settings.json")
    store.api.base_url = "https://x/v1"
    store.save()
    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.api_config("translate") is loaded.api
    assert loaded.api_config("translate").base_url == "https://x/v1"
    # 经 set_api_config 写入 → self.api 同步可见
    loaded.set_api_config("translate", model="gpt-4o-mini")
    assert loaded.api.model == "gpt-4o-mini"


def test_api_configs_legacy_top_level_api_migrates_to_translate(tmp_path):
    """旧版 JSON 只有顶层 api 字段 → 迁移为 translate 配置（兼容老版本）。"""
    (tmp_path / "settings.json").write_text(
        '{"api": {"mode": "api", "provider": "openai", '
        '"base_url": "https://old/v1", "api_key": "k-old", '
        '"model": "gpt-4o"}}', encoding="utf-8")
    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert loaded.api_config("translate").base_url == "https://old/v1"
    assert loaded.api_config("translate").model == "gpt-4o"
    # 新字段不存在时 review 为空配置（不在线，走本地）
    assert loaded.api_config("review").base_url == ""
    # 新字段存在时优先新字段（用户已在四卡配置过）
    (tmp_path / "settings.json").write_text(
        '{"api": {"base_url": "https://old/v1"}, "api_configs": '
        '{"translate": {"base_url": "https://new/v1", "model": "gpt-5"}}}',
        encoding="utf-8")
    loaded2 = SettingsStore(tmp_path / "settings.json")
    loaded2.load()
    assert loaded2.api_config("translate").base_url == "https://new/v1"


def test_api_configs_rerank_embed_not_provided(tmp_path):
    """重排/检索不提供在线 API（用户拍板恒本地）——api_configs 只有
    翻译/审核两个 kind，旧 JSON 里的 embed/rerank 配置被忽略。"""
    (tmp_path / "settings.json").write_text(
        '{"api_configs": {"translate": {"base_url": "https://t/v1"}, '
        '"review": {"base_url": "https://r/v1"}, '
        '"embed": {"base_url": "https://e/v1"}, '
        '"rerank": {"base_url": "https://rr/v1"}}}', encoding="utf-8")
    loaded = SettingsStore(tmp_path / "settings.json")
    loaded.load()
    assert set(loaded.api_configs) == {"translate", "review"}
    assert loaded.api_config("embed").base_url == ""
    assert loaded.api_config("rerank").base_url == ""
