"""fix-31 键名词对污染链 + 引号动作词豁免（headache 实证 2026-08-12）。

headache 第二轮 9 失败中 7 条根因：
1. PRESS SPACE TO CONTINUE/RESTART ×5 →「按空格键…」被 glossary_mismatch
   误杀——happy-cat-tavern 的 UI 词 Space→空间 learn 沉淀成词对，fix-27
   键名词对豁免只覆盖 _KEY_LABEL_CASEFOLD（强制表），space 因有中文通称
   「空格」被排除出强制表 → 词对豁免漏网，污染词对跨游戏误杀正确译文。
   修复：词对豁免扩到 PHYSICAL_KEY_NAMES_CASEFOLD 全集。
2. PRESS E TO INTERACT ×2 →「点击"PRESS E"以进行互动」被
   action_word_residue 误杀——引号内短语在原文出现是模型引用 UI 提示
   原文（untranslated_text 分支已有 quoted_terms 豁免，该分支缺失）。
   修复：action_word_residue 对齐 untranslated_text 的引号豁免。
"""
from tests.test_quality import _entry, validate_translation_quality


def test_space_glossary_pair_no_longer_kills():
    """'PRESS SPACE TO RESTART' →「按空格键进行重启」：SPACE 不在强制表
    （有中文通称「空格」），但 (SPACE→空间) 词对污染源覆盖全键名集 →
    豁免命中 → glossary_mismatch 不再误杀（headache 实证 5 条样本）。"""
    ok = validate_translation_quality(
        _entry("PRESS SPACE TO RESTART"), "按空格键进行重启")
    assert "glossary_mismatch" not in ok.reasons
    assert ok.passed


def test_shift_glossary_pair_still_exempt():
    """'Camera Control - Shift + RMB' →「镜头控制 - Shift + RMB」：SHIFT
    在强制表也在全键名集，词对豁免行为不变（goodmorning 实证回归）。"""
    ok = validate_translation_quality(
        _entry("Camera Control - Shift + RMB"), "镜头控制 - Shift + RMB")
    assert "glossary_mismatch" not in ok.reasons
    assert ok.passed


def test_rmb_renminbi_pair_still_blocks():
    """'RMB to scope' →「人民币 给 范围」：词对豁免只跳过检查，词对本身
    仍是污染——译文丢键名依然被 key_name_mistranslated 拦（fix-27/30
    回归，防污染词对场景）。"""
    bad = validate_translation_quality(
        _entry("RMB to scope"), "人民币 给 范围")
    assert "key_name_mistranslated" in bad.reasons
    assert not bad.passed


def test_quoted_press_e_passes():
    """'PRESS E TO INTERACT' →「点击"PRESS E"以进行互动」：PRESS 在引号内
    且引号内短语在原文出现（模型引用 UI 提示原文）→ action_word_residue
    引号豁免（headache 实证 2 条样本）。"""
    ok = validate_translation_quality(
        _entry("PRESS E TO INTERACT"), '点击"PRESS E"以进行互动')
    assert "action_word_residue" not in ok.reasons
    assert ok.passed


def test_unquoted_action_residue_still_fails():
    """'TOSS TRASH' →「TOSS 垃圾」：无引号包裹 → 动作词残留仍判失败
    （zero-deaths 知识库规则回归）。"""
    bad = validate_translation_quality(
        _entry("TOSS TRASH"), "TOSS 垃圾")
    assert "action_word_residue" in bad.reasons
    assert not bad.passed


def test_quoted_but_missing_elsewhere_still_fails():
    """'PRESS E TO INTERACT' →「点击"PRESS E"以进行互动 PRESS」：引号豁免
    放行引号内 PRESS，但译文另有裸露 PRESS 残留 → 仍失败。"""
    bad = validate_translation_quality(
        _entry("PRESS E TO INTERACT"), '点击"PRESS E"以进行互动 PRESS')
    assert "action_word_residue" in bad.reasons
    assert not bad.passed
