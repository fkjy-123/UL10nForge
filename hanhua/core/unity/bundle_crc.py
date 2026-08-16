"""UnityFS AssetBundle 校验修复（工具移植任务 2，2026-08-16）。

来源：UABEA patchcrc（AssetsTools.NET）逻辑。UnityFS header
（version ≥4）含两字段：
- hash（16 字节）：uncompressed 数据的 MD5（增量构建/缓存用）；
- crc（4 字节）：uncompressed 数据的标准 CRC32（IEEE）。

UnityPy 写回时保留原 hash/crc（内容已变但校验值未重算）——Unity
加载默认不校验（LoadFromFile 不传 crc 参数），但严格路径（显式 crc
校验/第三方工具读取）会失败。本模块在写回验证阶段重算并修复，
保证写回产物对所有读取路径有效。

Header 结构（version ≥4，无嵌套容器）：
  signature "UnityFS\\0"(7) + version u32(4)
  + unity_version 空串 + unity_revision 空串（变长）
  + size u64(8) + compressedBlockSize u32(4)
  + uncompressedBlockSize u32(4) + flags u32(4)
  + hash(16) + crc(4)   ← 校验字段
"""
from __future__ import annotations

import hashlib
import zlib

_UNITYFS_SIGNATURE = b"UnityFS"


def unityfs_checksum(uncompressed_data: bytes) -> tuple[bytes, int]:
    """UnityFS 校验：hash = MD5(uncompressed)，crc = CRC32(IEEE)。"""
    digest = hashlib.md5(uncompressed_data).digest()
    crc = zlib.crc32(uncompressed_data) & 0xFFFFFFFF
    return digest, crc


def checksum_header_offset(raw: bytes) -> int | None:
    """定位 UnityFS header 中 hash/crc 字段的偏移。

    返回 hash 偏移（crc 在 hash+16）；非 UnityFS 或 version<4 返回 None。
    """
    if not raw.startswith(_UNITYFS_SIGNATURE):
        return None
    pos = len(_UNITYFS_SIGNATURE) + 1          # 跳过 nul 结束符
    if pos + 4 > len(raw):
        return None
    version = int.from_bytes(raw[pos:pos + 4], "little")
    pos += 4
    for _ in range(2):                          # unity_version / revision
        end = raw.find(b"\x00", pos)
        if end < 0:
            return None
        pos = end + 1
    pos += 8 + 4 + 4 + 4                        # size + 2×blocksize + flags
    if version < 4:
        return None
    if pos + 20 > len(raw):
        return None
    return pos


def read_checksums(raw: bytes) -> tuple[bytes | None, int | None]:
    """读当前 header 中的 (hash, crc)。"""
    offset = checksum_header_offset(raw)
    if offset is None:
        return None, None
    return raw[offset:offset + 16], int.from_bytes(
        raw[offset + 16:offset + 20], "little")


def patch_checksums(raw: bytes, uncompressed_data: bytes) -> bytes:
    """重算并写回 hash/crc（patchcrc 等价）。非 UnityFS/version<4 原样。"""
    offset = checksum_header_offset(raw)
    if offset is None:
        return raw
    digest, crc = unityfs_checksum(uncompressed_data)
    out = bytearray(raw)
    out[offset:offset + 16] = digest
    out[offset + 16:offset + 20] = crc.to_bytes(4, "little")
    return bytes(out)


def verify_checksums(raw: bytes, uncompressed_data: bytes) -> bool:
    """校验当前 header 的 hash/crc 与内容是否一致。"""
    offset = checksum_header_offset(raw)
    if offset is None:
        return True                      # 无校验字段（旧版本）——视为有效
    expect_hash, expect_crc = unityfs_checksum(uncompressed_data)
    cur_hash = raw[offset:offset + 16]
    cur_crc = int.from_bytes(raw[offset + 16:offset + 20], "little")
    return cur_hash == expect_hash and cur_crc == expect_crc
