"""IL2CPP metadata 字符串写回测试（工具移植任务 3）。

变长写回：译文追加新数据区 + 重建 lookup_table + 更新偏移。
合成 v24（explicit）与 v39（implicit）最小 metadata 往返验证。
"""
import struct

from hanhua.core.unity.il2cpp import METADATA_MAGIC, parse_string_literals
from hanhua.core.unity.il2cpp_writeback import (
    extract_literal_texts, write_string_literals)


def _make_metadata(version: int, texts: list[str]):
    """构造最小 metadata：magic+version+layout 偏移+lookup 表+数据区。"""
    if version == 39:
        lit_off_pos, lit_size_pos, data_off_pos, data_size_pos = (
            0x08, 0x0C, 0x14, 0x18)
    else:
        lit_off_pos, lit_size_pos, data_off_pos, data_size_pos = (
            0x08, 0x0C, 0x10, 0x14)
    header = bytearray(0x40)
    struct.pack_into("<II", header, 0, METADATA_MAGIC, version)
    if version == 39:
        struct.pack_into("<I", header, 0x10, len(texts))  # 记录数（v39 校验）
    # 数据区（字符串+NUL）
    data = b"".join(t.encode("utf-8") + b"\x00" for t in texts)
    data_off = 0x40
    # lookup 表
    if version == 39:
        indexes = []
        cursor = 0
        for t in texts:
            indexes.append(cursor)
            cursor += len(t.encode("utf-8")) + 1
        table = b"".join(struct.pack("<I", i) for i in indexes)
        entry_size = 4
    else:
        table = bytearray()
        cursor = 0
        for t in texts:
            length = len(t.encode("utf-8")) + 1
            table += struct.pack("<II", length, cursor)
            cursor += length
        entry_size = 8
    lit_off = data_off + len(data)
    raw = bytearray(header) + data + bytes(table)
    struct.pack_into("<II", raw, lit_off_pos, lit_off, len(table))
    struct.pack_into("<II", raw, data_off_pos, data_off, len(data))
    return bytes(raw)


def test_extract_literal_texts_v24():
    raw = _make_metadata(24, ["Hello", "World", "Test"])
    texts = [t for _, t in extract_literal_texts(raw)]
    assert texts == ["Hello", "World", "Test"]


def test_extract_literal_texts_v39():
    raw = _make_metadata(39, ["Hello", "World"])
    texts = [t for _, t in extract_literal_texts(raw)]
    assert texts == ["Hello", "World"]


def test_writeback_v24_roundtrip():
    """译文替换（含变长：长译文>原文）→ 重提取验证。"""
    raw = _make_metadata(24, ["Hello", "World", "Keep"])
    out = write_string_literals(raw, {"Hello": "你好世界",
                                      "World": "世界"})
    assert out != raw
    texts = [t for _, t in extract_literal_texts(out)]
    assert texts == ["你好世界", "世界", "Keep"]   # 未命中的保留
    # 结构断言：magic/version 不变、lookup 可重解析
    assert struct.unpack_from("<II", out, 0)[0] == METADATA_MAGIC
    entries = parse_string_literals(out)
    assert len(entries) == 3
    assert entries[0][1] == len("你好世界".encode("utf-8")) + 1


def test_writeback_v39_roundtrip():
    raw = _make_metadata(39, ["Hello", "World"])
    out = write_string_literals(raw, {"Hello": "中文更长文本"})
    texts = [t for _, t in extract_literal_texts(out)]
    assert texts == ["中文更长文本", "World"]
    assert len(parse_string_literals(out)) == 2


def test_writeback_invalid_returns_same():
    assert write_string_literals(b"\x00" * 20, {"x": "y"}) == b"\x00" * 20
    bad = _make_metadata(24, ["A"])[:30]   # 截断
    assert write_string_literals(bad, {"A": "B"}) == bad


def test_writeback_no_matches_keeps_all():
    raw = _make_metadata(24, ["Hello", "World"])
    out = write_string_literals(raw, {"Missing": "翻译"})
    assert out == raw
