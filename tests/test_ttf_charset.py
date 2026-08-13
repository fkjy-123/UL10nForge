# -*- coding: utf-8 -*-
"""ttf_charset：TTF/OTF cmap 解析（字体闭环 Phase 2 实现重点 2/6）。

验证替换后 legacy Font 的真实字符集逐码点可验证——纯 Python 解析
format 4（BMP 分段）与 format 12（分组连续），畸形输入保守返回空集。
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hanhua.core.font.ttf_charset import ttf_charset


def _sfnt(cmap_bytes: bytes) -> bytes:
    """组装最小 sfnt：头 + 目录 + 单 cmap 表。"""
    num_tables = 1
    header = b"\x00\x01\x00\x00" + num_tables.to_bytes(2, "big") \
        + b"\x00" * 6
    cmap_offset = 12 + 16 * num_tables
    directory = b"cmap" + b"\x00" * 4 + cmap_offset.to_bytes(4, "big") \
        + len(cmap_bytes).to_bytes(4, "big")
    return header + directory + cmap_bytes


def _cmap(subtables: list[bytes]) -> bytes:
    """组装 cmap 表：header + encoding records + 子表。"""
    header = b"\x00" * 2 + len(subtables).to_bytes(2, "big")
    base = 4 + 8 * len(subtables)
    records = b""
    for i, sub in enumerate(subtables):
        records += b"\x00\x03\x00\x01" + base.to_bytes(4, "big")
        base += len(sub)
    return header + records + b"".join(subtables)


def _fmt4(segments) -> bytes:
    """format 4 子表。segments: (start, end, delta, range_offset) 列表。"""
    seg_count = len(segments)
    seg_x2 = seg_count * 2
    end_codes = b"".join(s[1].to_bytes(2, "big") for s in segments) + b"\x00\x00"
    start_codes = b"".join(s[0].to_bytes(2, "big") for s in segments)
    deltas = b"".join(struct.pack(">h", s[2]) for s in segments)
    ro = b"".join(s[3].to_bytes(2, "big") for s in segments)
    glyph_array = b""
    length = 14 + seg_x2 * 4 + 2 + len(glyph_array)
    return (struct.pack(">HHHHHHH", 4, length, 0, seg_x2,
                        seg_x2, 0, 0)
            + end_codes + start_codes + deltas + ro + glyph_array)


def _fmt12(groups) -> bytes:
    """format 12 子表。groups: (start_cp, end_cp, start_glyph)。"""
    body = b"".join(struct.pack(">III", *g) for g in groups)
    length = 16 + len(body)
    return struct.pack(">HHII", 12, 0, length, 0) + len(groups).to_bytes(4, "big") + body


def test_format4_dense_segment():
    # 段 [0x4E00, 0x4E05] delta=1（全段有字形），段 [0x41,0x43] delta=2
    sub = _fmt4([(0x4E00, 0x4E05, 1, 0), (0x41, 0x43, 2, 0)])
    chars = ttf_charset(_sfnt(_cmap([sub])))
    assert {0x4E00, 0x4E01, 0x4E05, 0x41, 0x43} <= chars
    assert 0x4E10 not in chars
    assert 0x40 not in chars


def test_format4_zero_delta_whole_segment():
    # delta=0 且无 range offset → glyph=(cp+delta)=cp≠0 → 全段有字形
    sub = _fmt4([(0x30, 0x32, 0, 0)])
    assert {0x30, 0x31, 0x32} <= ttf_charset(_sfnt(_cmap([sub])))


def test_format12_non_bmp():
    sub = _fmt12([(0x4E00, 0x4E02, 1), (0x1F600, 0x1F601, 9)])
    chars = ttf_charset(_sfnt(_cmap([sub])))
    assert {0x4E00, 0x1F600, 0x1F601} <= chars
    assert 0x1F602 not in chars


def test_format4_and_12_union():
    sub4 = _fmt4([(0x41, 0x41, 0, 0)])
    sub12 = _fmt12([(0x4E00, 0x4E00, 1)])
    chars = ttf_charset(_sfnt(_cmap([sub4, sub12])))
    assert {0x41, 0x4E00} <= chars


def test_garbage_returns_empty():
    assert ttf_charset(b"") == frozenset()
    assert ttf_charset(b"NOTATTF" + b"\x00" * 40) == frozenset()
    assert ttf_charset(_sfnt(b"junk")) == frozenset()      # 坏 cmap 内容


def test_no_cmap_table_returns_empty():
    # 只有 head 表的 sfnt：无 cmap → 空集
    data = b"\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00" \
        + b"head\x00\x00\x00\x00" + b"\x00\x00\x00\x20" + b"\x00\x00\x00\x10"
    assert ttf_charset(data) == frozenset()


def test_real_source_han_font():
    """白名单字体（思源黑体）真实 cmap 覆盖：CJK + 全 ASCII。"""
    p = Path(__file__).resolve().parents[1] / "fonts" \
        / "SimplifiedChinese" / "SourceHanSansSC-Regular.otf"
    if not p.is_file():
        return
    chars = ttf_charset(p.read_bytes())
    # 思源黑体：常用汉字 + 全可打印 ASCII（legacy 替换后逐码点验证基准）
    assert {0x4E00, 0x4E10, 0x9F99} <= chars
    assert all(c in chars for c in (0x41, 0x7A, 0x30, 0x20, 0x21))
