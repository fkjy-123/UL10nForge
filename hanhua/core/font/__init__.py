# -*- coding: utf-8 -*-
"""字体兼容闭环（Phase 0：方框字反馈环）。

Phase 0 锁定语义与可复现性，Phase 1 扩 RequiredGlyphSet 来源定位与
FontConsumerInventory，Phase 2 修正静态替换验证，Phase 3 运行时
attestation，Phase 4 统一发布门。
"""
from hanhua.core.font.coverable import (  # noqa: F401
    ATLAS_REFERENCE_UNRESOLVED, BLOCKED, CANDIDATE_ONLY, COVERED,
    DYNAMIC_FONT_REQUIRES_RUNTIME, MISSING_CODEPOINT, NOT_A_CJK_TARGET,
    PENDING_RUNTIME_ATTESTATION, RUNTIME_PROVIDER_UNAVAILABLE,
    STALE_RUNTIME_ATTESTATION, TMP_LAYOUT_MISMATCH, UNSUPPORTED_RENDERER,
    ConsumerCoverage, FontConsumer, FontCoverageOutcome, compute_coverage,
    coverage_blocks_publish,
)
from hanhua.core.font.diagnostics import (  # noqa: F401
    ATLAS_MISSING, DATA_CORRUPTION, MISSING_GLYPH, OK, SPRITE_ONLY,
    UNCOVERED_CONSUMER, Diagnosis, FontSymptom, classify_data,
    diagnose_render,
)
from hanhua.core.font.glyph_set import (  # noqa: F401
    RequiredGlyphSet, build_required_glyph_set, strip_rich_text,
    text_codepoints,
)
from hanhua.core.font.inventory import (  # noqa: F401
    ContainerEvidence, FontConsumerInventory, FontObjectEvidence,
    inventory_font_consumers,
)
from hanhua.core.font.contracts import (  # noqa: F401
    ATLAS_REFERENCE_UNRESOLVED, BITMAP_FONT_INJECTION_REQUIRED,
    DYNAMIC_FONT_REQUIRES_RUNTIME, EVIDENCE_RUNTIME_ATTESTED,
    EVIDENCE_STATIC, EVIDENCE_UNVERIFIED, MATERIAL_REFERENCE_UNRESOLVED,
    MISSING_CODEPOINT, NOT_A_CJK_TARGET, RUNTIME_PROVIDER_UNAVAILABLE,
    STALE_RUNTIME_ATTESTATION, TMP_LAYOUT_MISMATCH, UNKNOWN_UNITY_VERSION,
    UNSUPPORTED_RENDERER, CoverageEvidence, REASON_CODES,
)
