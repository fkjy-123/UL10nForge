"""Addressables catalog 中 AssetBundle CRC 的写回测试。"""

import pytest

from hanhua.core.unity.writer import _patch_catalog_crc_bytes


def test_patch_catalog_crc_bytes_replaces_exactly_one_entry():
    """Addressables catalog 必须把原 bundle CRC 更新为输出 bundle CRC。"""
    original_crc = 0x13E7A863
    translated_crc = 0xDF652EC0
    catalog = b"prefix" + original_crc.to_bytes(4, "little") + b"suffix"

    patched = _patch_catalog_crc_bytes(catalog, {original_crc: translated_crc})

    assert patched == b"prefix" + translated_crc.to_bytes(4, "little") + b"suffix"


def test_patch_catalog_crc_bytes_rejects_ambiguous_crc():
    """同一旧 CRC 出现多次时不能盲目替换。"""
    original_crc = 0x13E7A863
    catalog = original_crc.to_bytes(4, "little") * 2

    with pytest.raises(ValueError, match="出现 2 次"):
        _patch_catalog_crc_bytes(catalog, {original_crc: 0xDF652EC0})


def test_patch_catalog_crc_requires_every_changed_crc_to_match():
    """变化 bundle 的旧 CRC 未出现在 catalog 时必须失败，不能输出不可加载副本。"""
    with pytest.raises(ValueError, match="未找到"):
        _patch_catalog_crc_bytes(
            b"catalog without requested crc",
            {0x12345678: 0x87654321},
            require_match=True,
        )


def test_validate_addressables_skips_when_source_has_no_catalog(tmp_path):
    """bundle 放在 aa 目录但源本身没有 catalog.bin（无 Addressables 管线）时，
    跳过校验而非误报『输出目录缺少 catalog』（真实案例：project-arrhythmia、
    resonance-of-the-ocean 仅把普通 AssetBundle 放 aa 目录）。"""
    from pathlib import Path
    from hanhua.core.unity.writer import _validate_addressables_catalog_sources
    game = tmp_path / "game"
    out = tmp_path / "out"
    aa = game / "game_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64"
    aa.mkdir(parents=True)
    (aa / "defaultlocalgroup_assets_all.bundle").write_bytes(b"BNDL\0\0")
    out.mkdir()

    # 源无 catalog + 输出无 catalog → 跳过（不抛错）
    _validate_addressables_catalog_sources(
        game, out,
        [{"rel_path": "game_Data/StreamingAssets/aa/StandaloneWindows64/defaultlocalgroup_assets_all.bundle"}])

    # 源有 catalog 但输出（staging 副本）缺失 → 仍报错（复制遗漏检测）
    (game / "game_Data" / "StreamingAssets" / "aa" / "catalog.bin").write_bytes(b"catalog")
    import pytest
    with pytest.raises(ValueError, match="catalog.bin"):
        _validate_addressables_catalog_sources(
            game, out,
            [{"rel_path": "game_Data/StreamingAssets/aa/StandaloneWindows64/defaultlocalgroup_assets_all.bundle"}])


def test_update_addressables_catalogs_skips_without_catalog(tmp_path, monkeypatch):
    """输出无 catalog.bin（源也无 Addressables 管线）时，不解析 bundle CRC
    直接返回空 —— 否则 UnityPy 对部分 bundle 会崩
    （'EndianBinaryReader_Memoryview' has no attribute 'reader'，
    真实案例：project-arrhythmia / resonance-of-the-ocean）。"""
    from hanhua.core.unity.writer import _update_addressables_catalogs
    game = tmp_path / "game"
    out = tmp_path / "out"
    aa = game / "game_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64"
    aa.mkdir(parents=True)
    bundle = aa / "defaultlocalgroup_assets_all.bundle"
    bundle.write_bytes(b"BNDL\0\0")
    out.mkdir()
    # 源也复制 bundle 到输出（写回副本含同名文件，但无 catalog）
    (out / "game_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64").mkdir(parents=True)
    (out / "game_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64" / bundle.name).write_bytes(b"BNDL\0\0")

    def boom(*_a, **_k):
        raise AttributeError("'EndianBinaryReader_Memoryview' object has no attribute 'reader'")

    monkeypatch.setattr(
        "hanhua.core.unity.writer._asset_bundle_content_crc", boom)
    # 不调用 CRC 解析 → 不抛错，返回空列表
    assert _update_addressables_catalogs(
        game, out,
        [{"rel_path": "game_Data/StreamingAssets/aa/StandaloneWindows64/defaultlocalgroup_assets_all.bundle"}]) == []
