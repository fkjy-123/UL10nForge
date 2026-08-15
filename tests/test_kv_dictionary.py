"""KV 词典 TextAsset 测试（多语言词典分组 + 键保真，electric-trains 实证）。"""
from __future__ import annotations

from pathlib import Path

from hanhua.core.formats import apply_format_text
from hanhua.core.unity.extractor import (_dictionary_base_name,
                                         _dictionary_language,
                                         _english_score,
                                         _looks_like_kv_dictionary,
                                         _textasset_entries,
                                         extract_asset_file)


class TestDetection:
    def test_kv_dictionary_shape(self):
        assert _looks_like_kv_dictionary(
            "missions=Missioni\nfreeplay=Gioco gratuito\n"
            "settings=Impostazioni\nexit=Uscita\nstart=Start\n")

    def test_plain_text_not_dictionary(self):
        assert _looks_like_kv_dictionary(
            "Hello world\nThis is dialogue text\n") is False

    def test_name_variants(self):
        assert _dictionary_base_name("dictionary") == "dictionary"
        assert _dictionary_base_name("dictionary old") == "dictionary"
        assert _dictionary_base_name("dictionary_old") == "dictionary"
        assert _dictionary_base_name("dictionary veryold") == "dictionary"

    def test_language_scripts(self):
        assert _dictionary_language(["关卡", "设置"]) == "zh"
        assert _dictionary_language(["ミッション", "設定"]) == "ja"
        assert _dictionary_language(["임무", "설정"]) == "ko"
        assert _dictionary_language(["Миссии", "Настройки"]) == "ru"
        assert _dictionary_language(["Missioni", "Settings"]) == "latin"

    def test_english_score(self):
        # 英文表值普遍命中功能词；意/匈语表不命中
        assert _english_score([
            "You have to complete the training mission",
            "The train is late and you need to finish the mission",
        ]) >= 0.15
        assert _english_score([
            "Per sbloccare mappe e treni, devi completare le missioni",
            "Il tuo treno è in ritardo",
        ]) < 0.15


class TestKvEntries:
    def test_values_only_keys_preserved(self):
        entries = _textasset_entries(
            "f", 1, b"missions=Missioni\nsettings=Impostazioni\n"
                     b"exit=Uscita\nstart=Start\nscore=PUNTI\n",
            skipped={})
        by_key = {e.meta["kv_key"]: e for e in entries}
        assert by_key["missions"].original == "Missioni"
        assert by_key["settings"].original == "Impostazioni"
        assert by_key["missions"].meta["textasset_format"] == "kv"
        assert by_key["missions"].status == "pending"

    def test_structural_value_skipped(self):
        entries = _textasset_entries(
            "f", 1, b"url=https://example.com\nname=Start\n",
            skipped={})
        values = [e.original for e in entries]
        assert "https://example.com" not in values

    def test_roundtrip_key_preserved(self):
        body = ("missions=Missioni\nsettings=Impostazioni\n"
                "exit=Uscita\nstart=Start\nscore=PUNTI\n")
        entries = _textasset_entries("f", 1, body.encode(), skipped={})
        table = {"missions": "任务", "settings": "设置",
                 "exit": "退出", "start": "开始", "score": "分数"}
        for e in entries:
            e.translation = table[e.meta["kv_key"]]
        out = apply_format_text("kv", entries, body, {"kind": "textasset"})
        assert out == ("missions=任务\nsettings=设置\n"
                       "exit=退出\nstart=开始\nscore=分数\n")


class TestMultilangGrouping:
    def _fake_textasset(self, path, pid, name, content):
        data = type("Data", (), {
            "m_Name": name, "m_Script": content.encode("utf-8")})()
        return type("Obj", (), {
            "path_id": pid,
            "type": type("T", (), {"name": "TextAsset"})(),
            "assets_file": type("AF", (), {"name": path.name,
                                           "objects": {}})(),
            "read": lambda self, _d=data: _d,
        })()

    def test_english_table_preferred(self, tmp_path, monkeypatch):
        # 意大利表在前、英文表在后——用户指令：多语言游戏英文优先
        import UnityPy
        content_it = ("missions=Missioni\nsettings=Impostazioni\n"
                      "start=Start\nexit=Uscita\nscore=PUNTI\n")
        content_en = ("missions=The missions you have to complete\n"
                      "settings=You can change the settings here\n"
                      "start=Start the game\nexit=Exit the game\n"
                      "score=Your score is\n")
        a = self._fake_textasset(tmp_path / "x.assets", 100,
                                 "dictionary", content_it)
        b = self._fake_textasset(tmp_path / "x.assets", 200,
                                 "dictionary", content_en)

        class Env:
            objects = [a, b]
            files = {}

            def load(self, paths):
                pass

        p = tmp_path / "x.assets"
        p.write_bytes(b"\x00" * 8)
        monkeypatch.setattr(UnityPy, "Environment", lambda: Env())
        pf = extract_asset_file(p, "x.assets")
        kv_values = [e for e in pf.entries
                     if e.meta.get("reason") == "textasset_kv_value"]
        # 英文表被选为源表（意大利表留档跳过）
        assert "The missions you have to complete" in [
            e.original for e in kv_values]
        assert "Missioni" not in [e.original for e in kv_values]

    def test_only_first_table_extracted(self, tmp_path, monkeypatch):
        import UnityPy
        content_a = ("missions=Missioni\nsettings=Impostazioni\n"
                     "start=Start\nexit=Uscita\nscore=PUNTI\n")
        content_b = ("missions=关卡\nsettings=设置\nstart=开始\n"
                     "exit=退出\nscore=分数\n")
        a = self._fake_textasset(tmp_path / "x.assets", 100,
                                 "dictionary", content_a)
        b = self._fake_textasset(tmp_path / "x.assets", 200,
                                 "dictionary", content_b)

        class Env:
            objects = [a, b]
            files = {}

            def load(self, paths):
                pass

        p = tmp_path / "x.assets"
        p.write_bytes(b"\x00" * 8)
        monkeypatch.setattr(UnityPy, "Environment", lambda: Env())
        pf = extract_asset_file(p, "x.assets")
        kv_values = [e for e in pf.entries
                     if e.meta.get("reason") == "textasset_kv_value"]
        locale_skips = [e for e in pf.entries
                        if e.meta.get("reason", "").startswith(
                            "textasset_locale_table")]
        assert [e.original for e in kv_values] == [
            "Missioni", "Impostazioni", "Start", "Uscita", "PUNTI"]
        # 中文表（第二张）留档跳过
        assert locale_skips
        assert "textasset_locale_table_zh" in pf.skipped_reasons
        assert pf.skipped_reasons["textasset_locale_table_zh"] >= 1
