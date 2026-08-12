"""翻译语义审核器（任务一阶段 1：四级深审闭环，本地 4B 推理）。

历史沿革：
- 2026-08-12 首版：走云端 deepseek API 审核（二值 pass/flag）
- 2026-08-13 全面升级：按执行指令删除云端审核——审核统一走本地
  Qwen3.5-4B（llama.cpp 单实例，--reasoning off 固化在 review spec
  server_args），不存在云端路径

闭环（实施计划 T1-1~T1-7，阶段 1）：
  质量门 → risk_gate 分流（4B 调用率 <15% 硬约束）→ 4B 四级判定
  （PASS/MINOR/MAJOR/CRITICAL，九维审核）→ apply_verdict 分发
  （PASS 写库 / MINOR 记录放行 / MAJOR 修正 / CRITICAL 重译）→
  反馈式重译（审核理由注入）→ 再审收敛（≤2 轮）→ 记忆门禁
  （MAJOR/CRITICAL 不进记忆）→ 审核日志（review_report.md）

四级定义（实施计划 §4.1）：
- PASS     语义/结构/术语全部正确 → 写库 + 记忆候选
- MINOR    语义正确但有小瑕疵，不改变含义 → 记录放行
- MAJOR    语义有偏差（术语误用/语气不符/信息缺失未颠倒）→ 修正再审
- CRITICAL 语义错误（否定颠倒/关系颠倒/数量时间错误/含义完全不同）→ 重译

审核维度（§4.1 九项）：语义一致性/否定/人物关系/条件与因果/数量/
时间/语气/信息完整性/术语一致性/风格。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .models import TextEntry
from .risk_gate import gate_entries
from .review_server import ReviewModelService

# ── 审核维度与四级判定标准 ─────────────────────────────────────────

_REVIEW_SYSTEM_PROMPT = """你是游戏本地化质量审核员。审核必须严格，逐项核对九
个审核维度，任一维度有问题就按严重程度定级，宁严勿松。

审核维度（九项）：
1. 语义一致性：译文是否传达原文全部含义，不张冠李戴、不增删信息
2. 否定：not/no/never/never/without 等否定是否准确（「不」被吞是 CRITICAL）
3. 人物关系：主宾关系是否颠倒（A 打 B 译成 B 打 A 是 CRITICAL）
4. 条件与因果：if/unless/only/因为/所以 等条件因果是否准确
5. 数量：数字/单复数/百分比是否准确（50 HP 译成 60 HP 是 CRITICAL）
6. 时间：时态/早晚/先后是否准确
7. 语气：按钮动词/对话口语/提示清楚，与文本类型匹配
8. 信息完整性：不丢字不丢句，长句不截断
9. 术语一致性：游戏术语与 UI 标准词必须用行业标准译法——
   Resume=继续（不是简历/恢复）、Start=开始（不是播放）、Save=保存、
   Load=读取、Quit=退出、Options=选项、New Game=新游戏、
   Main Menu=主菜单、Back=返回、Settings=设置、Continue=继续

级别定义：
- PASS：语义/结构/术语全部正确，可直接写库
- MINOR：语义正确但有瑕疵（语序不自然、用词不够地道），不改变含义
- MAJOR：语义有偏差（术语误用、语气不符、信息缺失但未颠倒），需修正
- CRITICAL：语义错误（否定颠倒、人物关系颠倒、数量/时间错误、
  含义完全不同），译文不可用

输出严格 JSON 对象，不要输出任何其他文字（包括思考、解释）：
{"level": "PASS|MINOR|MAJOR|CRITICAL", "reason": "<一句话中文理由>",
"issues": [{"type": "<错误类型>", "detail": "<详情>", "suggestion": "<建议译文>"}]}
PASS/MINOR 时 issues 可为空数组。"""

_LEVELS = ("PASS", "MINOR", "MAJOR", "CRITICAL")

# 旧二值审核词形 → 四级映射（兼容历史模型输出）
_LEGACY_FLAG_VALUES = frozenset({
    "flag", "fail", "incorrect", "bad", "wrong", "poor", "failed",
    "不合格", "错误", "需优化", "需要优化", "不通过", "改进",
})


def _parse_level(raw: str | None) -> str:
    """解析四级判定（兼容旧 verdict 词形：pass/flag/incorrect…）。

    优先级：精确四级值 → 前缀匹配 → 子串匹配 → 旧 flag 词形 →
    默认 PASS。
    """
    v = (raw or "").strip().upper()
    if not v:
        return "PASS"
    for level in _LEVELS:
        if v == level:
            return level
    for level in _LEVELS:
        if v.startswith(level) or f"({level})" in v or f"[{level}]" in v:
            return level
    if v in {w.upper() for w in _LEGACY_FLAG_VALUES}:
        return "MAJOR"
    for start in ("INCORRECT", "FAIL", "FLAG", "BAD", "WRONG", "不合格",
                  "需优化", "需要优化"):
        if v.startswith(start):
            return "MAJOR"
    return "PASS"


def _parse_verdict(raw: str) -> str:
    """旧二值解析兼容（部分调用方仍按 pass/flag 处理）。"""
    return "flag" if _parse_level(raw) in ("MAJOR", "CRITICAL") else "pass"


@dataclass
class ReviewConfig:
    """审核服务配置（本地 Qwen3.5-4B，无云端路径）。"""
    timeout: float = 120.0
    max_tokens: int = 1024
    batch_size: int = 1        # 4B 单实例并发 1，逐条送审
    enabled: bool = True


@dataclass
class ReviewItem:
    """单条待审核翻译。"""
    entry_id: str
    original: str
    translation: str
    text_type: str = ""


@dataclass
class ReviewResult:
    """单条四级审核结论。"""
    entry_id: str
    level: str = "PASS"          # PASS / MINOR / MAJOR / CRITICAL
    reason: str = ""
    issues: tuple[dict, ...] = ()    # [{"type", "detail", "suggestion"}]
    reviewed: bool = True
    # 兼容旧字段（旧二值接口：verdict/issue/suggestion）
    verdict: str = "pass"        # flag = level in (MAJOR, CRITICAL)
    issue: str = ""              # 首个 issue type
    suggestion: str = ""         # 首个 issue suggestion

    def __post_init__(self):
        if self.level not in _LEVELS:
            self.level = _parse_level(self.level)
        # 兼容旧二值构造点：显式 verdict="flag" 且未显式传 level →
        # 映射为 MAJOR（旧语义「需优化」= 现 MAJOR 起；真 PASS 的
        # verdict 默认值在下方重算不会误映射）
        if self.level == "PASS" and self.verdict == "flag":
            self.level = "MAJOR"
        self.verdict = "flag" if self.level in ("MAJOR", "CRITICAL") else "pass"
        if self.issues:
            first = self.issues[0]
            self.issue = str(first.get("type") or self.issue)
            self.suggestion = str(first.get("suggestion") or self.suggestion)

    @property
    def needs_optimization(self) -> bool:
        """兼容旧语义：需优化 = MAJOR 或 CRITICAL（MINOR 记录放行不打扰）。"""
        return self.level in ("MAJOR", "CRITICAL")

    def apply_verdict(self, entry: TextEntry) -> str:
        """T1-2 处置分发：按级别对条目落 meta 标记。

        返回处置名：
          write        PASS → 保持写库态（质量门已过），meta 记 review_level
          pass_minor   MINOR → 记录放行（meta review_level + review_reason）
          revise       MAJOR → 修正队列（meta 标 need_revision + 建议）
          retranslate  CRITICAL → 重译队列（meta 标 need_retranslate + 建议）
        """
        entry.meta = dict(entry.meta)
        entry.meta["review_level"] = self.level
        if self.reason:
            entry.meta["review_reason"] = self.reason[:400]
        if self.suggestion:
            entry.meta["review_suggestion"] = self.suggestion[:200]
        if self.level == "PASS":
            return "write"
        if self.level == "MINOR":
            return "pass_minor"
        if self.level == "MAJOR":
            entry.meta["need_revision"] = True
            return "revise"
        entry.meta["need_retranslate"] = True
        return "retranslate"


def _build_item_prompt(item: ReviewItem) -> str:
    """构造单条四级审核 prompt（含系统维度说明 + 条目）。"""
    return (
        _REVIEW_SYSTEM_PROMPT
        + f"\n类型：{item.text_type or '未知'}"
        + f"\n原文：{item.original[:600]}"
        + f"\n译文：{item.translation[:600]}"
    )


def _parse_result(raw: str, entry_id: str) -> ReviewResult | None:
    """解析审核模型 JSON 输出 → ReviewResult（容错：剥离代码围栏）。

    围栏形态处理：```json\n{...}\n``` → 去掉首行 ```json 与尾部 ```；
    直接 ```{...}``` → 去掉首尾 ```。
    """
    try:
        text = raw.strip()
        if text.startswith("```"):
            body = text[3:]
            if "```" in body:
                body = body.split("```", 1)[0]
            body = body.strip()
            if body.startswith("json"):
                body = body[4:].strip()
            text = body
        data = json.loads(text)
    except (json.JSONDecodeError, AttributeError):
        # 非 JSON 兜底：整段视为 reason，级别按词形粗判
        level = _parse_level(raw)
        return ReviewResult(entry_id=entry_id, level=level,
                            reason=raw.strip()[:300], reviewed=False)
    if not isinstance(data, dict):
        return None
    issues_raw = data.get("issues") or []
    issues = tuple(
        {str(k): str(v) for k, v in item.items() if isinstance(item, dict)}
        for item in issues_raw if isinstance(item, dict)) \
        if isinstance(issues_raw, list) else ()
    return ReviewResult(
        entry_id=entry_id,
        level=_parse_level(data.get("level")),
        reason=str(data.get("reason") or "").strip(),
        issues=issues,
    )


class SemanticReviewer:
    """本地四级审核器：Qwen3.5-4B 逐条判定（无云端路径）。

    服务生命周期由 ReviewModelService 管理（review_runtime.json
    跨实例复用）；审核失败返回空结果（调用方保守处理 + 告警）。
    """

    def __init__(self, config: ReviewConfig | None = None,
                 service: ReviewModelService | None = None,
                 app_dir: str | Path | None = None):
        self.config = config or ReviewConfig()
        self.service = service or ReviewModelService(
            Path(app_dir or Path.cwd()).resolve())

    @property
    def usable(self) -> bool:
        """本地模式：模型文件存在即可用（服务按需启动）。"""
        return self.service is not None

    @property
    def model_name(self) -> str:
        """当前审核模型名（GGUF 文件名，registry 实际定位结果）。

        旧接口 ReviewConfig.model 不存在（审核模型由 ModelRegistry
        按 models/ 目录管理，配置类只管超时/长度）——报告等展示侧
        一律走本属性（hickory 实证：runner 访问 config.model 崩溃）。
        """
        try:
            spec = self.service._spec()
            if spec.path.is_file():
                return spec.path.stem
            return "Qwen3.5-4B"   # 模型缺失时展示约定名而非兜底文件名
        except Exception:  # noqa: BLE001 - 注册表异常不阻断展示
            return "Qwen3.5-4B"

    def review_one(self, item: ReviewItem) -> ReviewResult | None:
        """单条四级审核（本地 4B）。失败返回 None。"""
        try:
            content = self.service.chat(
                _build_item_prompt(item),
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout)
        except Exception:  # noqa: BLE001 - 审核失败不阻断主流程（保守 pass）
            return None
        try:
            return _parse_result(content, item.entry_id)
        except Exception:  # noqa: BLE001
            return None

    def review_batch(self, items: list[ReviewItem]) -> dict[str, ReviewResult]:
        """逐条审核一批（4B 单实例并发 1，串行送审）。

        返回 {entry_id: ReviewResult}；服务失败条目缺失（调用方
        按保守处理——旧二值语义「未覆盖 = pass」）。
        """
        out: dict[str, ReviewResult] = {}
        if not items:
            return out
        for item in items:
            result = self.review_one(item)
            if result is not None:
                out[item.entry_id] = result
        return out


# ── 文本类型推断 ────────────────────────────────────────────────────

def text_type_for(meta: dict) -> str:
    """从条目 meta 推断文本类型（供审核模型语境判断，runner 与 GUI 共用）。"""
    kind = meta.get("kind") or ""
    if kind == "us":
        return "DLL 字符串"
    if kind == "il2cpp":
        return "IL2CPP 字符串"
    if kind == "textasset":
        return "文本脚本"
    if kind == "plain":
        return "纯文本"
    role = str(meta.get("role") or "")
    if "button" in role or role == "display" and len(role) < 12:
        return "UI 显示文本"
    if "log" in role or "debug" in role:
        return "调试日志"
    if "dialog" in role or "conv" in role or "chat" in role:
        return "对话文本"
    return "游戏文本"


# ── 词对提取 → 术语沉淀（保留：C5 语境保护门禁链） ─────────────────

_TERM_ISSUES = {"术语错误", "专名误译"}
_TERM_PAIR_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9 .'\-]{0,48}?)[：:→\->]+\s*"
    r"([一-鿿][^，。；;\n]{1,20})")
_ENG_WORD = re.compile(r"[A-Za-z]{2,}")
_STOP_WORDS = {"and", "the", "of", "to", "in", "on", "for", "you", "your",
               "with", "from", "this", "that", "not", "are", "was", "were"}


def extract_term_pairs(results: list[ReviewResult],
                       originals: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """从需修正结果中提取术语词对（英文原词→建议译法）。

    只收术语/专名类问题（issue type 或 suggestion 含分隔符形态）。
    供知识库沉淀：后续游戏翻译时按词对约束模型输出。
    """
    pairs: list[tuple[str, str]] = []
    try:
        return _extract_term_pairs_impl(results, originals)
    except Exception:  # noqa: BLE001 - 词对提取失败不阻断审核主流程
        return pairs


def _extract_term_pairs_impl(results: list[ReviewResult],
                             originals: dict[str, str] | None) -> list[tuple[str, str]]:
    """词对提取主体（2026-08-12 根因修复：`|` 后装饰字符类未闭合，
    `)` 裸括号 → unbalanced parenthesis 崩溃——修正为字符类 + 外层
    try/except 防御。词对是附带产出，绝不允许拖垮审核主流程）。"""
    pairs: list[tuple[str, str]] = []
    _STRIP_PREFIX = re.compile(
        r"^(?:建议)?(?:应当|应|宜|建议)?(?:译为|翻译为|翻译成|译成|译作|"
        r"翻成|翻为|作|为)+")
    _STRIP_WRAP_ZH = re.compile(
        r"[“”\"'「『【（( ]*[\"']?|[\"']?[“”\"'」』】）) 。]*")
    for r in results:
        if not r.needs_optimization:
            continue
        sug = r.suggestion.strip()
        if not sug or len(sug) > 60:
            continue
        m = _TERM_PAIR_RE.search(sug)
        if m:
            source = m.group(1).strip()
            if len(source.split()) <= 5:
                pairs.append((source, m.group(2)))
            continue
        sug_clean = _STRIP_PREFIX.sub("", sug)
        if re.fullmatch(
                r"[“”\"'「『【（( ]*[一-鿿][^，。；;\n]{1,24}[“”\"'」』】）) 。]*",
                sug_clean):
            orig = ((originals or {}).get(r.entry_id, "") or "").strip()
            if re.fullmatch(
                    r"[A-Za-z0-9 .'\-]{1,60}", orig
            ) and 1 <= len(orig.split()) <= 5:
                pairs.append(
                    (orig, _STRIP_WRAP_ZH.sub("", sug_clean).strip()))
    return pairs


# ── 主入口：翻译后深审闭环 ─────────────────────────────────────────

def _active_glossary_pairs(glossary) -> list[tuple[str, str]]:
    """术语库 active 词对（candidate 只参考不强制，不参与分流信号）。"""
    try:
        rows = glossary.list_all()
    except Exception:  # noqa: BLE001 - 术语库异常不阻断审核
        return []
    pairs = []
    for row in rows:
        status = str(row.get("status") or "active")
        term = str(row.get("term") or "")
        trans = str(row.get("translation") or "")
        if status == "active" and term and trans:
            pairs.append((term, trans))
    return pairs


def _memory_apply(memory, entry: TextEntry, level: str, model: str,
                  lang: str) -> None:
    """T1-6 记忆门禁：MAJOR/CRITICAL 的译文不进记忆（移除坏记忆）；
    PASS/修正后译文进记忆。"""
    if memory is None or not entry.translation:
        return
    try:
        if level in ("MAJOR", "CRITICAL"):
            memory.remove_memory(entry.original, model, lang)
        else:
            memory.add_memory(entry.original, entry.translation, model, lang)
    except Exception:  # noqa: BLE001 - 记忆门禁失败不阻断审核主流程
        pass


def review_entries(entries, glossary, *, game_name: str = "",
                   on_note: Callable[[str], None] | None = None,
                   translator=None, memory=None, app_dir: str | Path | None = None,
                   model_name: str = "", lang: str = "zh-CN",
                   max_send_rate: float = 0.15) -> dict:
    """翻译后深审闭环核心（runner 与 GUI 共用；翻译 C6 闭口升级版）。

    流程（阶段 1）：
      分流（risk_gate，4B 调用率 ≤ max_send_rate）→ 4B 逐条四级判定
      → apply_verdict 分发（PASS 写库 / MINOR 放行 / MAJOR 修正 /
      CRITICAL 重译）→ translator 传入时反馈式重译 + 再审收敛
      （≤2 轮）→ 记忆门禁 → 术语词对沉淀（C5 语境保护）。

    返回 summary（向后兼容旧二值键 + 新增四级统计）：
      used          是否发出审核请求
      reviewed      模型返回判定的条数
      results       {eid: ReviewResult} 全量判定
      flagged       list[ReviewResult]（MAJOR+CRITICAL——旧语义「需优化」）
      levels        {PASS: n, MINOR: n, MAJOR: n, CRITICAL: n, PARSE_FAIL: n}
      sent          送审条数（分流后）
      rate          送审率（≤ max_send_rate）
      retranslated  反馈重译次数
      converged     重译后收敛条数（降级到 MINOR 以下或 PASS）
      blocked       仍 CRITICAL 保留原文标记条数
      pairs_added / pairs_rejected / originals / locators   （旧键）
    """
    summary: dict = {"used": False, "reviewed": 0, "results": {},
                     "flagged": [], "levels": {}, "sent": 0, "rate": 0.0,
                     "retranslated": 0, "converged": 0, "blocked": 0,
                     "pairs_added": 0, "pairs_rejected": {},
                     "originals": {}, "locators": {}}
    if not entries:
        return summary
    items: list[ReviewItem] = []
    item_entries: list[TextEntry] = []
    for e in entries:
        if e.status != "translated" or not e.translation:
            continue
        if str(e.translation) == str(e.original):
            continue                       # 回显跳过非审核对象
        eid = f"e{len(items)}"
        items.append(ReviewItem(
            entry_id=eid,
            original=str(e.original)[:600],
            translation=str(e.translation)[:600],
            text_type=text_type_for(e.meta),
        ))
        item_entries.append(e)
        summary["originals"][eid] = str(e.original)
        summary["locators"][eid] = f"{e.file_id}:{e.key_path}"
    if not items:
        return summary
    reviewer = SemanticReviewer(app_dir=app_dir or Path.cwd())
    if not reviewer.usable:
        if on_note:
            on_note("语义审核跳过：本地审核服务不可用（模型缺失或启动失败）")
        return summary
    # 风险分流：只送可疑条目（4B 调用率硬约束）
    pairs = _active_glossary_pairs(glossary) if glossary is not None else []
    to_review, _passed, gate_stats = gate_entries(
        item_entries, pairs, max_send_rate=max_send_rate)
    summary["sent"] = gate_stats["sent"]
    summary["rate"] = gate_stats["rate"]
    if not to_review:
        if on_note:
            on_note("语义审核：无风险条目（分流直放），4B 零调用")
        summary["used"] = False
        return summary
    summary["used"] = True
    if on_note:
        on_note(f"风险分流：送审 {len(to_review)}/{len(items)} 条"
                f"（4B 调用率 {summary['rate']:.0%} ≤ {max_send_rate:.0%}）…")
    review_items = [
        ReviewItem(
            entry_id=it.entry_id, original=it.original,
            translation=it.translation, text_type=it.text_type)
        for it, e in zip(items, item_entries) if e in to_review]
    results = reviewer.review_batch(review_items)
    summary["reviewed"] = len(results)
    summary["results"] = results
    for level in _LEVELS:
        summary["levels"][level] = 0
    summary["levels"]["PARSE_FAIL"] = 0
    for r in results.values():
        summary["levels"][r.level] = summary["levels"].get(r.level, 0) + 1
    flagged = [r for r in results.values() if r.needs_optimization]
    summary["flagged"] = flagged
    # 处置分发 + 反馈重译闭环（translator 传入时）
    for r in results.values():
        entry = _entry_for(items, item_entries, r.entry_id)
        if entry is None:
            continue
        action = r.apply_verdict(entry)
        if action in ("revise", "retranslate"):
            if translator is not None:
                outcome = _retranslate_with_feedback(
                    translator, entry, r, on_note)
                if outcome == "converged":
                    summary["converged"] += 1
                elif outcome == "blocked":
                    summary["blocked"] += 1
                summary["retranslated"] += 1
        # 记忆门禁：MAJOR/CRITICAL 不进记忆；PASS/MINOR 进记忆
        _memory_apply(memory, entry, r.level, model_name, lang)
    # 术语词对沉淀（C5 语境保护门禁链）
    if flagged:
        originals = summary["originals"]
        contexts: dict[str, str] = {}
        for r in flagged:
            orig = (originals.get(r.entry_id, "") or "").strip()
            for term, _trans in extract_term_pairs(
                    flagged, originals):
                if term and term in orig and term not in contexts:
                    contexts[term] = orig[:120]
        for term, trans in extract_term_pairs(flagged, originals):
            try:
                reason = glossary.add_reviewed(
                    term, trans, context=contexts.get(term, ""),
                    game=game_name)
                if reason:
                    summary["pairs_rejected"][term] = reason
                else:
                    summary["pairs_added"] += 1
            except Exception:  # noqa: BLE001 - 词对沉淀失败不阻断审核主流程
                pass
    return summary


def _entry_for(items: list[ReviewItem], entries: list[TextEntry],
               entry_id: str) -> TextEntry | None:
    for it, e in zip(items, entries):
        if it.entry_id == entry_id:
            return e
    return None


def _retranslate_with_feedback(translator, entry: TextEntry,
                               result: ReviewResult,
                               on_note: Callable[[str], None] | None,
                               max_rounds: int = 2) -> str:
    """T1-4/T1-5 反馈式重译 + 再审收敛（上限 2 轮）。

    注入审核理由重译 → 过质量门 → 再审（若再审器可用）→
    仍 CRITICAL → 保留原文 + blocked 标记（不无限循环）。

    返回 'converged'（降到 MINOR 以下或 PASS）| 'blocked' |
    'failed'（重译请求失败）。
    """
    feedback = result.reason or ""
    if result.suggestion:
        feedback += f"；建议译文：{result.suggestion}"
    for round_no in range(1, max_rounds + 1):
        try:
            ok, translation = translator.retranslate_with_feedback(
                entry, feedback, round_no=round_no)
        except Exception:  # noqa: BLE001 - 重译失败记 blocked 终止循环
            entry.meta = dict(entry.meta)
            entry.meta["review_blocked"] = True
            return "blocked"
        if not ok or not translation:
            entry.meta = dict(entry.meta)
            entry.meta["review_blocked"] = True
            return "blocked"
        entry.translation = translation
        entry.meta = dict(entry.meta)
        entry.meta["review_level"] = "RETRANSLATED"
        # 再审（1 轮内判定收敛；再审失败保守放行——重译已过质量门）
        re_result = _re_review(entry)
        if re_result is None:
            entry.meta["review_level"] = "PASS"
            return "converged"
        if re_result.level in ("PASS", "MINOR"):
            entry.meta["review_level"] = re_result.level
            return "converged"
        feedback = re_result.reason or feedback   # 新一轮反馈
    entry.meta = dict(entry.meta)
    entry.meta["review_blocked"] = True
    entry.meta["review_blocked_rounds"] = max_rounds
    return "blocked"


def _re_review(entry: TextEntry, reviewer: SemanticReviewer | None = None,
               app_dir: str | Path | None = None) -> ReviewResult | None:
    """再审一次（收敛判定）。失败返回 None（保守放行）。"""
    if reviewer is None:
        reviewer = SemanticReviewer(app_dir=app_dir or Path.cwd())
    return reviewer.review_one(ReviewItem(
        entry_id=f"re_{entry.id or entry.key_path}",
        original=str(entry.original)[:600],
        translation=str(entry.translation)[:600],
        text_type=text_type_for(entry.meta),
    ))


def write_review_report(summary: dict, report_path: str | Path,
                        game_name: str = "") -> Path:
    """T1-7 审核日志：生成 review_report.md（每游戏一份）。

    内容：送审数/各级分布/重译收敛率/CRITICAL 明细（原文/错译/
    审核理由/正确译文——含 suggestions）。
    """
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    levels = summary.get("levels") or {}
    flagged = summary.get("flagged") or []
    originals = summary.get("originals") or {}
    locators = summary.get("locators") or {}
    criticals = [r for r in flagged if r.level == "CRITICAL"]
    sent = summary.get("sent", 0)
    total = summary.get("reviewed", 0)
    converged = summary.get("converged", 0)
    blocked = summary.get("blocked", 0)
    retranslated = summary.get("retranslated", 0)
    lines = [
        f"# 审核日志 {game_name}".rstrip(),
        "",
        f"- 送审：{sent} 条（送审率 {summary.get('rate', 0.0):.0%}）"
        f" · 判定：{total} 条",
        f"- 级别分布：PASS {levels.get('PASS', 0)} / MINOR "
        f"{levels.get('MINOR', 0)} / MAJOR {levels.get('MAJOR', 0)} / "
        f"CRITICAL {levels.get('CRITICAL', 0)} / PARSE_FAIL "
        f"{levels.get('PARSE_FAIL', 0)}",
        f"- 反馈重译：{retranslated} 次 · 收敛 {converged} · 未收敛阻塞 "
        f"{blocked}（重译收敛率 "
        f"{converged / max(1, retranslated):.0%}）",
        f"- 术语词对沉淀：+{summary.get('pairs_added', 0)}（门禁拒绝 "
        f"{len(summary.get('pairs_rejected', {}))}）",
        "",
        "## CRITICAL 明细（语义错译，需人工复核）",
        "",
    ]
    if not criticals:
        lines.append("无（本轮无 CRITICAL 级错译）。")
    for r in criticals:
        loc = locators.get(r.entry_id, "")
        lines.append(f"### {loc or r.entry_id}")
        lines.append(f"- 原文：{originals.get(r.entry_id, '')}")
        lines.append(f"- 错译：{_translation_of(r)}")
        lines.append(f"- 审核理由：{r.reason}")
        for issue in r.issues:
            if issue.get("suggestion"):
                lines.append(f"- 正确译文建议：{issue['suggestion']}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _translation_of(result: ReviewResult) -> str:
    """从 results 关联取错译文本（summary 不存译文时取 suggestion 首个）。"""
    return result.suggestion or "（无译文记录）"
