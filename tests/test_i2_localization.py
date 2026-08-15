"""I2 Localization 语言源提取测试（识别通用载体，覆盖全部 I2 游戏）。"""
from __future__ import annotations

from hanhua.core.unity.extractor import (_i2_localization_entries_from_tree,
                                         _is_i2_language_source_tree)


def _i2_tree(terms, container_key="mSource", languages=None):
    data = {
        "mTerms": terms,
        "mLanguages": languages or [{"Name": "English"}, {"Name": "Chinese"}],
    }
    return {container_key: data} if container_key else dict(data)


def _term(key, languages, term_type=None):
    term = {"Term": key, "Languages": languages}
    if term_type is not None:
        term["TermType"] = term_type
    return term


class TestDetection:
    def test_nested_m_source(self):
        assert _is_i2_language_source_tree(_i2_tree([_term("K", ["V"])]))

    def test_m_data_variant(self):
        assert _is_i2_language_source_tree(_i2_tree([_term("K", ["V"])],
                                                    "mData"))

    def test_flat_terms(self):
        assert _is_i2_language_source_tree(_i2_tree([_term("K", ["V"])],
                                                    container_key=None))

    def test_not_i2(self):
        assert _is_i2_language_source_tree({"m_Name": "x"}) is False
        assert _is_i2_language_source_tree({}) is False


class TestExtraction:
    def test_source_value_extracted(self):
        tree = _i2_tree([
            _term("MENU_START", ["New Game", "新游戏"]),
            _term("MENU_QUIT", ["", "退出"]),  # 源语言空 → 取首个非空
        ])
        entries = _i2_localization_entries_from_tree("f", 7, tree)
        by_key = {e.meta["i2_term"]: e for e in entries}
        assert by_key["MENU_START"].original == "New Game"
        assert by_key["MENU_START"].status == "pending"
        assert by_key["MENU_START"].meta["reason"] == "i2_language_source"
        assert by_key["MENU_START"].meta["confidence"] == "high"
        # 源语言空时取首个非空语言值
        assert by_key["MENU_QUIT"].original == "退出"
        assert by_key["MENU_QUIT"].meta["i2_lang_index"] == 1

    def test_english_preferred_over_first(self):
        # 用户指令：多语言游戏语言优先翻译英文——中文在前、英文在后
        # 时仍取英文值
        tree = _i2_tree(
            [_term("MENU_START", ["开始游戏", "Start the game"])],
            languages=[{"Name": "中文"}, {"Name": "English"}])
        entries = _i2_localization_entries_from_tree("f", 7, tree)
        assert entries[0].original == "Start the game"
        assert entries[0].meta["i2_lang_index"] == 1

    def test_asset_term_type_skipped(self):
        tree = _i2_tree([
            _term("TEXT_1", ["Hello"]),
            _term("FONT_REF", ["Fonts/Roboto"], term_type=1),
        ])
        entries = _i2_localization_entries_from_tree("f", 7, tree)
        assert [e.meta["i2_term"] for e in entries] == ["TEXT_1"]

    def test_key_path_has_typetree_field_path(self):
        tree = _i2_tree([_term("K", ["Hello world"])])
        entries = _i2_localization_entries_from_tree("f", 7, tree)
        assert entries[0].key_path.startswith("asset#7/field/k:")
        assert entries[0].meta["field_path"] == [
            "mSource", "mTerms", 0, "Languages", 0]

    def test_flat_tree_field_path(self):
        tree = _i2_tree([_term("K", ["Hello world"])], container_key=None)
        entries = _i2_localization_entries_from_tree("f", 7, tree)
        assert entries[0].meta["field_path"] == ["mTerms", 0, "Languages", 0]
