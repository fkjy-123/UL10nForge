# -*- coding: utf-8 -*-
"""位图字体 provider 测试（Phase 5，计划 §Phase 5）。

覆盖：registry 发现（evidence/NGUI/exclude）、audit 缺字清单（含坏
契约保守全缺）、inject 编排（staging 原样替换 + 重开验证）、
required_corpus 非 BMP 单 scalar、provider 包导出。
"""
from __future__ import annotations

from pathlib import Path
import struct
import zlib

import pytest

from hanhua.core.font.glyph_set import build_required_glyph_set
from hanhua.core.font.providers import (BitmapAudit, BitmapInjectionResult,
                                        BitmapProvider, audit_bitmap_font,
                                        inject_bitmap_font,
                                        resolve_bitmap_providers)
from hanhua.core.font.providers.bmfont import required_corpus
from hanhua.core.models import TextEntry
from hanhua.core.tooling.fingerprint import GameFingerprint


def _png(width: int = 8, height: int = 8) -> bytes:
    """最小合法 PNG（RGBA8，filter 0，像素全零——validate_fnt 只查
    尺寸/CRC/像素长度，不检查内容）。"""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + b"\x00\x00\x00\x00" * width
    raw = row * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _fnt(path: Path, characters: str, *, scale: tuple[int, int] = (8, 8),
         page_file: str | None = None) -> Path:
    """最小合法 .fnt：1 page + 每字符一条 char 记录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = scale
    lines = [
        f"common lineHeight={height} base=0 scaleW={width} scaleH={height} "
        f"pages=1 packed=0",
        f"page id=0 file={page_file or (path.stem + '.png')}",
        f"chars count={len(characters)}",
    ]
    for index, ch in enumerate(characters):
        x, y = (index * 2) % max(width - 1, 1), 0
        lines.append(
            f"char id={ord(ch)} x={x} y={y} width=1 height=1 xoffset=0 "
            f"yoffset=0 xadvance=2 page=0 chnl=15")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (path.parent / (page_file or (path.stem + ".png"))).write_bytes(
        _png(width, height))
    return path


def _required(*texts: str):
    entries = [TextEntry("f", f"k{i}", t, translation=t, status="translated")
               for i, t in enumerate(texts)]
    return build_required_glyph_set(entries)


def _fingerprint(*, evidence=("bitmap_font",), runtime="mono"):
    return type("FP", (), {"evidence": evidence, "runtime": runtime})()


# ── registry 发现 ──────────────────────────────────────────────

def test_resolve_finds_none_without_bitmap_evidence(tmp_path):
    fnt = tmp_path / "font.fnt"
    _fnt(fnt, "AB")
    providers = resolve_bitmap_providers(
        tmp_path, _fingerprint(evidence=("tmp",)))
    assert providers == ()


def test_resolve_finds_fnt_and_kind_bmfont(tmp_path):
    fnt = tmp_path / "Fonts" / "menu.fnt"
    _fnt(fnt, "AB")
    providers = resolve_bitmap_providers(tmp_path, _fingerprint())
    assert len(providers) == 1
    provider = providers[0]
    assert provider.provider_id == "bmfont"
    assert provider.kind == "bmfont"
    assert provider.fnt == fnt.resolve()
    assert "menu.fnt" in provider.reason


def test_resolve_kind_ngui_when_ngui_evidence(tmp_path):
    fnt = tmp_path / "ui.fnt"
    _fnt(fnt, "AB")
    providers = resolve_bitmap_providers(
        tmp_path, _fingerprint(evidence=("bitmap_font", "ngui")))
    assert providers[0].provider_id == "ngui_bmfont"
    assert providers[0].kind == "ngui"


def test_resolve_excludes_previous_output_roots(tmp_path):
    _fnt(tmp_path / "font.fnt", "AB")
    _fnt(tmp_path / "out" / "font.fnt", "AB")
    providers = resolve_bitmap_providers(
        tmp_path, _fingerprint(),
        exclude_roots=(tmp_path / "out",))
    assert len(providers) == 1
    assert "out" not in str(providers[0].fnt)


# ── audit 缺字清单 ─────────────────────────────────────────────

def test_audit_covered_fnt_has_no_missing(tmp_path):
    fnt = _fnt(tmp_path / "font.fnt", "继续游戏，")
    audit = audit_bitmap_font(fnt, _required("继续游戏，"))
    assert audit.valid is True
    assert audit.missing == frozenset()


def test_audit_missing_codepoints_reported(tmp_path):
    fnt = _fnt(tmp_path / "font.fnt", "继续游戏")
    audit = audit_bitmap_font(fnt, _required("继续游戏！"))
    assert audit.valid is True
    assert audit.missing == frozenset({ord("！")})
    assert "缺少字符" in audit.detail


def test_audit_invalid_fnt_is_conservatively_all_missing(tmp_path):
    fnt = tmp_path / "broken.fnt"
    fnt.write_text("not a bmfont\n", encoding="utf-8")
    required = _required("设置")
    audit = audit_bitmap_font(fnt, required)
    assert audit.valid is False
    assert audit.missing == frozenset(required.scalars)
    assert "无效" in audit.detail or "缺失" in audit.detail


# ── required_corpus 非 BMP ─────────────────────────────────────

def test_required_corpus_keeps_non_bmp_single_scalar():
    required = _required("继续😀")  # U+1F600 单 scalar
    corpus = required_corpus(required)
    assert 0x1F600 in {ord(ch) for ch in corpus}
    assert 0xD83D not in {ord(ch) for ch in corpus}  # 无 surrogate
    assert all(0xD800 <= ord(ch) > 0xDFFF for ch in corpus) is not True


# ── inject 编排（fake run_bmfont 产物） ─────────────────────────

def test_inject_writes_staging_same_relative_path_and_validates(
        tmp_path, monkeypatch):
    from hanhua.core.font.providers import bmfont as bmfont_module
    game = tmp_path / "game"
    (game / "Fonts").mkdir(parents=True)
    original_fnt = _fnt(game / "Fonts" / "menu.fnt", "AB")
    required = _required("设置")
    staging_fnt = tmp_path / "staging" / "Fonts" / "menu.fnt"
    generated_png = tmp_path / "gen" / "menu_0.png"
    generated_png.parent.mkdir(parents=True)
    generated_png.write_bytes(_png(16, 16))

    def fake_run(runner, spec, font_file, entries, *, width, height):
        from hanhua.core.tooling.bmfont import BmFontArtifact
        from types import SimpleNamespace
        generated_fnt = _fnt(tmp_path / "gen" / "font.fnt", "设置",
                             scale=(16, 16), page_file="font_0.png")
        (tmp_path / "gen" / "font_0.png").write_bytes(_png(16, 16))
        artifact = BmFontArtifact(
            generated_fnt, (tmp_path / "gen" / "font_0.png",),
            frozenset(ord(c) for c in "设置"), 16, 16,
            frozenset({0xFFFD}))
        return SimpleNamespace(succeeded=True, status="ok"), artifact

    monkeypatch.setattr(bmfont_module, "run_bmfont", fake_run)
    provider = BitmapProvider("bmfont", "bmfont", original_fnt, "fixture")
    artifact = inject_bitmap_font(
        provider, staging_fnt, required,
        runner=None, spec=None, font_file=tmp_path / "font.ttf",
        width=16, height=16)

    assert artifact.descriptor == staging_fnt.resolve()
    assert all(ord(c) in artifact.characters for c in "设置")
    assert (staging_fnt.parent / "font_0.png").is_file()
    # 注入失败语义：run_bmfont 失败 → 抛异常（调用方记 warning）
    def failing_run(runner, spec, font_file, entries, *, width, height):
        from types import SimpleNamespace
        return SimpleNamespace(succeeded=False, status="failed",
                               stderr="boom"), None

    monkeypatch.setattr(bmfont_module, "run_bmfont", failing_run)
    with pytest.raises(Exception, match="BMFont 工具失败"):
        inject_bitmap_font(
            provider, staging_fnt, required,
            runner=None, spec=None, font_file=tmp_path / "font.ttf",
            width=16, height=16)


# ── 聚合结果与导出 ─────────────────────────────────────────────

def test_injection_result_blocks_until_all_injected():
    result = BitmapInjectionResult(
        providers=[BitmapProvider("bmfont", "bmfont", Path("a.fnt"))],
        pending=1)
    assert result.blocks_publish() is True
    result.pending = 0
    assert result.blocks_publish() is False
    # 审计已覆盖（无需注入）同样不阻断
    assert BitmapInjectionResult(
        providers=[BitmapProvider("bmfont", "bmfont", Path("a.fnt"))],
        audited=1, pending=0).blocks_publish() is False


def test_provider_exports():
    from hanhua.core.font import providers
    assert providers.BitmapAudit is BitmapAudit
    assert providers.audit_bitmap_font is audit_bitmap_font
    assert providers.inject_bitmap_font is inject_bitmap_font
    assert providers.resolve_bitmap_providers is resolve_bitmap_providers
