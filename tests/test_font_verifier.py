"""#12 全链验证器测试：逐 Unicode Code Point Font→Character→Glyph→
Atlas→Fallback 链验证 + Case A-H 根因分类（验收计划第十八阶段）。

验证器是纯函数（字体问题文档.txt 原则：不猜测，逐码点实际验证）。
"""
from __future__ import annotations

import struct

import pytest

from hanhua.core.font.glyph_set import RequiredGlyphSet
from hanhua.core.font.verifier import (
    ATLAS_MISSING, CHARACTER_MISSING, CONSUMER_MISCONFIG,
    DATA_CORRUPTION, DYNAMIC_UNVERIFIED, FALLBACK_MISSING_GLYPH,
    FALLBACK_UNCONFIGURED, FONT_INVALID, GLYPH_MISSING, OK,
    FontSource, TmpAssetInfo, detect_fallback_cycle, verify_chain,
)


def _font(data: bytes, name: str = "main") -> FontSource:
    return FontSource(name, data)


def _make_ttf(codepoints: set[int]) -> bytes:
    """构造带真实 cmap format 4 的迷你 TTF（测试固定设施）。

    字体问题文档原则：不猜测字体支持什么——验证必须基于真实可解析的
    TTF 字节（sfnt 头 + cmap 表 + format 4 分段映射，delta=0 直接
    映射到目标码点），不用 mock 的码点集。
    """
    cps = sorted(codepoints)
    segments: list[tuple[int, int]] = []
    seg_start = prev = cps[0]
    for cp in cps[1:]:
        if cp != prev + 1:
            segments.append((seg_start, prev))
            seg_start = cp
        prev = cp
    segments.append((seg_start, prev))
    seg_count = len(segments)
    seg_count_x2 = seg_count * 2
    # format 4：14 字节头 + endCode + reservedPad + startCode + idDelta +
    # idRangeOffset（ro 全 0，无 glyphIdArray）
    fmt4_len = 14 + seg_count_x2 + 2 + 3 * seg_count_x2
    sub = bytearray(fmt4_len)
    search_range = (1 << (seg_count.bit_length() - 1)) * 2
    entry_selector = seg_count.bit_length() - 1
    struct.pack_into(">HHHHHHH", sub, 0, 4, fmt4_len, 0, seg_count_x2,
                     search_range, entry_selector, seg_count_x2 - search_range)
    end_base, start_base = 14, 14 + seg_count_x2 + 2
    delta_base, ro_base = start_base + seg_count_x2, start_base + 2 * seg_count_x2
    for i, (s, e) in enumerate(segments):
        struct.pack_into(">H", sub, end_base + 2 * i, e)
        struct.pack_into(">H", sub, start_base + 2 * i, s)
        struct.pack_into(">h", sub, delta_base + 2 * i, 0)
        struct.pack_into(">H", sub, ro_base + 2 * i, 0)
    # cmap 表：header(4) + 1 条编码记录(8) + subtable
    cmap_len = 12 + fmt4_len
    cmap = bytearray(cmap_len)
    struct.pack_into(">HH", cmap, 0, 0, 1)          # version, numRecords
    struct.pack_into(">HHI", cmap, 4, 3, 1, 12)     # platform3/enc1 → subtable
    cmap[12:12 + fmt4_len] = sub
    # sfnt：header(12) + 1 条表记录(16) + cmap 表
    total = 12 + 16 + cmap_len
    data = bytearray(total)
    data[:4] = b"\x00\x01\x00\x00"
    struct.pack_into(">H", data, 4, 1)              # numTables
    struct.pack_into(">HHH", data, 6, 0, 0, 0)
    data[12:16] = b"cmap"
    struct.pack_into(">III", data, 16, 0, 28, cmap_len)
    data[28:28 + cmap_len] = cmap
    return bytes(data)


def _fake_ttf() -> bytes:
    """覆盖 ASCII（32-126）的合法迷你 TTF——多数字母/数字测试的默认字体。"""
    return _make_ttf(set(range(32, 127)))


def _cjk_ttf(*chars: str) -> bytes:
    """覆盖指定 CJK 码点的合法迷你 TTF（fallback 命中场景用）。"""
    return _make_ttf(set(ord(ch) for ch in chars))


def _required(*chars: str) -> RequiredGlyphSet:
    scalars = frozenset(ord(ch) for ch in chars)
    return RequiredGlyphSet(
        scalars, {s: [f"f:{s}"] for s in scalars})


def _cjk_font() -> FontSource:
    """伪装含 CJK 的字体：解析失败不算（无效信号）——用真实逻辑：
    构造一个 cmap 含指定码点的字体成本高，这里用足够大的伪 TTF 无法
    保证——所以 CJK 场景通过 fallback 或临时补丁验证。"""
    return _font(_fake_ttf())


# ── Case H：字体文件无效 ─────────────────────────────────────

def test_font_invalid_empty():
    r = verify_chain(_required("你"), font=_font(b""))
    assert r.verdicts[0].case == FONT_INVALID


def test_font_invalid_bad_magic():
    r = verify_chain(_required("你"), font=_font(b"NOTATTF" + b"\x00" * 5000))
    assert r.verdicts[0].case == FONT_INVALID


def test_font_invalid_small_data():
    r = verify_chain(_required("你"), font=_font(b"\x00\x01\x00\x00" + b"x" * 100))
    assert r.verdicts[0].case == FONT_INVALID


# ── Case A/D/E：主字体缺字形 → Fallback 层 ──────────────────

def test_missing_glyph_no_fallback_is_fallback_unconfigured():
    """主字体缺字形 + 无 fallback → Case D（配置 fallback 即可解决）。"""
    r = verify_chain(_required("你"), font=_font(_fake_ttf()))
    v = r.verdicts[0]
    assert v.case == FALLBACK_UNCONFIGURED
    assert "缺字形" in v.chain[0]          # Case A 事实留档
    assert r.font_glyph_gaps == 1
    assert "Case A" in r.summary_text()


def test_missing_glyph_fallback_misses_is_fallback_missing_glyph():
    """主字体缺 + fallback 配置了但也缺 → Case E。"""
    r = verify_chain(
        _required("你"), font=_font(_fake_ttf()),
        fallbacks=(_font(_fake_ttf(), "fb1"),))
    assert r.verdicts[0].case == FALLBACK_MISSING_GLYPH
    assert len(r.verdicts[0].chain) >= 2   # Font缺 → Fallback 证据


def test_missing_glyph_fallback_hits_is_ok():
    """主字体缺但 fallback 命中 → 不口口（OK，chain 记录兜底成功）。"""
    r = verify_chain(
        _required("你"), font=_font(_fake_ttf()),
        fallbacks=(_font(_cjk_ttf("你"), "fb"),))
    v = r.verdicts[0]
    assert v.case == OK
    assert v.chain[0].startswith("Font[main]缺字形")   # Case A 事实留档
    assert v.chain[-1].startswith("Fallback[fb]")
    assert r.font_glyph_gaps == 1


# ── 基本覆盖 ─────────────────────────────────────────────────

def test_ascii_covered_by_tmp_chain():
    """码点在主字体 + TMP 字符/字形/图集全链通过 → OK。"""
    cps = frozenset({ord("A")})
    req = RequiredGlyphSet(cps, {ord("A"): ["f:k"]})
    tmp = TmpAssetInfo("a", character_table=cps, glyph_table=cps,
                       atlas_valid=True)
    r = verify_chain(req, font=_font(_fake_ttf()), tmp=tmp)
    assert r.verdicts[0].case == OK
    assert r.defect_count == 0
    assert r.ok_count == 1


def test_data_corruption_box_codepoint():
    """□ U+25A1 已写入文本 = 数据损坏，不归因字体（Case 数据层）。"""
    r = verify_chain(_required("□"), font=_font(_fake_ttf()))
    assert r.verdicts[0].case == DATA_CORRUPTION
    assert r.defect_count == 0            # 不是字体缺陷


# ── Case B：TMP 字符表/字形表缺口 ────────────────────────────

def test_character_table_missing_is_case_b():
    """cmap 有而 TMP 字符表无 → Case B（静态资产未收录）。"""
    cps = frozenset({ord("B")})
    req = RequiredGlyphSet(cps, {ord("B"): ["f:k"]})
    tmp = TmpAssetInfo("a", character_table=frozenset(),
                       glyph_table=frozenset(), atlas_valid=True)
    r = verify_chain(req, font=_font(_fake_ttf()), tmp=tmp)
    assert r.verdicts[0].case == CHARACTER_MISSING
    assert r.defect_count == 1


def test_glyph_table_missing_is_case_b_deep():
    """字符表有而字形表无 → GLYPH_MISSING（Case B 深化）。"""
    cps = frozenset({ord("C")})
    req = RequiredGlyphSet(cps, {ord("C"): ["f:k"]})
    tmp = TmpAssetInfo("a", character_table=cps, glyph_table=frozenset())
    r = verify_chain(req, font=_font(_fake_ttf()), tmp=tmp)
    assert r.verdicts[0].case == GLYPH_MISSING


# ── Case G：图集 ─────────────────────────────────────────────

def test_atlas_broken_is_case_g():
    cps = frozenset({ord("D")})
    req = RequiredGlyphSet(cps, {ord("D"): ["f:k"]})
    tmp = TmpAssetInfo("a", character_table=cps, glyph_table=cps,
                       atlas_valid=False)
    r = verify_chain(req, font=_font(_fake_ttf()), tmp=tmp)
    assert r.verdicts[0].case == ATLAS_MISSING


# ── Case F：动态字体 ─────────────────────────────────────────

def test_dynamic_tmp_is_unverified():
    """动态字体运行时生成字形——静态不可断言，诚实标注 Case F。"""
    cps = frozenset({ord("E")})
    req = RequiredGlyphSet(cps, {ord("E"): ["f:k"]})
    tmp = TmpAssetInfo("a", dynamic=True)
    r = verify_chain(req, font=_font(_fake_ttf()), tmp=tmp)
    assert r.verdicts[0].case == DYNAMIC_UNVERIFIED
    assert "dynamic" in r.verdicts[0].chain[-1]


# ── Case C：消费者配置 ───────────────────────────────────────

def test_consumer_misconfig_is_case_c():
    """TMP 消费者未引用该字体资产 → Case C（消费端配置问题）。"""
    cps = frozenset({ord("F")})
    req = RequiredGlyphSet(cps, {ord("F"): ["f:k"]})
    r = verify_chain(req, font=_font(_fake_ttf()), consumer_ok=False,
                     consumer_kind="TMP_Text")
    assert r.verdicts[0].case == CONSUMER_MISCONFIG


# ── 无 TMP 层（纯 Font） ─────────────────────────────────────

def test_no_tmp_layer_font_covers():
    cps = frozenset({ord("G")})
    req = RequiredGlyphSet(cps, {ord("G"): ["f:k"]})
    r = verify_chain(req, font=_font(_fake_ttf()))
    assert r.verdicts[0].case == OK


# ── Fallback 循环（验收计划 16.3） ───────────────────────────

def test_fallback_cycle_detected():
    fb = [_font(_fake_ttf(), "A"), _font(_fake_ttf(), "B"),
          _font(_fake_ttf(), "A")]
    assert detect_fallback_cycle(fb) == ("A", "B", "A")
    assert detect_fallback_cycle(fb[:2]) == ()


def test_cycle_reported_in_report():
    r = verify_chain(
        _required("A"), font=_font(_fake_ttf()),
        fallbacks=(_font(_fake_ttf(), "x"), _font(_fake_ttf(), "x")))
    assert r.fallback_cycle == ("x", "x")
    assert "循环" in r.summary_text()


# ── 多码点混合 ───────────────────────────────────────────────

def test_mixed_report_cases_and_sources():
    """混合需求：OK + Case B + Case D 同时出现，报告按分类聚合，
    断点码点可回溯到来源 locator。"""
    cps = frozenset({ord("A"), ord("B"), ord("你")})
    locators = {s: [f"game:{chr(s)}"] for s in cps}
    req = RequiredGlyphSet(cps, locators)
    tmp = TmpAssetInfo("a", character_table=frozenset({ord("A")}),
                       glyph_table=frozenset({ord("A")}))
    r = verify_chain(req, font=_font(_fake_ttf()), tmp=tmp)
    by = r.by_case()
    assert by[OK][0].scalar == ord("A")
    assert by[CHARACTER_MISSING][0].scalar == ord("B")
    assert by[FALLBACK_UNCONFIGURED][0].scalar == ord("你")
    # 来源回溯：断点码点能查到出处
    assert by[CHARACTER_MISSING][0].sources == ("game:B",)
    # 报告 = 汇总行（含 Case A 事实）+ 每缺陷分类一行
    lines = r.summary_text().splitlines()
    assert len(lines) == 3
    assert "CHARACTER_MISSING" in lines[1] and "FALLBACK_UNCONFIGURED" in lines[2]
