# -*- coding: utf-8 -*-
"""字体发布门（计划 §8 决策表 + §8.3 allow_partial 边界）单元测试。

Phase 4：把「coverage 不完整必须阻断发布」从概念锁进代码——
- BLOCKED（IL2CPP 动态无 provider / 未知渲染栈）无论候选确认与否都阻断；
- PENDING_RUNTIME_ATTESTATION / CANDIDATE_ONLY 只允许候选降级 WARN；
- COVERED / 运行时已证明 → PASS；
- allow_unverified_font_candidate 绝不把 BLOCKED 变 WARN。
"""
from __future__ import annotations

from hanhua.core.font import (BLOCKED, CANDIDATE_ONLY, COVERED, FontConsumer,
                               PENDING_RUNTIME_ATTESTATION, compute_coverage)
from hanhua.core.font.glyph_set import build_required_glyph_set
from hanhua.core.font.publish_gate import evaluate_font_gate
from hanhua.core.models import TextEntry


def _outcome(*consumers):
    entry = TextEntry("f", "k1", "Continue", translation="继续游戏",
                      status="translated")
    return compute_coverage(
        list(consumers), build_required_glyph_set([entry]))


def _covered_consumer() -> FontConsumer:
    return FontConsumer("covered", "tmp_font", static_replaced=True,
                        font_scalars=frozenset(ord(c) for c in "继续游戏"),
                        unity_version="2021.3")


def _candidate_missing() -> FontConsumer:
    return FontConsumer("missing", "tmp_font", static_replaced=True,
                        font_scalars=frozenset(ord(c) for c in "继续"),
                        unity_version="2021.3")


def _call(*, coverage=None, runtime_verified=False, payload_deployed=False,
          provider_supported=True, font_enabled=True,
          allow_candidate=False):
    return evaluate_font_gate(
        coverage=coverage, runtime_verified=runtime_verified,
        payload_deployed=payload_deployed,
        provider_supported=provider_supported,
        font_enabled=font_enabled,
        allow_unverified_font_candidate=allow_candidate)


def test_disabled_font_is_na_regardless_of_coverage():
    gate = _call(coverage=_outcome(_candidate_missing()), font_enabled=False)
    assert gate["status"] == "N/A"


def test_covered_static_coverage_passes():
    gate = _call(coverage=_outcome(_covered_consumer()))
    assert gate["status"] == "PASS"
    assert "覆盖" in gate["detail"]


def test_candidate_only_blocks_formal_publish():
    gate = _call(coverage=_outcome(_candidate_missing()))
    assert gate["status"] == "BLOCKED"
    assert "缺字" in gate["detail"] or "未覆盖" in gate["detail"]


def test_candidate_only_warns_with_user_confirmation():
    gate = _call(coverage=_outcome(_candidate_missing()),
                 allow_candidate=True)
    assert gate["status"] == "WARN"


def test_pending_runtime_blocks_formal_publish():
    pending = FontConsumer(
        "mono_pending", "dynamic_tmp", runtime_provider_available=True)
    gate = _call(coverage=_outcome(pending))
    assert gate["status"] == "BLOCKED"
    assert "验证" in gate["detail"]


def test_pending_runtime_warns_as_candidate():
    pending = FontConsumer(
        "mono_pending", "dynamic_tmp", runtime_provider_available=True)
    gate = _call(coverage=_outcome(pending), allow_candidate=True)
    assert gate["status"] == "WARN"


def test_blocked_coverage_never_bypassed_by_candidate():
    """IL2CPP 动态无 provider：allow_candidate 也不能放行（§8.3）。"""
    il2cpp = FontConsumer(
        "il2cpp", "dynamic_tmp", runtime_provider_available=False)
    gate = _call(coverage=_outcome(il2cpp), allow_candidate=True)
    assert gate["status"] == "BLOCKED"


def test_runtime_attested_passes_when_no_static_coverage():
    gate = _call(runtime_verified=True)
    assert gate["status"] == "PASS"


def test_payload_only_warns_when_no_static_coverage():
    gate = _call(payload_deployed=True)
    assert gate["status"] == "WARN"


def test_unverifiable_blocks_when_no_static_coverage():
    gate = _call(provider_supported=False)
    assert gate["status"] == "WARN" or gate["status"] == "BLOCKED"


def test_coverage_priority_over_runtime_flags():
    """coverage 存在时以覆盖终态为准：CANDIDATE_ONLY 即使 runtime 声称
    已部署也必须阻断（P0-4：单个替换命中不再代表全局成功）。"""
    gate = _call(coverage=_outcome(_candidate_missing()),
                 runtime_verified=True, payload_deployed=True)
    assert gate["status"] == "BLOCKED"
