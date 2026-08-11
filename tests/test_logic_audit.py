"""写回逻辑层审计（logic_audit）测试。

覆盖：逻辑敏感形态识别、写回前审计分级（只报告不阻断）、rawstr 扩容
记录、重开逻辑验证（译文存在性 / 序列对齐 / 短译文豁免 / 边界破坏
检出 / 译文缺失检出）。
"""
from __future__ import annotations

from hanhua.core.unity.logic_audit import (
    audit_entries_before_writeback,
    audit_raw_expansion,
    logic_pattern_of,
    snapshot_object_strings,
    verify_logic_layer,
)


def _ser_str(s: str) -> bytes:
    """Unity 序列化字符串：int32 长度头 + UTF-8 内容 + 4 字节对齐零填充。"""
    data = s.encode("utf-8")
    return len(data).to_bytes(4, "little") + data + b"\x00" * (-(4 + len(data)) % 4)


def _align(value: int, boundary: int = 4) -> int:
    return value + (-value % boundary)


def _patch_first(raw: bytearray, translation: str) -> bytearray:
    """模拟 _patch_serialized_string 对 offset=0 字符串的原位替换。"""
    old_length = int.from_bytes(raw[0:4], "little")
    old_end = _align(4 + old_length)
    payload = translation.encode("utf-8")
    new_end = _align(4 + len(payload))
    raw[0:old_end] = (
        len(payload).to_bytes(4, "little")
        + payload
        + b"\x00" * (new_end - 4 - len(payload))
    )
    return raw


# ── 形态识别 ──────────────────────────────────────────────────────

def test_logic_pattern_of_identifies_identifier_shapes():
    assert logic_pattern_of("fieldtrigger") == "lowercode_word"
    assert logic_pattern_of("doPunch") == "camel_case"
    assert logic_pattern_of("enemy_spawner") == "snake_case"
    assert logic_pattern_of("MENU_PLAY") == "uppercase_const"
    assert logic_pattern_of("player2") == "numeric_mix"
    assert logic_pattern_of(
        "UnityEngine.UI.Text, UnityEngine") == "type_descriptor"
    assert logic_pattern_of("Doctor, Doctor") is None   # 对话文本不误报
    assert logic_pattern_of("dEad") == "camel_case"  # 游戏 stylization 大小写
    assert logic_pattern_of("settings") == "lowercode_word"  # 长纯小写词
    assert logic_pattern_of("WASD") is None        # 全大写短词——合法显示文本
    assert logic_pattern_of("Hello World") is None  # 正常句子
    assert logic_pattern_of("点 击") is None
    assert logic_pattern_of("") is None


def test_audit_before_writeback_reports_without_blocking():
    entries = [
        {"key_path": "a", "original": "back", "translation": "返回"},
        {"key_path": "b", "original": "doPunch", "translation": "出拳"},
        {"key_path": "c", "original": "Hello World", "translation": "你好世界"},
        {"key_path": "d", "original": "back", "translation": "back"},  # 回显不审
        {"key_path": "e", "original": "Settings", "translation": "设置"},
    ]
    audit = audit_entries_before_writeback(entries)
    by_loc = {a["locator"]: a for a in audit}
    # 只报告不阻断：正常句子不产生记录，回显跳过
    assert "c" not in by_loc and "d" not in by_loc
    # 代码标识符形态 → warn
    assert by_loc["b"]["pattern"] == "camel_case"
    assert by_loc["b"]["severity"] == "warn"
    # 常见按钮文本短词 → note
    assert by_loc["a"]["pattern"] == "short_code_word"
    assert by_loc["a"]["severity"] == "note"


def test_audit_raw_expansion_records_only_growth():
    entry = {"key_path": "k"}
    growth = audit_raw_expansion(entry, {"obj": 7},
                                 "Start", "开始游戏")
    assert growth is not None
    assert growth["src_bytes"] == 5 and growth["dst_bytes"] == 12
    shrink = audit_raw_expansion(entry, {"obj": 7},
                                 "Settings", "设置")
    assert shrink is None
    same = audit_raw_expansion(entry, {"obj": 7},
                               "Hello", "Hello")
    assert same is None


# ── 快照与重开验证 ────────────────────────────────────────────────

def test_snapshot_object_strings_lists_all_visible():
    raw = _ser_str("Start") + _ser_str("Welcome")
    assert snapshot_object_strings(raw) == ["Start", "Welcome"]


def test_verify_logic_layer_ok_when_translation_expands():
    """中文译文扩容（插入字节后移后续字段）——序列对齐后必须通过。"""
    raw = bytearray(_ser_str("Start") + _ser_str("Welcome"))
    expected = snapshot_object_strings(bytes(raw))
    _patch_first(raw, "开始游戏")          # 5 字节 → 12 字节（扩容）
    ok, problems = verify_logic_layer(
        bytes(raw), expected, {"Start": "开始游戏"})
    assert ok, problems


def test_verify_logic_layer_short_translation_exempt():
    """短译文（2 中文字符 < 扫描 min_len=3）——扫描不可见是预期行为。"""
    raw = bytearray(_ser_str("Settings") + _ser_str("Welcome"))
    expected = snapshot_object_strings(bytes(raw))
    _patch_first(raw, "设置")
    ok, problems = verify_logic_layer(
        bytes(raw), expected, {"Settings": "设置"})
    assert ok, problems


def test_verify_logic_layer_detects_broken_boundary():
    """后续字符串长度头被破坏 → 序列缺失 → 失败（写回必须拒绝）。"""
    raw = bytearray(_ser_str("Settings") + _ser_str("Welcome"))
    expected = snapshot_object_strings(bytes(raw))
    _patch_first(raw, "设置")
    # 破坏第二个字符串的长度头（把边界写坏）
    second_offset = 4 + 6 + 2  # 第一个字段补丁后 12 字节
    raw[second_offset:second_offset + 4] = b"\xff\xff\xff\xff"
    ok, problems = verify_logic_layer(
        bytes(raw), expected, {"Settings": "设置"})
    assert not ok
    assert any("Welcome" in p for p in problems)


def test_verify_logic_layer_detects_missing_translation():
    """译文字节未出现在写回后数据 → 失败。"""
    raw = _ser_str("Settings") + _ser_str("Welcome")
    expected = snapshot_object_strings(raw)
    ok, problems = verify_logic_layer(
        raw, expected, {"Settings": "设置"})   # 没补丁，译文不存在
    assert not ok
    assert any("未出现" in p for p in problems)


# ── 知识库案例转规则（2026-08-11）──

class TestUnityEventRule:
    """案例「UnityEvent 事件绑定断裂按钮无反应」→ 对象信号判定。"""

    def test_object_is_unityevent_detects_signals(self):
        from hanhua.core.unity.logic_audit import object_is_unityevent
        assert object_is_unityevent(["m_PersistentCalls", "SomeMethod"])
        assert object_is_unityevent(["persistentCalls", "OnClick"])
        assert object_is_unityevent(["m_Target", "m_MethodName"])
        assert not object_is_unityevent(["Settings", "Welcome"])
        assert not object_is_unityevent([])


class TestLogicKeyEvidence:
    """统一逻辑键判定（识别层与写回后反向审计共用）。"""

    def test_type_descriptor_reverts(self):
        from hanhua.core.unity.logic_audit import logic_key_evidence
        verdict = logic_key_evidence("System.String, mscorlib", {})
        assert verdict and verdict[0] == "revert"
        assert verdict[1] == "type_descriptor"

    def test_unityevent_object_binding_reverts(self):
        from hanhua.core.unity.logic_audit import logic_key_evidence
        obj_strings = ["m_PersistentCalls", "OnClick", "Play"]
        verdict = logic_key_evidence("OnClick", {}, obj_strings)
        assert verdict and verdict[0] == "revert"
        assert verdict[1] == "unityevent_binding"

    def test_code_object_compare_word_reverts(self):
        from hanhua.core.unity.logic_audit import logic_key_evidence
        # 代码对象（结构跳过身份）中的比较词 = 代码按字符串分发键
        verdict = logic_key_evidence("Continue",
                                     {"structural_reason": "code_heavy_identifier"})
        assert verdict and verdict[0] == "revert"
        assert verdict[1].startswith("logic_key_in_code_object")

    def test_input_binding_object_camel_reverts(self):
        from hanhua.core.unity.logic_audit import logic_key_evidence
        verdict = logic_key_evidence("moveForward",
                                     {"structural_reason": "input_binding"})
        assert verdict and verdict[0] == "revert"

    def test_identifier_without_context_reports(self):
        from hanhua.core.unity.logic_audit import logic_key_evidence
        verdict = logic_key_evidence("isReady", {})
        assert verdict and verdict[0] == "report"
        assert verdict[1] == "camel_case"

    def test_button_word_reports_but_not_reverts(self):
        from hanhua.core.unity.logic_audit import logic_key_evidence
        # 逻辑比较词无对象上下文：可能是真实按钮文本 → report 不 revert
        verdict = logic_key_evidence("Continue", {})
        assert verdict and verdict[0] == "report"
        assert verdict[1] == "logic_compare_word"

    def test_common_button_word_no_verdict(self):
        from hanhua.core.unity.logic_audit import logic_key_evidence
        # 常见按钮文本白名单（LOGIC_KEYS_COMMON）不触发短词 report；
        # 但 Back 同时是逻辑比较词（LOGIC_COMPARE_WORDS）→ report 复核
        assert logic_key_evidence("Back", {})[1] == "logic_compare_word"
        assert logic_key_evidence("Welcome", {}) is None
        assert logic_key_evidence("", {}) is None


class TestRepeatConsistency:
    """同原文互斥一致性（防「译文+原文」混排断链）。"""

    @staticmethod
    def _entry(original, translation, offset, structural=None):
        return ({"original": original, "translation": translation},
                {"obj": 7, "offset": offset, "structural_reason": structural})

    def test_structural_skip_reverts_whole_group(self):
        from hanhua.core.unity.logic_audit import audit_repeat_consistency
        items = [
            self._entry("Splash", "画面", 100),                       # 要翻译
            self._entry("Splash", "Splash", 140, structural="code_line"),  # 键身份
        ]
        records = audit_repeat_consistency(items)
        assert records and records[0]["action"] == "all_reverted"
        # 翻译条目被改回原文（保留原文防混排）
        assert items[0][0]["translation"] == "Splash"

    def test_inconsistent_translations_revert_whole_group(self):
        from hanhua.core.unity.logic_audit import audit_repeat_consistency
        items = [
            self._entry("Splash", "画面", 100),
            self._entry("Splash", "水花", 140),   # 模型波动：不同译文
        ]
        records = audit_repeat_consistency(items)
        assert records and records[0]["action"] == "all_reverted"
        assert "译文不一致" in records[0]["reason"]

    def test_consistent_group_untouched(self):
        from hanhua.core.unity.logic_audit import audit_repeat_consistency
        items = [
            self._entry("Splash", "画面", 100),
            self._entry("Splash", "画面", 140),
        ]
        assert audit_repeat_consistency(items) == []


class TestStringLengthHeaders:
    """译文长度头自证（扩容插入后长度头同步检查）。"""

    def test_correct_header_passes(self):
        from hanhua.core.unity.logic_audit import verify_string_length_headers
        raw = bytearray(_ser_str("Settings"))
        payload = "设置".encode("utf-8")
        raw[0:4] = (len(payload)).to_bytes(4, "little")  # 长度头同步
        raw[4:4 + len(payload)] = payload
        assert verify_string_length_headers(bytes(raw), {"Settings": "设置"}) == []

    def test_stale_header_detected(self):
        from hanhua.core.unity.logic_audit import verify_string_length_headers
        raw = bytearray(_ser_str("Settings"))
        payload = "设置".encode("utf-8")
        raw[4:10] = payload
        # 长度头还是旧值 8（未同步）
        raw[0:4] = (8).to_bytes(4, "little")
        problems = verify_string_length_headers(
            bytes(raw), {"Settings": "设置"})
        assert problems and any("长度头" in p for p in problems)
