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
