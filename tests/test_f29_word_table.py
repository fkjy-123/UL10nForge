"""fix-29 词表/字典对象判定（happy-cat-tavern 实证 2026-08-12）。

打字游戏单词库对象（level1#1311 1700 条 100% 单 token 单词）中白名单
常见词（play/time/gold…）被 direct_code_signal/ui_control_signal 误放行
进池翻译，写回后玩家无法按英文打字（打字玩法破坏）。修复：对象级判定
——字符串几乎全部是单 token 单词且数量大 → 整对象跳过（word_table_object）。

证据分层：大型全单词数组是确定性词表结构证据，优先于形态性猜测；
正常 UI 对象含句式/描述文本且条目数少，不触发。
"""
import pytest

from hanhua.core.unity.extractor import _raw_string_entries

from tests.test_v2 import _scriptable_object_raw, _with_len


# 真实词表样本（happy-cat-tavern level1#1311 中被误译的单词）
_WORD_SAMPLE = ["play", "time", "gold", "walk", "read", "shop", "open",
                "money", "music", "window", "friend", "stamina", "victory",
                "keyboard", "size", "Batou", "placeholder", "Normal",
                "Hard", "Mild", "Winkle", "Regular", "Mirrored", "Smiley"]


def _word_table_raw(n: int) -> bytes:
    texts = [_WORD_SAMPLE[i % len(_WORD_SAMPLE)] for i in range(n)]
    return _scriptable_object_raw(*texts)


def _find(entries, text: str):
    hit = [e for e in entries if e.original == text]
    assert hit, f"{text!r} 未产生条目：{[e.original for e in entries]}"
    return hit[0]


def test_large_word_table_skipped_entirely():
    """≥50 条且 100% 单词的词表对象：全部跳过（含白名单词 play/time）——
    白名单显示词证据只在真实 UI 组件对象生效，词表词翻译破坏打字玩法。"""
    entries = _raw_string_entries("f1", 5, _word_table_raw(100), {},
                                  "sharedassets0.assets")
    assert len(entries) == 100
    for e in entries:
        assert e.status == "skipped", f"{e.original} 未跳过"
        assert e.meta["reason"] == "word_table_object", e.original
    # 白名单词同样跳过（词表对象里白名单不生效）
    assert _find(entries, "play").meta["reason"] == "word_table_object"
    assert _find(entries, "gold").meta["reason"] == "word_table_object"


def test_small_word_list_not_triggered():
    """小词表（<50 条）：不触发对象级判定，白名单词仍走原判定链
    （防误伤正常小 UI 对象/小配置）。"""
    entries = _raw_string_entries("f1", 5, _word_table_raw(20), {},
                                  "sharedassets0.assets")
    assert len(entries) == 20
    reasons = {e.meta["reason"] for e in entries}
    assert "word_table_object" not in reasons


def test_large_object_with_sentences_not_triggered():
    """大对象但含句式文本（单词占比 <95%）：对话/UI 描述对象不触发
    （单词占比被句式拉低，词表判定防过宽）。"""
    texts = [_WORD_SAMPLE[i % len(_WORD_SAMPLE)] for i in range(60)]
    texts += ["Word length starts at FOUR with normal bar speed",
              "Practice your typing with no pressure!",
              "Hard mode but all words are mirrored",
              "LIST OF COMMANDS"] * 3  # 60 单词 + 12 句式 ≈ 83%
    entries = _raw_string_entries("f1", 5, _scriptable_object_raw(*texts),
                                  {}, "sharedassets0.assets")
    reasons = {e.meta["reason"] for e in entries}
    assert "word_table_object" not in reasons


def test_normal_ui_object_unaffected():
    """正常 UI 对象（少量标签+句式）：词表判定不干预，显示文本照常进池。"""
    raw = (_with_len("Main Menu")
           + _with_len("Play")
           + _with_len("Word length starts at FOUR with normal bar speed"))
    entries = _raw_string_entries("f1", 5, raw, {}, "sharedassets0.assets")
    assert len(entries) == 3
    assert _find(entries, "Main Menu").status == "pending"
