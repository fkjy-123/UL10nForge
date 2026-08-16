"""UnityCN 加密 bundle 解密测试（工具移植任务 1）。

算法：AES-ECB + XOR 双层（头向量解密）+ \\w{16} key 暴力探测。
无真实加密样本时用反向构造验证：已知 key → 构造签名向量 →
brute_force_key 必须找到该 key。
"""
import tempfile
from pathlib import Path

import pytest

from hanhua.core.unity.unitycn_decrypt import (
    UNITY3D_SIGNATURE, brute_force_key, set_decrypt_key,
    _decrypt_key)


def test_brute_force_no_key_on_plain():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "plain.bundle"
        p.write_bytes(b"\x00" * 128)
        assert brute_force_key(p) is None


def test_decrypt_key_xor_aes_roundtrip():
    """AES-ECB+XOR 双层验证：key_sig 构造后解密签名必须匹配。"""
    key = b"0123456789abcdef"
    data_sig = b"\x11" * 16
    from Crypto.Cipher import AES
    target = bytes(x ^ y for x, y in zip(UNITY3D_SIGNATURE, data_sig))
    key_sig = AES.new(key, AES.MODE_ECB).decrypt(target)
    assert _decrypt_key(key_sig, data_sig, key) == UNITY3D_SIGNATURE


def test_brute_force_finds_key_in_metadata_source():
    """key 常驻 metadata：bundle 头向量 + 辅助源含 key → 必须找到。"""
    from Crypto.Cipher import AES
    key = b"0123456789abcdef"
    data_sig = b"\x22" * 16
    target = bytes(x ^ y for x, y in zip(UNITY3D_SIGNATURE, data_sig))
    key_sig = AES.new(key, AES.MODE_ECB).decrypt(target)
    with tempfile.TemporaryDirectory() as td:
        bundle = Path(td) / "enc.bundle"
        bundle.write_bytes(
            UNITY3D_SIGNATURE
            + (0).to_bytes(4, "little")
            + b"\x00" * 33
            + data_sig + key_sig + b"\x00"
            + b"\x00" * 64)
        meta = Path(td) / "global-metadata.dat"
        meta.write_bytes(b"padding" + key + b"more padding")
        found = brute_force_key(bundle, extra_sources=[meta])
        assert found == key


def test_set_decrypt_key_wires_unitypy():
    """set_decrypt_key 必须写入 UnityPy 全局（后续 load 消费）。"""
    from UnityPy.helpers import ArchiveStorageManager
    set_decrypt_key(b"0123456789abcdef")
    assert ArchiveStorageManager.DECRYPT_KEY == b"0123456789abcdef"
    with pytest.raises(ValueError):
        set_decrypt_key(b"short")
