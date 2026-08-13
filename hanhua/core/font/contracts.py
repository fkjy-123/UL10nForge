# -*- coding: utf-8 -*-
"""字体兼容闭环强类型契约（Phase 1，审计 §7 目标架构）。

- reason code 全集（§9 Phase 1「必须实现的 reason code」10 项）——
  单一来源，coverable/inventory 均从此导入；
- evidence level：静态资产契约 / 运行时 attestation / 未验证——任何
  「已证明」结论必须带证据等级，禁止把静态命中混称运行时证明
  （审计 §1：runtime_verified 错误口径）。
"""
from __future__ import annotations

from dataclasses import dataclass

# ── reason code（§9 Phase 1 必须实现清单） ────────────────────────
MISSING_CODEPOINT = "MISSING_CODEPOINT"
DYNAMIC_FONT_REQUIRES_RUNTIME = "DYNAMIC_FONT_REQUIRES_RUNTIME"
TMP_LAYOUT_MISMATCH = "TMP_LAYOUT_MISMATCH"
ATLAS_REFERENCE_UNRESOLVED = "ATLAS_REFERENCE_UNRESOLVED"
MATERIAL_REFERENCE_UNRESOLVED = "MATERIAL_REFERENCE_UNRESOLVED"
UNKNOWN_UNITY_VERSION = "UNKNOWN_UNITY_VERSION"
UNSUPPORTED_RENDERER = "UNSUPPORTED_RENDERER"
BITMAP_FONT_INJECTION_REQUIRED = "BITMAP_FONT_INJECTION_REQUIRED"
RUNTIME_PROVIDER_UNAVAILABLE = "RUNTIME_PROVIDER_UNAVAILABLE"
STALE_RUNTIME_ATTESTATION = "STALE_RUNTIME_ATTESTATION"

#: 非失败类 reason（不阻断发布）
NOT_A_CJK_TARGET = "NOT_A_CJK_TARGET"

REASON_CODES: frozenset[str] = frozenset({
    MISSING_CODEPOINT, DYNAMIC_FONT_REQUIRES_RUNTIME, TMP_LAYOUT_MISMATCH,
    ATLAS_REFERENCE_UNRESOLVED, MATERIAL_REFERENCE_UNRESOLVED,
    UNKNOWN_UNITY_VERSION, UNSUPPORTED_RENDERER,
    BITMAP_FONT_INJECTION_REQUIRED, RUNTIME_PROVIDER_UNAVAILABLE,
    STALE_RUNTIME_ATTESTATION, NOT_A_CJK_TARGET,
})

# ── evidence level（审计 §7.4：静态覆盖与运行时证明的职责） ──────
EVIDENCE_STATIC = "static_contract"        # 静态资产契约（字形表/图集字节链）
EVIDENCE_RUNTIME_ATTESTED = "runtime_attestation"  # 运行时逐字符证明
EVIDENCE_UNVERIFIED = "unverified"         # 已部署未验证（§8.2 PENDING）


@dataclass(frozen=True)
class CoverageEvidence:
    """一条覆盖证明：等级 + 来源描述（可审计溯源）。"""

    level: str = EVIDENCE_UNVERIFIED
    source: str = ""
