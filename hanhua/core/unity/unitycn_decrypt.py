"""UnityCN 加密 AssetBundle 解密支持（工具移植任务 1，2026-08-16）。

来源：UnityPy ArchiveStorageManager（Razmoth/PGRStudio 同源，Python）
+ AssetStudio C# 参考。算法：AES-ECB + XOR 双层（头向量解密）+
ArchiveStorageDecryptor 数据块级流式解密（index/substitute 表）。

**集成设计**（与 UnityPy 解析流程一致，不做整体文件解密）：
UnityCN 加密只作用于 UnityFS 的**压缩数据块**（flags & 0x100）——
解密发生在解压之前，由 BundleFile 解析流程内部调用。正确用法：
1. `brute_force_key`：从 bundle 头向量 + 辅助源（global-metadata.dat
   等）暴力探测 16 字符 key（AES-ECB 解签名验证魔数）；
2. `set_decrypt_key`：设置全局 key（UnityPy ArchiveStorageManager）；
3. UnityPy `Environment.load` 正常解析——内部自动解密数据块。

写回限制：UnityPy 未实现 encrypt（加密回写）——解密态写回，原加密
文件保持解密格式（游戏读取兼容性列为观察项）。
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    from Crypto.Cipher import AES
except ImportError:  # pragma: no cover - 依赖缺失时探测报错
    AES = None

from UnityPy.helpers import ArchiveStorageManager
from UnityPy.streams import EndianBinaryReader

# UnityCN 加密签名（与 UnityPy/AssetStudio 一致）
UNITY3D_SIGNATURE = b"#$unity3dchina!@"
# key 候选模式：16 字符 \w（UnityCN 密钥格式，暴力探测用）
_KEY_PATTERN = re.compile(rb"(?=(\w{16}))")


class UnityCNError(Exception):
    """UnityCN 解密失败（无 key/签名不匹配/数据损坏）。"""


def _decrypt_key(key: bytes, data: bytes, keybytes: bytes) -> bytes:
    """AES-ECB 解密密钥向量 + XOR（双层解密的核心）。"""
    if AES is None:
        raise UnityCNError("pycryptodome 未安装，无法解密 UnityCN bundle")
    enc = AES.new(keybytes, AES.MODE_ECB).encrypt(key)
    return bytes(x ^ y for x, y in zip(data, enc))


def _read_vector(reader: EndianBinaryReader) -> tuple[bytes, bytes]:
    """读 0x10 数据 + 0x10 密钥 + 1 字节跳过（UnityCN 头向量格式）。"""
    data = reader.read_bytes(0x10)
    key = reader.read_bytes(0x10)
    reader.Position += 1
    return data, key


def _bundle_signature_vectors(path: Path) -> tuple[bytes, bytes] | None:
    """读加密 bundle 头向量（key_sig, data_sig）——key 验证用。"""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not raw.startswith(UNITY3D_SIGNATURE):
        return None
    reader = EndianBinaryReader(raw)
    reader.read_bytes(len(UNITY3D_SIGNATURE))
    reader.read_u_int()          # unknown_1
    _read_vector(reader)         # data/key（解密用）
    return _read_vector(reader)  # data_sig/key_sig（验证用）


def brute_force_key(
        bundle_path: str | Path,
        extra_sources: list[str | Path] | None = None,
        verbose: bool = False) -> bytes | None:
    """在 bundle 与辅助源（global-metadata.dat 等）中暴力探测解密 key。

    原理：UnityCN 的 key 是 16 字符 `\w` 字符串（常驻游戏二进制）——
    搜索所有 16 字符候选，用头向量解密签名验证（匹配魔数即命中）。
    """
    bundle = Path(bundle_path)
    vectors = _bundle_signature_vectors(bundle)
    if vectors is None:
        return None
    # _read_vector 返回 (data, key)——第二个向量即 (data_sig, key_sig)
    data_sig, key_sig = vectors
    sources: list[Path] = [bundle]
    if extra_sources:
        sources += [Path(s) for s in extra_sources]
    seen: set[bytes] = set()
    for src in sources:
        try:
            data = src.read_bytes()
        except OSError:
            continue
        for m in _KEY_PATTERN.finditer(data):
            key = m.group(1)
            if key in seen:
                continue
            seen.add(key)
            try:
                signature = _decrypt_key(key_sig, data_sig, key)
            except UnityCNError:
                return None
            if signature == UNITY3D_SIGNATURE:
                if verbose:
                    print(f"[unitycn] 找到 key: {key!r}（来源 {src.name}）")
                return key
    return None


def set_decrypt_key(key: bytes | str) -> None:
    """设置全局解密 key（UnityPy ArchiveStorageManager 消费）。

    之后 UnityPy Environment.load 解析加密 bundle 时自动解密数据块。
    """
    ArchiveStorageManager.set_assetbundle_decrypt_key(key)


def decrypt_bundle_file(
        path: str | Path,
        extra_key_sources: list[str | Path] | None = None,
        verbose: bool = False) -> bool:
    """文件级解密入口：探测 key 并设置全局 key。

    返回 True = key 找到且已设置（调用方继续用 UnityPy 解析）；
    False = 探测失败（调用方标记 blocked 保留原样）。
    """
    bundle = Path(path)
    if not _bundle_signature_vectors(bundle):
        return False
    key = brute_force_key(bundle, extra_sources=extra_key_sources,
                          verbose=verbose)
    if key is None:
        return False
    set_decrypt_key(key)
    return True


def find_and_set_game_key(game_dir: str | Path,
                          verbose: bool = False) -> bool:
    """游戏级 key 探测：扫描目录内加密 bundle + global-metadata.dat。

    单文件探测可能 miss（key 常驻 global-metadata.dat 或 game 二进制
    ——不总在 bundle 自身）。找到后设置全局 key（后续所有加密 bundle
    的 UnityPy load 自动解密）。返回 True = key 已设置。
    """
    game_root = Path(game_dir)
    # 1) 找加密 bundle 的头向量（第一个即够——同游戏同 key）
    bundle_path = None
    vectors = None
    for p in game_root.rglob("*"):
        if p.is_file() and p.stat().st_size < 200_000_000:
            v = _bundle_signature_vectors(p)
            if v is not None:
                bundle_path, vectors = p, v
                break
    if bundle_path is None:
        return False
    # 2) 辅助源：global-metadata.dat + 游戏根目录下所有文件（大文件跳过）
    meta = next(game_root.rglob("global-metadata.dat"), None)
    extras = [meta] if meta is not None else []
    if extras:
        key = brute_force_key(bundle_path, extra_sources=extras,
                              verbose=verbose)
        if key is not None:
            set_decrypt_key(key)
            return True
    # 3) 兜底：metadata 不存在时用 bundle 自身 + 同目录大文件
    key = brute_force_key(bundle_path, verbose=verbose)
    if key is not None:
        set_decrypt_key(key)
        return True
    return False
