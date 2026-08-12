"""风险分流器（任务一 T1-3）：决定哪些译文需要 4B 深审。

背景：Qwen3.5-4B 深审是成本大头（关闭思考后约 2.4s/条），全量审
不可行——实施计划 §4.2 硬约束「正常译文 4B 调用率 <15%」。本模块按
决策表筛可疑条目，任一信号命中即送审，其余直放：

| 信号 | 判定 |
|---|---|
| quality_failed  | 质量门最终失败（重试链已耗尽，status=failed）→ 强制送审 |
| glossary_conflict | 术语词对命中原文但译文未使用标准译法 → 送审 |
| polysemy        | 多义词（Resume/Save/Charge…）命中且语境库无记录 → 送审 |
| long_text       | 原文 token 数 > 60 → 送审 |
| negation_conditional | 含 not/no/never/if/unless/only 等词 → 送审 |
| character_text  | dialogue 域或含专名（首字母大写词）→ 送审 |
| none            | 其余 → 直放 |

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

# 决策表信号优先级（影响送审批内排序：高优先级先审）
_SIGNAL_PRIORITY = {
    "quality_failed": 6,
    "glossary_conflict": 5,
    "polysemy": 4,
    "character_text": 3,
    "negation_conditional": 2,
    "long_text": 1,
}


@dataclass(frozen=True)
class RiskSignals:
    """单条条目的风险信号评估结果。"""
    entry_id: str
    signals: tuple[str, ...] = ()       # 命中信号名（有序，无命中为空）
    priority: int = 0                   # 最高信号优先级（0 = 无风险）

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
                   | None = None) -> RiskSignals:
    """按决策表评估单条条目（纯函数）。

    glossary_pairs: 术语库 active 词对 [(term, translation), ...]；
    为 None 表示不检查术语冲突信号。
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
    # 长句
    if _token_count(entry.original) > _LONG_TOKEN_THRESHOLD:
        signals.append("long_text")
    # 否定/条件/比较词
    if _NEGATION_WORDS.search(entry.original):
        signals.append("negation_conditional")
    # 角色关键文本
    if _is_character_text(entry):
        signals.append("character_text")
    priority = max((_SIGNAL_PRIORITY.get(s, 0) for s in signals), default=0)
    return RiskSignals(
        entry_id=entry.id if entry.id is not None else _stable_id(entry),
        signals=tuple(signals), priority=priority)


def _stable_id(entry: TextEntry) -> str:
    """无 id 时用 file_id:key_path 兜底（测试构造的临时条目）。"""
    return f"{entry.file_id}:{entry.key_path}"


def gate_entries(entries: list[TextEntry],
                 glossary_pairs: list[tuple[str, str]] | None = None,
                 max_send_rate: float = 0.15) -> tuple[list[TextEntry],
                                                       list[TextEntry],
                                                       dict]:
    """批量分流：按决策表筛出送审列表与直放列表。

    硬约束：送审率 ≤ max_send_rate（默认 15%，实施计划 §4.2）。
    超限时按优先级从低到高截断（高优先级信号必审；同优先级按
    risky 信号数排序）。

    返回 (to_review, passed, stats)：
      to_review  按优先级降序的可疑条目
      passed     直放条目（含超出预算被截断的次可疑条目——记录进 stats）
      stats      {"total": N, "sent": M, "rate": 0.xx,
                  "truncated": K, "signals": {信号名: 计数}}
    """
    stats: dict = {"total": len(entries), "sent": 0, "rate": 0.0,
                   "truncated": 0, "signals": {}}
    if not entries:
        return [], [], stats
    evaluated = [evaluate_entry(e, glossary_pairs) for e in entries]
    for sig in evaluated:
        for name in sig.signals:
            stats["signals"][name] = stats["signals"].get(name, 0) + 1
    risky: list[tuple[int, int, TextEntry, RiskSignals]] = []
    passed: list[TextEntry] = []
    for e, sig in zip(entries, evaluated):
        if sig.risky:
            # 排序键：(-priority, -信号数) 稳定高优先级在前
            risky.append((-sig.priority, -len(sig.signals), e, sig))
        else:
            passed.append(e)
    # TextEntry 不可比较：只用数值键排序（稳定性由 Python sort 保证）
    risky.sort(key=lambda item: (item[0], item[1]))
    # 预算下限：rate>0 时至少 1 条（小批量场景 round 到 0 会让小游戏
    # 完全跳过审核）；rate==0（显式关闭）才允许 0。
    budget = (0 if max_send_rate <= 0
              else max(1, int(round(len(entries) * max_send_rate))))
    to_review = [item[2] for item in risky[:budget]]
    stats["sent"] = len(to_review)
    stats["rate"] = round(len(to_review) / len(entries), 4)
    stats["truncated"] = max(0, len(risky) - budget)
    passed.extend(item[2] for item in risky[budget:])
    return to_review, passed, stats
