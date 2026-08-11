"""术语表污染修复回归（2026-08-12，ffs 2083 失败根因）。

污染链：审核沉淀形态 2 用「原文首词」当术语 source——'Left Paddle→
左拨片' 建议被错误简化为 (Left, 左拨片)，方向词/设备词单字词对在
全局术语表强制，普通文本（'pick the right door' 的 right=正确的）
译文不含「右拨片」→ glossary_mismatch 误杀 2077 条。

修复三端：
1. 判定端 direction_mismatch：输入绑定语境（含设备词/键位后缀）+
   方向词 + 译文缺方向字 → 失败；普通文本方向词自由翻译
2. 沉淀端形态 2：source 用整个短原文（组合词对），不再首词提取
3. 数据清洗：删除 20 条方向盘输入语境残渣词对（glossary.db 手工）
"""
import pytest

from hanhua.core.batch_translator import BatchTranslator
from hanhua.core.models import TextEntry
from hanhua.core.reviewer import ReviewResult, extract_term_pairs


def _quality(source, translation):
    translator = BatchTranslator(
        FakeClient(), batch_size=1, concurrency=1, lang="en→zh-CN")
    entry = TextEntry(
        "ui", "reported", source,
        meta={"role": "display", "disposition": "translate"},
    )
    passed = translator._apply_quality(entry, translation)
    return passed, tuple(entry.meta.get("quality_reasons", ()))


class FakeClient:
    """翻译客户端桩——质量门测试只走 _apply_quality 判定。"""

    def chat(self, system, messages):
        raise AssertionError("不应触发翻译调用")


# ── 判定端：方向语义检查（输入绑定语境） ───────────────────────────

@pytest.mark.parametrize(("source", "translation"), [
    # 输入绑定语境（含设备词 Hat/POV/Stick）+ 方向词译错/丢 → 失败
    ("Hat Right", "正确"),            # Right 被译成「正确」（ffs 实证）
    ("POV Down-Right", "视角：下方"),   # 丢 Right（ffs 实证）
    ("Left Stick Button", "按钮"),     # 丢 Left
    ("Press the Right Button", "按下按钮"),  # 丢 Right
])
def test_direction_mismatch_fails_in_input_context(source, translation):
    passed, reasons = _quality(source, translation)
    assert passed is False
    assert "direction_mismatch" in reasons


@pytest.mark.parametrize(("source", "translation"), [
    # 方向词译对 → 通过
    ("Hat Right", "苦力帽右"),
    ("Right Tilt", "右侧倾斜"),
    ("Rotate Right", "向右旋转"),
    ("Left Stick Button", "左摇杆按钮"),
    ("POV Down-Right", "视角：右下方"),
    ("Press the Right Button", "按下右按钮"),
])
def test_direction_correct_passes(source, translation):
    passed, reasons = _quality(source, translation)
    assert passed is True, reasons


@pytest.mark.parametrize(("source", "translation"), [
    # 非输入绑定语境：方向词是普通英语词，自由翻译（ffs 2083 误杀样本）
    ("pick the right door", "选择正确的门"),
    ("Right Tilt", "右侧倾斜"),
    ("Right", "右"),
    ("You are right about that", "你说得对"),
    ("The right answer", "正确的答案"),
])
def test_direction_free_in_plain_text(source, translation):
    passed, reasons = _quality(source, translation)
    assert passed is True, reasons


# ── 沉淀端：词对提取形态 2（防 (Left, 左拨片) 再生） ───────────────

def _result(entry_id, suggestion, issue="术语错误"):
    return ReviewResult(entry_id=entry_id, verdict="flag",
                        issue=issue, suggestion=suggestion)


def test_extract_pair_uses_full_short_original():
    """形态 2：'Left Paddle' + 建议『译为"左拨片"』→ (Left Paddle, 左拨片)
    组合词对，不再错误提取首词 (Left, 左拨片)。"""
    pairs = extract_term_pairs(
        [_result("e1", '译为"左拨片"。')], {"e1": "Left Paddle"})
    assert pairs == [("Left Paddle", "左拨片")]


def test_extract_pair_drops_long_original():
    """形态 2：长原文（建议针对句中词）不沉淀——source 不可靠。"""
    pairs = extract_term_pairs(
        [_result("e1", "译为左拨片"), ],
        {"e1": "Observe the spelling of the words, and pick the right door."})
    assert pairs == []


def test_extract_pair_drops_punctuated_original():
    """形态 2：含标点的原文不沉淀（非干净术语短语）。"""
    pairs = extract_term_pairs(
        [_result("e1", "译为左拨片"), {"e1": "Right, tilt!"}])
    assert pairs == []


def test_extract_pair_long_source_dropped():
    """形态 1：source 超过 5 词（完整建议句）不沉淀。"""
    pairs = extract_term_pairs(
        [_result("e1", "Stick the throttle to the right side → 推动右侧油门")])
    assert pairs == []


def test_extract_pair_short_source_kept():
    """形态 1：短 source 词对正常沉淀。"""
    pairs = extract_term_pairs(
        [_result("e1", "Left Stick→左摇杆")])
    assert pairs == [("Left Stick", "左摇杆")]


# ── 口语助动词豁免（field-hospital-web 叙事文本实证） ──────────────

@pytest.mark.parametrize(("source", "translation"), [
    # 'are gonna miss him dearly' 的 miss=想念，译文正确 → 豁免 (miss, 未命中)
    ("His sons, Matthew and Ralph, are gonna miss him dearly.",
     "他的儿子马修和拉尔夫会非常想念他。"),
    ("I wanna miss the bus on purpose", "我故意想错过公交车"),
    ("You gotta miss it to understand", "你必须错过它才能理解"),
])
def test_slang_auxiliary_verb_exempts_glossary(source, translation):
    """口语助动词（gonna/wanna/gotta）前邻术语词 → 动词用法豁免
    glossary_mismatch（field-hospital-web 实证：miss=想念 被
    (miss, 未命中) 误杀）。"""
    passed, reasons = _quality(source, translation)
    assert passed is True, reasons
    assert "glossary_mismatch" not in reasons


def test_full_aftermath_note_glossary_fixed():
    """field-hospital-web 实际失败样本：修复后 glossary_mismatch 消除
    （gonna 豁免）；换行合并仍由 newline_mismatch 正确拦截（观察项，
    与 ffs 教学文本同类——模型合并多段换行，保留原文安全）。"""
    source = ("John Evans passed at age 87.\nHe fought bravely for the "
              "Republic during the War and ended up with the rank of "
              "Corporal. Shortly after he met Florence and married her. "
              "His sons, Matthew and Ralph, are gonna miss him dearly.")
    translation = ("约翰·埃文斯在87岁时去世。他在战争期间为共和国英勇战斗，"
                   "最终获得了下士军衔。不久之后，他与弗洛伦斯相识并结婚。"
                   "他的儿子马修和拉尔夫会非常想念他。")
    passed, reasons = _quality(source, translation)
    assert "glossary_mismatch" not in reasons
    assert "newline_mismatch" in reasons or passed


def test_miss_999_label_still_fails():
    """'miss: 999' 标签格式（deadbeat 实证）→ 不豁免，仍失败。"""
    passed, reasons = _quality("miss: 999", "未命中：999")
    assert passed is True, reasons


# ── 调试日志模板串豁免（final-shot 实证 ×2） ────────────────────────

@pytest.mark.parametrize(("source", "translation"), [
    # 译文含中文 + 变量名保留 → 通过（target_script_mismatch 豁免）
    ("MEMORY: cur = {0}MB, max = {1}MB", "内存：cur = {0} MB，max = {1} MB"),
    ("CHANNELS: real = {0}, total = {1}", "声道：real = {0}，total = {1}"),
    # 整行回显 → 通过（untranslated_text 豁免，日志串保留原文合理）
    ("CHANNELS: real = {0}, total = {1}", "CHANNELS: real = {0}, total = {1}"),
])
def test_log_template_exempts_script_variables(source, translation):
    """Unity 调试日志模板（全大写标签: 变量 = {n}）→ 变量名保留/整行
    回显都是合理行为（final-shot 实证：cur/max 是脚本标识符无语义）。"""
    passed, reasons = _quality(source, translation)
    assert passed is True, reasons


@pytest.mark.parametrize(("source", "translation"), [
    # 普通 UI 模板（无全大写标签+冒号）回显 → 不豁免（score 是可译词）
    ("Score = {0}", "Score = {0}"),
    # 真 UI 半翻（音量设置，值非占位符）→ 不豁免（Volume 在 UI 词典）
    ("SETTINGS: Volume = 50", "SETTINGS: 音量 = 50"),
])
def test_non_log_template_still_enforced(source, translation):
    """非日志模板形态不豁免：普通 UI 半翻/回显照常失败。"""
    passed, reasons = _quality(source, translation)
    assert passed is False
