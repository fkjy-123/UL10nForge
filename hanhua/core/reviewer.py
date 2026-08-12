"""翻译语义审核器（翻译质量升级核心，2026-08-12）。

背景：质量门（quality.py）只查机械问题（回显/格式/长度/脚本结构），
「翻译评价：已产出译文 / 需要优化：否」是形式化字段——Resume→简历、
Start→播放 这类语义/术语错误检测不到，质量评价形同空功能（用户
实证：很多不好的翻译也显示不需要优化）。

方案：翻译完成后用强模型（deepseek-v4-flash via Anthropic 兼容 API，
与用户 Claude Code 同源）对译文做语义级审核。审核维度：

  1. 术语正确性：游戏术语/UI 标准词（Resume=继续 非 简历；
     Start=开始 非 播放——按钮动词 vs 播放动词的语境区分）
  2. 语境适配：按钮/菜单/对话/提示不同文本类型
  3. 专名处理：品牌/人名/地名保持原文或正确音译（不意译专名）
  4. 语义保真：不改变原意、不增删信息、不张冠李戴
  5. 风格一致性：与游戏基调（恐怖/轻松/正式/口语）一致

输出：逐条 verdict（pass/flag）+ 问题类别 + 原因 + 建议译文。
不合格条目标记「需要优化」，问题模式聚合沉淀知识库（术语词对建议
自动生成），后续游戏翻译时用沉淀规则约束模型输出——翻译质量随
大闭环逐游戏上升。

审核模型比翻译模型（1.8B）强一个量级，能判断语义；审核只发生在
写回前（翻译成功后），不拖慢翻译吞吐（批量并发请求）。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import requests

from .translator import extract_json_array

# ── 审核维度与判定标准 ─────────────────────────────────────────────

_REVIEW_SYSTEM_PROMPT = """你是一位严格的游戏本地化质量审核员。你的任务是审核
中文本地化译文是否合格。审核必须严格，不合格就标记，宁严勿松。

审核五个维度（任一不合格即 flag）：
1. 术语正确性：游戏术语与 UI 标准词必须使用游戏行业标准译法。
   UI 按钮/菜单词的标准译法：Resume=继续（不是简历/恢复）、
   Start=开始（不是播放）、Play=播放/游玩、Quit=退出、Settings=设置、
   Continue=继续、Load=读取、Save=保存、New Game=新游戏、
   Main Menu=主菜单、Back=返回、Options=选项、Exit=退出。
   必须结合上下文：按钮文本用动词短译，标题用名词。
2. 语境适配：根据文本类型（按钮/菜单项/对话框/对话/提示/字幕/日志）
   选择相应风格——按钮简洁动词、对话自然口语、提示清楚明白。
3. 专名处理：品牌名（7 Up、PlayStation、Xbox）、人名、地名、游戏名、
   组织名必须保留原文或标准音译，禁止意译（Ubuntu 不许翻成「乌班图」
   之外的任意改写；Steam 保持 Steam）。
4. 语义保真：不改变原意、不增删信息、不混淆对象（把 A 的说明安到
   B 上）、不错译（"clutch" 在音游语境是按键术语，不是离合器）。
5. 风格一致性：译文风格与游戏基调一致（恐怖/轻松/正式/口语/像素
   复古），整体协调。

输出严格 JSON 数组，每条：
{"id": "<条目ID>", "verdict": "pass" 或 "flag", "issue": "术语错误" 或
"语境不当" 或 "专名误译" 或 "语义偏差" 或 "风格不一致"（仅 flag 时填写，
否则 null）, "reason": "一句话原因（仅 flag 时填写）",
"suggestion": "建议译文（仅 flag 时填写）"}
只输出 JSON，不要任何其他文字。"""

# 上下文可传递给审核模型的最大字符数（每条原文+译文+类型）
_MAX_ITEM_CHARS = 600
# 每批审核条目数（平衡上下文长度与审核一致性）。deepseek-v4-flash 是
# reasoning 模型：thinking 块占输出 token，120 条/8192 时 text 块被
# 截断为空（JSON 缺失 → 整批丢弃，ffs 6224 条实证）。60 条/32768
# 输出 token 实测 end_turn 完整返回（~7KB JSON/批）。
_REVIEW_BATCH_SIZE = 60


@dataclass
class ReviewConfig:
    """语义审核服务配置（Anthropic 兼容端点）。"""
    base_url: str = "https://api.deepseek.com/anthropic"
    api_key: str = ""
    model: str = "deepseek-v4-flash"
    timeout: float = 300.0
    max_tokens: int = 32768
    batch_size: int = _REVIEW_BATCH_SIZE
    # 并发批数：串行审核 267 批（faerie）约 4-7h，多流并行可压到 1.5-2h。
    # 实测（两进程并行请求时）单批 49s 正常返回，API 无明显限流。
    concurrency: int = 3
    enabled: bool = True


def _default_config() -> ReviewConfig:
    """从 ~/.claude/settings.json 继承 Claude Code 同源凭据（若未显式配置）。"""
    cfg = ReviewConfig()
    try:
        path = os.path.expanduser("~/.claude/settings.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        env = data.get("env", {})
        cfg.api_key = cfg.api_key or env.get("ANTHROPIC_AUTH_TOKEN", "")
        cfg.base_url = env.get("ANTHROPIC_BASE_URL", cfg.base_url)
        cfg.model = (env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL")
                     or env.get("ANTHROPIC_MODEL") or cfg.model)
    except Exception:  # noqa: BLE001 - 无 claude 配置则用默认值
        pass
    return cfg


@dataclass
class ReviewItem:
    """单条待审核翻译。"""
    entry_id: str
    original: str
    translation: str
    text_type: str = ""


@dataclass
class ReviewResult:
    """单条审核结论。"""
    entry_id: str
    verdict: str = "pass"          # pass / flag
    issue: str = ""                # 术语错误/语境不当/专名误译/语义偏差/风格不一致
    reason: str = ""
    suggestion: str = ""
    reviewed: bool = True

    @property
    def needs_optimization(self) -> bool:
        return self.verdict == "flag"


def _build_batch_prompt(items: list[ReviewItem]) -> str:
    """构造一批审核请求体（条目列表 + JSON 输出要求）。"""
    lines = ["以下是待审核的中文译文，逐条审核后输出 JSON 数组：", ""]
    for it in items:
        orig = it.original[:_MAX_ITEM_CHARS]
        trans = it.translation[:_MAX_ITEM_CHARS]
        lines.append(f'[id: {it.entry_id}]')
        lines.append(f'类型：{it.text_type or "未知"}')
        lines.append(f'原文：{orig}')
        lines.append(f'译文：{trans}')
        lines.append("---")
    lines.append("")
    lines.append("输出 JSON 数组，每项含 id/verdict/issue/reason/suggestion。")
    return "\n".join(lines)


# 不合格标记词形（实测模型输出 "incorrect"——2026-08-12 端到端验证
# 暴露：旧解析只认 "flag"，"incorrect" 被当 pass，Resume→简历 漏报）
_FLAG_VALUES = frozenset({
    "flag", "fail", "incorrect", "bad", "wrong", "poor", "failed",
    "不合格", "错误", "需优化", "需要优化", "不通过", "改进",
})


def _parse_verdict(raw: str) -> str:
    v = (raw or "").strip().lower()
    if v in _FLAG_VALUES:
        return "flag"
    # 前缀匹配：incorrectly / fail-1 等变体
    for start in ("incorrect", "fail", "flag", "bad", "wrong",
                  "不合格", "需优化", "需要优化"):
        if v.startswith(start):
            return "flag"
    return "pass"


class SemanticReviewer:
    """翻译语义审核器：翻译完成后批量审核译文语义质量。

    用法：reviewer = SemanticReviewer(config)；结果 = reviewer.review_batch(items)
    结果按 entry_id 索引，未返回的条目视为 pass（保守不打扰）。
    """

    def __init__(self, config: ReviewConfig | None = None):
        self.config = config or _default_config()

    @property
    def usable(self) -> bool:
        """审核服务可用性：有凭据且启用。"""
        return bool(self.config.enabled and self.config.api_key)

    def review_batch(self, items: list[ReviewItem],
                     timeout: float | None = None) -> dict[str, ReviewResult]:
        """审核一批译文，返回 {entry_id: ReviewResult}。

        - 批次内条目超出上下文限制时自动按 batch_size 分批
        - API 失败返回空 dict（调用方按全部 pass 处理并告警）
        - 模型未覆盖的条目（截断/漏判）按 pass 保守处理
        """
        out: dict[str, ReviewResult] = {}
        if not items or not self.usable:
            return out
        timeout = timeout or self.config.timeout
        chunks = [items[i:i + self.config.batch_size]
                  for i in range(0, len(items), self.config.batch_size)]
        if self.config.concurrency <= 1 or len(chunks) <= 1:
            for chunk in chunks:
                results = self._review_one_batch(chunk, timeout)
                if results is None:
                    continue
                out.update(results)
            return out
        # 多流并发分批（2026-08-12 基础设施升级）：267 批串行 ~4-7h，
        # 3 并发实测 API 无限流（两进程并行时单批仍 49s 正常返回）
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=self.config.concurrency) as pool:
            futures = {
                pool.submit(self._review_one_batch, chunk, timeout): i
                for i, chunk in enumerate(chunks)
            }
            for fut in as_completed(futures):
                results = fut.result()  # 内部已捕获异常，不会 raise
                if results is None:
                    continue
                out.update(results)
        return out

    def _review_one_batch(self, items: list[ReviewItem],
                          timeout: float) -> dict[str, ReviewResult] | None:
        prompt = _build_batch_prompt(items)
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        try:
            resp = requests.post(
                self.config.base_url.rstrip("/") + "/v1/messages",
                headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
        except Exception:  # noqa: BLE001 - 审核失败不阻断写回（按全部 pass 保守处理）
            return None
        content = "".join(
            b.get("text", "") for b in resp.json().get("content", [])
            if b.get("type") == "text")
        data = extract_json_array(content)
        if data is None:
            return None
        want = {it.entry_id for it in items}
        out: dict[str, ReviewResult] = {}
        for row in data:
            if not isinstance(row, dict):
                continue
            eid = str(row.get("id", ""))
            if eid not in want:
                continue
            out[eid] = ReviewResult(
                entry_id=eid,
                verdict=_parse_verdict(str(row.get("verdict", "pass"))),
                issue=str(row.get("issue") or "").strip(),
                reason=str(row.get("reason") or "").strip(),
                suggestion=str(row.get("suggestion") or "").strip(),
            )
        return out


# ── 问题模式聚合 → 术语沉淀 ────────────────────────────────────────

# 术语问题的关键词标记（审核模型 issue 字段）
_TERM_ISSUES = {"术语错误", "专名误译"}
# 词对形态：「英文原词 + 分隔符（→/：/：） + 中文译法」
_TERM_PAIR_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9 .'\-]{0,48}?)[：:→\->]+\s*"
    r"([一-鿿][^，。；;\n]{1,20})")
# 建议纯中文形态（无英文原词）：原文含英文词时按「原文首词→建议」沉淀
_ENG_WORD = re.compile(r"[A-Za-z]{2,}")
_STOP_WORDS = {"and", "the", "of", "to", "in", "on", "for", "you", "your",
               "with", "from", "this", "that", "not", "are", "was", "were"}


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
    return "游戏文本"


def review_entries(entries, glossary, *, game_name: str = "",
                   on_note=None) -> dict:
    """翻译后语义审核核心（runner 与 GUI 主路径共用，翻译 C6 闭口）。

    对 status == translated 且非回显的条目做五维语义审核（术语/语境/
    专名/语义/风格）；flag 条目的术语词对经 C5 门禁沉淀全局术语库
    （add_reviewed——高频普通词单 token 拒绝，组合词对/语境支撑词对
    才入库）。审核服务不可用/无凭据/无条目时返回 used=False（不阻断
    调用方，on_note 可告警）。

    返回 summary：
      used          审核请求是否已发出（True 且 flagged 为空 = 全过）
      reviewed      模型返回的判定条数
      results       {eid: ReviewResult} 全量判定（含 pass，报告存档用）
      flagged       list[ReviewResult]（verdict == flag 的条目）
      pairs_added   经 C5 门禁沉淀的词对数
      pairs_rejected {term: 拒绝原因}
      originals     {eid: 原文}（词对提取/报告用）
      locators      {eid: "file_id:key_path"}
    """
    summary: dict = {"used": False, "reviewed": 0, "results": {},
                     "flagged": [], "pairs_added": 0, "pairs_rejected": {},
                     "originals": {}, "locators": {}}
    if not entries:
        return summary
    reviewer = SemanticReviewer()
    if not reviewer.usable:
        if on_note:
            on_note("语义审核跳过：未配置审核凭据（~/.claude/settings.json）")
        return summary
    items: list[ReviewItem] = []
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
        summary["originals"][eid] = str(e.original)
        summary["locators"][eid] = f"{e.file_id}:{e.key_path}"
    if not items:
        return summary
    summary["used"] = True
    if on_note:
        on_note(f"开始语义审核 {len(items)} 条（{reviewer.config.model}）…")
    results = reviewer.review_batch(items)
    summary["reviewed"] = len(results)
    summary["results"] = results
    flagged = [r for r in results.values() if r.verdict == "flag"]
    summary["flagged"] = flagged
    if not flagged:
        return summary
    # 术语词对沉淀：审核发现术语/专名错误 → 建议词对 → 全局术语库
    # （后续游戏翻译 prompt 注入按词对约束模型输出，质量逐游戏上升）
    pairs = extract_term_pairs(flagged, summary["originals"])
    # 翻译 C5 语境保护：为每个词对收集首个原文例句（term 在原文中出现
    # 的那条），随词对沉淀——单 token 高频普通词靠例句才能区分语境，
    # 语境留档也便于日后人工回查沉淀决策。
    contexts: dict[str, str] = {}
    for r in flagged:
        orig = (summary["originals"].get(r.entry_id, "") or "").strip()
        for term, _trans in pairs:
            if term and term in orig and term not in contexts:
                contexts[term] = orig[:120]
    for term, trans in pairs:
        try:
            # C5 门禁：单 token 高频普通词拒绝全局强制（返回拒绝原因），
            # 其他词对进 candidate 桶参考不强制、跨游戏复现升级 active
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


def extract_term_pairs(results: list[ReviewResult],
                       originals: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """从 flag 结果中提取术语词对（英文原词→建议译法）。

    供知识库沉淀：后续游戏翻译时按词对约束模型输出。
    只收术语/专名类问题。形态：
    1. 建议含分隔符（Resume→继续 / Resume：继续 / Resume: 继续）
    2. 建议为纯中文且原文含英文词 → （原文首词, 建议）
    """
    pairs: list[tuple[str, str]] = []
    try:
        return _extract_term_pairs_impl(results, originals)
    except Exception:  # noqa: BLE001 - 词对提取失败不阻断审核主流程
        return pairs


def _extract_term_pairs_impl(results: list[ReviewResult],
                             originals: dict[str, str] | None) -> list[tuple[str, str]]:
    """词对提取主体（2026-08-12 根因修复：`|` 后装饰字符类未闭合，
    `)` 裸括号 → unbalanced parenthesis 崩溃——ffs 724 flag 实证，
    崩溃点在审核最后一步，会导致整场审核结果丢失（_run_semantic_review
    异常 → review_results 空）。修正为 `[」』】）) ]` 字符类 + 外层
    try/except 防御（词对是附带产出，绝不允许拖垮审核主流程）。"""
    pairs: list[tuple[str, str]] = []
    _STRIP_WRAP = re.compile(r"[\"'「『【（( ]*[\"']?|[\"']?[」』】）) ]*")
    # 「译为/应译为/翻译为…」提示语前缀（审核建议常见包装，剥离后才是
    # 译文本身）；引号装饰统一中英文（“”"）
    _STRIP_PREFIX = re.compile(
        r"^(?:建议)?(?:应当|应|宜|建议)?(?:译为|翻译为|翻译成|译成|译作|"
        r"翻成|翻为|作|为)+")
    _STRIP_WRAP_ZH = re.compile(
        r"[“”\"'「『【（( ]*[\"']?|[\"']?[“”\"'」』】）) 。]*")
    for r in results:
        if r.verdict != "flag" or r.issue not in _TERM_ISSUES:
            continue
        sug = r.suggestion.strip()
        if not sug or len(sug) > 60:
            continue
        # 形态 1：英文词 + 分隔符 + 中文（source 限 ≤5 词——长建议串是
        # 完整翻译句，不是术语词对，提取成词对会污染全局术语表）
        m = _TERM_PAIR_RE.search(sug)
        if m:
            source = m.group(1).strip()
            if len(source.split()) <= 5:
                pairs.append((source, m.group(2)))
            continue
        # 形态 2：建议纯中文（可能带引号/书名号装饰）→ source 用整个短
        # 原文（≤5 词无标点）。原「原文首词」提取把 'Left Paddle→左拨片'
        # 错误简化为 (Left, 左拨片)——方向词/设备词单字对在普通文本全局
        # 误杀（ffs 2083 失败实证：'pick the right door' 被 (Right, 右拨片)
        # 拦截）。组合词对（Left Paddle→左拨片）只在原文含完整短语时命中。
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
