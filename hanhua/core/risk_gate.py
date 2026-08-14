"""风险分流器（任务一 T1-3）：决定哪些译文需要 4B 深审。

背景：Qwen3.5-4B 深审是成本大头（关闭思考后约 2.4s/条），全量审
不可行——实施计划 §4.2 硬约束「正常译文 4B 调用率 <15%」。本模块按
决策表筛可疑条目，任一信号命中即送审，其余直放：

| 信号 | 通道 | 判定 |
|---|---|---|
| quality_failed  | mandatory | 质量门最终失败（重试链已耗尽，status=failed）→ 强制送审 |
| glossary_conflict | mandatory | 术语词对命中原文但译文未使用标准译法 → 强制送审 |
| polysemy        | discretionary | 多义词（Resume/Save/Charge…）命中且语境库无记录 → 送审 |
| long_text       | discretionary | 原文 token 数 > 60 → 送审 |
| negation_conditional | discretionary | 含 not/no/never/if/unless/only 等词 → 送审 |
| character_text  | discretionary | dialogue 域或含专名（首字母大写词）→ 送审 |
| none            | — | 其余 → 直放 |

双通道（审计 §5 P0-5）：mandatory（机械失败、硬冲突）不受抽样配额，
超出预算时绝不截断放行；discretionary（概率风险）才受 5/15/30% 预算，
截断条目归入 `deferred_due_to_budget`（人工队列），不再命名为 passed。

纯函数 + 显式依赖（glossary 词对列表由调用方传入），无 IO、
无状态，便于单测覆盖决策表全分支。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import TextEntry

# 多义词种子（实施计划 T2-4 首批 10 词 + 冒烟实证的陷阱词）：
# 命中即送审（语境库建成前保守全审，见 _POLYSEMY_HINT 注释）
_POLYSEMY_WORDS = frozenset({
    "resume", "save", "load", "charge", "quit", "options",
    "attack", "guard", "run", "skill", "start", "press",
})

# 否定/条件/比较词（实施计划 §4.2）：语义反转与条件逻辑最易错译
_NEGATION_WORDS = re.compile(
    r"\b(not|no|never|none|nothing|without|unless|except|instead|"
    r"only|more|most|least|than|if|but|yet|although|though|"
    r"either|neither|both|none|all)\b", re.IGNORECASE)

# 首字母大写词（专名启发式：人名/地名/品牌，需送审确认不意译）
_PROPRIAL_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")

# 长句阈值：原文 token > 60 送审（1.8B 对长句易丢信息）
_LONG_TOKEN_THRESHOLD = 60

# 语境证据直填门禁（与 context_library 同源：低于此只参考不裁决）
_DIRECT_FILL_MIN_CONFIDENCE = 0.3

# 决策表信号优先级（影响送审批内排序：高优先级先审）
_SIGNAL_PRIORITY = {
    "quality_failed": 6,
    "glossary_conflict": 5,
    "polysemy": 4,
    "context_conflict": 4,   # 语境证据反对候选译文（歧义未决）
    "error_pattern_hit": 3,  # 历史错误模式命中（#43 阶段 D）
    "character_text": 3,
    "negation_conditional": 2,
    "long_text": 1,
}

# #43 阶段 D（重构指令 §13 风险评分）：信号分值表。risk_score = Σ分值，
# 截断 0-100。等级：CRITICAL ≥85（禁写回）/ HIGH ≥60（人工确认）/
# MEDIUM ≥35（本地模型二次审）/ LOW <35（自动通过）。
_SIGNAL_SCORES = {
    "quality_failed": 55,           # 规则硬错（确定性）
    "glossary_conflict": 40,        # 术语硬冲突
    "polysemy": 35,                 # 多义词（=MEDIUM 阈值：命中即二次审）
    "context_conflict": 30,         # 语境证据全部反对候选（歧义未决）
    "long_text": 15,                # token>60 长句（信息丢失风险）
    "negation_conditional": 15,     # 否定/条件（语义反转）
    "character_text": 10,           # 角色/专名文本（术语一致风险）
}

#: 历史错误模式命中分值（× 模式置信度，0.85 → 21 分）
_ERROR_PATTERN_SCORE = 25

#: 风险等级阈值（等级由分数 + 强制基线决定）
RISK_CRITICAL = 85
RISK_HIGH = 60
RISK_MEDIUM = 35

#: 强制基线：质量门硬错最低 HIGH（确定性错误绝不因分数截断降级）
_MANDATORY_FLOOR = RISK_HIGH


def risk_level_for(score: int) -> str:
    """分数 → 等级（LOW/MEDIUM/HIGH/CRITICAL）。"""
    if score >= RISK_CRITICAL:
        return "CRITICAL"
    if score >= RISK_HIGH:
        return "HIGH"
    if score >= RISK_MEDIUM:
        return "MEDIUM"
    return "LOW"

# 强制通道（审计 §5 P0-5）：机械失败、结构/术语硬冲突——不受抽样配额，
# 超出预算时绝不截断放行（超过系统处理能力 → deferred_due_to_budget 阻断发布
# 并进入人工队列）。其余信号为 discretionary 概率风险，才受 5/15/30% 预算。
_MANDATORY_SIGNALS = frozenset({"quality_failed", "glossary_conflict"})

# 语境证据参与消歧的信号（审计 Phase C，P1-3）：kind 限定语境库/重排
# 证据——向量相似召回（kind=vector）置信链较弱，不参与消歧裁决。
_CONTEXT_EVIDENCE_KINDS = frozenset(
    {"context_exact", "context_similar", "rerank"})


def _is_mandatory(signals: tuple[str, ...]) -> bool:
    """信号是否命中强制通道（任一 mandatory 信号即强制）。"""
    return any(s in _MANDATORY_SIGNALS for s in signals)


@dataclass(frozen=True)
class RiskSignals:
    """单条条目的风险信号评估结果。"""
    entry_id: str
    signals: tuple[str, ...] = ()       # 命中信号名（有序，无命中为空）
    priority: int = 0                   # 最高信号优先级（0 = 无风险）
    # 语境证据消费（审计 Phase C，P1-3）："supported" = 语境库高置信
    # 证据与候选译文一致（多义词已消歧）；"conflict" = 证据全部反对
    # 候选译文（歧义未决，应送审）。空串 = 无证据/未评估。
    context: str = ""
    # #43 阶段 D（重构指令 §13）：风险评分 0-100 + 等级。无信号 = 0/LOW
    # （直放语义不变）；quality_failed 强制 ≥60（HIGH 基线不降级）。
    risk_score: int = 0
    risk_level: str = "LOW"

    @property
    def risky(self) -> bool:
        """是否需送审：任一信号命中即送审。"""
        return bool(self.signals)


def _token_count(text: str) -> int:
    """token 数近似：英文按词、CJK 按字符。"""
    if not text:
        return 0
    words = len(re.findall(r"[A-Za-z0-9]+", text))
    cjk = len(re.findall(r"[一-鿿]", text))
    return words + cjk


def _has_polysemy(original: str) -> bool:
    """多义词命中（大小写不敏感、词边界）。"""
    words = {w.casefold() for w in re.findall(r"[A-Za-z]+", original)}
    return bool(words & _POLYSEMY_WORDS)


def _is_character_text(entry: TextEntry) -> bool:
    """角色关键文本：dialogue 域（role/kind 含对话线索）或
    含专名短语（≥2 个首字母大写单词——连续大写字词是专名/标题特征：
    Left Paddle、Iron Key；单句首大写不命中，避免普通句全量误伤）。"""
    role = str(entry.meta.get("role") or "").casefold()
    kind = str(entry.meta.get("kind") or "").casefold()
    if ("dialog" in role or "conv" in role or "chat" in role
            or kind == "us" and "dialogue" in role):
        return True
    return len(_PROPRIAL_RE.findall(entry.original)) >= 2


def _glossary_mismatch(entry: TextEntry, pairs: list[tuple[str, str]]) -> str:
    """术语冲突：active 词对命中原文（词边界）但标准译法不在译文中。

    返回命中的词对译法（用于审核参考），无命中返回空串。
    """
    original = entry.original
    translation = str(entry.translation or "")
    for term, trans in pairs:
        if not term or not trans:
            continue
        if re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])",
                     original, re.IGNORECASE):
            if trans not in translation:
                return trans
    return ""


def evaluate_entry(entry: TextEntry, glossary_pairs: list[tuple[str, str]]
                   | None = None,
                   context_evidence: list | None = None,
                   error_patterns: list | None = None) -> RiskSignals:
    """按决策表评估单条条目（纯函数）。

    glossary_pairs: 术语库 active 词对 [(term, translation), ...]；
    为 None 表示不检查术语冲突信号。
    context_evidence: KnowledgeRetrieval.query() 返回的语境证据列表
    （审计 Phase C，P1-3，鸭子类型：kind/translation/confidence）；
    为 None 表示不评估语境（行为与旧版完全一致）。
    error_patterns: 该条目的错误模式命中（#43 阶段 D，ErrorPatternStore
    .search() 的 dict 列表，鸭子类型 original/wrong/correct/confidence）；
    为 None 表示不评估历史错误信号（行为与旧版完全一致）。

    语境消歧语义：
      - 存在高置信（≥ 直填门禁）语境证据且与候选译文一致 → 多义词
        已消歧：从 signals 移除 polysemy（不因歧义送审），context=supported
        （语境直填本身已过质量门复查，证据同源不重复送审）；
      - 存在高置信证据但全部反对候选译文 → 追加 context_conflict 信号
        （歧义未决），context=conflict，送审优先级提升。

    #43 阶段 D 评分：risk_score = Σ信号分值（截断 0-100）+ 等级。
    质量门硬错强制 ≥ HIGH 基线（确定性错误绝不因分数截断降级）。
    """
    signals: list[str] = []
    # 质量门最终失败（status=failed = 重试链已耗尽）→ 强制送审
    if entry.status == "failed":
        signals.append("quality_failed")
    # 术语冲突
    if glossary_pairs:
        mismatch = _glossary_mismatch(entry, glossary_pairs)
        if mismatch:
            signals.append("glossary_conflict")
    # 多义词（语境库记录检查由调用方补充，见 gate_entries）
    if _has_polysemy(entry.original):
        signals.append("polysemy")
    # 语境证据消歧（Phase C，P1-3）
    context = ""
    if context_evidence:
        ctx = _consume_context_evidence(entry, context_evidence)
        if ctx == "supported":
            context = "supported"
            if "polysemy" in signals:
                signals.remove("polysemy")   # 已消歧：不再因歧义送审
        elif ctx == "conflict":
            context = "conflict"
            signals.append("context_conflict")  # 歧义未决，应送审
    # 长句
    if _token_count(entry.original) > _LONG_TOKEN_THRESHOLD:
        signals.append("long_text")
    # 否定/条件/比较词
    if _NEGATION_WORDS.search(entry.original):
        signals.append("negation_conditional")
    # 角色关键文本
    if _is_character_text(entry):
        signals.append("character_text")
    # 历史错误模式（#43 阶段 D：Charge 曾被误译「收费」→ 本条目
    # 命中错误模式 → 提高风险识别，重构指令 §16/Case 5）
    pattern_confidence = 0.0
    if error_patterns:
        pattern_confidence = max(
            (float(_evidence_attr(p, "confidence", 0.0)) or 0.0)
            for p in error_patterns)
        if pattern_confidence > 0:
            signals.append("error_pattern_hit")
    # 评分：Σ信号分值，截断 0-100
    score = sum(_SIGNAL_SCORES.get(s, 0) for s in signals)
    if pattern_confidence > 0:
        score += int(_ERROR_PATTERN_SCORE * pattern_confidence)
    if "quality_failed" in signals:
        score = max(score, _MANDATORY_FLOOR)   # 硬错强制 ≥ HIGH
    score = min(score, 100)
    priority = max((_SIGNAL_PRIORITY.get(s, 0) for s in signals), default=0)
    return RiskSignals(
        entry_id=entry.id if entry.id is not None else _stable_id(entry),
        signals=tuple(signals), priority=priority, context=context,
        risk_score=score, risk_level=risk_level_for(score))


def _evidence_attr(e, name: str, default=""):
    """dict/对象双形态证据字段读取（鸭子类型：retrieval 可返回两者）。"""
    if isinstance(e, dict):
        return e.get(name, default)
    return getattr(e, name, default)


def _consume_context_evidence(entry: TextEntry,
                              evidence: list) -> str:
    """语境证据裁决：返回 "supported" / "conflict" / ""（无有效证据）。

    只采信语境库/重排证据（kind ∈ _CONTEXT_EVIDENCE_KINDS）且置信度
    ≥ 直填门禁——低于门禁的证据只参考不裁决（与 match_exact 资格同源）。
    """
    translation = str(entry.translation or "")
    valid = [
        e for e in evidence
        if _evidence_attr(e, "kind") in _CONTEXT_EVIDENCE_KINDS
        and float(_evidence_attr(e, "confidence", 0.0))
        >= _DIRECT_FILL_MIN_CONFIDENCE
        and str(_evidence_attr(e, "translation") or "")
    ]
    if not valid:
        return ""
    if any(str(_evidence_attr(e, "translation")).strip()
           == translation.strip() for e in valid):
        return "supported"
    return "conflict"


def _stable_id(entry: TextEntry) -> str:
    """无 id 时用 file_id:key_path 兜底（测试构造的临时条目）。"""
    return f"{entry.file_id}:{entry.key_path}"


def gate_entries(entries: list[TextEntry],
                 glossary_pairs: list[tuple[str, str]] | None = None,
                 max_send_rate: float = 0.15,
                 error_patterns_by_id: dict[str, list] | None = None,
                 context_evidence_by_id: dict[str, list] | None = None
                 ) -> tuple[list[TextEntry], list[TextEntry],
                            list[TextEntry], dict]:
    """批量分流：按决策表筛出强制送审、预算送审、直放与预算截断。

    双通道（审计 §5 P0-5）：
      - mandatory（quality_failed / glossary_conflict）不受配额，全部送审；
      - discretionary（polysemy / long_text / negation_conditional /
        character_text）受 max_send_rate 预算（默认 15%），超限条目归入
        deferred_due_to_budget（人工队列），绝不再命名为 passed；
      - max_send_rate >= 1.0（全量送审，2026-08-14）：连无风险直放
        条目也进 4B 复核——「全部译文」承诺与设置页文案一致。

    error_patterns_by_id（#43 阶段 D）：{entry_id: 错误模式命中列表}——
    调用方（review 流程）负责检索，本函数保持纯函数（无 IO）。
    context_evidence_by_id（#43 阶段 D）：{entry_id: 语境证据列表}
    （KnowledgeRetrieval.query() 返回值，鸭子类型 kind/translation/
    confidence）——多义词已消歧（证据支持候选）→ 移除 polysemy 信号，
    证据全部反对候选 → 追加 context_conflict 信号（歧义未决送审）。

    返回 (to_review, passed, deferred_due_to_budget, stats)：
      to_review               按优先级降序的可疑条目（mandatory 在前）
      passed                  直放条目（无任何风险信号）
      deferred_due_to_budget  超出预算的 discretionary 条目（不入直放）
      stats                   {"total", "sent", "mandatory", "discretionary",
                               "deferred_due_to_budget", "rate",
                               "truncated", "signals", "risk": {id: score},
                               "risk_levels": {LOW: n, ...}}
      rate 只统计 discretionary 送审率（mandatory 单独统计，不受 15% 约束）。
    """
    stats: dict = {"total": len(entries), "sent": 0, "mandatory": 0,
                   "discretionary": 0, "deferred_due_to_budget": 0,
                   "rate": 0.0, "truncated": 0, "signals": {},
                   "risk": {}, "risk_levels": {}}
    if not entries:
        return [], [], [], stats
    def _key(e: TextEntry) -> str:
        return e.id if e.id is not None else _stable_id(e)

    evaluated = [evaluate_entry(
        e, glossary_pairs,
        context_evidence=(context_evidence_by_id or {}).get(_key(e)),
        error_patterns=(error_patterns_by_id or {}).get(_key(e)))
        for e in entries]  # 两个字典都用关键字传参（避免误绑位置参数）
    for sig in evaluated:
        for name in sig.signals:
            stats["signals"][name] = stats["signals"].get(name, 0) + 1
        stats["risk"][sig.entry_id] = sig.risk_score
        stats["risk_levels"][sig.risk_level] = (
            stats["risk_levels"].get(sig.risk_level, 0) + 1)
    mandatory: list[tuple[int, int, TextEntry, RiskSignals]] = []
    discretionary: list[tuple[int, int, TextEntry, RiskSignals]] = []
    passed: list[TextEntry] = []
    for e, sig in zip(entries, evaluated):
        if not sig.risky:
            passed.append(e)
            continue
        # 排序键：(-priority, -信号数) 稳定高优先级在前
        bucket = (mandatory if _is_mandatory(sig.signals)
                  else discretionary)
        bucket.append((-sig.priority, -len(sig.signals), e, sig))
    # TextEntry 不可比较：只用数值键排序（稳定性由 Python sort 保证）
    mandatory.sort(key=lambda item: (item[0], item[1]))
    discretionary.sort(key=lambda item: (item[0], item[1]))
    to_review = [item[2] for item in mandatory]
    stats["mandatory"] = len(mandatory)
    # 预算 100%（max_send_rate >= 1.0）= 全量送审（2026-08-14 用户实证
    # 「送审 171/641 不是全审」：语境错误常藏在无风险信号条目里，直放
    # 让多数译文没被 4B 看过——设置页「审核范围：全部译文」文案与之一
    # 致。全审 = 直放条目也进 4B 复核，语义不变（4B 判定仍走质量门）。
    if max_send_rate >= 1.0:
        to_review.extend(item[2] for item in discretionary)
        to_review.extend(passed)
        passed = []
        stats["discretionary"] = len(discretionary)
        stats["deferred_due_to_budget"] = 0
        stats["truncated"] = 0
        stats["sent"] = len(to_review)
        stats["rate"] = 1.0   # discretionary 送审率 = 100%（预算内全送）
        return to_review, passed, [], stats
    # discretionary 预算：rate>0 时至少 1 条（小批量场景 round 到 0 会让
    # 小游戏完全跳过审核）；rate==0（显式关闭）或无可送 discretionary → 0。
    if max_send_rate <= 0 or not discretionary:
        budget = 0
    else:
        budget = max(1, int(round(len(discretionary) * max_send_rate)))
    disc_to_review = [item[2] for item in discretionary[:budget]]
    deferred = [item[2] for item in discretionary[budget:]]
    to_review.extend(disc_to_review)
    stats["discretionary"] = len(disc_to_review)
    stats["deferred_due_to_budget"] = len(deferred)
    stats["truncated"] = len(deferred)
    stats["sent"] = len(to_review)
    # rate = discretionary 实际送审 / discretionary 总数（2026-08-14 口径
    # 修正：此前分母用全量条目，641 条里送审 160 条 discretionary 显示成
    # 25%——真实送审率是 100%，日志误导「没全审」）
    stats["rate"] = round(
        len(disc_to_review) / len(discretionary), 4) \
        if discretionary else 0.0
    return to_review, passed, deferred, stats
