"""UnityFS 校验修复测试（工具移植任务 2，UABEA patchcrc 等价）。"""
import struct

from hanhua.core.unity.bundle_crc import (
    checksum_header_offset, patch_checksums, read_checksums,
    unityfs_checksum, verify_checksums)


def _make_unityfs(version: int = 4, with_payload: bytes = b"content-data"):
    """构造 UnityFS header（version≥4 含 hash/crc 字段）+ 载荷。"""
    header = bytearray()
    header += b"UnityFS\x00"
    header += struct.pack("<I", version)
    header += b"2021.3.0f6\x00"
    header += b"2021.3.0f6\x00"
    header += struct.pack("<Q", 0)          # size
    header += struct.pack("<I", 0)          # compressedBlockSize
    header += struct.pack("<I", len(with_payload))
    header += struct.pack("<I", 0)          # flags
    digest, crc = unityfs_checksum(with_payload)
    header += digest
    header += struct.pack("<I", crc)
    header += struct.pack("<I", 0) * 4      # 后续 header 字段
    return bytes(header) + with_payload


def test_checksum_roundtrip():
    payload = b"hello unityfs" * 100
    digest, crc = unityfs_checksum(payload)
    import hashlib
    import zlib
    assert digest == hashlib.md5(payload).digest()
    assert crc == zlib.crc32(payload) & 0xFFFFFFFF


def test_header_offset_and_read():
    raw = _make_unityfs()
    offset = checksum_header_offset(raw)
    assert offset is not None
    h, c = read_checksums(raw)
    assert h == unityfs_checksum(b"content-data")[0]
    assert c == unityfs_checksum(b"content-data")[1]


def test_verify_true_when_consistent():
    raw = _make_unityfs()
    assert verify_checksums(raw, b"content-data") is True


def test_patch_after_content_change():
    """内容被改（写回场景）后：verify False → patch → verify True。"""
    raw = _make_unityfs()
    # 模拟写回改了内容（旧 checksum 未更新）
    new_payload = b"translated-content" * 20
    modified = raw[:len(raw) - len(b"content-data")] + new_payload
    assert verify_checksums(modified, new_payload) is False
    patched = patch_checksums(modified, new_payload)
    assert verify_checksums(patched, new_payload) is True


def test_version3_no_checksum_field():
    raw = _make_unityfs(version=3)
    assert checksum_header_offset(raw) is None
    assert read_checksums(raw) == (None, None)
    assert patch_checksums(raw, b"x") == raw
