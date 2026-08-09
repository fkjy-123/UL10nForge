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
