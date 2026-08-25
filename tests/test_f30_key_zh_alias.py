"""fix-30 键名中文通称豁免（headache 实证 2026-08-12）。

'PRESS SPACE TO RESTART' →「按空格键进行重启」、「PRESS ESCAPE TO GO
BACK」→「按 ESC 键以返回」——按键名译成中文标准通称/简写是正确翻译
（玩家能识别），input_token_mismatch（按键字面量序列检查）与
key_name_mistranslated（键名保留检查）却要求译文中含英文键名原文而
误杀。修复：键名中文通称等价表（空格=space、esc=escape…）——译文含
通称即视为键名保留。

反例锁定：RMB 译「人民币」（无「右键」通称）仍失败；键名丢失（
「拿起锤子」无 RMB/右键）仍失败。
"""
from tests.test_quality import _entry, validate_translation_quality


def test_space_key_zh_alias_passes():
    """'PRESS SPACE TO RESTART' →「按空格键进行重启」：SPACE 按键
    token 无英文字面量但含中文通称「空格」→ input_token_mismatch
    豁免通过（headache 实证误杀样本）。"""
    ok = validate_translation_quality(
        _entry("PRESS SPACE TO RESTART"), "按空格键进行重启")
    assert "input_token_mismatch" not in ok.reasons
    assert ok.passed


def test_escape_key_zh_alias_passes():
    """'PRESS ESCAPE TO GO BACK' →「按 ESC 键以返回」：ESCAPE 的
    key_name_mistranslated 与 input_token_mismatch 均被「esc」通称
    豁免（headache 实证双误杀样本）。"""
    ok = validate_translation_quality(
        _entry("PRESS ESCAPE TO GO BACK"), "按 ESC 键以返回")
    assert "key_name_mistranslated" not in ok.reasons
    assert "input_token_mismatch" not in ok.reasons
    assert ok.passed


def test_rmb_zh_alias_passes():
    """'RMB TO PICK UP THE HAMMER' →「鼠标右键拿起锤子」：RMB 中文
    通称「右键」→ key_name_mistranslated 豁免通过。"""
    ok = validate_translation_quality(
        _entry("RMB TO PICK UP THE HAMMER"), "鼠标右键拿起锤子")
    assert "key_name_mistranslated" not in ok.reasons
    assert ok.passed


def test_rmb_lost_still_fails():
    """'RMB TO PICK UP THE HAMMER' →「拿起锤子」：键名丢失（无 RMB
    字面量也无「右键」通称）→ 仍失败（headache 真失败样本，拦截正确）。"""
    bad = validate_translation_quality(
        _entry("RMB TO PICK UP THE HAMMER"), "拿起锤子")
    assert "key_name_mistranslated" in bad.reasons
    assert not bad.passed


def test_rmb_renminbi_still_fails():
    """RMB→「人民币」：无「右键」通称 → 仍失败（fix-27 防污染词对
    场景回归——污染词对 RMB→人民币 必须继续被拦）。"""
    bad = validate_translation_quality(
        _entry("RMB to scope"), "人民币 给 范围")
    assert "key_name_mistranslated" in bad.reasons


def test_escape_plain_word_not_mistranslated():
    """'escape the room' →「逃离房间」：escape 兼作普通英语词（逃跑），
    排除键名强制检查（fix-30 新增排除）→ 不再误杀。"""
    ok = validate_translation_quality(
        _entry("escape the room"), "逃离房间")
    assert "key_name_mistranslated" not in ok.reasons


def test_shift_noun_night_shift_not_mistranslated():
    """fix-54 键名兼作普通名词：'night shift / day shift' 的 shift 是
    「班次」普通名词，译文「夜班/日班」完全正确——源文小写普通名词形态
    非键位绑定 → key_name_mistranslated 跳过（Flabby Pizza 实证 3 条
    对话被误杀阻断）。"""
    for original, translation in (
            ("Boss: How was your night shift yesterday?", "老板：昨天夜班过得怎么样？"),
            ("Find the apartment key to head out for your night shift",
             "找到公寓钥匙，然后去参加夜班工作"),
            ("Boss: Your job consists of cleaning the pizzeria and preparing pizza for the day shift",
             "老板：你的任务就是清洁披萨店，并为当日班次的员工准备披萨。")):
        ok = validate_translation_quality(_entry(original), translation)
        assert "key_name_mistranslated" not in ok.reasons
        assert ok.passed


def test_shift_binding_still_enforced():
    """键名兼作普通名词的判别不放过真键位绑定：源文大写专有键拼写
    （Shift/RMB）或作为交互提示字面量（Press Shift to…）→ 仍强制保留，
    译成中文仍判失败。"""
    # 大写专有键拼写 → 强制保留
    bad = validate_translation_quality(
        _entry("Camera Control - Shift + RMB"), "相机控制 - 移位 + 人民币")
    assert "key_name_mistranslated" in bad.reasons
    # 交互提示字面量（小写 shift 也是按键）→ 强制保留
    bad2 = validate_translation_quality(
        _entry("Press Shift to sprint"), "按 移位 冲刺")
    assert "key_name_mistranslated" in bad2.reasons
    # 真绑定保留键名 → 通过
    ok = validate_translation_quality(
        _entry("Camera Control - Shift + RMB"), "相机控制 - Shift + RMB")
    assert "key_name_mistranslated" not in ok.reasons
    assert ok.passed
