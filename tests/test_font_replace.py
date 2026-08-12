"""font_replace.py 静态字体替换单元测试。

覆盖：版本→bundle 映射、TMP 布局代判定、字体字段复制、
legacy Font TTF 替换判定、候选文件筛选、manifest 完整性。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hanhua.core.models import FontConfig
from hanhua.core.unity.font_replace import (
    TmpBundlePayload,
    _asset_candidates,
    _copy_font_fields,
    _font_ttf_candidate,
    _patch_font_object,
    _ttf_has_magic,
    _ttf_metrics,
    _typetree_layout_version,
    install_static_fonts,
    select_tmp_bundle,
)

FONTS_DIR = Path(__file__).resolve().parents[1] / "fonts"
BUNDLE_DIR = FONTS_DIR / "TMP_Font_AssetBundles_2025-12-08"


# ── 版本映射 ────────────────────────────────────────────────

@pytest.mark.parametrize("version,expected", [
    ("5.6.1", "arialuni_sdf-u55to2017"),
    ("2017.4.40", "arialuni_sdf-u55to2017"),
    ("2018.4.36", "arialuni_sdf_u2018"),
    ("2019.4.40", "arialuni_sdf_u2019"),
    ("2020.3.48", "arialuni_sdf_u2019"),
    ("2021.3.33", "arialuni_sdf_u2021"),
    ("2022.3.20", "arialuni_sdf_u2022"),
    ("6000.3.32f1", "arialuni_sdf_u6000"),
    ("2050.1.0", None),
])
def test_select_tmp_bundle(version, expected):
    bundle = select_tmp_bundle(version)
    if expected is None:
        assert bundle is None
    else:
        assert bundle is not None
        assert bundle.name == expected
        assert bundle.is_file()


def test_select_tmp_bundle_none():
    assert select_tmp_bundle(None) is None
    assert select_tmp_bundle("") is None
    assert select_tmp_bundle("invalid") is None


# ── 布局代判定 ──────────────────────────────────────────────

def test_layout_version():
    assert _typetree_layout_version({"m_GlyphTable": []}) == "tmp2"
    assert _typetree_layout_version({"m_glyphInfoList": []}) == "tmp1"
    assert _typetree_layout_version({"m_Name": "x"}) is None
    assert _typetree_layout_version({}) is None


# ── TTF magic ───────────────────────────────────────────────

def test_ttf_has_magic():
    assert _ttf_has_magic(b"\x00\x01\x00\x00" + b"x" * 20)
    assert _ttf_has_magic(b"OTTO" + b"x" * 20)
    assert not _ttf_has_magic(b"ABCDEFGH")
    assert not _ttf_has_magic(b"")


# ── legacy Font 对象替换 ────────────────────────────────────

class _StubFontObj:
    def __init__(self, font_data):
        self._tree = {
            "m_Name": "f", "m_FontData": font_data, "m_FontSize": 16.0,
            "m_Ascent": 12.0, "m_Descent": -4.0, "m_LineSpacing": 16.0,
            "m_FontRenderingMode": 2,
        }
        self.saved = None

    def read_typetree(self):
        return self._tree

    def save_typetree(self, tree):
        self.saved = tree
        return b"raw"


def _make_font_ttf(n=4096):
    # 伪造一个有效的 TTF 头 + 数据
    return b"\x00\x01\x00\x00" + bytes((i % 251 for i in range(n - 4)))


# 构造含真实 head/hhea 表的迷你 TTF：upm=1000, ascent=860, descent=-200, gap=0
def _make_metric_ttf():
    head = b"\x00\x01\x00\x00" + b"\x00" * 14 + (1000).to_bytes(2, "big") \
        + b"\x00" * 36
    hhea = b"\x00" * 4 + (860).to_bytes(2, "big", signed=True) \
        + (-200).to_bytes(2, "big", signed=True) + b"\x00" * 4 + b"\x00" * 12
    body = head + hhea
    body += bytes((i % 251 for i in range(4096 - len(body))))
    num_tables = 2
    # sfnt 头 12 字节：magic(4) + numTables(2) + searchRange/entrySelector/rangeShift(6)
    header = b"\x00\x01\x00\x00" + num_tables.to_bytes(2, "big") + b"\x00" * 6
    table_entries = b""
    # head 表：紧随目录；hhea 表：跟在 head 后
    head_len = len(head)
    for i, (tag, length, data) in enumerate([
            (b"head", head_len, head), (b"hhea", len(hhea), hhea)]):
        offset = 12 + 16 * num_tables + (head_len if i == 1 else 0)
        table_entries += tag + b"\x00" * 4 \
            + offset.to_bytes(4, "big") + length.to_bytes(4, "big")
    return header + table_entries + body


def test_ttf_metrics_real_fonts():
    import os
    ttf = Path(os.path.join(
        str(Path(__file__).resolve().parents[1]), "fonts",
        "SimplifiedChinese", "SourceHanSansSC-Regular.otf"))
    if ttf.is_file():
        ascent, descent, gap = _ttf_metrics(ttf.read_bytes())
        # 思源黑体 hhea: ascent≈0.92em, descent≈-0.24em
        assert 0.7 < ascent < 1.2
        assert -0.35 < descent < -0.1
        assert -0.2 < gap < 0.2


def test_ttf_metrics_synthetic():
    ascent, descent, gap = _ttf_metrics(_make_metric_ttf())
    assert ascent == 0.86
    assert descent == -0.2
    assert gap == 0.0
    assert _ttf_metrics(b"") is None
    assert _ttf_metrics(b"NOTATTF" + b"\x00" * 40) is None


def test_patch_font_object_replaces():
    obj = _StubFontObj(list(_make_font_ttf()))
    ttf = _make_font_ttf(8192)
    assert _patch_font_object(None, obj, ttf) is True
    assert obj.saved is not None
    assert bytes(obj.saved["m_FontData"]) == ttf


def test_patch_font_object_syncs_metrics():
    # 目标 TTF 度量（0.86/-0.2）→ m_Ascent/m_Descent/m_LineSpacing 按 16px 换算
    obj = _StubFontObj(list(_make_font_ttf()))
    assert _patch_font_object(None, obj, _make_metric_ttf()) is True
    assert obj.saved["m_Ascent"] == 13.76
    assert obj.saved["m_Descent"] == -3.2
    assert obj.saved["m_LineSpacing"] == 16.96
    # 像素字体渲染模式（2=HintedRaster）→ Smooth(0) 提高矢量 TTF 清晰度
    assert obj.saved["m_FontRenderingMode"] == 0


def test_patch_font_object_keeps_smooth_mode():
    obj = _StubFontObj(list(_make_font_ttf()))
    obj._tree["m_FontRenderingMode"] = 0
    assert _patch_font_object(None, obj, _make_metric_ttf()) is True
    assert obj.saved["m_FontRenderingMode"] == 0


def test_patch_font_object_skips_small_data():
    obj = _StubFontObj(list(b"\x00\x01\x00\x00" + b"\x00" * 100))
    assert _patch_font_object(None, obj, _make_font_ttf()) is False
    assert obj.saved is None


def test_patch_font_object_skips_non_ttf():
    obj = _StubFontObj(list(b"NOTAFONT" + b"\x00" * 300))
    assert _patch_font_object(None, obj, _make_font_ttf()) is False
    assert obj.saved is None


def test_patch_font_object_skips_empty():
    obj = _StubFontObj([])
    assert _patch_font_object(None, obj, _make_font_ttf()) is False


# ── TMP 字段复制 ────────────────────────────────────────────

def _payload(layout, fields):
    return TmpBundlePayload(
        bundle_path=Path("b"),
        font_name="test",
        glyph_count=100,
        layout_version=layout,
        font_typetree=fields,
        atlas_texture={},
        atlas_stream=b"",
        atlas_width=8,
        atlas_height=8,
        atlas_format=1,
    )


def test_copy_fields_tmp2():
    payload = _payload("tmp2", {
        "m_GlyphTable": [{"i": 1}], "m_CharacterTable": [{"c": 65}],
    })
    game = {"m_GlyphTable": [], "m_Name": "game"}
    assert _copy_font_fields(game, payload) is True
    assert game["m_GlyphTable"] == [{"i": 1}]
    assert game["m_CharacterTable"] == [{"c": 65}]
    # 未出现在 bundle 的字段不动
    assert game["m_Name"] == "game"


def test_copy_fields_tmp1():
    payload = _payload("tmp1", {"m_glyphInfoList": [{"id": 1}]})
    game = {"m_glyphInfoList": []}
    assert _copy_font_fields(game, payload) is True
    assert game["m_glyphInfoList"] == [{"id": 1}]


def test_copy_fields_no_change():
    payload = _payload("tmp2", {"m_GlyphTable": [{"i": 1}]})
    game = {"m_GlyphTable": [{"i": 1}]}
    assert _copy_font_fields(game, payload) is False


def test_copy_fields_layout_mismatch_fields():
    # 布局匹配由调用方保证（replace_tmp_fonts_in_container 内 layout 检查）；
    # _copy_font_fields 只复制 bundle 里存在的字段，tmp1 字段写入即可
    payload = _payload("tmp1", {"m_glyphInfoList": [{"id": 1}]})
    game = {"m_GlyphTable": []}
    assert _copy_font_fields(game, payload) is True
    assert game["m_glyphInfoList"] == [{"id": 1}]
    assert game["m_GlyphTable"] == []


# ── 字体候选 ────────────────────────────────────────────────

def test_font_ttf_candidate_whitelist():
    cfg = FontConfig(filename="SimplifiedChinese/SourceHanSansSC-Regular.otf")
    cand = _font_ttf_candidate(cfg)
    assert cand is not None and cand.is_file()


def test_font_ttf_candidate_unknown():
    cfg = FontConfig(filename="不存在.ttf")
    assert _font_ttf_candidate(cfg) is None
    assert _font_ttf_candidate(FontConfig(filename="")) is None


# ── 候选文件筛选 ────────────────────────────────────────────

def test_asset_candidates_filters(tmp_path):
    big = b"x" * 4096
    (tmp_path / "data.unity3d").write_bytes(big)
    (tmp_path / "globalgamemanagers.assets").write_bytes(big)
    (tmp_path / "mainData").write_bytes(big)
    (tmp_path / "level1").write_bytes(big)
    (tmp_path / "resources.assets").write_bytes(big)
    (tmp_path / "readme.txt").write_bytes(big)
    (tmp_path / "il2cpp_data" / "Metadata").mkdir(parents=True)
    (tmp_path / "il2cpp_data" / "Metadata" / "global-metadata.dat").write_bytes(big)
    (tmp_path / "MonoBleedingEdge").mkdir()
    (tmp_path / "MonoBleedingEdge" / "x.bundle").write_bytes(big)
    names = {p.name for p in _asset_candidates(tmp_path)}
    assert names == {"data.unity3d", "globalgamemanagers.assets",
                     "mainData", "level1", "resources.assets"}
    assert "global-metadata.dat" not in names


def test_asset_candidates_skips_tiny_placeholder(tmp_path):
    # <256 字节的占位文件（如测试 fixture 的 10 字节 globalgamemanagers）
    # 不是真实 Unity 容器，必须跳过，避免 UnityPy 以未知格式持有句柄
    (tmp_path / "globalgamemanagers").write_bytes(b"2022.3.34f1")
    assert _asset_candidates(tmp_path) == []


# ── manifest 完整性 ─────────────────────────────────────────

def test_manifest_matches_bundles():
    manifest = json.loads((BUNDLE_DIR / "manifest.json").read_text(
        encoding="utf-8"))
    integrity = manifest["integrity"]
    # manifest 里的每个 bundle 都必须真实存在且 sha256 匹配
    assert len(integrity) == 6
    for name, meta in integrity.items():
        p = BUNDLE_DIR / name
        assert p.is_file(), f"{name} missing"
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        assert sha == meta["sha256"], f"{name} sha256 mismatch"


def test_manifest_versions_cover_all_bundles():
    manifest = json.loads((BUNDLE_DIR / "manifest.json").read_text(
        encoding="utf-8"))
    integrity = manifest["integrity"]
    for name in ["arialuni_sdf-u55to2017", "arialuni_sdf_u2018",
                 "arialuni_sdf_u2019", "arialuni_sdf_u2021",
                 "arialuni_sdf_u2022", "arialuni_sdf_u6000"]:
        assert name in integrity


# ── install_static_fonts 容错 ───────────────────────────────

def test_install_static_fonts_empty_dir(tmp_path):
    result = install_static_fonts(tmp_path, FontConfig(enabled=True))
    assert result.replaced == 0
    assert result.skipped == []
    assert result.warnings == []


def test_install_static_fonts_disabled_tmp(tmp_path):
    # enabled=False 时 TMP 路径不执行，legacy 仍按 TTF 替换
    result = install_static_fonts(tmp_path, FontConfig(enabled=False))
    assert result.replaced == 0


def test_install_static_fonts_collects_replaced_paths(
        tmp_path, monkeypatch):
    """C5：整容器重建的 bundle 必须记下相对路径，供 catalog CRC 二次同步。"""
    ttf = tmp_path / "f.otf"
    ttf.write_bytes(_make_font_ttf())
    bundle = tmp_path / "StreamingAssets" / "aa" / "fonts.bundle"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle")

    monkeypatch.setattr(
        "hanhua.core.unity.font_replace._font_ttf_candidate",
        lambda _cfg: ttf)
    monkeypatch.setattr(
        "hanhua.core.unity.font_replace._asset_candidates",
        lambda _out_dir: [bundle])
    monkeypatch.setattr(
        "hanhua.core.unity.font_replace.replace_legacy_fonts_in_container",
        lambda _asset, _ttf_bytes: (2, []))

    result = install_static_fonts(tmp_path, FontConfig(enabled=True))

    assert result.replaced == 2
    assert result.replaced_paths == ["StreamingAssets/aa/fonts.bundle"]
