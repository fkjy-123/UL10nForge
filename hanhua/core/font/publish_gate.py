# -*- coding: utf-8 -*-
"""字体发布门：把覆盖终态决策表（计划 §8.2/§8.3）落成单一 gate 评估。

Phase 4：project._evaluate_writeback_gates 的 runtime 门从「installed /
payload_deployed 启发式」升级为 coverage 终态决策——任何 CANDIDATE_ONLY /
BLOCKED 消费者阻断正式发布；allow_unverified_font_candidate（现有
allow_partial 的用户明确确认）只允许 PENDING_RUNTIME_ATTESTATION /
CANDIDATE_ONLY 降级为候选 WARN，绝不绕过 BLOCKED（IL2CPP 无 provider /
未知渲染栈）。COVERED 的静态覆盖或运行时 attestation 证明才允许正式发布。
"""
from __future__ import annotations

from hanhua.core.font.coverable import (CANDIDATE_ONLY, COVERED,
                                        FontCoverageOutcome,
                                        PENDING_RUNTIME_ATTESTATION)


def evaluate_font_gate(
        *,
        coverage: FontCoverageOutcome | None,
        runtime_verified: bool,
        payload_deployed: bool,
        provider_supported: bool,
        font_enabled: bool,
        allow_unverified_font_candidate: bool,
) -> dict:
    """评估字体发布门，返回 {"status", "detail"}。

    状态语义（与 _evaluate_writeback_gates 的四态闸门一致）：
      N/A     用户未启用中文字体，字体门不参与
      PASS    静态覆盖完整或运行时 attestation 已证明
      WARN    候选副本（已知缺字/未验证，用户已确认）
      BLOCKED 阻断发布副本（缺字未确认 / IL2CPP 无 provider / 未知栈）

    coverage 优先：静态覆盖计算存在时以其终态为准，runtime/payload 标志
    不再能单独把 CANDIDATE_ONLY/BLOCKED 翻成 PASS（P0-4 缺陷锁：
    「至少一个对象被替换」不代表全局成功）。
    """
    if not font_enabled:
        return {"status": "N/A", "detail": "用户未启用中文字体"}
    if coverage is not None:
        state = coverage.overall
        if state == COVERED:
            return {"status": "PASS",
                    "detail": coverage.summary_text()}
        if state == PENDING_RUNTIME_ATTESTATION:
            detail = "等待启动游戏完成字体验证（runtime 已部署未证明）"
            status = "WARN" if allow_unverified_font_candidate else "BLOCKED"
            return {"status": status, "detail": detail}
        if state == CANDIDATE_ONLY:
            detail = (coverage.summary_text()
                      + "——存在缺字/未覆盖消费者，默认阻断发布")
            status = "WARN" if allow_unverified_font_candidate else "BLOCKED"
            return {"status": status, "detail": detail}
        # BLOCKED（IL2CPP 动态无 provider / 未知渲染栈）：
        # §8.3 候选确认不可绕过——必须显式 provider 修复后才可发布
        return {"status": "BLOCKED",
                "detail": coverage.summary_text()
                + "——当前无法自动保证动态字体（候选确认不可绕过）"}
    # 无静态覆盖计算（无消费者记录/静态未跑）：退回部署启发式
    if runtime_verified:
        return {"status": "PASS", "detail": "字体运行时覆盖已证明"}
    if payload_deployed:
        return {"status": "WARN",
                "detail": "字体运行时回退层已部署（尚未运行验证）"}
    if not provider_supported:
        return {"status": "WARN", "detail": "无可用字体 provider（unsupported）"}
    return {"status": "BLOCKED", "detail": "字体运行时回退层不可验证"}
