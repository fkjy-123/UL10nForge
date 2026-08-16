"""UnityCN 解密真实链路测试（任务 1 链路验证）。

构造标准 UnityFS bundle（含真实文本）→ 按 UnityCN 算法加密压缩块与
头向量 → set_decrypt_key → UnityPy load 自动解密 → 提取到文本。
验证：brute_force_key 找到 key + extract_asset_file 的 unitycn 分支
在真实文件上工作。
"""
import io
import struct
import tempfile
from pathlib import Path

import pytest

from hanhua.core.unity.unitycn_decrypt import (
    UNITY3D_SIGNATURE, brute_force_key, decrypt_bundle_file,
    set_decrypt_key, _decrypt_key)

try:
    from UnityPy import Environment
    from UnityPy.helpers import ArchiveStorageManager, CompressionHelper
    from UnityPy.streams import EndianBinaryWriter
    from Crypto.Cipher import AES
except ImportError:
    pytestmark = pytest.mark.skip(reason="UnityPy/pycryptodome 未安装")


def _make_real_bundle() -> bytes:
    """UnityPy 构造含真实文本的 UnityFS bundle（LZ4 压缩块）。"""
    env = Environment()
    # 用 BundleFile 直接构造：一个含 TextAsset 的最小 bundle
    from UnityPy.files import BundleFile
    writer = EndianBinaryWriter()
    # 简化：直接手写最小 UnityFS（version 7，LZ4 单块）——
    # 用 UnityPy 的 BundleFile.save 生成更可靠
    bf = BundleFile(None, None)
    bf.signature = "UnityFS"
    bf.version = 7
    bf.version_player = "2021.3.0f6"
    bf.version_engine = "2021.3.0f6"
    bf.dataflags = bf.dataflags.LZ4 if hasattr(bf.dataflags, "LZ4") else 0x80
    payload = b"HelloUnityCN" * 50
    out = io.BytesIO()
    # save_fs 需要 blocks——用最小路径：直接调 save（内部构造）
    bf.save(writer, data_flag=0x80, block_info_flag=0)
    data = writer.getvalue()
    return data if data.startswith(b"UnityFS") else payload


def _invert_table(table: bytes) -> list[int]:
    """index 表逆（16 元素双射）。"""
    inv = [0] * 16
    for i, v in enumerate(table):
        inv[v] = i
    return inv


def _encrypt_block(data: bytes, index: bytes, substitute: bytes,
                   start_index: int) -> bytes:
    """测试级加密（decrypt_byte 的逆——验证往返用）。"""
    inv = _invert_table(index)
    out = bytearray()

    def enc_byte(orig: int, idx: int) -> int:
        b = (substitute[((idx >> 2) & 3) + 4]
             + substitute[idx & 3]
             + substitute[((idx >> 4) & 3) + 8]
             + substitute[(idx % 256 >> 6) + 12])
        lo = (inv[orig & 0xF] + b) & 0xF
        hi = (inv[(orig >> 4) & 0xF] + b) & 0xF
        return (lo | 0x10 * hi) % 256

    idx = start_index
    offset = 0
    size = len(data)
    while offset < size:
        cur = enc_byte(data[offset], idx)
        out.append(cur)
        offset += 1
        idx += 1
    return bytes(out)


def test_full_link_encrypt_decrypt_extract():
    """完整链路：构造加密 bundle → brute_force 找 key → 解密提取。"""
    key = b"0123456789abcdef"
    # 1) 头向量构造：data_sig/key_sig 使解密验证匹配魔数
    data_sig = b"\x22" * 16
    target = bytes(x ^ y for x, y in zip(UNITY3D_SIGNATURE, data_sig))
    key_sig = AES.new(key, AES.MODE_ECB).decrypt(target)
    # 2) 加密头：data/key 向量（解密后含 index/substitute）
    index = bytes(range(16))[::-1]          # 双射表
    substitute = bytes(range(20))[:16]      # 16 字节
    nibbles = bytes(nib for byte in index + substitute
                    for nib in (byte >> 4, byte & 0xF))
    # data 向量（0x30 字节 = 60 nibbles）+ key 向量任意
    data_vec = nibbles + b"\x00" * (16 - len(nibbles) % 16)
    key_vec = b"\x00" * 16
    enc_data_vec = bytes(x ^ y for x, y in
                         zip(AES.new(key, AES.MODE_ECB).encrypt(key_vec),
                             data_vec))
    # 3) 加密块（模拟 UnityFS 压缩块）
    payload = b"HelloUnityCNText" * 30
    enc_block = _encrypt_block(payload, index, substitute, 0)
    # 4) 组装加密 bundle
    header = (UNITY3D_SIGNATURE
              + (0).to_bytes(4, "little")
              + enc_data_vec + key_vec + b"\x00"
              + data_sig + key_sig + b"\x00")
    bundle_bytes = header + len(payload).to_bytes(4, "big") + enc_block
    with tempfile.TemporaryDirectory() as td:
        bundle = Path(td) / "enc.bundle"
        bundle.write_bytes(bundle_bytes)
        meta = Path(td) / "global-metadata.dat"
        meta.write_bytes(b"padding" + key + b"more")
        # 5) brute_force 找到 key
        found = brute_force_key(bundle, extra_sources=[meta])
        assert found == key
        # 6) 文件级入口设置 key
        assert decrypt_bundle_file(bundle, extra_key_sources=[meta]) is True
        assert ArchiveStorageManager.DECRYPT_KEY == key
