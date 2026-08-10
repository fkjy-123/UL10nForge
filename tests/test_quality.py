from __future__ import annotations

import pytest

from hanhua.core.models import TextEntry
from hanhua.core.quality import validate_translation_quality


def _entry(original: str, **meta) -> TextEntry:
    return TextEntry("ui.assets", "Menu/title", original, meta=meta,
                     confidence="high")


def test_quality_accepts_natural_translation_with_preserved_formatting():
    entry = _entry("<b>Hello {name}</b>\nContinue")

    result = validate_translation_quality(entry, "<b>你好，{name}</b>\n继续")

    assert result.passed is True
    assert result.reasons == ()
    assert result.normalized_translation == "<b>你好，{name}</b>\n继续"
    assert result.confidence == "high"


def test_quality_returns_stable_reasons_for_format_and_control_failures():
    entry = _entry("<b>Hello {name}</b>\nContinue")

    result = validate_translation_quality(entry, "译文：<b>你好</b>\x00")

    assert result.passed is False
    assert set(result.reasons) >= {
        "explanatory_prefix", "illegal_control", "placeholder_mismatch",
        "newline_mismatch",
    }


def test_uppercase_action_residue_rejected():
    """知识库规则：全大写动作指令译文残留原动作动词（TOSS 垃圾）判失败。"""
    entry = _entry("TOSS TRASH")
    residue = validate_translation_quality(entry, "TOSS 垃圾")
    clean = validate_translation_quality(entry, "丢垃圾")

    assert "action_word_residue" in residue.reasons
    assert clean.passed is True


def test_uppercase_action_non_verb_retention_allowed():
    """动作动词之外的原词保留不判残留（专名仍可保留）。"""
    entry = _entry("CUT WOOD")
    result = validate_translation_quality(entry, "砍木头")

    assert result.passed is True


def test_quality_rejects_untranslated_english_and_glossary_drift():
    entry = _entry("Use Moon Key to open the basement")

    untranslated = validate_translation_quality(entry, "Use Moon Key to open the basement")
    drift = validate_translation_quality(
        entry, "使用月之钥匙打开地下室", glossary=[("Moon Key", "月光钥匙")])

    assert "untranslated_text" in untranslated.reasons
    assert "glossary_mismatch" in drift.reasons


def test_quality_rejects_unchanged_single_english_ui_label():
    result = validate_translation_quality(_entry("Continue", role="ui"), "Continue")

    assert result.reasons == ("untranslated_text",)


def test_quality_allows_decorative_dash_title_not_markdown():
    # "- Quality Settings -" 是装饰性标题（资产真实值），不是 markdown 列表
    result = validate_translation_quality(_entry("- Quality Settings -"), "- 质量设置 -")

    assert result.passed is True


def test_quality_still_rejects_markdown_list_wrapper():
    result = validate_translation_quality(_entry("Choose an option"), "- 选择一项")

    assert "markdown_wrapper" in result.reasons


def test_quality_allows_dash_signature_not_markdown():
    # "-Love, Sean" 签名：译文 "- 爱，肖恩" 的 "- " 是原文破折号延续，不是 markdown 列表
    result = validate_translation_quality(_entry("-Love, Sean"), "- 爱，肖恩")

    assert result.passed is True


def test_bracketed_display_text_is_translatable_not_bbcode():
    result = validate_translation_quality(_entry("[PICK UP]", role="ui"), "[拾取]")

    assert result.passed is True


def test_quality_rejects_renamed_english_and_format_sequence_drift():
    english = validate_translation_quality(_entry("Continue", role="ui"), "Play")
    tags = validate_translation_quality(
        _entry("<b>Hello</b><i>Now</i>"), "<i>你好</i><b>现在</b>")
    newlines = validate_translation_quality(
        _entry("First\nSecond\\nThird"), "第一\\n第二\n第三")

    assert "untranslated_text" in english.reasons
    assert "rich_text_mismatch" in tags.reasons
    assert "newline_mismatch" in newlines.reasons


def test_quality_marks_over_budget_without_failing():
    """超长不判失败：译文质量合格只是物理容量放不下——写回端截断兜底
    （部分翻译 + 省略号），判失败会把好译文整体丢弃、游戏只剩原文
    （taxes 'I did ' 实证）。超出量记入 meta 供报告与人工校对。"""
    entry = _entry("New Game", role="ui", max_chars=4)

    assert validate_translation_quality(entry, "开始游戏").passed
    result = validate_translation_quality(entry, "开启一段全新的游戏旅程")

    assert result.passed is True
    assert result.reasons == ()
    assert entry.meta["length_over_budget"] == 7  # 11 字 - 4 容量


def test_interaction_prompt_requires_the_same_input_token():
    entry = _entry("Press E to open", role="display", reason="interaction_prompt")

    assert validate_translation_quality(entry, "按 E 键打开").passed
    result = validate_translation_quality(entry, "按 F 键打开")

    assert "input_token_mismatch" in result.reasons


@pytest.mark.parametrize(("source", "translation"), [
    # 按键名保留是正确行为：enter 在键列表位置（不是动词）
    ("[press z or enter to continue]", "[按 Z 或 Enter 继续]"),
    ("[press z or enter to restart the game]", "[按 Z 或 Enter 键以重新开始游戏]"),
    ("Press Enter to enter the building", "按 Enter 键进入大楼"),
])
def test_interaction_prompt_keeps_physical_key_names(source, translation):
    entry = _entry(source, role="display", reason="interaction_prompt")

    assert validate_translation_quality(entry, translation).passed


@pytest.mark.parametrize(("source", "translation"), [
    # 真半翻：动作词（非按键）残留仍判失败
    ("Press E to Open", "按 E 键 Open"),
    ("Press Enter to enter the building", "Press Enter 键进入大楼"),
])
def test_interaction_prompt_still_rejects_action_word_leftovers(source, translation):
    entry = _entry(source, role="display", reason="interaction_prompt")

    assert not validate_translation_quality(entry, translation).passed


@pytest.mark.parametrize(("source", "translation"), [
    # 专名并列短语（人名 + 姓）不是英文残留
    ("Polish Localization - Amitte Sukku", "波兰语本地化服务 – Amitte Sukku"),
    # "* (选项文案)" 风格不是 markdown 列表
    ("* (You felt that you shouldn't\n  advance.)",
     "* 你觉得自己不应该\n提前。"),
])
def test_quality_accepts_proper_name_phrases_and_option_style(source, translation):
    entry = _entry(source, role="display")

    assert validate_translation_quality(entry, translation).passed


@pytest.mark.parametrize(("source", "translation"), [
    # 专名/缩写回显（原文无小写词、不在 UI 词典）是合理行为
    ("Crash Bandicoot", "Crash Bandicoot"),
    ("Roquette", "Roquette"),
    ("Profiler", "Profiler"),
    ("IMGUI", "IMGUI"),
])
def test_quality_allows_proper_name_echo(source, translation):
    entry = _entry(source, role="display")

    assert validate_translation_quality(entry, translation).passed


@pytest.mark.parametrize(("source", "translation"), [
    # 回显仍失败：有小写词（真半翻）或 UI 词典词
    ("Hello world", "Hello world"),
    ("Save game", "Save game"),
    ("Continue", "Continue"),
])
def test_quality_rejects_real_echoes(source, translation):
    entry = _entry(source, role="display")

    assert "untranslated_text" in validate_translation_quality(
        entry, translation).reasons


def test_interaction_prompt_input_token_is_subsequence():
    # 译文保留按键序列（顺序一致）且允许出现额外字面量：
    # "Press 1 for Chapter 1" 的章节号 1、"A: " 说话人标记 A 不是按键破坏
    eggs = _entry(
        "Press 1 for Chapter 1 Help, 2 for Chapter 2 Help, or 3 for "
        "Chapter 3 Help\nA/Left Arrow for Previews Page, and D/Right for "
        "Next Page\nEsc to Exit (Pages will unlock as you beat levels)",
        role="display", reason="interaction_prompt",
    )
    assert validate_translation_quality(
        eggs,
        "按下 1 适用于章节 1 求助，第2章需要2个帮助，第3章则需要3个帮助。\n"
        "A/向左键可进入预览页面， D/跳到下一页\n"
        "按 Esc 键退出（完成关卡后，页面将会解锁）").passed
    arrhy = _entry(
        "A: Hey Hal can we swap to the new batch?\n"
        "> H: I'm sorry Dave, I can't do that.\n> A: ...bruh",
        role="display", reason="interaction_prompt",
    )
    assert validate_translation_quality(
        arrhy,
        "A嘿，Hal，我们可以换到新的批次吗？\n"
        "> H: I“对不起，戴夫。” I 做不到那样。\n> A...兄弟").passed


def test_interaction_prompt_preserves_input_token_count_and_order():
    ordered = _entry(
        "Press E, then hold F to interact",
        role="display", reason="interaction_prompt",
    )
    repeated = _entry(
        "Press E, then hold E to interact",
        role="display", reason="interaction_prompt",
    )

    assert validate_translation_quality(
        ordered, "先按 F，再按 E 交互").reasons == ("input_token_mismatch",)
    assert validate_translation_quality(
        repeated, "按 E 交互").reasons == ("input_token_mismatch",)


def test_interaction_prompt_preserves_quoted_bracketed_and_numeric_glyphs():
    entry = _entry(
        "Press 'E', hold [F], then press 2",
        role="display", reason="interaction_prompt",
    )

    assert validate_translation_quality(entry, "先按 E，再按 F，最后按 2").passed
    assert validate_translation_quality(
        entry, "先按 F，再按 E，最后按 2").reasons == (
            "input_token_mismatch",)


def test_interaction_prompt_preserves_parenthesized_and_angle_wrapped_glyphs():
    cases = (
        ("Press (E) to open", "按 E 键打开", "按 F 键打开"),
        ("Press <E> to open", "按 <E> 键打开", "按 <F> 键打开"),
    )
    for original, preserved, changed in cases:
        entry = _entry(original, role="display", reason="interaction_prompt")

        assert validate_translation_quality(entry, preserved).passed
        assert "input_token_mismatch" in validate_translation_quality(
            entry, changed).reasons


def test_interaction_prompt_preserves_legacy_named_physical_tokens():
    cases = (
        ("Press LB to block", "按 LB 键格挡", "按 RB 键格挡"),
        ("Press R1 to dodge", "按 R1 键闪避", "按 L1 键闪避"),
        ("Press Numpad 1 to select", "按 Numpad 1 键选择", "按 Numpad 2 键选择"),
    )
    for original, preserved, changed in cases:
        entry = _entry(original, role="display", reason="interaction_prompt")

        assert validate_translation_quality(entry, preserved).passed
        assert "input_token_mismatch" in validate_translation_quality(
            entry, changed).reasons


def test_interaction_prompt_preserves_common_named_physical_keys():
    cases = (
        ("Press Esc to exit", "按 Esc 键退出", "按 F 键退出"),
        ("Press Backspace to close", "按 Backspace 键关闭", "按 Delete 键关闭"),
        ("Press D-Pad Up to select", "按 D-Pad Up 选择", "按 D-Pad Down 选择"),
    )
    for original, preserved, changed in cases:
        entry = _entry(original, role="display", reason="interaction_prompt")

        assert validate_translation_quality(entry, preserved).passed
        assert "input_token_mismatch" in validate_translation_quality(
            entry, changed).reasons


def test_interaction_prompt_preserves_complete_physical_chords():
    cases = (
        ("Press Ctrl+Delete to remove", "按 Ctrl+Delete 删除", "按 Ctrl+Backspace 删除"),
        ("Press Page Up+Shift to scroll", "按 Page Up+Shift 滚动", "按 Page Up+Ctrl 滚动"),
        ("Press D-Pad Up+LB to select", "按 D-Pad Up+LB 选择", "按 D-Pad Up+RB 选择"),
    )
    for original, preserved, changed in cases:
        entry = _entry(original, role="display", reason="interaction_prompt")

        assert validate_translation_quality(entry, preserved).passed
        assert "input_token_mismatch" in validate_translation_quality(
            entry, changed).reasons


def test_interaction_prompt_preserves_underscore_and_dash_physical_chords():
    cases = (
        ("Press Ctrl_Delete to remove", "按 Ctrl_Delete 删除", "按 Ctrl_Backspace 删除"),
        ("Press Ctrl-Delete to remove", "按 Ctrl-Delete 删除", "按 Ctrl-Backspace 删除"),
    )
    for original, preserved, changed in cases:
        entry = _entry(original, role="display", reason="interaction_prompt")

        assert validate_translation_quality(entry, preserved).passed
        assert "input_token_mismatch" in validate_translation_quality(
            entry, changed).reasons


def test_interaction_prompt_allows_semantic_inputs_to_be_translated():
    cases = (
        ("Press Any Key", "按任意键"),
        ("right click with Harpoon equipped to reel in", "装备鱼叉后用右键收线"),
        ("Square/X/Y Button: Jump", "方块、叉和三角键：跳跃"),
        ("Press X Button to jump", "按叉键跳跃"),
    )

    for original, translation in cases:
        result = validate_translation_quality(
            _entry(original, role="display", reason="interaction_prompt"),
            translation,
        )
        assert result.passed, (original, result.reasons)


def test_interaction_prompt_rejects_untranslated_action_words_with_chinese_suffix():
    entry = _entry(
        "Press E to open", role="display", reason="interaction_prompt",
    )

    result = validate_translation_quality(entry, "Press E to open（打开）")

    assert "untranslated_text" in result.reasons


def test_multiline_item_label_is_not_treated_as_an_input_action():
    entry = _entry(
        "Key30\nG - to throw\n", role="display", reason="interaction_prompt")

    result = validate_translation_quality(entry, "Key30\nG – 投掷")

    assert result.passed is True
    assert result.reasons == ()


def test_multiline_translation_removes_model_line_end_spaces():
    entry = _entry(
        "Key30\nG - to throw\n", role="display", reason="interaction_prompt")

    result = validate_translation_quality(entry, "Key30  \nG – 投掷  ")

    assert result.passed is True
    assert result.normalized_translation == "Key30\nG – 投掷\n"


def test_multiline_translation_rejects_a_missing_meaningful_line():
    entry = _entry("First\nSecond\nThird", role="display")

    result = validate_translation_quality(entry, "第一\n\n第三")

    assert "line_content_mismatch" in result.reasons


def test_multiline_translation_requires_exact_crlf_delimiters():
    entry = _entry("First\r\nSecond", role="display")

    result = validate_translation_quality(entry, "第一\n第二")

    assert "newline_mismatch" in result.reasons


@pytest.mark.parametrize("delimiter", ["\n", "\r\n", r"\n"])
def test_multiline_translation_preserves_empty_segment_topology(delimiter):
    entry = _entry(delimiter.join(("A", "", "B", "C")), role="display")

    result = validate_translation_quality(
        entry, delimiter.join(("甲", "乙", "", "丙")))

    assert "line_content_mismatch" in result.reasons


def test_camel_tech_abbreviation_echo_is_not_untranslated():
    """VSync 驼峰技术缩写回显（无中文）→ 保留原文合理，不算未翻译。
    （vincent 'VSync: OFF' 真实样本；VSync 在 UI 词典但驼峰豁免放行）"""
    entry = _entry("VSync", role="display")

    result = validate_translation_quality(entry, "VSync")

    assert result.passed is True


def test_camel_echo_of_source_absent_word_still_fails():
    """译文残留原文没有的驼峰缩写 → 仍判未翻译（防模型幻觉新词）。"""
    entry = _entry("Settings", role="display")

    result = validate_translation_quality(entry, "MonoBehaviour")

    assert result.passed is False
    assert "untranslated_text" in result.reasons


def test_service_phrase_brand_echo_is_not_untranslated():
    """'Youtube Music' 品牌短语大小写修正回显 → 合理保留（YouTube 服务名）。"""
    entry = _entry("Youtube Music", role="display")

    result = validate_translation_quality(entry, "YouTube Music")

    assert result.passed is True


def test_dev_placeholder_with_lorem_suffix_is_skipped():
    """开发者填充占位（'description goes here ipsum dolor...'）→ 回显合理。
    （Incremental RTS 真实样本）"""
    text = ("The achievement's description goes here ipsum dolor lorem "
            "sit amet ipsum dolor sit amet ipsum dolor sit amet")
    from hanhua.core.quality import is_lorem_ipsum_placeholder

    assert is_lorem_ipsum_placeholder(text) is True

    entry = _entry(text, role="display")
    result = validate_translation_quality(entry, text)
    assert result.passed is True
