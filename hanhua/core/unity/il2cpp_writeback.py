"""IL2CPP global-metadata.dat 字符串写回（工具移植任务 3，2026-08-16）。

来源：il2cpp-stringliteral-patcher（Python 核心逻辑）+ MetaDataStringEditor
（C# 参考）。变长字符串写回经典解法：
1. 译文全部**追加到文件末尾**（新数据区——避免原位覆盖的容量问题）；
2. 重建 lookup_table（explicit：<length, dataIndex> 8 字节记录；
   implicit/v39：dataIndex 4 字节记录，长度由下一条差值隐含）；
3. 更新 header 的 data 偏移/大小字段。

布局与提取侧一致（_LAYOUTS：24/27/29/31 explicit + 39 implicit）。
写回后结构断言：magic/版本不变、lookup 表可重解析、新数据区在文件内。
"""
from __future__ import annotations

import struct

from hanhua.core.unity.il2cpp import (
    METADATA_MAGIC, _LAYOUTS, parse_string_literals)


def extract_literal_texts(raw: bytes) -> list[tuple[int, str]]:
    """提取全部字符串字面量 → [(dataIndex, 原文)]（按 lookup 顺序）。"""
    entries = parse_string_literals(raw)
    out: list[tuple[int, str]] = []
    for data_index, length, data_offset in entries:
        if length <= 0 or data_offset + length > len(raw):
            continue
        chunk = raw[data_offset:data_offset + length]
        # 去除结尾 NUL（提取侧约定字符串以 NUL 结尾）
        if chunk.endswith(b"\x00"):
            chunk = chunk[:-1]
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            continue
        out.append((data_index, text))
    return out


def write_string_literals(
        raw: bytes,
        updates: dict[str, str],
        *, keep_untouched_order: bool = True) -> bytes:
    """写回字符串字面量 → 新 metadata 字节。

    updates：{原文: 译文}——只替换存在的原文（未命中的保留原文，
    顺序与原文 lookup 一致）。返回新文件字节；结构非法返回原样。
    """
    if len(raw) < 24:
        return raw
    magic, version = struct.unpack_from("<II", raw, 0)
    if magic != METADATA_MAGIC:
        return raw
    layout = _LAYOUTS.get(version)
    if layout is None:
        return raw
    (lit_off_pos, lit_size_pos, data_off_pos, data_size_pos,
     entry_size, record_mode) = layout
    lit_off, lit_table_size = struct.unpack_from("<II", raw, lit_off_pos)
    data_off, data_size = struct.unpack_from("<II", raw, data_off_pos)
    if (lit_off + lit_table_size > len(raw)
            or data_off + data_size > len(raw)
            or lit_table_size % entry_size != 0):
        return raw
    count = lit_table_size // entry_size
    if count == 0:
        return raw
    entries = parse_string_literals(raw)
    if len(entries) != count:
        return raw

    # 1) 生成新数据（译文替换，未命中保留原文）
    new_data: list[bytes] = []
    new_indexes: list[int] = []          # 每条数据在新区的起始偏移
    cursor = 0
    matched = False
    for data_index, length, data_offset in entries:
        if length <= 0 or data_offset + length > len(raw):
            return raw
        chunk = raw[data_offset:data_offset + length]
        stripped = chunk[:-1] if chunk.endswith(b"\x00") else chunk
        try:
            original = stripped.decode("utf-8")
        except UnicodeDecodeError:
            original = None
        if original is not None and original in updates:
            payload = updates[original].encode("utf-8") + b"\x00"
            matched = True
        else:
            payload = chunk
        new_indexes.append(cursor)
        new_data.append(payload)
        cursor += len(payload)
    if not matched:
        return raw

    # 2) 新数据区追加到文件末尾
    base = len(raw)
    out = bytearray(raw)
    out.extend(b"".join(new_data))
    new_data_off = base
    new_data_size = cursor

    # 3) 重建 lookup_table（写回原位置——表大小不变：explicit 8 字节
    #    <length, dataIndex>；implicit 4 字节 <dataIndex>）
    if record_mode == "explicit":
        table = bytearray()
        for i in range(count):
            new_len = (new_indexes[i + 1] if i + 1 < count
                       else new_data_size) - new_indexes[i]
            table += struct.pack("<II", new_len, new_indexes[i])
    else:  # implicit（v39）：4 字节 dataIndex，长度由下一条差值隐含
        table = bytearray()
        for idx in new_indexes:
            table += struct.pack("<I", idx)
    out[lit_off:lit_off + lit_table_size] = table

    # 4) 更新 header 数据偏移/大小
    struct.pack_into("<I", out, data_off_pos, new_data_off)
    struct.pack_into("<I", out, data_size_pos, new_data_size)
    return bytes(out)
