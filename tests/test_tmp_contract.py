# -*- coding: utf-8 -*-
"""TMP bundle 资产契约验证（字体闭环 Phase 2 实现重点 6）。

character → glyph → atlas rect → texture/material 链逐环验证：
坏链必须在发布门内被发现，不能等游戏里出方框。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from hanhua.core.font.tmp_contract import (charset_contract,
                                            validate_tmp_contract)
from hanhua.core.unity.font_replace import TmpBundlePayload

BUNDLE_DIR = Path(__file__).resolve().parents[1] / "fonts" \
    / "TMP_Font_AssetBundles"


def _payload(**kw) -> TmpBundlePayload:
    """合法 tmp2 载荷：2 字符、2 glyph、矩形在图集内、像素流匹配 RGBA32。"""
    font_typetree = {
        "m_Name": "test",
        "m_CharacterTable": [
            {"m_Unicode": 0x4E00, "m_GlyphIndex": 0},
            {"m_Unicode": 0x4E01, "m_GlyphIndex": 1},
        ],
        "m_GlyphTable": [
            {"m_GlyphRect": {"m_X": 0, "m_Y": 0, "m_Width": 4, "m_Height": 4}},
            {"m_GlyphRect": {"m_X": 4, "m_Y": 4, "m_Width": 4, "m_Height": 4}},
        ],
    }
    base = dict(
        bundle_path=Path("b"), font_name="test", glyph_count=2,
        layout_version="tmp2", font_typetree=font_typetree,
        atlas_texture={}, atlas_stream=b"\x00" * (8 * 8 * 4),
        atlas_width=8, atlas_height=8, atlas_format=62,
        charset=frozenset({0x4E00, 0x4E01}),
        material_name="TMP SDF", shader_name="TextMeshPro/Distance Field",
    )
    base.update(kw)
    return TmpBundlePayload(**base)


# ── 链：character → glyph ────────────────────────────────────

def test_ok_payload_passes_contract():
    result = validate_tmp_contract(_payload())
    assert result.ok is True
    assert result.errors == ()
    assert result.summary_text() == "TMP 契约通过"


def test_character_glyph_index_out_of_range():
    tree = _payload().font_typetree
    tree["m_CharacterTable"][1]["m_GlyphIndex"] = 5
    result = validate_tmp_contract(_payload(font_typetree=tree))
    assert result.ok is False
    assert any("glyph 索引 5" in e for e in result.errors)


def test_sparse_glyph_table_resolves_by_m_index():
    """真实 arialuni 语义：字形表稀疏（m_Index 3..49496，表长 38917），
    字符按 m_Index 规范值引用——越出数组位置的索引仍合法。"""
    font_typetree = {
        "m_Name": "test",
        "m_CharacterTable": [
            {"m_Unicode": 0xAE50, "m_GlyphIndex": 38917},   # > 表长 2
            {"m_Unicode": 0x4E00, "m_GlyphIndex": 3},
        ],
        "m_GlyphTable": [
            {"m_Index": 3, "m_GlyphRect":
                {"m_X": 0, "m_Y": 0, "m_Width": 4, "m_Height": 4}},
            {"m_Index": 38917, "m_GlyphRect":
                {"m_X": 4, "m_Y": 0, "m_Width": 4, "m_Height": 4}},
        ],
    }
    payload = _payload(glyph_count=2, font_typetree=font_typetree,
                       charset=frozenset({0x4E00, 0xAE50}))
    result = validate_tmp_contract(payload)
    assert result.ok is True, result.errors


def test_sparse_glyph_table_bad_index_still_fails():
    # 稀疏表中引用了 m_Index 不存在的 glyph → 链断裂
    tree = _payload().font_typetree
    tree["m_CharacterTable"][0]["m_GlyphIndex"] = 999
    for glyph in tree["m_GlyphTable"]:
        glyph["m_Index"] = glyph["m_GlyphRect"]["m_X"] + 1
    result = validate_tmp_contract(_payload(font_typetree=tree))
    assert result.ok is False
    assert any("glyph 索引 999" in e for e in result.errors)


def test_empty_character_table():
    tree = _payload().font_typetree
    tree["m_CharacterTable"] = []
    result = validate_tmp_contract(_payload(font_typetree=tree))
    assert result.ok is False
    assert "字符表为空" in result.errors


# ── 链：glyph → atlas rect ───────────────────────────────────

def test_glyph_rect_out_of_bounds():
    tree = _payload().font_typetree
    tree["m_GlyphTable"][1]["m_GlyphRect"] = \
        {"m_X": 7, "m_Y": 0, "m_Width": 2, "m_Height": 2}
    result = validate_tmp_contract(_payload(font_typetree=tree))
    assert result.ok is False
    assert any("超出图集" in e for e in result.errors)


def test_zero_size_rect_skipped():
    tree = _payload().font_typetree
    tree["m_GlyphTable"][0]["m_GlyphRect"] = \
        {"m_X": 0, "m_Y": 0, "m_Width": 0, "m_Height": 0}
    result = validate_tmp_contract(_payload(font_typetree=tree))
    assert result.ok is True                      # 空字形合法，不误报


# ── 链：atlas → texture bytes ────────────────────────────────

def test_atlas_bytes_too_short():
    result = validate_tmp_contract(_payload(atlas_stream=b"\x00" * 100))
    assert result.ok is False
    assert any("像素流" in e for e in result.errors)


def test_unknown_atlas_format_warns_not_fails():
    result = validate_tmp_contract(_payload(atlas_format=99))
    assert result.ok is True
    assert any("未知图集格式" in w for w in result.warnings)


# ── 链：material / shader ────────────────────────────────────

def test_missing_material_warns():
    result = validate_tmp_contract(_payload(shader_name=""))
    assert result.ok is True
    assert any("Material/shader" in w for w in result.warnings)


def test_non_tmp_shader_warns():
    result = validate_tmp_contract(
        _payload(shader_name="Standard"))
    assert result.ok is True
    assert any("非 TextMeshPro 族" in w for w in result.warnings)


# ── tmp1 布局 ────────────────────────────────────────────────

def test_tmp1_layout_contract():
    font_typetree = {
        "m_Name": "test",
        "m_glyphInfoList": [
            {"m_characterCode": 0x4E00}, {"m_characterCode": 0x4E01},
        ],
    }
    payload = _payload(layout_version="tmp1", glyph_count=2,
                       font_typetree=font_typetree,
                       charset=frozenset({0x4E00, 0x4E01}))
    result = validate_tmp_contract(payload)
    assert result.ok is True
    assert any("跳过 rect 校验" in w for w in result.warnings)


def test_tmp1_glyph_count_mismatch():
    font_typetree = {"m_glyphInfoList": [{"m_characterCode": 0x4E00}]}
    payload = _payload(layout_version="tmp1", glyph_count=3,
                       font_typetree=font_typetree)
    result = validate_tmp_contract(payload)
    assert result.ok is False


# ── 字符集摘要（manifest 交叉校验） ──────────────────────────

def test_charset_contract_summary():
    summary = charset_contract(_payload(
        charset=frozenset({0x4E00, 0x4E10, 0x9F99, 0x41, 0x7A, 0x30})))
    assert summary["count"] == 6
    assert summary["cjk_count"] == 3
    assert summary["ascii_ok"] is False          # 只含 3 个 ASCII，未全量覆盖
    assert summary["hash"]
    assert summary["min_codepoint"] == 0x30
    assert summary["max_codepoint"] == 0x9F99


def test_charset_contract_full_ascii():
    chars = frozenset(range(0x20, 0x7F)) | {0x4E00}
    summary = charset_contract(_payload(charset=chars))
    assert summary["ascii_ok"] is True
    assert summary["count"] == 96


# ── manifest：schema + 契约声明 ──────────────────────────────

def test_manifest_schema_and_contracts():
    manifest = json.loads((BUNDLE_DIR / "manifest.json").read_text(
        encoding="utf-8"))
    assert manifest["schema_version"] == 2
    # 用户 SDF 资产是 TMP 2.x/3.x 布局（tmp2）：TMP1（Unity ≤2018）无
    # 中文 SDF bundle（select_tmp_bundle 返回 None），旧 tmp1 arialuni
    # 清单不适用于新字符表
    assert set(manifest["tmp_versions"]) == {"tmp2"}
    charset = manifest["charset_contract"]
    assert charset["cjk_range"] == [0x4E00, 0x9FFF]
    assert charset["min_cjk_count"] >= 3000
    assert charset["ascii_range"] == [0x21, 0x7E]
    assert set(manifest["weights"]) == {"heavy", "medium", "thin"}
    # 三档 × 四版本完整性（u2019/u2021/u2022/u6000，select_tmp_bundle
    # 按 Unity 主版本 + weight 选择的后端）
    from hanhua.core.unity.font_replace import select_tmp_bundle
    for weight in ("heavy", "medium", "thin"):
        for ver in ("2019.4", "2021.3", "2022.3", "6000.0"):
            bundle = select_tmp_bundle(ver, weight=weight)
            assert bundle is not None and bundle.is_file(), (
                f"缺少 {weight}/{ver} bundle")
    for name, meta in manifest["integrity"].items():
        assert meta["unity"] and meta["tmp_layout"] == "tmp2" \
            and meta["sha256"] and meta["weight"]


@pytest.mark.skipif(
    not (BUNDLE_DIR / "arialuni_sdf_u2021").is_file(),
    reason="TMP bundle 缺失")
def test_real_bundle_contract_and_charset():
    """真实 bundle 端到端：载荷字符集覆盖 manifest 契约（CJK + ASCII）。"""
    from hanhua.core.unity.font_replace import load_tmp_bundle
    payload = load_tmp_bundle(BUNDLE_DIR / "arialuni_sdf_u2021")
    result = validate_tmp_contract(payload)
    assert result.ok is True, result.errors
    summary = charset_contract(payload)
    assert summary["cjk_count"] >= 3000
    assert summary["ascii_ok"] is True
    assert summary["hash"]
    assert payload.layout_version == "tmp2"
