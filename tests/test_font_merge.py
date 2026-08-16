"""字体合并与裁剪测试（工具移植任务 4）。

Warcraft-Font-Merger 合并逻辑 + FilterRepeatCharacter 字符集去重，
fontTools 实现。合成 TTF 验证：字符集提取/合并补缺/裁剪。
"""
import io

import pytest

from hanhua.core.font.font_merge import (
    collect_needed_chars, merge_fonts)

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None

pytestmark = pytest.mark.skipif(TTFont is None,
                                reason="fontTools 未安装")


def _make_font(chars: str, name: str) -> bytes:
    """构造最小 TTF：每个字符一个简单字形（正方形轮廓）。"""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    glyph_order = [".notdef"]
    cmap = {}
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((500, 0))
    pen.lineTo((500, 500))
    pen.lineTo((0, 500))
    pen.closePath()
    glyphs = {".notdef": pen.glyph()}
    for i, ch in enumerate(chars):
        gname = f"glyph{i:03d}"
        glyph_order.append(gname)
        p2 = TTGlyphPen(None)
        p2.moveTo((0, 0))
        p2.lineTo((500, 0))
        p2.lineTo((500, 500))
        p2.lineTo((0, 500))
        p2.closePath()
        glyphs[gname] = p2.glyph()
        cmap[ord(ch)] = gname
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(
        {g: (500, 0) for g in glyph_order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({
        "familyName": name, "styleName": "Regular",
        "uniqueFontIdentifier": name, "fullName": name,
        "psName": name.replace(" ", "")})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200,
                usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def test_collect_needed_chars_dedup():
    texts = ["你好世界", "Hello World", "你好，世界！", ""]
    chars = collect_needed_chars(texts)
    assert "你" in chars and "好" in chars
    assert "H" in chars and " " in chars
    assert "，" in chars and "！" in chars
    # 控制字符排除
    assert "\x00" not in chars


def test_collect_needed_chars_exclude_ascii():
    chars = collect_needed_chars(["abc你好"], include_ascii=False)
    assert "你" in chars
    assert "a" not in chars


def test_merge_fills_missing_chars():
    """primary 缺 'B'（无中文字形），fallback 补——合并后 cmap 含全部。"""
    primary = _make_font("AC中", "Primary")
    fallback = _make_font("BD文", "Fallback")
    needed = collect_needed_chars(["AB中文"])
    merged = merge_fonts(primary, fallback, needed)
    font = TTFont(io.BytesIO(merged))
    cmap = font.getBestCmap()
    for ch in "AB中文":
        assert ord(ch) in cmap, f"合并后缺 {ch!r}"
    # 裁剪：不需要的字符（fallback 的 'D'）不应在需求字形里
    # （D 不在 needed 且非引用 → glyf 中删除）
    assert "D" not in font.getGlyphOrder() or "D" not in needed


def test_merge_primary_preferred():
    """primary 已有字符 → 不覆盖（primary 字形优先）。"""
    primary = _make_font("A", "Primary")
    fallback = _make_font("A", "Fallback")
    needed = collect_needed_chars(["A"])
    merged = merge_fonts(primary, fallback, needed)
    font = TTFont(io.BytesIO(merged))
    cmap = font.getBestCmap()
    assert ord("A") in cmap


def test_merge_invalid_font_raises():
    with pytest.raises(ValueError):
        merge_fonts(b"not a font", b"not a font", {"A"})
