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
