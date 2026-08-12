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
