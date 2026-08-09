# -*- coding: utf-8 -*-
"""F8：写回模块升级的契约与预检回归测试（2026-08-10 写回大升级）。

覆盖修复清单：
- F1 契约闭环：提取端产生 record_offset（前缀位置）→ 写回端按同一语义消费
  → 单记录重开验证 → 二次提取读到译文（MyRustySubmarine 根因 B1 的回归防线）
- 旧库零迁移：仅 heap_offset（数据位置）→ 回退记录起始，写回成功
- F5 鲁棒遍历：非紧凑堆（残留区）流式遍历不 break，后续真实记录仍完整
- F3 预检：meta utf16_len 与文件记录不符 → 拒绝且文件字节不变
- F7 预检：data_index 长度与文件不符 → 拒绝且文件字节不变
"""
import json
from pathlib import Path

from hanhua.core.unity.mono_dll import (
    _walk_us_heap_records, extract_dll_user_strings, read_us_record_at)
from hanhua.core.unity.writer import (
    _encode_compressed_uint, _patch_dll, _patch_metadata, WriteResult)
from tests.test_v2_patch_pools import _build, _meta_entry, _us_heap

FIXTURE_DLL = Path(__file__).parent / "fixtures" / "mono_ui_wrapper.dll"


def _us_entry(record_offset: int, utf16_len: int, original: str,
              translation: str, **extra) -> dict:
    """#US 写回 entry：record_offset = 记录起始（压缩前缀）位置。"""
    return {
        "file_id": "dll", "key_path": f"us#{record_offset}",
        "original": original, "translation": translation,
        "meta": json.dumps({
            "kind": "us", "record_offset": record_offset,
            "utf16_len": utf16_len, "disposition": "translate", **extra,
        }),
    }


def test_contract_extract_then_patch_roundtrip(tmp_path):
    """F8 契约闭环：真实 DLL 提取 → 写回 → 单记录重开验证 → 二次提取。

    提取端 meta（record_offset=前缀位置）与写回端 _patch_dll 的消费语义
    必须一致——这是 MyRustySubmarine「#US 记录缺失 offset=45922」的
    实证根因（B1 heap_offset 语义错位）的回归防线。
    """
    patched = tmp_path / "patched.dll"
    patched.write_bytes(FIXTURE_DLL.read_bytes())
    pf = extract_dll_user_strings(patched, file_id="f")
    candidates = [e for e in pf.entries if e.status == "pending"]
    assert candidates, "fixture 需含可译条目"
    entry = candidates[0]
    meta = dict(entry.meta)
    # 契约断言：新字段 record_offset = 记录起始；旧字段 heap_offset = 数据区
    # 位置（此后 1 字节前缀）。提取端必须同时产两字段（旧项目库兼容）。
    assert meta["record_offset"] == meta["heap_offset"] - 1
    translation = "直接文本赋值测试"
    result = WriteResult()
    _patch_dll(patched, [{
        "file_id": "f", "key_path": entry.key_path,
        "original": entry.original, "translation": translation,
        "meta": json.dumps(meta),
    }], result)
    assert not result.rejected, [(r.reason) for r in result.rejected]
    assert result.written == 1
    # 单记录定位重开：数据 = 译文 UTF-16LE，尾部 flag 重算为 1（含非 ASCII）
    record = read_us_record_at(patched.read_bytes(), meta["record_offset"])
    assert record is not None
    _data_start, raw = record
    assert raw[:-1].decode("utf-16-le") == translation
    assert raw[-1] == 1
    # 二次提取：文本已被替换且无遗漏（同 key 仍是同一记录）
    pf2 = extract_dll_user_strings(patched, file_id="f")
    texts = {e.original for e in pf2.entries}
    assert translation in texts
    assert entry.original not in texts


def test_legacy_heap_offset_fallback(tmp_path):
    """旧项目库零迁移：meta 只有 heap_offset（数据位置）+ utf16_len。

    写回端按「heap_offset - 旧前缀宽」推回记录起始——与旧库数据语义
    一致，兼容无需迁移。
    """
    path = tmp_path / "Assembly-CSharp.dll"
    path.write_bytes(_us_heap([(b"\x41", 0), ("Open".encode("utf-16-le"), 0)]))
    result = WriteResult()
    _patch_dll(path, [{
        "file_id": "f", "key_path": "us#4",
        "original": "Open", "translation": "打开",
        # 仅旧字段：heap_offset=数据区位置（前缀之后），utf16_len=数据字节数
        "meta": json.dumps({
            "kind": "us", "heap_offset": 5, "utf16_len": 8,
            "disposition": "translate",
        }),
    }], result)
    assert result.written == 1, [(r.reason) for r in result.rejected]
    blob = path.read_bytes()
    assert blob[5:9].decode("utf-16-le") == "打开"
    assert blob[9] == 1                       # 中文 → flag 重算为 1
    assert blob[10:14] == b"\x00" * 4         # 残留区清零（旧记录末 @13 前）


def test_walk_us_heap_survives_garbage_tail():
    """F5 鲁棒遍历：非紧凑堆（写回后残留区）流式遍历不 break。

    旧实现遇坏前缀（残留 0x00 → ln=0）即 break，残留区之后的记录全部
    丢失 → 二次汉化遗漏。新实现步进 1 继续，后续真实记录仍完整提取。
    """
    heap = bytearray(b"\x00")
    heap += _encode_compressed_uint(5) + b"\x61\x00\x62\x00" + b"\x00"   # 记录1 @1
    heap += b"\x00" * 4                                                 # 残留区 @7..10
    heap += _encode_compressed_uint(3) + b"\x63\x00" + b"\x00"           # 记录2 @11
    records = _walk_us_heap_records(bytes(heap))
    assert len(records) == 2, f"残留区不应吞掉后续记录：{records}"
    _tok1, off1, raw1 = records[0]
    assert raw1[:-1].decode("utf-16-le") == "ab"
    tok2, off2, raw2 = records[1]
    assert tok2 == 11
    assert raw2[:-1].decode("utf-16-le") == "c"
    assert off1 == 2 and off2 == 12


def test_patch_dll_rejects_stale_capacity(tmp_path):
    """F3 预检：meta utf16_len 与文件记录不符 → 拒绝且文件字节不变。

    这是 heap_offset 语义错位 / 提取后文件变化的最后防线：在写坏任何
    字节之前拦截（MyRustySubmarine 根因即此类错位）。
    """
    path = tmp_path / "Assembly-CSharp.dll"
    heap = _us_heap([(b"\x41", 0), ("Open".encode("utf-16-le"), 0)])
    path.write_bytes(heap)
    result = WriteResult()
    _patch_dll(path, [_us_entry(4, 4, "Open", "打开")], result)  # utf16_len 错：实际 8
    assert result.written == 0
    assert len(result.rejected) == 1
    assert "记录长度不符" in result.rejected[0].reason
    assert path.read_bytes() == heap            # 文件未被触碰


def test_patch_dll_rejects_out_of_bounds_offset(tmp_path):
    """F3 预检：offset 越界/无记录 → 拒绝定位失败且文件不变。"""
    path = tmp_path / "Assembly-CSharp.dll"
    heap = _us_heap([(b"\x41", 0)])
    path.write_bytes(heap)
    result = WriteResult()
    _patch_dll(path, [_us_entry(999, 2, "A", "甲")], result)
    assert result.written == 0
    assert len(result.rejected) == 1
    assert "定位失败" in result.rejected[0].reason
    assert path.read_bytes() == heap


def test_patch_metadata_rejects_stale_capacity(tmp_path):
    """F7 预检：meta length 与文件记录不符 → 拒绝且文件字节不变。"""
    raw = _build(31, ["Press {0} to continue"])     # 记录 data_index 0，length 21
    path = tmp_path / "global-metadata.dat"
    path.write_bytes(raw)
    result = WriteResult()
    _patch_metadata(
        path, [_meta_entry(0x200, 99, "Press {0} to continue", "继续")], result)
    assert result.written == 0
    assert len(result.rejected) == 1
    assert "长度与文件不符" in result.rejected[0].reason
    assert path.read_bytes() == raw
