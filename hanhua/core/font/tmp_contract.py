# -*- coding: utf-8 -*-
"""TMP_FontAsset bundle 资产契约验证（字体闭环 Phase 2）。

Phase 2 实现重点 6：验证 character → glyph → atlas rect → texture/material
链，而不是只比总 glyph 数。对版本化 TMP 字体 bundle 载荷（TmpBundlePayload）
做静态自洽检查——载荷是我们自己的资产，坏链必须在发布门内被发现，不能等
游戏里出方框。

链的每一环：
- character → glyph：字符表条目的 glyph index 必须落在字形表内；
- glyph → atlas rect：字形矩形必须完全落在图集尺寸内；
- atlas → texture bytes：像素流长度必须等于 w×h×每像素字节（格式可解析时）；
- material/shader：TMP_FontAsset 必须引用 bundle 内 Material，且 shader
  属于 TextMeshPro 族（缺失记 warning——部分 bundle 无独立材质对象）。

错误 = 链断裂（必须修复 bundle）；警告 = 缺失但可降级（如实报告，不静默）。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

# Unity m_TextureFormat → 每像素字节数（仅覆盖 TMP SDF 常见格式；
# 未知格式跳过字节长度校验并记 warning，绝不猜测后误判）
_BYTES_PER_PIXEL = {1: 1, 3: 3, 4: 4, 62: 4}  # Alpha8 / RGB24 / RGBA32


@dataclass(frozen=True)
class TmpContractResult:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def summary_text(self) -> str:
        if self.ok:
            return (f"TMP 契约通过（{len(self.warnings)} 警告）"
                    if self.warnings else "TMP 契约通过")
        return f"TMP 契约失败：{len(self.errors)} 错误"


def _character_glyph_entries(tree: dict) -> tuple[list[dict], list[dict]]:
    """(字符表条目, 字形表条目) —— tmp2 布局。"""
    return (tree.get("m_CharacterTable") or [],
            tree.get("m_GlyphTable") or [])


def _tmp1_codes(tree: dict) -> list[int]:
    """tmp1 布局：m_glyphInfoList 内嵌 m_characterCode。"""
    codes: list[int] = []
    for glyph in tree.get("m_glyphInfoList") or []:
        code = glyph.get("m_characterCode") if isinstance(glyph, dict) \
            else None
        if isinstance(code, int):
            codes.append(code)
    return codes


def validate_tmp_contract(payload) -> TmpContractResult:
    """验证 TMP bundle 载荷的 character→glyph→rect→texture/material 链。"""
    errors: list[str] = []
    warnings: list[str] = []
    layout = payload.layout_version
    tree = payload.font_typetree

    if layout == "tmp2":
        chars, glyphs = _character_glyph_entries(tree)
        if not chars:
            errors.append("字符表为空")
        if not glyphs:
            errors.append("字形表为空")
        # glyph 表的 m_Index 是规范索引（表本身可能稀疏：arialuni 的
        # m_Index 3..49496 而表长 38917）；旧布局无 m_Index 时退化为
        # 数组位置语义
        glyph_indexes = {g.get("m_Index") for g in glyphs}
        by_index = glyph_indexes and None not in glyph_indexes
        # character → glyph
        for entry in chars:
            glyph_index = entry.get("m_GlyphIndex")
            if glyph_index is None:
                continue
            if (by_index and glyph_index not in glyph_indexes) or (
                    not by_index and glyph_index >= len(glyphs)):
                errors.append(
                    f"字符 U+{entry.get('m_Unicode', '?'):04X} 的 glyph "
                    f"索引 {glyph_index} 超出字形表（{len(glyphs)}）")
                break
        # glyph → atlas rect
        for glyph in glyphs:
            rect = glyph.get("m_GlyphRect") or {}
            x, y, w, h = (rect.get(k) or 0 for k in
                          ("m_X", "m_Y", "m_Width", "m_Height"))
            if (w or h) and (x + w > payload.atlas_width
                             or y + h > payload.atlas_height):
                errors.append(
                    f"glyph 矩形 ({x},{y},{w}×{h}) 超出图集 "
                    f"{payload.atlas_width}×{payload.atlas_height}")
                break
    else:  # tmp1
        codes = _tmp1_codes(tree)
        if not codes:
            errors.append("tmp1 字形表为空（无 m_characterCode）")
        if len(tree.get("m_glyphInfoList") or []) != payload.glyph_count:
            errors.append("tmp1 glyph 数量与载荷记录不一致")
        warnings.append("tmp1 布局无 glyph 矩形字段，跳过 rect 校验")

    # atlas → texture bytes
    bpp = _BYTES_PER_PIXEL.get(payload.atlas_format)
    if bpp is None:
        warnings.append(f"未知图集格式 {payload.atlas_format}，跳过字节长度校验")
    elif len(payload.atlas_stream) < payload.atlas_width * payload.atlas_height * bpp:
        errors.append(
            f"图集像素流 {len(payload.atlas_stream)} 字节 < "
            f"{payload.atlas_width}×{payload.atlas_height}×{bpp}B")
    elif len(payload.atlas_stream) != payload.atlas_width * payload.atlas_height * bpp:
        warnings.append(
            f"图集像素流 {len(payload.atlas_stream)} 字节与 "
            f"{payload.atlas_width}×{payload.atlas_height}×{bpp}B 不一致"
            "（SDF 图集常带填充，仅警告）")

    # material / shader 契约
    if payload.shader_name:
        if "TextMeshPro" not in payload.shader_name:
            warnings.append(
                f"shader 非 TextMeshPro 族：{payload.shader_name}")
    else:
        warnings.append("bundle 无独立 Material/shader 信息（缺失但可降级）")

    return TmpContractResult(not errors, tuple(errors), tuple(warnings))


def charset_contract(payload) -> dict[str, object]:
    """载荷字符集摘要：数量/CJK 覆盖/ascii/指纹——manifest 交叉校验用。"""
    chars = sorted(payload.charset)
    cjk = [c for c in chars if 0x4E00 <= c <= 0x9FFF]
    return {
        "count": len(chars),
        "cjk_count": len(cjk),
        "ascii_ok": all(c in chars for c in range(0x21, 0x7F)),
        "hash": hashlib.sha256(
            "".join(chr(c) for c in chars).encode("utf-8")
        ).hexdigest() if chars else "",
        "min_codepoint": chars[0] if chars else None,
        "max_codepoint": chars[-1] if chars else None,
    }
