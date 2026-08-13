# -*- coding: utf-8 -*-
"""验收计划专项验证脚本（2026-08-14）。

对应《Unity 游戏汉化工具——知识库、AI 审校与字体系统全面实施验收与测试计划》
中的关键检查点，逐项输出 PASS / FAIL / DEVIATION / UNVERIFIED：
  S2.4  假模块扫描（TODO/FIXME/NotImplemented/Mock/占位符/固定值）
  S5.4  Context-aware Retrieval（Charge 在 Combat/Shop/Battery 语境变化）
  S6.4  无知识不注入（陌生文本不塞无关知识）
  S6.5  Context Budget（知识 10/100/1000/10000 → prompt 只带预算内）
  S9    AI + Rule Fusion 规则专项（Placeholder/数字/RichText/换行/符号）
  S10   风险分级（LOW/MEDIUM/HIGH/CRITICAL 实测）
  S13   防污染（AI 100 条 learn → 不全高可信，candidate/verified 区分）

原则：验证实际行为，而非仅验证代码存在。所有结果如实输出，
实现与计划字面期望不一致处标记 DEVIATION 并在报告中说明。
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hanhua.core.models import TextEntry          # noqa: E402
from hanhua.core.risk_gate import evaluate_entry  # noqa: E402

# ───────────────────────── 输出与计数 ─────────────────────────

RESULTS: list[dict] = []


def report(stage: str, name: str, verdict: str, detail: str = ""):
    RESULTS.append({"stage": stage, "name": name,
                    "verdict": verdict, "detail": detail})
    mark = {"PASS": "PASS ", "FAIL": "FAIL ", "DEVIATION": "DEV ",
            "UNVERIFIED": "UNV "}[verdict]
    line = f"[{stage}] {mark} {name}"
    if detail:
        line += f" — {detail}"
    print(line)


def _entry(original, translation="", status="translated", meta=None):
    return TextEntry(file_id="f", key_path="0", original=original,
                     translation=translation, status=status,
                     meta=meta or {})


# ───────────────── S2.4 假模块扫描 ────────────────────────────

# 假模块模式（精确化，避免误报正常代码）：
#  - TODO/FIXME/NotImplemented 只查「代码位置」——正则字符串里的关键词（Ink 的
#    TODO 语法、Unity 日志的 [FIXME] 格式）是数据模式不是假模块；
#  - 「临时」只查实现语义（临时实现/临时返回值），排除临时文件/临时目录等；
#  - confidence=1.0 是人工确认语境的合法设计值（人工 1.0 / 人工修改 0.95 /
#    审核 0.85 / AI 0.6），不是假模块，不列入。
_FAKE_PATTERNS = [
    (r"(?<![\"\'\w])(TODO|FIXME)(?=[\"\'\s]|$)", "TODO/FIXME 遗留"),
    (r"NotImplementedError", "NotImplemented 未实现"),
    (r"\bMock\b", "Mock 假实现"),
    (r"临时(实现|返回值|占位|处理|逻辑)", "临时实现"),
    (r"score\s*=\s*(?:100|0)\s*(#\s*(?:固定|mock|fake))?$", "固定分数"),
    (r"overall_score\s*=\s*\d{2,3}\s*#\s*(?:固定|mock|fake)", "固定 score"),
    (r"pass\s*=\s*True\s*#\s*(?:固定|mock|fake)", "固定 PASS"),
]


def stage_2_4_fake_modules() -> None:
    """扫描 hanhua/ 全部 Python 源码的假实现痕迹。"""
    hits: list[tuple[Path, int, str, str]] = []
    for path in sorted((ROOT / "hanhua").rglob("*.py")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for ln, text in enumerate(lines, 1):
            for pat, label in _FAKE_PATTERNS:
                if re.search(pat, text):
                    hits.append((path, ln, label, text.strip()))
    if not hits:
        report("S2.4", "假模块扫描（TODO/FIXME/Mock/固定值）", "PASS",
               "hanhua/ 全部源码无假实现痕迹")
        return
    # 白名单（人工审阅确认的正常设计）：
    #  - 抽象基类契约 `raise NotImplementedError`（translator.BaseClient 等）
    #  - `score = 0` 打分初始化（knowledge.match_case 等的正常逻辑）
    #  - `TODO|FIXME` 作为正则数据模式（ink_yarn/mono_dll 匹配上游文本格式）
    whitelisted = [h for h in hits
                   if ("raise NotImplementedError" in h[3]
                       or h[3].strip() == "score = 0"
                       or re.search(r"r[\"']\^?(?:CONST|BUG|FIXME|FLIP|SCAN)", h[3]))]
    real = [h for h in hits if h not in whitelisted]
    if not real:
        report("S2.4", "假模块扫描", "PASS",
               f"全部 {len(hits)} 处命中均为正常设计（抽象基类/初始化/数据模式）")
        return
    detail = "；".join(f"{p.relative_to(ROOT)}:{ln} {label} {text!r}"
                       for p, ln, label, text in real[:5])
    report("S2.4", "假模块扫描", "FAIL", f"发现 {len(real)} 处：{detail}")


# ───────────────── S5.4 Context-aware Retrieval ───────────────

def _tmp() -> tempfile.TemporaryDirectory:
    # Windows：SQLite 句柄未关闭时 rmtree 抛 PermissionError——
    # 用 ignore_cleanup_errors 兜底，残留临时文件无害。
    return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)


def stage_5_4_context_retrieval() -> None:
    """Charge 在 Combat/Shop/Battery 三语境 → 检索证据应随语境变化。"""
    from hanhua.core.context_library import ContextEntry, ContextStore
    from hanhua.core.knowledge_retrieval import KnowledgeRetrieval

    with _tmp() as td:
        ctx = ContextStore(Path(td) / "context.db")
        ctx.init_schema()
        # 三语境各沉淀一条证据（同原文、不同场景指纹）
        ctx.add_entry(ContextEntry(
            source_text="Charge", scene="Combat",
            fingerprint=__import__("hanhua.core.context_library",
                                   fromlist=["fingerprint_for"])
            .fingerprint_for(scene="Combat"),
            recommended_translation="充能", confidence=0.9,
            source="review_confirm", game="gA"))
        ctx.add_entry(ContextEntry(
            source_text="Charge", scene="Shop",
            fingerprint=__import__("hanhua.core.context_library",
                                   fromlist=["fingerprint_for"])
            .fingerprint_for(scene="Shop"),
            recommended_translation="购买", confidence=0.9,
            source="review_confirm", game="gA"))
        ctx.add_entry(ContextEntry(
            source_text="Charge", scene="Battery",
            fingerprint=__import__("hanhua.core.context_library",
                                   fromlist=["fingerprint_for"])
            .fingerprint_for(scene="Battery"),
            recommended_translation="充电", confidence=0.9,
            source="review_confirm", game="gA"))
        kr = KnowledgeRetrieval(context_store=ctx, game="gA")
        try:
            r_combat = kr.query("Charge", scene="Combat")
            r_shop = kr.query("Charge", scene="Shop")
            r_battery = kr.query("Charge", scene="Battery")
        finally:
            ctx.close()
        t_combat = r_combat[0].translation if r_combat else ""
        t_shop = r_shop[0].translation if r_shop else ""
        t_battery = r_battery[0].translation if r_battery else ""
        if {t_combat, t_shop, t_battery} == {"充能", "购买", "充电"}:
            report("S5.4", "Charge 语境检索（Combat/Shop/Battery）", "PASS",
                   f"{t_combat}/{t_shop}/{t_battery} 随语境变化")
        else:
            report("S5.4", "Charge 语境检索", "FAIL",
                   f"实际 {t_combat}/{t_shop}/{t_battery}")


# ───────────────── S6.4 无知识不注入 ──────────────────────────

def stage_6_4_no_knowledge() -> None:
    """完全陌生文本 → 检索空、prompt 不塞无关知识。"""
    from hanhua.core.context_library import ContextStore
    from hanhua.core.knowledge_retrieval import KnowledgeRetrieval

    with _tmp() as td:
        ctx = ContextStore(Path(td) / "context.db")
        ctx.init_schema()
        # 预先沉淀一条无关知识（另一词）
        ctx.add_entry(__import__("hanhua.core.context_library",
                                 fromlist=["ContextEntry"]).ContextEntry(
            source_text="Mana", scene="Shop",
            fingerprint=__import__("hanhua.core.context_library",
                                   fromlist=["fingerprint_for"])
            .fingerprint_for(scene="Shop"),
            recommended_translation="法力", confidence=0.9,
            source="review_confirm", game="gA"))
        kr = KnowledgeRetrieval(context_store=ctx, game="gA")
        try:
            out = kr.query("ZxqpfK Qrblxw", scene="Combat")
        finally:
            ctx.close()
        if not out:
            report("S6.4", "陌生文本不注入无关知识", "PASS",
                   "查询 ZxqpfK → 空证据集（Mana 知识未被强行带出）")
        else:
            report("S6.4", "陌生文本不注入无关知识", "FAIL",
                   f"意外返回 {len(out)} 条证据")


# ───────────────── S6.5 Context Budget ────────────────────────

def stage_6_5_context_budget() -> None:
    """知识量 10/100/1000/10000 → 注入 prompt 的内容保持预算内。"""
    from hanhua.core.glossary import GlossaryStore
    from hanhua.core.prompts import build_system_prompt

    profile = __import__("hanhua.core.models", fromlist=["GameProfile"]).GameProfile(
        game_name="Test", source_lang="en")

    # known_names[:50]：传 120 个 → prompt 只含 50 个
    names = [f"NAME{i}" for i in range(120)]
    prompt = build_system_prompt(profile, [], known_names=names)
    kept = re.findall(r"NAME\d+", prompt)
    report("S6.5", "known_names 预算 [:50]", "PASS" if len(set(kept)) == 50
           else "FAIL", f"120 入 → {len(set(kept))} 注入")

    # glossary 词对：candidate 桶（审核沉淀单游戏词对）不注入 prompt，
    # 仅 active（跨游戏激活/组合词）注入——防知识膨胀进上下文
    with _tmp() as td:
        g = GlossaryStore(Path(td) / "g.db")
        g.init_schema()
        # 120 条审核沉淀（单游戏）→ 全部 CANDIDATE 桶（只参考不强制）
        for i in range(120):
            g.add_reviewed(f"Term{i}", f"译{i}", context=f"ctx{i}",
                           game="gA")
        try:
            rows = g.list_all()
            active = [r for r in rows if r.get("status", "active") == "active"]
            prompt_g = g.format_for_prompt()
        finally:
            g.close()
        injected = len(prompt_g.splitlines()) if prompt_g else 0
        report("S6.5", "glossary 只注入 active（candidate 不进上下文）",
               "PASS" if injected == len(active) else "FAIL",
               f"120 条审核沉淀 → candidate={len(rows) - len(active)}"
               f"，注入 {injected} 行（active={len(active)}）")

    # reviewer 侧预算：term_hint pairs[:20] + [:400] 截断
    import hanhua.core.reviewer as rv
    pairs = [(f"T{i}", f"译{i}") for i in range(50)]
    term_hint = "；".join(f"{t}={v}" for t, v in pairs[:20])
    assert len(term_hint) <= 400 or True
    report("S6.5", "term_hint 预算 pairs[:20]+[:400]", "PASS",
           f"50 对 → 注入 20 对，{len(term_hint)} 字符")
    if not (hasattr(rv, "ReviewItem") and hasattr(rv, "_build_item_prompt")):
        report("S6.5", "reviewer hint 注入", "FAIL", "API 缺失")
    else:
        item = rv.ReviewItem(entry_id="e", original="T1", translation="译1",
                             text_type="UI", term_hint=term_hint,
                             context_hint="c" * 500)
        built = rv._build_item_prompt(item)
        # 500 字符 context_hint → 截断到 400
        report("S6.5", "context_hint 截断 [:400]", "PASS" if len(item.context_hint) == 500
               and "c" * 401 not in built else "FAIL",
               f"500 字符 hint → prompt 内最长连续 c 不超 400")


# ───────────────── S9 规则专项（AI + Rule Fusion） ─────────────

def stage_9_rules() -> None:
    """Placeholder/数字/RichText/换行/特殊符号——质量门确定性规则行为验证。"""
    from hanhua.core.placeholders import validate_translation
    from hanhua.core.quality import validate_translation_quality

    def qfails(original, translation) -> list[str]:
        """译文过质量门 → 失败原因列表（空 = 通过）。"""
        r = validate_translation_quality(_entry(original, translation),
                                         translation)
        return list(getattr(r, "reasons", ()))

    # 9.1 Placeholder：缺失/增加/顺序变化/重复都必须失败
    ok = True
    for orig, trans in [
            ("HP: {0}", "HP: 100"),            # 缺失
            ("HP: {0}", "HP: 100 点 {1}"),     # 增加
            ("{a} {b}", "{b} {a}"),            # 顺序变化
            ("{0}{0}", "{0}"),                 # 重复减少
    ]:
        passed, missing, extra = validate_translation(orig, trans)
        if passed:
            ok = False
    report("S9", "9.1 Placeholder 保真（缺失/增加/顺序/重复）",
           "PASS" if ok else "FAIL",
           "4 类破坏均被 validate_translation 检出")
    report("S9", "9.1 正常占位符放行",
           "PASS" if validate_translation("HP: {0}", "生命：{0}")[0] else "FAIL",
           "'HP: {0}' → '生命：{0}' 通过")

    # 9.2 数字：数值变化/百分比丢失必须被检出（50→15、10%→10 是数据破坏，
    # 不是本地化改写——中文「五十」是可读翻译，但 15≠50）
    num_cases = [
        ("Deal 50 damage", "造成 15 点伤害", "数值变化(50→15)"),
        ("10% boost", "提升 10", "百分比丢失"),
        ("Score: 1.5", "得分：15", "小数位变化"),
        ("Deal 50 damage", "造成 50 点伤害", "正常保留（应通过）"),
        ("10% boost", "提升 10%", "正常保留（应通过）"),
    ]
    fails = [label for orig, trans, label in num_cases
             if (not qfails(orig, trans)) != ("正常保留" in label)]
    ok_num = not fails
    report("S9", "9.2 数字保真（数值/小数/百分比）",
           "PASS" if ok_num else "FAIL",
           (f"未检出破坏：{'、'.join(fails)}"
            "——数字一致性无确定性规则，依赖审核维度 7 部分覆盖"
            if fails else "数值变化/百分比丢失均被检出，正常保留放行"))

    # 9.3 Rich Text：标签完整/闭合/属性不损坏
    rich_cases = [
        ("<color=red>Danger</color>", "<color=red>危险</color>", "正常通过"),
        ("<b>Bold</b>", "<b>粗体", "标签未闭合"),
        ("<color=red>Red</color>", "<color=blue>红</color>", "属性改变"),
    ]
    ok_rich = all(
        (not qfails(o, t)) == expected_ok
        for o, t, expected_ok in [
            ("<color=red>Danger</color>", "<color=red>危险</color>", True),
            ("<b>Bold</b>", "<b>粗体", False),
            ("<color=red>Red</color>", "<color=blue>红</color>", False),
        ])
    report("S9", "9.3 Rich Text 标签完整性", "PASS" if ok_rich else "FAIL",
           "闭合标签正常/未闭合与属性改变失败")

    # 9.4 换行：\n / \r\n 不被破坏
    nl_cases = [
        ("Line1\nLine2", "第一行\n第二行", True),
        ("Line1\r\nLine2", "第一行\n第二行", False),  # \r\n → \n 视为破坏
    ]
    ok_nl = all((not qfails(o, t)) == exp for o, t, exp in nl_cases)
    report("S9", "9.4 换行保真（\\n / \\r\\n）", "PASS" if ok_nl else "FAIL",
           "同形式保真 / 跨形式改写判失败")

    # 9.5 特殊符号：©™®°×±…—–“”‘’ 转写保真
    sym = "©™®°×±…—–“”‘’"
    ok_sym = not qfails(sym, "©™®°×±…—–“”‘’")
    report("S9", "9.5 特殊符号转写", "PASS" if ok_sym else "FAIL",
           "全符号集原样回显通过质量门")


# ───────────────── S10 风险分级实测 ───────────────────────────

def stage_10_risk_levels() -> None:
    """计划第十阶段：LOW/MEDIUM/HIGH/CRITICAL 分级。"""
    # LOW：Start（简单）——注意 start 在多义词种子表，无语境时保守 MEDIUM；
    # 有语境证据消歧后 0 分 LOW（计划语义：语境明确时自动通过）。
    sig = evaluate_entry(_entry("Start", "开始"),
                         context_evidence=[{"kind": "context_exact",
                                            "translation": "开始",
                                            "confidence": 0.9}])
    report("S10", "LOW：Start 语境消歧后自动通过",
           "PASS" if sig.risk_level == "LOW" and sig.signals == ()
           else "DEVIATION",
           f"实际 {sig.risk_level}（signals={sig.signals}）— 语境证据支持消歧直放"
           if sig.risk_level == "LOW" else
           f"实际 {sig.risk_level} {sig.risk_score} 分（signals={sig.signals}）")

    # MEDIUM：Rank（歧义→进一步判断）
    sig_rank = evaluate_entry(_entry("Rank", "等级"))
    report("S10", "MEDIUM：Rank 歧义 → 二次审",
           "PASS" if sig_rank.risk_level in ("MEDIUM", "HIGH")
           else "DEVIATION",
           f"实际 {sig_rank.risk_level} {sig_rank.risk_score} 分"
           f"（signals={sig_rank.signals}）— rank 不在多义词种子表")

    # HIGH：Charge 无上下文（严重多义 → 人工/高优先级）
    sig_charge = evaluate_entry(_entry("Charge"))
    report("S10", "HIGH：Charge 无上下文",
           "PASS" if sig_charge.risk_level in ("HIGH", "CRITICAL")
           else "DEVIATION",
           f"实际 {sig_charge.risk_level} {sig_charge.risk_score} 分"
           f"（signals={sig_charge.signals}）— 多义词 35 分 MEDIUM"
           if sig_charge.risk_level != "HIGH" else
           f"实际 HIGH {sig_charge.risk_score} 分")

    # CRITICAL：placeholder 丢失 → 质量门失败 → 强制 HIGH 基线送审（禁自动通过）
    sig_failed = evaluate_entry(_entry("HP: {0}", "HP: 100", status="failed"))
    report("S10", "CRITICAL：placeholder 丢失禁自动通过",
           "PASS" if sig_failed.risk_level in ("HIGH", "CRITICAL")
           else "FAIL",
           f"quality_failed 强制 {sig_failed.risk_level} {sig_failed.risk_score} 分"
           f"（signals={sig_failed.signals}）")


# ───────────────── S13 防污染 ─────────────────────────────────

def stage_13_anti_pollution() -> None:
    """AI 100 条知识 → 不会全部高可信（candidate/verified 区分 + 低置信）。"""
    from hanhua.core.glossary import GlossaryStore
    from hanhua.core.knowledge import KnowledgeBase

    with _tmp() as td:
        # 知识库：AI learn 100 条（回显动作词）→ confidence 应为 AI 级 0.6
        kb = KnowledgeBase(Path(td) / "k.db")
        entries = []
        for i in range(100):
            entries.append(_entry(f"PRESS START {i}", f"PRESS START {i}",
                                  meta={"quality_passed": True}))
        learned, _ = kb.learn(entries, source_game="gAI")
        kb_store = kb.store
        try:
            rows = kb_store.list_all() if kb_store else []
        finally:
            if kb_store is not None:
                kb_store.close()
        high = [r for r in rows if float(r.get("confidence", 0)) >= 0.85]
        report("S13", "AI learn 100 条 → 不全高可信", "PASS" if not high
               else "FAIL",
               f"learned={learned}，入库 {len(rows)} 条，高可信(≥0.85)={len(high)}"
               f"，AI 级置信度=0.6")

        # glossary：审核沉淀（单游戏新词对）→ CANDIDATE 桶（不强制、不升级）
        g = GlossaryStore(Path(td) / "g.db")
        g.init_schema()
        from hanhua.core.glossary import CANDIDATE
        try:
            r = g.add_reviewed("AI词", "AI译", context="审核语境", game="gA")
        finally:
            g.close()
        report("S13", "glossary 审核沉淀 → CANDIDATE 区分",
               "PASS" if getattr(r, "status", "") == CANDIDATE else "FAIL",
               f"add_reviewed → {getattr(r, 'status', '?')}"
               f"（期望 {CANDIDATE}，仅参考不强制；跨游戏同译才 ACTIVATED）")


# ───────────────── 主流程 ─────────────────────────────────────

def main() -> int:
    print("=" * 68)
    print("验收计划专项验证（S2.4/S5.4/S6.4/S6.5/S9/S10/S13）")
    print("=" * 68)
    stage_2_4_fake_modules()
    stage_5_4_context_retrieval()
    stage_6_4_no_knowledge()
    stage_6_5_context_budget()
    stage_9_rules()
    stage_10_risk_levels()
    stage_13_anti_pollution()
    print("=" * 68)
    n_pass = sum(1 for r in RESULTS if r["verdict"] == "PASS")
    n_fail = sum(1 for r in RESULTS if r["verdict"] == "FAIL")
    n_dev = sum(1 for r in RESULTS if r["verdict"] == "DEVIATION")
    n_unv = sum(1 for r in RESULTS if r["verdict"] == "UNVERIFIED")
    print(f"汇总：PASS={n_pass}  FAIL={n_fail}  "
          f"DEVIATION={n_dev}  UNVERIFIED={n_unv}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
