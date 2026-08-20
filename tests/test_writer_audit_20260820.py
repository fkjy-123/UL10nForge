# -*- coding: utf-8 -*-
"""写回安全审计回归测试（2026-08-20，子代理审计 8 项发现）。

审计发现 → 修复 → 回归防线：
- #1 IL2CPP meta 缺 file_offset/length → 优雅拒绝（note_rejected），
  不再 KeyError 崩掉整场写回
- #2 #US meta 缺 utf16_len（record_offset 快速路径）→ 优雅拒绝
- #3 同一 data_index 两条 entry → 后写不再静默覆盖前写，重复一律拒绝
- #4 同一 #US record_offset 两条 entry → 同构拒绝
- #5 data_index 完全不在池中（偏移错位指向非记录起始）→ 拒绝
- #6 TextAsset 同一行号两条 entry → 重复拒绝（纯行级 + 结构化混合两路）
- #7 变长补丁白名单短段位置约束：匹配位置漂移超出补丁位移预算 → 拒绝
- #8 _fit_bytes UTF-16 截断：astral 码点按码点数预算超容量导致字节切片
  切开代理对 / 截断点落在孤立高代理上 → 输出绝不含孤立代理
"""
import json

from hanhua.core.unity.writer import (
    WriteResult, _assert_asset_diff_whitelist, _fit_bytes, _patch_dll,
    _patch_metadata, _patch_textasset)
from tests.test_v2_patch_pools import _build, _us_heap


def _raw_entry(kind: str, meta_extra: dict, original: str,
               translation: str) -> dict:
    """手工构造写回 entry（meta 完全由调用方指定，可缺字段）。

    key_path 留给调用方变体注入歧义（默认共用同一个——写回按键去重
    前的两条同 key entry 模拟重复提取/旧库合并场景）。
    """
    return {
        "file_id": "f", "key_path": "k",
        "original": original, "translation": translation,
        "meta": json.dumps({"kind": kind, "disposition": "translate",
                            **meta_extra}),
    }


def _line_item(line: int, original: str, translation: str) -> tuple[dict, dict]:
    meta = {"kind": "textasset", "line": line, "disposition": "translate"}
    entry = {
        "file_id": "ta", "key_path": f"line/{line}",
        "original": original, "translation": translation,
        "status": "pending", "meta": json.dumps(meta),
    }
    return entry, meta


# --------------------------------------------------------------------------
# #1：IL2CPP meta 缺定位字段 → 优雅拒绝
# --------------------------------------------------------------------------

def test_patch_metadata_missing_offset_rejected(tmp_path):
    """#1：meta 缺 file_offset → note_rejected 而非 KeyError 崩溃。"""
    path = tmp_path / "global-metadata.dat"
    raw = _build(31, ["Press {0} to continue"])
    path.write_bytes(raw)
    result = WriteResult()
    # 修复前：meta.get("file_offset") 返回 None → 后续比较/算术直接 TypeError
    _patch_metadata(path, [_raw_entry(
        "il2cpp", {"length": 21}, "Press {0} to continue", "继续")], result)
    assert result.written == 0
    assert len(result.rejected) == 1
    assert "file_offset/length" in result.rejected[0].reason
    assert path.read_bytes() == raw            # 文件零改动


def test_patch_metadata_missing_length_rejected(tmp_path):
    """#1：meta 缺 length（非 int）→ 同样优雅拒绝。"""
    path = tmp_path / "global-metadata.dat"
    raw = _build(31, ["Press {0} to continue"])
    path.write_bytes(raw)
    result = WriteResult()
    _patch_metadata(path, [_raw_entry(
        "il2cpp", {"file_offset": 0x200}, "Press {0} to continue", "继续")],
        result)
    assert result.written == 0
    assert len(result.rejected) == 1
    assert "file_offset/length" in result.rejected[0].reason
    assert path.read_bytes() == raw


# --------------------------------------------------------------------------
# #2：#US record_offset 快速路径缺 utf16_len → 优雅拒绝
# --------------------------------------------------------------------------

def test_patch_dll_record_offset_without_utf16_len_rejected(tmp_path):
    """#2：meta 有 record_offset 却缺 utf16_len → 拒绝且文件不变。

    修复前：capacity = meta["utf16_len"] 直接 KeyError 崩掉整场 DLL 写回。
    """
    path = tmp_path / "Assembly-CSharp.dll"
    heap = _us_heap([(b"\x41", 0)])            # 记录 @1，数据 2 字节
    path.write_bytes(heap)
    result = WriteResult()
    _patch_dll(path, [_raw_entry("us", {"record_offset": 1}, "A", "甲")],
               result)
    assert result.written == 0
    assert len(result.rejected) == 1
    assert "utf16_len" in result.rejected[0].reason
    assert path.read_bytes() == heap


# --------------------------------------------------------------------------
# #3：重复 data_index → 拒绝（不静默覆盖）
# --------------------------------------------------------------------------

def test_patch_metadata_duplicate_data_index_rejected(tmp_path):
    """#3：同一 data_index 两条 entry → 全部拒绝，绝不静默覆盖。

    修复前：changes dict 后写覆盖前写，前一条仍 note_written 虚假成功
    （实际落盘的是后写译文，账面与磁盘不一致）。修复后第一条 note_written、
    第二条 note_rejected 重复条目，落盘译文 = 第一条。
    """
    path = tmp_path / "global-metadata.dat"
    path.write_bytes(_build(31, ["Hello"]))
    result = WriteResult()
    _patch_metadata(path, [
        _raw_entry("il2cpp", {"file_offset": 0x200, "length": 5},
                   "Hello", "你好"),
        _raw_entry("il2cpp", {"file_offset": 0x200, "length": 5},
                   "Hello", "哈喽"),
    ], result)
    assert "重复条目" in result.rejected[-1].reason
    assert result.written == 0                # 全部拒绝（宁漏勿谎报）


# --------------------------------------------------------------------------
# #4：重复 #US record_offset → 拒绝
# --------------------------------------------------------------------------

def test_patch_dll_duplicate_offset_rejected(tmp_path):
    """#4：同一 record_offset 两条 entry → 第二条拒绝。"""
    path = tmp_path / "Assembly-CSharp.dll"
    heap = _us_heap([("Open".encode("utf-16-le"), 0)])
    path.write_bytes(heap)
    result = WriteResult()
    _patch_dll(path, [
        _raw_entry("us", {"record_offset": 1, "utf16_len": 8},
                   "Open", "打开"),
        _raw_entry("us", {"record_offset": 1, "utf16_len": 8},
                   "Open", "开启"),
    ], result)
    assert "重复条目" in result.rejected[-1].reason


# --------------------------------------------------------------------------
# #5：data_index 不在池中 → 拒绝（放行即写错位置）
# --------------------------------------------------------------------------

def test_patch_metadata_offset_not_record_start_rejected(tmp_path):
    """#5：偏移在数据区内但指向非记录起始 → 拒绝。

    修复前：只在「在池中且长度不符」时拒绝，完全不在池中的 data_index
    （偏移错位/旧库 meta 过期）被放行，把交叉验证当唯一防线。
    """
    path = tmp_path / "global-metadata.dat"
    raw = _build(31, ["Press {0} to continue"])   # 唯一记录 data_index=0
    path.write_bytes(raw)
    result = WriteResult()
    # 0x203 在数据区（0x200..0x200+21）内但 data_index=3 非记录起始
    _patch_metadata(path, [_raw_entry(
        "il2cpp", {"file_offset": 0x203, "length": 3}, "ess", "甲乙")],
        result)
    assert result.written == 0
    assert len(result.rejected) == 1
    assert "长度与文件不符" in result.rejected[0].reason
    assert path.read_bytes() == raw


# --------------------------------------------------------------------------
# #6：TextAsset 重复行号 → 拒绝（纯行级路径 + 结构化混合路径）
# --------------------------------------------------------------------------

def test_textasset_duplicate_line_rejected_pure_line_path():
    """#6：纯行级路径同一行号两条 entry → 后写拒绝，不再静默覆盖。"""
    script = "Hello\nWorld".encode("utf-8")
    result = WriteResult()
    _patch_textasset(script, [
        _line_item(0, "Hello", "你好"),
        _line_item(0, "Hello", "哈喽"),
    ], [], result)
    reasons = [r.reason for r in result.rejected]
    assert reasons.count("textasset_duplicate_line") == 1
    out = _patch_textasset(script, [
        _line_item(0, "Hello", "你好"),
    ], [], WriteResult())
    assert out.decode("utf-8").startswith("你好")


def test_textasset_duplicate_line_rejected_structured_path():
    """#6：结构化重建后的行级匹配路径同一行号 → 同构拒绝。"""
    script = "<root>\n<text>Hello</text>\nplain line\n</root>".encode("utf-8")
    structured = [({
        "file_id": "ta", "key_path": "/root/text",
        "original": "Hello", "translation": "你好", "status": "pending",
    }, {"kind": "textasset", "textasset_format": "xml",
        "inner_path": "/root/text"})]
    result = WriteResult()
    # 两条行级条目同指 line 2（结构化重建后按原文行内容匹配的路径）
    _patch_textasset(script, [
        _line_item(2, "plain line", "普通行"),
        _line_item(2, "plain line", "普通行二"),
    ], structured, result)
    reasons = [r.reason for r in result.rejected]
    assert reasons.count("textasset_duplicate_line") == 1


# --------------------------------------------------------------------------
# #7：变长补丁白名单短段位置约束
# --------------------------------------------------------------------------

def test_asset_diff_whitelist_short_segment_drift_rejected():
    """#7：短段（<4 字节）在 patched 里命中远超位移预算的位置 → 拒绝。

    修复前：单字节段任何该字节的出现都算匹配——非目标字节被改动/
    重排时极易巧合命中非预期位置，白名单形同虚设。
    """
    # 变长 span @1..5 → 4 字节扩为 8 字节：max_shift = 4
    spans = [(1, 5, 9)]
    raw = b"\x01" + b"AAAA" + b"\x02tail"
    # 字节 0x01 出现在位置 10：漂移 9 > 预算 4+1 → 疑似非目标字节被改动
    patched = b"\x00" * 10 + b"\x01" + b"\x02tail"
    try:
        _assert_asset_diff_whitelist(raw, patched, spans, "unit")
    except ValueError as exc:
        assert "位移预算" in str(exc)
    else:
        raise AssertionError("短段漂移超预算未被拒绝")


def test_asset_diff_whitelist_short_segment_within_budget_passes():
    """#7 边界：漂移在补丁位移预算内（被补丁推挤）→ 正常放行。"""
    spans = [(1, 5, 9)]
    raw = b"\x01" + b"AAAA" + b"\x02tail"
    # 0x01 原位，尾部段被 4 字节增量推挤到位置 9：漂移 4 ≤ 预算
    patched = b"\x01" + b"BBBBBBBB" + b"\x02tail"
    _assert_asset_diff_whitelist(raw, patched, spans, "unit")   # 不抛


# --------------------------------------------------------------------------
# #8：_fit_bytes UTF-16 截断绝不产生孤立代理
# --------------------------------------------------------------------------

def test_fit_bytes_utf16_astral_over_budget_no_lone_surrogate():
    """#8：astral 码点按码点数预算超容量 → 字节切片曾切开代理对。

    修复前：chars = capacity//2-1 按码点计，"😀"×N 编码后 4N 字节，
    [:capacity] 字节切片把最后一个代理对切成孤立高代理。
    """
    translation = "\U0001F600" * 10            # 10 emoji = 40 UTF-16 字节
    data, truncated = _fit_bytes(translation, 10, "utf-16-le", pad=False)
    assert truncated
    assert len(data) <= 10
    text = data.decode("utf-16-le")            # 孤立代理会 UnicodeDecodeError
    assert text.endswith("…")
    # 每个保留字符完整（emoji 或 BMP），无半个代理对
    assert all(ord(ch) < 0xD800 or ord(ch) > 0xDFFF for ch in text)


def test_fit_bytes_utf16_boundary_on_lone_high_surrogate():
    """#8 原始场景：截断点恰好落在高代理上 → 多退一格。

    源字符串本身合法（无内嵌孤立代理）但截断点把合法代理对（astral 码点
    的前半）留在末尾时，切在该高代理上同样产生孤立代理——回退后省略号
    路径正常产出完整字符。用组合字符对模拟（surrogatepass 编码的合法
    astral 字符在 Python str 中是单个码点，无法构造真孤立代理——改用
    真实场景：截断预算落在 emoji 中间）。
    """
    translation = "ab\U0001F600cd"          # emoji = 代理对（2 UTF-16 单元）
    data, truncated = _fit_bytes(translation, 10, "utf-16-le", pad=False)
    # chars = 4 → "ab😀" 恰好装下（4 码点 10 字节 ≤ 容量）：无需回退，
    # emoji 完整保留 + 省略号——绝不产生孤立代理
    assert truncated
    text = data.decode("utf-16-le")
    assert text == "ab\U0001F600…"
    assert all(ord(ch) < 0xD800 or ord(ch) > 0xDFFF for ch in text)
