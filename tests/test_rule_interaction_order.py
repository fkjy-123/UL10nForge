"""规则交互顺序测试套件（审计 P2-9 / 根因 A 防护）。

识别管线的判定链是 if-elif 行序 = 证据优先级（审计报告根因 A：规则补丁化——
每个游戏的新形态在链尾加分支，新分支插队就改变所有旧规则优先级）。
本套件钉死「规则间顺序交互」契约：单规则测试全绿但顺序被插队改坏时，
这些测试必须红。证据分层总则：
  确定性形态（引擎串/结构角色） > 显式显示证据（交互提示/白名单词/
  控件词缀/句子档） > 对象级猜测（键列表/代码重/小配置） > 命名猜测。
"""
import pytest

from hanhua.core.engine_strings import (
    is_engine_string, is_engine_string_core, is_engine_string_gated)
from hanhua.core.unity.extractor import _raw_string_entries

from tests.test_v2 import _scriptable_object_raw, _with_len


def _entries(*texts: str, freq: dict | None = None) -> list:
    return _raw_string_entries("f1", 5, _scriptable_object_raw(*texts),
                               freq or {}, "sharedassets0.assets")


def _find(entries, text: str):
    hit = [e for e in entries if e.original == text]
    assert hit, f"{text!r} 未产生条目：{[e.original for e in entries]}"
    return hit[0]


# ── A. 预过滤顺序（engine > key > high_frequency）────────────────────

def test_prefilter_engine_string_beats_key_identifier():
    """'ui_newGame' 同时命中命名猜测层（小写下划线）+ 键风格标识符——
    引擎串预过滤先判（R5 留档 reason 必须是 engine_string 而非
    key_identifier；若有人在预过滤链首插键标识符分支，本用例红）。"""
    entries = _raw_string_entries("f1", 5, _with_len("ui_newGame"), {}, "sharedassets0.assets")
    hit = _find(entries, "ui_newGame")
    assert hit.meta["reason"] == "prefilter_engine_string"


def test_prefilter_engine_beats_high_frequency():
    """'_MainTex' freq=300：引擎串先判，即使高频（高频分支在引擎串之后）。"""
    entries = _raw_string_entries(
        "f1", 5, _with_len("_MainTex"), {"_MainTex": 300}, "sharedassets0.assets")
    hit = _find(entries, "_MainTex")
    assert hit.meta["reason"] == "prefilter_engine_string"


def test_key_identifier_beats_high_frequency():
    """'MENU_PLAY' freq=50：键风格标识符（大写+下划线，不命中命名猜测层）
    先于高频（should_skip 在 freq 前）。用不命中 engine 层的键形态——
    'phone_call_01' 会同时命中命名猜测层（小写下划线）被 engine_string
    先拦，不是本交互点的用例。"""
    entries = _raw_string_entries(
        "f1", 5, _with_len("MENU_PLAY"), {"MENU_PLAY": 50},
        "sharedassets0.assets")
    hit = _find(entries, "MENU_PLAY")
    assert hit.meta["reason"] == "prefilter_key_identifier"


def test_high_frequency_waives_with_display_evidence():
    """'Press E to open' freq=50：强显示证据（交互提示）豁免高频预过滤——
    真实对话句高频出现（跨对象复用）不得被高频规则吞掉。"""
    entries = _raw_string_entries(
        "f1", 5, _with_len("Press E to open"), {"Press E to open": 50},
        "sharedassets0.assets")
    hit = _find(entries, "Press E to open")
    assert hit.status == "pending"
    assert hit.meta["reason"] == "interaction_prompt"


def test_high_frequency_catches_plain_word():
    """'generic' freq=50（非引擎/非键/无显示证据）：高频预过滤拦截并留档。"""
    entries = _raw_string_entries(
        "f1", 5, _with_len("generic"), {"generic": 50}, "sharedassets0.assets")
    hit = _find(entries, "generic")
    assert hit.meta["reason"] == "prefilter_high_frequency"


# ── B. 分类链顺序（结构 > 代码 > 交互 > 对象级 > 键列表 > 菜单 > 句子）──

def test_lifecycle_method_beats_object_level_config():
    """input_system_object 对象里的 'Start'：生命周期方法分支在对象级
    input/timeline/unityevent 分支之前——引擎生命周期名不被输入对象
    规则二次解释（reason 精确到 lifecycle_method）。"""
    raw = _with_len("Press(behavior=2)") + _with_len("Start")
    entries = _raw_string_entries("f1", 5, raw, {}, "sharedassets0.assets")
    hit = _find(entries, "Start")
    assert hit.status == "skipped"
    assert hit.meta["reason"] == "lifecycle_method"


def test_interaction_prompt_beats_object_level_config():
    """input_system_object 对象里 'Press E to open'：交互提示分支在对象级
    引擎配置分支之前——交互提示是显式显示证据，不被输入对象信号吞掉。"""
    raw = _with_len("<Keyboard>/z") + _with_len("Press E to open")
    entries = _raw_string_entries("f1", 5, raw, {}, "sharedassets0.assets")
    hit = _find(entries, "Press E to open")
    assert hit.status == "pending"
    assert hit.meta["reason"] == "interaction_prompt"


def test_value_evidence_lifts_words_in_config_shape_object():
    """值特征（对象含句子）改变整个对象身份：'Timothy'+句子 → 对象不再是
    小配置形态（含句子），词走值特征放行（object_has_display_evidence）；
    对照 'Timothy'+'White Flash'（纯短词无句子）→ 小配置跳过。句子证据
    只经对象级形态判定生效，不经分支 8 的 per-entry 豁免——交互点：
    has_value_evidence 分支（15）在 identifier 分支（16）之前。"""
    lifted = _entries("Timothy", "This is a visible sentence here.")
    word = _find(lifted, "Timothy")
    assert word.status == "pending"
    assert word.meta["reason"] == "object_has_display_evidence"
    sentence = _find(lifted, "This is a visible sentence here.")
    assert sentence.status == "pending"
    assert sentence.meta["reason"] == "natural_language"
    config = _entries("Timothy", "White Flash")
    assert _find(config, "Timothy").status == "skipped"


def test_key_list_beats_code_heavy():
    """键列表对象（≥85% 标识符，6/7）且代码重（≥2 方法名信号）：键列表
    分支在代码重分支之前——键存储结构优先定性。'CREDITOS'（单词式
    显示值，不被预过滤）在键列表对象中走分支 11 得 localization_key_
    list；若分支顺序被改成 code_heavy 先判，reason 会变成
    code_heavy_identifier（本用例红）。键标识符用不命中命名猜测层的
    形态（x9y 类，含 a-f 的 'a12b' 会命中字符区间表 pattern 被 engine
    预过滤）。"""
    entries = _entries("x9y", "q7r", "zz9", "j4k", "m2n", "w8v",
                       "get_X", "get_Y", "CREDITOS")
    hit = _find(entries, "CREDITOS")
    assert hit.status == "skipped"
    assert hit.meta["reason"] == "localization_key_list"


def test_core_menu_collection_beats_sentence_tier():
    """核心菜单集合对象（≥2 菜单词）里的 'Settings'：菜单集合分支在句子
    档之前——集合信号给单词高置信显示身份（reason=core_menu_collection
    而非落入 identifier 分支）。"""
    entries = _entries("Settings", "Quit")
    hit = _find(entries, "Settings")
    assert hit.status == "pending"
    assert hit.meta["reason"] == "core_menu_collection"


def test_sentence_beats_object_display_evidence():
    """值特征对象（Localization 标记）里的句子：句子档分支在
    object_has_display_evidence 之前——句子是更强证据，reason 精确。"""
    raw = _with_len("UnityEngine.Localization") + _with_len("A visible sentence here.")
    entries = _raw_string_entries("f1", 5, raw, {}, "sharedassets0.assets")
    hit = _find(entries, "A visible sentence here.")
    assert hit.status == "pending"
    assert hit.meta["reason"] == "natural_language"


def test_code_line_beats_interaction_prompt():
    """Lua 代码行在交互对象里：代码行分支在交互提示之前——代码行不被
    交互提示规则放行（硬结构规则优先于显示形态）。"""
    raw = _with_len("Press E to open") + _with_len("local choice = {}")
    entries = _raw_string_entries("f1", 5, raw, {}, "sharedassets0.assets")
    hit = _find(entries, "local choice = {}")
    assert hit.status == "skipped"
    assert hit.meta["reason"] == "code_line"


# ── C. 证据分层豁免（显式显示证据 > 对象级猜测）──────────────────────

def test_ui_word_signal_waives_small_config_but_unknown_words_do_not():
    """白名单显示词（'Pause'+'Menu'）豁免小配置跳过；同形态的非白名单词
    （'Timothy'+'White Flash' 引擎配置名）不得豁免——豁免只对显式显示
    词生效，猜测性放行不得扩大。"""
    waive = _entries("Pause", "Menu")
    assert _find(waive, "Pause").status == "pending"
    assert _find(waive, "Menu").status == "pending"
    no_waive = _entries("Timothy", "White Flash")
    assert _find(no_waive, "Timothy").status == "skipped"
    assert _find(no_waive, "Timothy").meta["reason"] == "shared_resource_config_object"


def test_resources_single_display_word_beats_resource_guess():
    """resources.assets 单串对象：白名单词 'Continue' 优先于「单串即资源键」
    猜测（放行）；非白名单标识符 'timothy' 保持跳过。"""
    display = _raw_string_entries(
        "f1", 5, _with_len("Continue"), {}, "resources.assets")
    hit = _find(display, "Continue")
    assert hit.status == "pending"
    assert hit.meta["reason"] == "single_visible_string"
    guess = _raw_string_entries(
        "f1", 5, _with_len("timothy"), {}, "resources.assets")
    hit2 = _find(guess, "timothy")
    assert hit2.status == "skipped"
    assert hit2.meta["reason"] == "resource_identifier_without_display_evidence"


def test_code_heavy_display_word_requires_ui_evidence():
    """代码重对象里的白名单词：有 UI 证据（≥3 控件状态名）才放行
    （code_heavy_display_word）；无 UI 证据保持跳过（code_heavy_identifier）
    ——白名单词是按钮文本还是代码常量靠对象证据区分。"""
    no_ui = _entries("System.Boolean, mscorlib", "System.Single, mscorlib", "Play")
    hit = _find(no_ui, "Play")
    assert hit.status == "skipped"
    assert hit.meta["reason"] == "code_heavy_identifier"
    with_ui = _entries(
        "System.Boolean, mscorlib", "System.Single, mscorlib",
        "Normal", "Highlighted", "Pressed", "Play")
    hit2 = _find(with_ui, "Play")
    assert hit2.status == "pending"
    assert hit2.meta["reason"] == "code_heavy_display_word"


# ── D. 三层判定契约（确定性 > 门控 > 命名猜测）───────────────────────

def test_naming_layer_is_fallback_after_core():
    """'lockedEntrance'：核心层（确定性形态）不命中，命名猜测层兜底——
    证明三层是「core 先判、naming 兜底」而非合并判定（core 独立可测）。"""
    assert is_engine_string_core("lockedEntrance") is False
    assert is_engine_string("lockedEntrance") is True


def test_gated_words_flow_to_rawstr_classifier():
    """'press'：门控层命中但 rawstr 预过滤不拦（extractor 用 is_engine_string
    不含 gated）——门控词流入分类链按证据放行（'Press' 按钮文本 / 交互
    提示同形）。若有人把 gated 并入预过滤，本用例红（R2 契约）。"""
    assert is_engine_string_gated("press") is True
    assert is_engine_string("press") is False
    entries = _raw_string_entries("f1", 5, _with_len("Press E to open"), {}, "sharedassets0.assets")
    assert _find(entries, "Press E to open").status == "pending"


def test_core_layer_unconditional():
    """'monologuetable'：确定性层命中即拦，不依赖上下文（与 naming 层
    的猜测性质形成对照）。"""
    assert is_engine_string_core("monologuetable") is True
    assert is_engine_string("monologuetable") is True


def test_hidden_shader_prefix_unconditional():
    """'Hidden/Post FX/FXAA'：引擎内置 shader 路径——确定性形态，任何
    上下文都拦（tiiny-ragdoll 启动卡死实证，翻译破坏 Shader.Find）。"""
    assert is_engine_string("Hidden/Post FX/FXAA") is True
    entries = _raw_string_entries(
        "f1", 5, _with_len("Hidden/Post FX/FXAA"), {}, "sharedassets0.assets")
    hit = _find(entries, "Hidden/Post FX/FXAA")
    assert hit.meta["reason"] == "prefilter_engine_string"
