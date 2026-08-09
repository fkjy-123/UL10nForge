from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import zlib

import pytest

from hanhua.core.models import TextEntry
from hanhua.core.tooling.bmfont import (
    BmFontValidationError,
    build_corpus,
    validate_fnt,
    write_bmfont_config,
)
from hanhua.core.tooling.il2cpp_dumper import (
    Il2CppLiteral,
    Il2CppOutputError,
    compare_literals,
    load_string_literals,
    write_private_config,
    run_il2cpp_dumper,
)
from hanhua.core.tooling.bmfont import run_bmfont
from hanhua.core.tooling.fingerprint import fingerprint_game
from hanhua.core.tooling.manifest import ToolRegistry
from hanhua.core.tooling.runner import IsolatedToolRunner
from hanhua.core.unity.il2cpp import parse_string_literals


def _png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    pixels = b"".join(b"\0" + b"\0" * (width * 4) for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


def test_il2cpp_private_config_disables_key_pause_without_touching_source(tmp_path):
    source = tmp_path / "source-config.json"
    source.write_text(json.dumps({
        "DumpMethod": True,
        "GenerateDummyDll": True,
        "RequireAnyKey": True,
    }), encoding="utf-8")
    before = source.read_bytes()
    private = tmp_path / "job" / "config.json"

    write_private_config(source, private)

    configured = json.loads(private.read_text(encoding="utf-8"))
    assert configured["RequireAnyKey"] is False
    assert configured["GenerateDummyDll"] is False
    assert configured["GenerateStruct"] is True
    assert configured["DumpMethod"] is True
    assert source.read_bytes() == before


def test_il2cpp_sidecar_schema_and_cross_check_never_expose_write_offsets(tmp_path):
    sidecar = tmp_path / "stringliteral.json"
    sidecar.write_text(json.dumps([
        {"value": "[PICK UP]", "address": "0x1000"},
        {"value": "Hello", "address": "0x1010"},
    ]), encoding="utf-8")

    literals = load_string_literals(sidecar)
    report = compare_literals(["[PICK UP]", "Native only"], literals)

    assert [(item.value, item.address) for item in literals] == [
        ("[PICK UP]", 0x1000), ("Hello", 0x1010)]
    assert report.intersection == 1
    assert report.native_only == 1
    assert report.sidecar_only == 1
    assert not hasattr(report, "file_offset")


@pytest.mark.parametrize("payload", [
    {},
    [{"value": 123, "address": "0x10"}],
    [{"value": "ok", "address": "ten"}],
])
def test_il2cpp_sidecar_rejects_invalid_schema(tmp_path, payload):
    sidecar = tmp_path / "stringliteral.json"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(Il2CppOutputError):
        load_string_literals(sidecar)


@pytest.mark.parametrize("value", ["", "bad\x00value", "bad\x1fvalue"])
def test_il2cpp_sidecar_rejects_empty_or_control_literals(tmp_path, value):
    sidecar = tmp_path / "stringliteral.json"
    sidecar.write_text(json.dumps([
        {"value": value, "address": "0x10"},
    ]), encoding="utf-8")

    with pytest.raises(Il2CppOutputError):
        load_string_literals(sidecar)


def test_il2cpp_dumper_enriches_version_gap_from_tool_log(tmp_path):
    """dumper 退出码 0 但日志报版本不支持时，reason 必须提升为版本缺口
    （#183），上层据此降级而非误判为 JSON 输出损坏。"""
    from hanhua.core.tooling.il2cpp_dumper import _enrich_dumper_failure

    failure_dir = tmp_path / "tool-failures" / "il2cpp_dumper-deadbeef"
    failure_dir.mkdir(parents=True)
    (failure_dir / "stderr.log").write_text(
        "Initializing metadata...\n"
        "System.NotSupportedException: ERROR: Metadata file supplied "
        "is not a supported version[39].\n", encoding="utf-8")
    exc = Il2CppOutputError(
        f"stringliteral.json 不是有效 UTF-8 JSON；日志：{failure_dir}")

    enriched = _enrich_dumper_failure(exc)

    assert "not a supported version[39]" in enriched.args[0]
    assert "不是有效 UTF-8 JSON" in enriched.args[0]
    # 原 reason 前缀保留，版本缺口作为（工具日志：...）附加在其后
    assert enriched.args[0].startswith(
        f"stringliteral.json 不是有效 UTF-8 JSON；日志：{failure_dir}")


def test_il2cpp_dumper_reraises_enriched_version_gap(tmp_path):
    """run_il2cpp_dumper 在 validate 阶段失败但日志含版本缺口时，
    重抛异常必须携带版本缺口信息。"""
    failure_dir = tmp_path / "tool-failures" / "dumper-x"

    class FakeRunner:
        def run(self, spec, inputs, params, **kwargs):
            failure_dir.mkdir(parents=True, exist_ok=True)
            (failure_dir / "stderr.log").write_text(
                "System.NotSupportedException: ERROR: Metadata file supplied "
                "is not a supported version[39].\n", encoding="utf-8")
            raise Il2CppOutputError(
                f"stringliteral.json 不是有效 UTF-8 JSON；日志：{failure_dir}")

    with pytest.raises(Il2CppOutputError) as excinfo:
        run_il2cpp_dumper(
            FakeRunner(), None, tmp_path / "game.dll",
            tmp_path / "global-metadata.dat", tmp_path / "config.json")

    assert "not a supported version[39]" in str(excinfo.value)


def test_il2cpp_dumper_preserves_plain_failure_without_version_gap(tmp_path):
    """无版本缺口的通用失败不提升，保持原 reason 供上层保持 blocked。"""
    from hanhua.core.tooling.il2cpp_dumper import _enrich_dumper_failure

    failure_dir = tmp_path / "tool-failures" / "il2cpp_dumper-other"
    failure_dir.mkdir(parents=True)
    (failure_dir / "stderr.log").write_text(
        "System.IO.IOException: disk full\n", encoding="utf-8")
    exc = Il2CppOutputError(
        f"stringliteral.json 不是有效 UTF-8 JSON；日志：{failure_dir}")

    enriched = _enrich_dumper_failure(exc)

    assert enriched.args[0] == f"stringliteral.json 不是有效 UTF-8 JSON；日志：{failure_dir}"


def test_il2cpp_cross_check_reports_missing_required_anchor():
    report = compare_literals(
        ["[PICK UP]", "Hello"],
        (Il2CppLiteral("Hello", 0x10),),
        required_anchors=("[PICK UP]",),
    )

    assert report.anchors_found == ()
    assert report.anchors_missing == ("[PICK UP]",)


def test_il2cpp_sidecar_rejects_addresses_larger_than_64_bits(tmp_path):
    sidecar = tmp_path / "stringliteral.json"
    sidecar.write_text(json.dumps([{
        "value": "Hello", "address": "0x" + "F" * 5000,
    }]), encoding="utf-8")

    with pytest.raises(Il2CppOutputError):
        load_string_literals(sidecar)


def test_bmfont_corpus_uses_only_quality_passed_translations():
    entries = [
        TextEntry("a", "1", "New Game", "开始游戏", "translated",
                  meta={"quality_passed": True}),
        TextEntry("a", "2", "Failed", "不该进入", "failed"),
        TextEntry("a", "3", "Low", "低置信", "translated",
                  meta={"quality_passed": False}),
        TextEntry("a", "4", "Legacy", "没有证据", "translated"),
        TextEntry("a", "5", "PlayerController", "结构文本", "translated",
                  meta={"quality_passed": True, "role": "structural"}),
        TextEntry("a", "6", "Maybe", "低置信文本", "translated",
                  meta={"quality_passed": True, "role": "display", "confidence": "low"}),
    ]

    corpus = build_corpus(entries)

    assert all(char in corpus for char in "开始游戏")
    assert all(char not in corpus for char in "不该进入低置信没有证据结构文本")
    assert "\uFFFD" in corpus
    assert corpus == "".join(sorted(set(corpus), key=ord))


def test_bmfont_corpus_rejects_unverifiable_plain_strings():
    with pytest.raises(TypeError):
        build_corpus(["开始游戏"])


def test_bmfont_config_and_descriptor_cover_every_required_character(tmp_path):
    font = tmp_path / "font.ttf"
    font.write_bytes(b"fixture-font")
    config = tmp_path / "font.bmfc"
    write_bmfont_config(config, font, width=1024, height=1024)
    assert f"fontFile={font.resolve()}" in config.read_text(encoding="utf-8")

    descriptor = tmp_path / "font.fnt"
    (tmp_path / "font_0.png").write_bytes(_png(1024, 1024))
    descriptor.write_text(
        'info face="fixture" size=32 unicode=1\n'
        'common lineHeight=40 scaleW=1024 scaleH=1024 pages=1 packed=0\n'
        'page id=0 file="font_0.png"\n'
        'chars count=2\n'
        f'char id={ord("中")} x=0 y=0 width=10 height=10 xoffset=0 yoffset=0 xadvance=10 page=0 chnl=15\n'
        f'char id={ord("文")} x=10 y=0 width=10 height=10 xoffset=0 yoffset=0 xadvance=10 page=0 chnl=15\n',
        encoding="utf-8")

    artifact = validate_fnt(descriptor, "中文")

    assert artifact.characters == frozenset({ord("中"), ord("文")})
    assert artifact.pages == (tmp_path / "font_0.png",)


def test_bmfont_descriptor_reports_missing_codepoints(tmp_path):
    descriptor = tmp_path / "font.fnt"
    (tmp_path / "font_0.png").write_bytes(_png(512, 512))
    descriptor.write_text(
        'common lineHeight=40 scaleW=512 scaleH=512 pages=1 packed=0\n'
        'page id=0 file="font_0.png"\nchars count=1\n'
        f'char id={ord("中")} x=0 y=0 width=10 height=10 page=0\n',
        encoding="utf-8")

    with pytest.raises(BmFontValidationError, match=rf"U\+{ord('文'):04X}"):
        validate_fnt(descriptor, "中文")


def test_bmfont_descriptor_must_match_requested_dimensions(tmp_path):
    descriptor = tmp_path / "font.fnt"
    (tmp_path / "font_0.png").write_bytes(_png(512, 512))
    descriptor.write_text(
        'common lineHeight=40 scaleW=512 scaleH=512 pages=1 packed=0\n'
        'page id=0 file="font_0.png"\nchars count=1\n'
        f'char id={ord("中")} x=0 y=0 width=10 height=10 page=0\n',
        encoding="utf-8",
    )

    with pytest.raises(BmFontValidationError, match="请求尺寸"):
        validate_fnt(descriptor, "中", expected_width=1024, expected_height=1024)


def test_bmfont_descriptor_rejects_excessive_total_atlas_pixels(tmp_path):
    descriptor = tmp_path / "font.fnt"
    descriptor.write_text(
        'common lineHeight=40 scaleW=8192 scaleH=8192 pages=2 packed=0\n'
        'page id=0 file="font_0.png"\npage id=1 file="font_1.png"\n'
        'chars count=0\n', encoding="utf-8")

    with pytest.raises(BmFontValidationError, match="总像素"):
        validate_fnt(descriptor, "")


@pytest.mark.parametrize("failure", [
    "not_png", "wrong_dimensions", "wrong_char_count", "duplicate_char",
])
def test_bmfont_descriptor_rejects_untrusted_artifacts(tmp_path, failure):
    descriptor = tmp_path / "font.fnt"
    page = tmp_path / "font_0.png"
    page.write_bytes(b"not a png" if failure == "not_png" else _png(
        256 if failure == "wrong_dimensions" else 512, 512))
    char_lines = [
        f'char id={ord("中")} x=0 y=0 width=10 height=10 page=0',
    ]
    if failure == "duplicate_char":
        char_lines.append(char_lines[0])
    declared = 2 if failure == "wrong_char_count" else len(char_lines)
    descriptor.write_text(
        'common lineHeight=40 scaleW=512 scaleH=512 pages=1 packed=0\n'
        'page id=0 file="font_0.png"\n'
        f'chars count={declared}\n' + "\n".join(char_lines) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(BmFontValidationError):
        validate_fnt(descriptor, "中")


@pytest.mark.skipif(os.environ.get("HANHUA_RUN_REAL_TOOLS") != "1",
                    reason="set HANHUA_RUN_REAL_TOOLS=1 to run bundled CLI gates")
def test_real_il2cpp_dumper_cross_checks_seijundrop_read_only(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    games = Path(os.environ["HANHUA_GAMES_DIR"])
    game = games / "seijunDROP - version 1.21"
    fingerprint = fingerprint_game(game)
    assert fingerprint.game_assembly is not None and fingerprint.metadata is not None
    before = fingerprint.metadata.read_bytes()
    registry = ToolRegistry.load(project_root)
    result, sidecar = run_il2cpp_dumper(
        IsolatedToolRunner(tmp_path / "app-data"), registry.specs["il2cpp_dumper"],
        fingerprint.game_assembly, fingerprint.metadata,
        project_root / "tools" / "Il2CppDumper" / "config.json",
    )
    native = [before[pos:pos + length].decode("utf-8")
              for _, length, pos in parse_string_literals(before)]
    report = compare_literals(native, sidecar, required_anchors=("[PICK UP]",))
    validation_report = json.loads(
        (result.artifact_dir / "validation-report.json").read_text(encoding="utf-8"))

    assert result.cache_hit is False
    assert report.native_total == 5693
    assert report.sidecar_total == 5630
    assert report.intersection == 5630
    assert report.native_only == 63
    assert report.sidecar_only == 0
    assert report.agreement > 0.98
    assert report.anchors_found == ("[PICK UP]",)
    assert report.anchors_missing == ()
    assert validation_report["accepted_records"] == len(sidecar)
    assert validation_report["normalized_unique_records"] == report.sidecar_total
    assert validation_report["source_records"] == (
        validation_report["accepted_records"]
        + sum(validation_report["rejected"].values())
    )
    assert sum(validation_report["rejected"].values()) > 0
    assert any(item.value == "[PICK UP]" for item in sidecar)
    assert fingerprint.metadata.read_bytes() == before


@pytest.mark.skipif(os.environ.get("HANHUA_RUN_REAL_TOOLS") != "1",
                    reason="set HANHUA_RUN_REAL_TOOLS=1 to run bundled CLI gates")
def test_real_bmfont_generates_validated_chinese_atlas(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    registry = ToolRegistry.load(project_root)
    entries = [TextEntry(
        "fixture", "1", "New Game", "开始游戏，继续！", "translated",
        meta={"quality_passed": True})]

    result, artifact = run_bmfont(
        IsolatedToolRunner(tmp_path / "app-data"), registry.specs["bmfont"],
        project_root / "fonts" / "SimplifiedChinese" / "SourceHanSansSC-Regular.otf",
        entries,
        width=1024, height=1024,
    )

    assert result.cache_hit is False
    assert all(ord(char) in artifact.characters for char in "开始游戏继续")
    assert artifact.unavailable == frozenset({0xFFFD})
    assert all(page.is_file() and page.stat().st_size > 0 for page in artifact.pages)
