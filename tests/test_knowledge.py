"""知识库：多形态知识（文本/文件/抽象规则）分库存储 + 匹配 + 学习 + prompt 注入。"""
from pathlib import Path

import pytest

from hanhua.core.knowledge import (BUILTIN_RULES, KnowledgeBase,
                                   KnowledgeStore, _is_multilingual_source,
                                   _is_spaced_action, _is_uppercase_action,
                                   translate_uppercase_action)
from hanhua.core.models import TextEntry


class _Entry:
    """TextEntry 轻量替身（只含 learn() 用到的字段）。"""

    def __init__(self, original, status="translated", translation=None,
                 meta=None):
        self.original = original
        self.status = status
        self.translation = translation if translation is not None else original
        self.meta = {"quality_passed": True, **(meta or {})}


# ── 内置形态识别 ──

class TestUppercaseAction:
    def test_action_phrase_detected(self):
        assert _is_uppercase_action("TOSS TRASH")
        assert _is_uppercase_action("PRESS START")
        assert _is_uppercase_action("PICK UP THE AXE")
        assert _is_uppercase_action("THROW THE BALL NOW")

    def test_proper_name_not_detected(self):
        # 真专名无动作动词 → 不误命中（专名仍走 proper_name_echo 豁免）
        assert not _is_uppercase_action("MEGA CORP")
        assert not _is_uppercase_action("STAR WARS")
        assert not _is_uppercase_action("GAME OVER")  # 无动作动词
        assert not _is_uppercase_action("NEW GAME")   # 无动作动词

    def test_edge_cases(self):
        assert not _is_uppercase_action("")
        assert not _is_uppercase_action("123")
        assert not _is_uppercase_action("just a sentence")  # 非全大写
        assert not _is_uppercase_action("A")                # 单词太短
        assert not _is_uppercase_action("LONG " + "WORD " * 6 + " HERE")  # 超 5 词


class TestTranslateUppercaseAction:
    def test_mechanical_translation(self):
        assert translate_uppercase_action("TOSS TRASH") == "丢垃圾"
        assert translate_uppercase_action("PRESS START") == "按开始"
        assert translate_uppercase_action("OPEN THE DOOR") == "打开门"
        assert translate_uppercase_action("PICK UP THE AXE") == "捡起斧头"

    def test_unknown_word_no_fallback(self):
        assert translate_uppercase_action("TOSS THE ZARBUL") is None
        assert translate_uppercase_action("MEGA CORP") is None
        assert translate_uppercase_action("") is None


class TestSpacedAction:
    def test_spaced_words_detected(self):
        assert _is_spaced_action("* Y A W N *")
        assert _is_spaced_action("G A S P")
        assert _is_spaced_action("* S C O F F *")

    def test_non_spaced_not_detected(self):
        assert not _is_spaced_action("* TOSS TRASH *")
        assert not _is_spaced_action("HELLO")
        assert not _is_spaced_action("")


# ── 持久库：多形态分库 ──

class TestKnowledgeStore:
    def test_upsert_idempotent_hits_increment(self, tmp_path):
        store = KnowledgeStore(tmp_path / "knowledge.db")
        store.init_schema()
        assert store.upsert("text", "spaced_action", "G A S P",
                            action="translate") is True
        assert store.upsert("text", "spaced_action", "G A S P",
                            action="translate") is False
        rows = store.list_by_domain("text")
        assert len(rows) == 1
        assert rows[0]["hits"] == 2
        store.close()

    def test_multiple_domains_separate_libraries(self, tmp_path):
        store = KnowledgeStore(tmp_path / "knowledge.db")
        store.init_schema()
        store.upsert("text", "spaced_action", "Y A W N", action="translate")
        store.upsert("file", "us_record", "#US 固定码元", action="capacity_fixed")
        store.upsert("rule", "placeholder_restore", "{n} 补末尾", action="restore_to_end")
        assert len(store.list_by_domain("text")) == 1
        assert len(store.list_by_domain("file")) == 1
        assert len(store.list_by_domain("rule")) == 1
        store.close()

    def test_delete(self, tmp_path):
        store = KnowledgeStore(tmp_path / "knowledge.db")
        store.init_schema()
        store.upsert("text", "uppercase_action", "TOSS TRASH", action="translate")
        store.delete("text", "uppercase_action", "TOSS TRASH")
        assert store.list_by_domain("text") == []
        store.close()


# ── KnowledgeBase：匹配 / prompt 注入 / 学习 ──

class TestKnowledgeBase:
    def test_match_text_builtin_detection(self, tmp_path):
        kb = KnowledgeBase(tmp_path / "knowledge.db")
        assert kb.requires_translation("TOSS TRASH")
        assert kb.requires_translation("* Y A W N *")
        assert not kb.requires_translation("MEGA CORP")
        kb.close()

    def test_persisted_exact_phrase_injected(self, tmp_path):
        kb = KnowledgeBase(tmp_path / "knowledge.db")
        kb.store.upsert("text", "uppercase_action", "TOSS TRASH",
                        action="translate", map_to="丢垃圾")
        prompt = kb.format_for_prompt()
        assert "TOSS TRASH" in prompt
        assert "丢垃圾" in prompt
        # 无 map_to 的条目（纯学习标记）不注入，避免 prompt 膨胀
        kb.store.upsert("text", "uppercase_action", "TOSS COINS",
                        action="translate", map_to="")
        assert "TOSS COINS" not in kb.format_for_prompt()
        kb.close()

    def test_builtin_seed_rules_described(self, tmp_path):
        kb = KnowledgeBase(tmp_path / "knowledge.db")
        described = kb.describe()
        domains = {item["domain"] for item in described}
        # 六库蓝图齐备：text/file/rule 三形态 + 结构/文本类型/组件/质量/写回验证
        assert domains == {"text", "file", "rule", "unity_struct",
                           "text_type", "component", "quality",
                           "writeback_verify"}
        # 三形态种子齐备：文本规则 / 文件知识 / 抽象规则
        assert any(k["kind"] == "us_record" for k in described if k["domain"] == "file")
        assert any(k["kind"] == "placeholder_restore" for k in described if k["domain"] == "rule")
        assert any(k["kind"] == "textmeshpro" for k in described if k["domain"] == "component")
        assert any(k["kind"] == "verify_flow" for k in described if k["domain"] == "writeback_verify")
        assert len(described) >= len(BUILTIN_RULES)
        kb.close()

    def test_learn_from_echo_entries(self, tmp_path):
        kb = KnowledgeBase(tmp_path / "knowledge.db")
        entries = [
            _Entry("TOSS TRASH"),                 # 回显 + 大写动作 → 学习
            _Entry("* Y A W N *"),                # 回显 + 间隔动作词 → 学习
            _Entry("MEGA CORP"),                  # 纯专名回显 → 不学习
            _Entry("Princess Peach"),             # 小写词 + 不在专名单 → 不学习
            _Entry("Press START", translation="按开始"),  # 已翻译 → 不学习
            # 质量门拒绝的回显条目（重试仍回显的模型惯性）→ 学习
            _Entry("TOSS COINS", status="failed",
                   meta={"quality_reasons": ["untranslated_text"]}),
            # 失败但已翻译（translation != original）→ 不学习
            _Entry("TAKE CARE", status="failed",
                   translation="保重",
                   meta={"quality_reasons": ["untranslated_text"]}),
            # 半翻译残留（action_word_residue 拒绝，译文≠原文）→ 学习
            _Entry("TOSS RUBBISH", status="failed",
                   translation="TOSS 垃圾",
                   meta={"quality_reasons": ["action_word_residue"]}),
            # 非知识库形态失败（换行等）→ 不学习
            _Entry("LONG TEXT", status="failed",
                   translation="长文",
                   meta={"quality_reasons": ["newline_mismatch"]}),
        ]
        learned, hits = kb.learn(entries, "test-game", names={"Princess Peach"})
        assert learned == 4
        assert hits == 4
        rows = kb.store.list_by_domain("text")
        assert {r["pattern"] for r in rows} == {
            "TOSS TRASH", "* Y A W N *", "TOSS COINS", "TOSS RUBBISH"}
        kb.close()

    def test_learn_idempotent_accumulates_hits(self, tmp_path):
        kb = KnowledgeBase(tmp_path / "knowledge.db")
        kb.learn([_Entry("G A S P")], "game-a")
        learned, hits = kb.learn([_Entry("G A S P")], "game-b")
        assert learned == 0
        assert hits == 1
        row = kb.store.list_by_domain("text")[0]
        assert row["hits"] == 2
        assert "game-b" in row["note"]
        kb.close()

    def test_learn_generates_map_to_for_reference_pairs(self, tmp_path):
        """learn 给大写动作指令生成机械直译建议——native 降级重试靠它
        注入译例（Hy-MT2 无 system prompt，只能走 references 的 terms）。"""
        kb = KnowledgeBase(tmp_path / "knowledge.db")
        kb.learn([_Entry("TOSS TRASH", status="failed",
                         meta={"quality_reasons": ["untranslated_text"]})],
                 "game-x")
        pairs = kb.format_reference_pairs()
        assert ("TOSS TRASH", "丢垃圾") in pairs
        kb.close()

    def test_learn_without_store_is_noop(self, tmp_path):
        kb = KnowledgeBase()  # 无持久库 → learn 空操作
        assert kb.learn([_Entry("TOSS TRASH")], "game") == (0, 0)
        kb.close()

    def test_learn_multilingual_echo(self, tmp_path):
        """多语言源回显条目（法语 Clé en Fer 等模型不认识的语言）→ 沉淀
        text/multilingual_source 形态规则（alisa-demo 实证 1 条法语回显）。"""
        kb = KnowledgeBase(tmp_path / "knowledge.db")
        entries = [
            _Entry("Clé en Fer", status="failed",
                   meta={"quality_reasons": ["untranslated_text"]}),
            # 日语回显（模型输出英语时 translation != original → 不学；
            # 双跳修复在 batch_translator 层，learn 只管纯回显）
            _Entry("右手の鍵", status="translated",
                   translation="Right-hand key",
                   meta={"quality_reasons": ["target_script_mismatch"],
                         "quality_passed": False}),
        ]
        learned, hits = kb.learn(entries, "alisa-demo")
        assert learned == 1
        rows = kb.store.list_by_domain("text")
        assert {r["pattern"] for r in rows} == {"Clé en Fer"}
        assert rows[0]["kind"] == "multilingual_source"
        assert kb.match_text("Clé en Fer")[0]["kind"] == "multilingual_source"
        kb.close()


class TestMultilingualSource:
    """多语言源文本形态：含日文假名或带重音拉丁字母 → 其他语言（非英语）
    源文本。模型对其倾向输出英语译文（alisa-demo 实证 26 条），须译中文。"""

    def test_japanese_kana_detected(self):
        assert _is_multilingual_source("右手の鍵")
        assert _is_multilingual_source("この鍵も 役に立つかも")
        assert _is_multilingual_source("ラベルには　こう書かれている")

    def test_accented_latin_detected(self):
        assert _is_multilingual_source("Clé en Fer")      # 法语 é
        assert _is_multilingual_source("Perchè hai transformato")  # 意语 è
        assert _is_multilingual_source("J'ai emprunté")   # 法语 é

    def test_ascii_romance_function_words_detected(self):
        # 意语/法语与英语共用拉丁字母，无重音字符时靠功能词识别
        assert _is_multilingual_source("Chiave di Ferro")   # di
        assert _is_multilingual_source("Canna da Pesca")    # da
        assert _is_multilingual_source("Il cibo su questo tavolo")  # il
        assert _is_multilingual_source("Clé en Fer")

    def test_plain_scripts_not_detected(self):
        assert not _is_multilingual_source("Iron Key")
        assert not _is_multilingual_source("TOSS TRASH")
        assert not _is_multilingual_source("Hello, world!")
        assert not _is_multilingual_source("中文文本")
        assert not _is_multilingual_source("")

    def test_rule_in_builtin_and_match(self):
        assert any(r["kind"] == "multilingual_source"
                   for r in BUILTIN_RULES)


def test_builtin_rules_shape():
    for rule in BUILTIN_RULES:
        assert rule["domain"] in {"text", "file", "rule", "unity_struct",
                                  "text_type", "component", "quality",
                                  "writeback_verify"}
        assert rule["kind"]
        assert rule["pattern"]
        assert rule["action"]


def test_prompt_injection_via_build_system_prompt(tmp_path):
    """runner/GUI 注入链路：knowledge_lines → build_system_prompt 块。"""
    from hanhua.core.models import GameProfile
    from hanhua.core.prompts import build_system_prompt
    kb = KnowledgeBase(tmp_path / "knowledge.db")
    kb.store.upsert("text", "uppercase_action", "TOSS TRASH",
                    action="translate", map_to="丢垃圾")
    system = build_system_prompt(GameProfile(), "", known_names=None,
                                 knowledge_lines=kb.format_for_prompt())
    assert "【特殊情况规则·优先遵守】" in system
    assert "TOSS TRASH" in system
    kb.close()
    # 不传知识库 → 无该块（默认行为不变）
    assert "【特殊情况规则" not in build_system_prompt(GameProfile(), "")
