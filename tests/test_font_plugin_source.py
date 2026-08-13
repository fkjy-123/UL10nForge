from pathlib import Path


def _plugin_source() -> str:
    return (Path(__file__).resolve().parents[1]
            / "font_plugin" / "Hanhua.FontFallback"
            / "HanhuaFontPlugin.cs").read_text(encoding="utf-8")


def test_runtime_uses_exact_then_normalized_then_unique_template_mapping():
    source = _plugin_source()
    apply_method = source[
        source.index("private int ApplyExactTranslation"):
        source.index("private static bool IsTargetUnavailable")
    ]

    assert apply_method.index("TryGetExactTranslation") < apply_method.index(
        "TryGetNormalizedTranslation")
    assert apply_method.index("TryGetNormalizedTranslation") < (
        apply_method.index("TryGetUniqueTemplateTranslation"))
    assert "NormalizeRuntimeText" in source
    assert "Trim()" in source
    assert 'Replace("\\r\\n", "\\n")' in source
    assert "matchingTemplates != 1" in source
    assert "sourceFragments" in source and "targetFragments" in source
    assert "totalExactTranslationApplications" in source
    assert "totalNormalizedTranslationApplications" in source
    assert "totalTemplateTranslationApplications" in source
    assert '\\"exact_translations\\":' in source
    assert '\\"normalized_translations\\":' in source
    assert '\\"template_translations\\":' in source
    assert '\\"translation_targets\\":' in source
    assert "translationApplicationStates" in apply_method


def test_phase3_protocol_v5_per_scalar_verification_mechanisms():
    source = _plugin_source()

    # 协议 v5：逐 scalar 证明 + 会话 + 消费者统计
    assert "private const int HealthProtocolVersion = 5;" in source
    assert 'PluginVersion = "1.4.0"' in source
    assert 'sessionNonce = Guid.NewGuid().ToString("N")' in source
    assert "LoadRequiredGlyphs" in source
    assert "required-glyphs.json" in source
    assert "ReadJsonUintArray" in source
    assert "VerifyRequiredGlyphs" in source
    assert "legacyCovered" in source and "tmpCovered" in source
    assert "missingCodepoints" in source
    assert "verifiedMissingTotal" in source
    assert "CollectConsumerEvidence" in source
    assert "consumersDiscovered" in source and "consumersChinese" in source
    assert "NoteConsumerFailure" in source
    assert "MaxDetailRecords" in source
    assert '\\"snapshot_hash\\":' in source
    assert '\\"glyph_verification\\":' in source
    assert '\\"consumers\\":' in source
    assert '\\"failures\\":' in source
    assert '\\"session_nonce\\":' in source
    assert '\\"last_seen\\":' in source
    assert '\\"scenes\\":' in source
    # 扫描异常必须写入 error（不能假证明）
    assert "glyphVerificationError" in source
    assert 'glyphVerificationError = ""' in source
    # CLR 2.0 兼容的 unix 时间（不用 DateTimeOffset.ToUnixTimeSeconds）
    assert "new DateTime(1970, 1, 1" in source
    # 诚实报告：非 BMP 不能逐字添加 → 不假证明
    assert "char.ConvertFromUtf32" in source


def test_phase3_apply_fonts_runs_verification_before_manifest():
    source = _plugin_source()
    apply_fonts = source[
        source.index("private void ApplyFonts(string reason)"):
        source.index("private static bool RequiresDeferredTmpGlyphValidation")
    ]
    assert apply_fonts.index("VerifyRequiredGlyphs()") < apply_fonts.index(
        'WriteHealthManifest(reason == "periodic")')
    assert apply_fonts.index("CollectConsumerEvidence()") < apply_fonts.index(
        'WriteHealthManifest(reason == "periodic")')


def test_phase3_scan_exception_fails_attestation():
    source = _plugin_source()
    safe_apply = source[
        source.index("private void SafeApplyFonts(string reason)"):
        source.index("private void ApplyFonts(string reason)")
    ]
    assert safe_apply.index('glyphVerificationError = ""') < (
        safe_apply.index("ApplyFonts(reason)"))
    assert "font-scan-failed: " in safe_apply


def test_phase3_failure_details_are_capped_at_256():
    source = _plugin_source()
    assert source.count("MaxDetailRecords") >= 3
    assert "consumerFailures.Count >= MaxDetailRecords" in source
    assert "index < MaxDetailRecords" in source
