"""审核显式终态与发布门（审计 Phase A：ReviewOutcome → PublishGate）。

历史问题（2026-08-13 架构审计 §5 P0-1/P0-6/P0-7）：
`quality_passed`、`review_level`、`review_blocked`、`need_*` 多个松散
布尔字段共同承担审核状态机，机械质量门通过 + 语义审核判 MAJOR/CRITICAL
的译文仍可保持 publishable 进入写回；blocked 只是附加布尔字段，没有
恢复安全状态。本模块把「发布资格」收拢到单一显式终态
（`meta["review_outcome"]`）：只有 APPROVED / APPROVED_MINOR 可发布，
其余终态一律不可写回，同时原子地恢复条目到安全状态。

终态（§9 状态机建议）：
- PENDING           未审核（缺省；保持机械质量门作为第一道防线）
- APPROVED          PASS，可发布
- APPROVED_MINOR    MINOR，可发布
- NEEDS_REVISION    MAJOR/CRITICAL 且未收敛（需人工修正），不可发布
- BLOCKED           重译/再审未收敛或重译失败，保留坏译文供人工复核，不可发布
- REVIEW_ERROR      审核传输/解析/服务错误，不可发布、不得转 PASS
- CANCELLED         审核被取消，不可发布
"""
from __future__ import annotations

from .models import STATUS_BLOCKED

# ── 显式终态 ──────────────────────────────────────────────────────
PENDING = "PENDING"
APPROVED = "APPROVED"
APPROVED_MINOR = "APPROVED_MINOR"
NEEDS_REVISION = "NEEDS_REVISION"
BLOCKED = "BLOCKED"
REVIEW_ERROR = "REVIEW_ERROR"
CANCELLED = "CANCELLED"

# 只有 approved 系可进入写回（§9：仅 APPROVED / APPROVED_MINOR 可 PUBLISHED）
PUBLISHABLE = frozenset({APPROVED, APPROVED_MINOR})

# 审核错误类别（P0-6：错误必须显式化，不得伪装成判定）
TRANSPORT_ERROR = "TRANSPORT_ERROR"
PARSE_ERROR = "PARSE_ERROR"
UNAVAILABLE = "UNAVAILABLE"
ERROR_KINDS = frozenset({TRANSPORT_ERROR, PARSE_ERROR, UNAVAILABLE})

# 旧字段兼容：显式坏状态（审核落盘前遗留 meta）→ 一律拒绝发布
_NEGATIVE_LEGACY_FLAGS = (
    "review_blocked", "review_error", "need_revision", "need_retranslate",
)


def review_publishable(meta: dict) -> bool:
    """发布资格：显式终态 approved 系；否则旧字段出现坏状态即拒绝。

    缺省（无任何审核 meta）返回 True——保持机械质量门作为第一道防线，
    未启用审核/审核不可用时不阻断既有流程。一旦出现审核证据，坏证据
    即拒绝发布（fail-closed）。
    """
    outcome = meta.get("review_outcome")
    if outcome is not None:
        return str(outcome) in PUBLISHABLE
    for flag in _NEGATIVE_LEGACY_FLAGS:
        if meta.get(flag) is True:
            return False
    if str(meta.get("review_level") or "") in ("MAJOR", "CRITICAL"):
        return False
    return True


def _safe_meta(entry) -> dict:
    """确保 entry.meta 是可写 dict（reviewer 外链 TextEntry 有时共享 dict）。"""
    if not isinstance(entry.meta, dict):
        entry.meta = {}
    else:
        entry.meta = dict(entry.meta)
    return entry.meta


def apply_outcome(entry, state: str, *, level: str = "", reason: str = "",
                  suggestion: str = "", rejected_candidate: str = "",
                  error_kind: str = "", rounds: int = 0,
                  clear_translation: bool = False) -> None:
    """把审核终态原子写入条目（meta + status + quality_passed）。

    - APPROVED / APPROVED_MINOR：quality_passed=True（可发布）。
    - NEEDS_REVISION：quality_passed=False（未收敛不可发布）。
    - BLOCKED：status=blocked、quality_passed=False，发布译文清空
      （clear_translation=True 时）或安全保留原文；坏译文单独存入
      `meta["rejected_candidate"]` 供人工复核，不再位于发布槽位。
    - REVIEW_ERROR / CANCELLED：quality_passed=False，记录错误类别。

    无论哪个终态都保留 review_level/reason/suggestion 作为审计证据。
    """
    meta = _safe_meta(entry)
    meta["review_outcome"] = state
    if level:
        meta["review_level"] = level
    if reason:
        meta["review_reason"] = reason[:400]
    if suggestion:
        meta["review_suggestion"] = suggestion[:200]
    if error_kind:
        meta["review_error_kind"] = error_kind
    if rounds:
        meta["review_blocked_rounds"] = rounds
    if rejected_candidate:
        meta["rejected_candidate"] = rejected_candidate

    if state == BLOCKED:
        meta["review_blocked"] = True
        meta["quality_passed"] = False
        entry.status = STATUS_BLOCKED
        if clear_translation:
            entry.translation = ""
    elif state == REVIEW_ERROR:
        meta["review_error"] = True
        meta["quality_passed"] = False
    elif state == NEEDS_REVISION:
        # 未收敛/需人工：仍保留译文供审校，但不可发布
        meta["quality_passed"] = False
    elif state == CANCELLED:
        meta["quality_passed"] = False
    elif state in PUBLISHABLE:
        meta["quality_passed"] = True
