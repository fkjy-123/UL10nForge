# -*- coding: utf-8 -*-
"""IL2CPP metadata 多版本解析回归（#183，S172 用合成 fixture 先证，再用真实副本回归）。

真实语料验证结论（.scratch/diag_il2cpp_records2.py）：
- v24/v27/v29/v31：header 布局 litOff@0x08 litSize@0x0C dataOff@0x10 dataSize@0x14，
  8 字节 <length, dataIndex> 记录；12 个真实游戏 100% UTF-8 可解码。
- v39（Unity 6）：header 布局 dataOff@0x14 dataSize@0x18（0x10/0x1C 为新增字段），
  4 字节纯 <dataIndex> 记录，字符串长度 = 下一条 dataIndex 差值（最后一条到 data 区末尾）；
  u32@0x10 == 记录数 == litSize/4 强校验；3 个真实游戏全部命中。
"""
import struct
import tempfile
from pathlib import Path

from hanhua.core.unity.il2cpp import extract_metadata_strings, parse_string_literals

SUPPORTED = {24, 27, 29, 31, 39}


def _build(version: int, literals: list[str], *, data_off: int = 0x200,
           lit_off: int = 0x100) -> bytes:
    """构造指定版本的合成 metadata。v39 使用 4 字节 dataIndex 差分记录。"""
    data = b"".join(s.encode("utf-8") for s in literals)
    offsets = []
    pos = 0
    for s in literals:
        offsets.append((pos, len(s.encode("utf-8"))))
        pos += len(s.encode("utf-8"))
    header = bytearray(0x30)
    struct.pack_into("<II", header, 0, 0xFAB11BAF, version)
    if version == 39:
        table_size = len(literals) * 4
        # 0x10: 记录数（Unity 6 新增字段，必须 == litSize/4）
        struct.pack_into("<I", header, 0x10, len(literals))
        # 0x14/0x18: stringLiteralDataOffset/Size（v39 布局后移）
        struct.pack_into("<II", header, 0x14, data_off, len(data))
        lit_arr = b"".join(struct.pack("<I", off) for off, _ in offsets)
    else:
        table_size = len(literals) * 8
        struct.pack_into("<II", header, 0x10, data_off, len(data))
        lit_arr = b"".join(struct.pack("<II", ln, off) for off, ln in offsets)
    struct.pack_into("<II", header, 0x08, lit_off, table_size)
    buf = bytes(header) + b"\x00" * (lit_off - 0x30) + lit_arr
    buf += b"\x00" * (data_off - len(buf)) + data
    return buf


def _expected(literals: list[str], data_off: int = 0x200) -> list[tuple[int, int, int]]:
    out = []
    pos = 0
    for s in literals:
        ln = len(s.encode("utf-8"))
        out.append((pos, ln, data_off + pos))
        pos += ln
    return out


def test_parse_v24_v27_v31_records_explicit_layout():
    for version in (24, 27, 31):
        literals = ["Hello player", "Press {key} to jump", "继续游戏"]
        raw = _build(version, literals)
        assert parse_string_literals(raw) == _expected(literals)


def test_parse_v39_records_implicit_delta_length():
    literals = ["Hello player", "Press {key} to jump", "继续游戏"]
    raw = _build(39, literals)
    assert parse_string_literals(raw) == _expected(literals)


def test_v39_last_record_length_reaches_data_end():
    # 最后一条字符串后面直接接 data 区尾部：差分长度 = data_size - dataIndex
    raw = _build(39, ["Alpha", "Beta"])
    assert parse_string_literals(raw) == [(0, 5, 0x200), (5, 4, 0x205)]


def test_v39_record_count_field_must_match_table_size():
    raw = bytearray(_build(39, ["A", "B", "C"]))
    struct.pack_into("<I", raw, 0x10, 999)          # 记录数与 litSize/4 不符
    assert parse_string_literals(bytes(raw)) == []


def test_v39_rejects_data_index_going_backwards():
    raw = bytearray(_build(39, ["Alpha", "Beta", "Gamma"]))
    # 第三条记录 dataIndex 回退到 0（< 第二条的 5）：差分长度必须非负
    struct.pack_into("<I", raw, 0x100 + 8, 0)
    assert parse_string_literals(bytes(raw)) == []


def test_v39_rejects_data_index_out_of_range():
    raw = bytearray(_build(39, ["Alpha", "Beta"]))
    struct.pack_into("<I", raw, 0x100 + 4, 0x10000)
    assert parse_string_literals(bytes(raw)) == []


def test_v39_rejects_overlapping_table_and_data_sections():
    # v39 数据区声明与字面量表重叠（dataOff=0x104 落在表内部 0x100..0x108）
    raw = bytearray(_build(39, ["A", "B"], data_off=0x104))
    assert parse_string_literals(bytes(raw)) == []


def test_v39_skips_literal_that_is_not_valid_utf8():
    raw = bytearray(_build(39, ["First", "Second"]))
    raw[0x200] = 0xFF                                # 破坏第一条字符串
    literals = parse_string_literals(bytes(raw))
    assert [(di, ln) for di, ln, _ in literals] == [(5, 6)]


def test_v39_skips_zero_length_literal_record():
    # 连续相同 dataIndex 表示空字符串（真实 v39 前两条都是 0）
    raw = _build(39, ["", "Visible text"])
    assert [ln for _, ln, _ in parse_string_literals(raw)] == [12]


def test_unknown_versions_still_rejected():
    for version in (30, 32, 33, 35, 37, 40):
        raw = _build(version, ["Hello"])
        assert parse_string_literals(raw) == [], version


def test_extract_metadata_strings_v39(tmp_path):
    raw = _build(39, ["Hello player", "Press {key} to jump", "继续游戏"])
    p = tmp_path / "global-metadata.dat"
    p.write_bytes(raw)
    pf = extract_metadata_strings(p, "m.dat")
    orig = {e.key_path: e.original for e in pf.entries}
    assert orig == {"meta#0": "Hello player",
                    "meta#12": "Press {key} to jump",
                    "meta#31": "继续游戏"}
    by_key = {e.key_path: e.meta["file_offset"] for e in pf.entries}
    assert by_key == {"meta#0": 0x200, "meta#12": 0x20C, "meta#31": 0x21F}


def test_extract_metadata_strings_tracks_skipped_reasons(tmp_path):
    """R5：静默 continue 留档——代码标识符/引擎形态的跳过聚合可见
    （哑识别可观测；真实池 65% 字面量属静默过滤形态）。"""
    raw = _build(39, ["Hello player", "BackupManager", "OK", "Press Start"])
    p = tmp_path / "global-metadata.dat"
    p.write_bytes(raw)
    pf = extract_metadata_strings(p, "m.dat")
    assert pf.skipped_reasons.get("code_identifier", 0) == 1   # BackupManager
    assert pf.skipped_reasons.get("engine_morph", 0) == 1      # OK（短词无字母分布）
    # 留档不改变既有行为：显示文本照常提取
    assert {e.original for e in pf.entries
            if e.status == "pending"} == {"Hello player", "Press Start"}


def test_fake_metadata_rejects_wrong_magic():
    raw = bytearray(_build(39, ["Hello"]))
    struct.pack_into("<I", raw, 0, 0xDEADBEEF)
    assert parse_string_literals(bytes(raw)) == []


def test_metadata_header_layout_positions():
    # 布局自洽性：各版本 header 字段位置回归锚点（防止布局表被误改）
    for version in (24, 27, 29, 31):
        raw = _build(version, ["X"])
        assert parse_string_literals(raw) == [(0, 1, 0x200)]
    raw39 = _build(39, ["X"])
    assert parse_string_literals(raw39) == [(0, 1, 0x200)]
