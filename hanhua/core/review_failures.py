# -*- coding: utf-8 -*-
"""结构化审核失败闭环（Phase B-5，审计 P1-7）。

背景：runner 的 fail_case 沉淀只按机械 quality_reasons 聚合（质量门拒绝），
CRITICAL/MAJOR 语义错译没有结构化写入——错误译文、正确译文、错误类型、
审核理由全部丢失，知识库无法召回「同类语义错误」作为反例。

方案：review_failure_v1 版本化 JSON schema（强类型字段，note 即该 JSON）：
- 收敛与未收敛均记录（converged: bool）——「经验大脑」同时知道什么
  修得好、什么修不动；
- 只有终态 APPROVED 系（二审收敛 PASS / 人工确认）的译文才可写入
  correct_translation；BLOCKED / REVIEW_ERROR 一律留空——错误例与
  正确例分离，杜绝把坏译文当正确例学习；
- error_type: CRITICAL / MAJOR / REVIEW_ERROR（语义错误 vs 审核管线
  错误分开记账）；
- locator（file_id:key_path）+ game 构成幂等 pattern（knowledge.upsert
  同 pattern 重审只 hits+1 刷新 note）；
- 知识库 match_case/search_keyword 解析 note JSON 的 original 字段，
  可按原文召回同类失败作为反例（KnowledgeRetrieval 接入点）。
"""

SCHEMA_VERSION = "review_failure_v1"

#: error_type 取值
ERROR_CRITICAL = "CRITICAL"
ERROR_MAJOR = "MAJOR"
ERROR_REVIEW = "REVIEW_ERROR"

#: schema 全部字段（强类型留档，缺省字段一律空串）
_FIELDS = (
    "schema", "game", "model", "error_type",
    "original", "wrong_translation", "correct_translation",
    "review_reason", "suggestion",
    "converged", "final_outcome", "locator",
)


def build_review_failure(*, game: str, model: str, error_type: str,
                         original: str, wrong_translation: str,
                         review_reason: str, suggestion: str,
                         converged: bool, final_outcome: str,
                         locator: str,
                         correct_translation: str = "") -> dict:
    """构建 review_failure_v1 结构化失败记录（可 JSON 序列化）。

    correct_translation 只在调用方确认终态 APPROVED 系时传入；其余
    终态（BLOCKED/NEEDS_REVISION/REVIEW_ERROR/人工复核中）留空。
    """
    return {
        "schema": SCHEMA_VERSION,
        "game": game or "",
        "model": model or "",
        "error_type": error_type,
        "original": original or "",
        "wrong_translation": wrong_translation or "",
        "correct_translation": correct_translation or "",
        "review_reason": review_reason or "",
        "suggestion": suggestion or "",
        "converged": bool(converged),
        "final_outcome": final_outcome or "",
        "locator": locator or "",
    }


def failure_pattern(failure: dict) -> str:
    """幂等 pattern：game:locator——同条目重审命中同一行（hits+1），
    跨游戏同名 locator 不串（知识库为全局库）。"""
    game = str(failure.get("game") or "")
    locator = str(failure.get("locator") or "")
    if not locator:
        return ""
    return f"{game}:{locator}" if game else locator
