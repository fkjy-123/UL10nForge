"""tmp_tags.py TMP 富文本语法层测试（识别通用规则）。"""
from __future__ import annotations

from hanhua.core.tmp_tags import (is_pure_tags, is_tag_composed,
                                  referenced_names, strip_tags)


class TestTagScan:
    def test_strip_basic(self):
        assert strip_tags("<color=red>Warning!</color>") == (
            " " * 11 + "Warning!" + " " * 8)

    def test_strip_value_and_attr_forms(self):
        assert strip_tags('<sprite="Icons" index=3>Coin') == (
            " " * 24 + "Coin")
        assert strip_tags('<link="ID_5">text</link>') == (
            " " * 13 + "text" + " " * 7)

    def test_strip_color_shorthand(self):
        assert strip_tags("<#FF0000>Red</color>") == (
            " " * 9 + "Red" + " " * 8)


class TestClassification:
    def test_tag_composed_short(self):
        assert is_tag_composed("<b>hi</b>") is True

    def test_tag_composed_color(self):
        assert is_tag_composed("<color=red>Warning!</color>") is True

    def test_pure_tags(self):
        assert is_pure_tags("<size=30><align=center>") is True

    def test_plain_text_not_tagged(self):
        assert is_tag_composed("hello world") is False
        assert is_pure_tags("hello world") is False

    def test_unknown_angle_brackets_not_tags(self):
        # 非 TMP 标签的尖括号用法（不等式/数学）不触发
        assert is_tag_composed("x < y and y > x") is False
        assert is_pure_tags("<notatag>") is False

    def test_nested_tags(self):
        assert is_tag_composed(
            "<color=green><b>Yes</b></color>") is True


class TestReferencedNames:
    def test_sprite_font_style(self):
        names = referenced_names(
            '<sprite="MyIcons" name="coin"> <font="GameFont">')
        assert names == {"MyIcons", "coin", "GameFont"}

    def test_bare_form(self):
        assert referenced_names("<sprite=12>") == {"12"}

    def test_plain_no_refs(self):
        assert referenced_names("<b>hi</b>") == frozenset()
