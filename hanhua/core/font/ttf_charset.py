# -*- coding: utf-8 -*-
"""TTF/OTF cmap 解析 → 字体实际覆盖的 Unicode scalar 集（字体闭环 Phase 2）。

Phase 2 实现重点 2/6：静态替换从「比总 glyph 数」升级为「按真实字符集
逐码点验证」。legacy Font 替换后的字形表不是「猜的」——它就是白名单
TTF 的 cmap 内容。本模块是纯 Python 最小解析器（无 fontTools 依赖），
覆盖 cmap format 4（BMP 分段映射）与 format 12（分组连续映射），
两者覆盖 Unity 使用的全部 TTF/OTF 实际场景。

失败语义：任何解析异常返回空集（保守）——空集消费者会缺全部需求码点，
宁可阻断发布也不假 PASS（审计 §1：禁止把未知当已证明）。
"""
from __future__ import annotations

import struct


def ttf_charset(data: bytes) -> frozenset[int]:
    """返回 TTF/OTF 字体实际覆盖的 Unicode scalar 集（int）。

    解析 cmap 表（format 4 + format 12 全部子表并集）；任何畸形输入
    返回空集（保守：未知不得当已证明）。
    """
    scalars: set[int] = set()
    for subtable in _cmap_subtables(data):
        try:
            fmt = struct.unpack_from(">H", subtable, 0)[0]
            if fmt == 4:
                scalars |= _parse_format4(subtable)
            elif fmt == 12:
                scalars |= _parse_format12(subtable)
        except (struct.error, IndexError):
            continue
    return frozenset(scalars)


def _cmap_subtables(data: bytes) -> list[bytes]:
    """从 sfnt 目录找 cmap 表，返回其全部编码子表字节。"""
    if len(data) < 12 or data[:4] not in {b"\x00\x01\x00\x00", b"OTTO",
                                          b"true", b"ttcf"}:
        return []
    num_tables = struct.unpack_from(">H", data, 4)[0]
    cmap_offset = 0
    for index in range(num_tables):
        off = 12 + index * 16
        if off + 16 > len(data):
            return []
        tag = data[off:off + 4]
        _checksum, toffset, tlength = struct.unpack_from(
            ">III", data, off + 4)
        if tag == b"cmap":
            cmap_offset = toffset
            break
    if not cmap_offset or cmap_offset + 4 > len(data):
        return []
    version, num_records = struct.unpack_from(">HH", data, cmap_offset)
    if version != 0:
        return []
    subtables: list[bytes] = []
    for index in range(num_records):
        record_off = cmap_offset + 4 + index * 8
        if record_off + 8 > len(data):
            break
        _platform, _encoding, sub_offset = struct.unpack_from(
            ">HHI", data, record_off)
        start = cmap_offset + sub_offset
        if start + 2 > len(data):
            continue
        fmt = struct.unpack_from(">H", data, start)[0]
        # length 字段位置与宽度随 format 变化：format 4 在偏移 2（uint16），
        # format 12 在偏移 4（uint32）；未知 format 不截断（交给解析器
        # 边界检查），读多了无害
        if fmt == 4:
            length_off, length_fmt = start + 2, ">H"
        elif fmt == 12:
            length_off, length_fmt = start + 4, ">I"
        else:
            subtables.append(data[start:])
            continue
        if length_off + 4 > len(data):
            continue
        length = struct.unpack_from(length_fmt, data, length_off)[0]
        end = min(len(data), start + length)
        if length >= 2:
            subtables.append(data[start:end])
    return subtables


def _parse_format4(sub: bytes) -> set[int]:
    """format 4：分段映射（BMP）。返回段内有非零 glyph 的全部码点。"""
    seg_count_x2 = struct.unpack_from(">H", sub, 6)[0]
    seg_count = seg_count_x2 // 2
    if seg_count == 0:
        return set()
    end_base = 14
    start_base = end_base + seg_count_x2 + 2          # + reservedPad
    delta_base = start_base + seg_count_x2
    ro_base = delta_base + seg_count_x2
    id_array_base = ro_base + seg_count_x2
    if id_array_base > len(sub):
        return set()
    end_codes = struct.unpack_from(f">{seg_count}H", sub, end_base)
    start_codes = struct.unpack_from(f">{seg_count}H", sub, start_base)
    deltas = struct.unpack_from(f">{seg_count}h", sub, delta_base)
    ro_offsets = struct.unpack_from(f">{seg_count}H", sub, ro_base)
    scalars: set[int] = set()
    for i in range(seg_count):
        start_cp, end_cp = start_codes[i], end_codes[i]
        if end_cp < start_cp:
            continue
        if ro_offsets[i] == 0:
            # 全段连续：glyph = (cp + delta) & 0xFFFF
            for cp in range(start_cp, end_cp + 1):
                if ((cp + deltas[i]) & 0xFFFF) != 0:
                    scalars.add(cp)
        else:
            # 稀疏段：逐码点查 glyphIdArray
            for cp in range(start_cp, end_cp + 1):
                entry = ro_offsets[i] // 2 + (cp - start_cp) + i
                pos = ro_base + entry * 2
                if pos + 2 > len(sub):
                    continue
                glyph = struct.unpack_from(">H", sub, pos)[0]
                if glyph != 0:
                    glyph = (glyph + deltas[i]) & 0xFFFF
                if glyph != 0:
                    scalars.add(cp)
    return scalars


def _parse_format12(sub: bytes) -> set[int]:
    """format 12：分组连续映射（非 BMP 也覆盖）。"""
    n_groups = struct.unpack_from(">I", sub, 12)[0]
    base = 16
    if base + n_groups * 12 > len(sub):
        return set()
    scalars: set[int] = set()
    for i in range(n_groups):
        start_cp, end_cp, _start_glyph = struct.unpack_from(
            ">III", sub, base + i * 12)
        if end_cp < start_cp or end_cp - start_cp > 0x1_FFFF:
            continue
        scalars.update(range(start_cp, end_cp + 1))
    return scalars
