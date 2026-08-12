"""手动汉化完整记录自动导出（docs/all record/「游戏名」/）。

GUI 手动汉化每次写回后自动生成与 runner 闭环
（scripts/all_record_runner.py）同一结构的完整记录，避免「手动汉化
无记录」——用户实测问题没有落盘依据，无法复盘：

  summary.md                    # 识别/翻译/写回统计
  text/translated.txt|failed.txt|skipped.txt
  writeback/writeback.txt       # 文件清单 + 写回结果/闸门
  analysis/analysis-final.md    # 数据快照 + 分析待办清单
  fix record/fix-record.md      # 失败条目明细 + 分类统计
  final report/final-report.md  # 流程结果与结论

三份分析文档由本模块生成「数据快照 + 待办清单」（标注自动生成时间），
实质分析在后续会话中补充——与 runner 闭环「分析」流程一致。
"""
from __future__ import annotations

import collections
import datetime
import json
from pathlib import Path

_SEPARATOR = "─" * 64
_MAX_FAILED_DETAILS = 200  # fix-record 明细上限（防超长文档）

# ── 哨兵阈值（审计 P2-9：豁免放行统计哨兵，根因 C 防护）─────────────
# 识别/翻译跳过与豁免是正常机制，但异常比例说明「大块形态未被识别」——
# 用户实测发现前先告警（哑信号教训：跳过静默 → 零反馈；留档+统计+告警）。
_SENTINEL_SKIP_RATE = 0.7    # 跳过占识别条目比例超此值 → 告警
_SENTINEL_SKIP_MIN = 30      # 告警所需最少跳过条数（小样本不告警）
_SENTINEL_ECHO_RATE = 0.3    # 回显豁免占翻译比例超此值 → 告警
_SENTINEL_ECHO_MIN = 10      # 告警所需最少回显条数
_SENTINEL_REASON_RATE = 0.9  # 单一跳过原因占比超此值 → 提示复核
_SENTINEL_REASON_MIN = 30    # 提示所需最少跳过条数


def _meta_of(row: dict) -> dict:
    raw = row.get("meta", {})
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _format_detail(raw) -> str:
    """错误详情字段：已序列化的 JSON 展开为可读文本，其他原样返回。"""
    if raw is None or raw == "":
        return ""
    if isinstance(raw, dict):
        text = json.dumps(raw, ensure_ascii=False, indent=2)
    else:
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return str(raw)
        text = json.dumps(value, ensure_ascii=False, indent=2) \
            if isinstance(value, (dict, list)) else str(value)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines)


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _game_name(project, profile) -> str:
    return profile.game_name or Path(project.game_dir).name


def _record_root(project, profile, out_root: Path | None) -> Path:
    root = out_root or (Path(__file__).resolve().parents[2]
                        / "docs" / "all record")
    return root / _game_name(project, profile)


def _confidence_of(row: dict, meta: dict) -> str:
    return str(meta.get("confidence")
               or row.get("confidence") or "medium")


def _quality_text(meta: dict) -> str:
    quality = meta.get("quality_reasons", [])
    if isinstance(quality, list) and quality:
        return "、".join(str(r) for r in quality)
    return "—"


def _status_counts(store) -> dict[str, int]:
    return {status: store.count(status)
            for status in ("pending", "translated", "failed", "skipped")}


def _skipped_by_reason(rows: list[dict]) -> dict[str, int]:
    """跳过原因分布（真实总数）：预过滤留档条目的 skipped_count 承载
    （样本 ≤10 条/对象/原因），非留档条目计 1。"""
    by_reason: dict[str, int] = {}
    for row in rows:
        meta = _meta_of(row)
        reason = meta.get("reason") or "unknown"
        count = meta.get("skipped_count")
        by_reason[reason] = (
            by_reason.get(reason, 0) + (count if isinstance(count, int) else 1))
    return by_reason


def _exemption_sentinels(store) -> list[str]:
    """豁免放行统计哨兵（审计 P2-9）：跳过/回显豁免/单原因集中度超过
    阈值 → 返回显式告警行，写进 summary.md 让用户第一眼可见。

    跳过与豁免是正常机制，但异常比例是「大块形态未识别」的哑信号——
    用户实测发现前先落盘告警（根因 C 闭环：失败不可查 → 可查可告警）。
    阈值见 _SENTINEL_* 常量（保守，小样本不告警）。
    """
    rows = store.get_entries()
    counts = _status_counts(store)
    if not rows:
        return []
    warnings: list[str] = []
    # 跳过真实总数：留档样本（≤10 条/对象/原因）的 skipped_count 承载
    # 真实总数，行数只是样本数——哨兵必须用聚合值（R5 语义）；
    # 聚合只统计 status=skipped 的行（其他状态行不是跳过）。
    by_reason = _skipped_by_reason(
        [r for r in rows if r["status"] == "skipped"])
    skipped = sum(by_reason.values())
    # 真实总条目：非跳过状态行数是真实条目数（无样本截断），
    # 跳过用聚合值——跳过行数是样本数会虚高比率。
    total = sum(counts.values()) - counts.get("skipped", 0) + skipped
    translated = counts.get("translated", 0)
    if skipped >= _SENTINEL_SKIP_MIN and skipped / total > _SENTINEL_SKIP_RATE:
        warnings.append(
            f"跳过率 {skipped / total:.0%}（{skipped}/{total}）异常高——"
            f"可能存在大块未识别形态，对照 skipped.txt 逐条判定："
            f"该翻未翻则识别规则有漏洞，确为该跳（键/日志/引擎串）则记录判定")
    echo = sum(1 for row in rows if _meta_of(row).get("echo_exempt"))
    if (echo >= _SENTINEL_ECHO_MIN and translated
            and echo / translated > _SENTINEL_ECHO_RATE):
        warnings.append(
            f"回显豁免 {echo} 条（占翻译 {echo / translated:.0%}）——"
            f"模型大面积回显保留原文（未翻译），检查词表/术语覆盖与模型配置")
    if skipped >= _SENTINEL_REASON_MIN:
        dominant = max(by_reason.items(), key=lambda kv: kv[1], default=None)
        if dominant and dominant[1] / skipped > _SENTINEL_REASON_RATE:
            warnings.append(
                f"跳过集中于单一原因 {dominant[0]}（{dominant[1]}/{skipped}）"
                f"——确认该形态确为该跳；若是显示文本则对应识别规则有漏洞")
    return warnings


def _confidence_counts(store) -> dict[str, int]:
    counts: dict[str, int] = collections.Counter()
    for row in store.get_entries():
        counts[_confidence_of(row, _meta_of(row))] += 1
    return dict(counts)


def _failure_categories(store) -> list[tuple[str, int]]:
    """失败原因分类：quality_reasons 聚合（Q3 类别 + 细 reason 两级），倒序。"""
    counts: collections.Counter[str] = collections.Counter()
    for row in store.get_entries(status="failed"):
        meta = _meta_of(row)
        reasons = meta.get("quality_reasons", [])
        if isinstance(reasons, list) and reasons:
            label = "、".join(str(r) for r in reasons)
            # Q3：类别前缀（request/model_behavior/content_inherent）
            # ——策略路由 + attempt 预算的依据，报告可见可路由
            category = meta.get("failure_category")
            if category:
                label = f"{category}｜{label}"
            counts[label] += 1
        else:
            counts["（无原因记录）"] += 1
    return counts.most_common()


def _route_blocked_steps(result: dict | None) -> list[str]:
    """从写回结果的 analysis_report.route 提取被阻断的必需步骤。"""
    if not result:
        return []
    report = result.get("analysis_report")
    route = getattr(report, "route", ()) if report is not None else ()
    return [step.reason for step in route
            if step.required and step.status in {"blocked", "failed"}]


def _writeback_status_of(result: dict | None) -> dict[str, str] | None:
    """{locator: reason}——被拒条目标注实际未写入（防统计虚高）。"""
    if not result:
        return None
    verification = result.get("verification") or {}
    return {
        item["locator"]: item["reason"]
        for item in verification.get("rejected_entries", [])
    }


def _verification_block(verification: dict) -> list[str]:
    gates = verification.get("gates") or {}
    gate_lines = [
        f"  {name}={item.get('status', '?')}"
        for name, item in gates.items()
        if isinstance(item, dict) and name != "overall"
    ]
    blocks = [
        f"输入保护：{verification.get('input_protected')}",
        f"重开验证：{verification.get('reopen_verified')}",
        f"变更文件：{verification.get('changed_files')}",
        f"写入译文：{verification.get('written_translations')}",
        f"总体闸门：{verification.get('overall')}",
        f"字体层级：{verification.get('font_level')}",
        "",
        "四态闸门明细",
        *gate_lines,
    ]
    for warning in verification.get("warnings") or []:
        blocks.append(f"警告：{warning}")
    return blocks


def _export_text_records(project, out_text: Path, profile, *,
                         model_name: str = "",
                         writeback_status: dict[str, str] | None = None,
                         error_title: str = "",
                         error_detail: str = "") -> None:
    """导出 translated/failed/skipped 三类文本全字段记录。"""
    store = project.store
    categories = {
        "translated": ("成功文本", store.get_entries(status="translated")),
        "failed": ("失败文本", store.get_entries(status="failed")),
        "skipped": ("跳过文本", store.get_entries(status="skipped")),
    }
    now = _now()
    for category, (title, rows) in categories.items():
        path = out_text / f"{category}.txt"
        blocks = [
            f"游戏：{_game_name(project, profile)}",
            f"导出时间：{now}",
            f"翻译模型：{model_name or '—'}",
            f"{title}：{len(rows)} 条", "",
        ]
        if category == "skipped":
            # R5 跳过原因分布（消灭哑信号）：预过滤留档条目的
            # skipped_count 承载真实总数（样本 ≤10 条/对象/原因），
            # 用户可据此区分「日志/键（该跳）」与「该翻未翻（误跳）」。
            by_reason = _skipped_by_reason(rows)
            if by_reason:
                blocks += [
                    "跳过原因分布：", "",
                    *[f"- {reason}：{count}" for reason, count in
                      sorted(by_reason.items(), key=lambda kv: -kv[1])],
                    "",
                ]
        if error_title:
            blocks += [_SEPARATOR, f"写回失败：{error_title}"]
            if error_detail:
                blocks.append(f"详情：{_format_detail(error_detail)}")
            blocks.append("")
        for index, row in enumerate(rows, start=1):
            meta = _meta_of(row)
            reason = meta.get("reason") or ""
            role = meta.get("role") or ""
            confidence = _confidence_of(row, meta)
            source = meta.get("source") or row["file_id"]
            quality = _quality_text(meta)
            quality_passed = meta.get("quality_passed")
            detail = meta.get("request_error_detail")
            original = row.get("original", "")
            translation = row.get("translation", "") or "（无）"
            echoed = (category == "translated" and translation == original)
            wb_status = ""
            if writeback_status:
                locator = f"{row['file_id']}:{row.get('key_path', '')}"
                wb_status = writeback_status.get(locator)
            if wb_status:
                wb_line = f"写回：未写入（{wb_status}）"
            elif echoed:
                wb_line = "写回：未执行（回显——译文与原文相同，无需写回）"
            elif category == "translated" and writeback_status is not None:
                wb_line = "写回：已写入"
            else:
                wb_line = "写回：—"
            eval_text = ('回显保留原文（未实际翻译）' if echoed
                         else '已产出译文' if category == 'translated'
                         else quality or '—')
            opt_text = ('是（回显未翻译）' if echoed
                        else '否' if category == 'translated' else '—')
            blocks += [
                _SEPARATOR,
                f"[{index}] {title}",
                f"来源：{source}",
                f"键位：{row.get('key_path', '')}",
                f"原文：{original}",
                f"译文：{translation}",
                f"置信度：{confidence}",
                f"原因：{reason or '—'}",
                f"角色：{role or '—'}",
                f"质量评分：{quality}（passed={quality_passed}）",
                f"翻译评价：{eval_text}",
                f"需要优化：{opt_text}",
                wb_line,
            ]
            if detail:
                blocks.append(f"失败详情：{_format_detail(detail)}")
            blocks.append("")
        path.write_text("\n".join(blocks), encoding="utf-8")


def _export_writeback(project, out_writeback: Path, profile, *,
                      result: dict | None = None,
                      error_title: str = "",
                      error_detail: str = "") -> None:
    """写回清单：逐文件条目数 + 写回结果/闸门（失败时记录错误）。"""
    path = out_writeback / "writeback.txt"
    store = project.store
    files = store.get_files()
    all_rows = store.get_entries()
    per_file: dict[str, int] = collections.Counter(
        row["file_id"] for row in all_rows)
    blocks = [
        f"游戏：{_game_name(project, profile)}",
        f"写回时间：{_now()}",
        f"输出目录：{project.out_dir}", "",
        f"文件清单：{len(files)} 个", "",
    ]
    for f in files:
        blocks.append(
            f"- {f['rel_path']}（{per_file.get(f['id'], 0)} 条）")
    blocks.append("")
    if error_title:
        blocks += [_SEPARATOR, f"写回失败：{error_title}"]
        if error_detail:
            blocks.append(f"详情：{_format_detail(error_detail)}")
        blocks.append("")
    elif result is not None:
        verification = result.get("verification") or {}
        blocks += [
            _SEPARATOR,
            "写回结果",
            f"文本文件：{result.get('text_files', '—')}",
            *_verification_block(verification),
            f"备份：{verification.get('backup')}",
            f"清单：{verification.get('manifest')}",
            "",
        ]
        v2 = result.get("v2")
        if v2 is not None:
            blocks += [
                _SEPARATOR,
                "二进制资源（V2）",
                f"文件：{getattr(v2, 'files', 0)} · 候选："
                f"{getattr(v2, 'entries', 0)}",
            ]
            if getattr(v2, "truncated", 0):
                blocks.append(
                    f"截断（DLL/IL2CPP 长度限制）：{v2.truncated} 条")
            for warning in getattr(v2, "warnings", ()) or ():
                blocks.append(f"警告：{warning}")
            blocks.append("")
        font = result.get("font")
        if font is not None:
            blocks += [
                _SEPARATOR,
                "字体部署",
                f"字体：{getattr(font, 'family', '—')} · "
                f"层级：{getattr(font, 'level', '—')}",
                f"安装：{getattr(font, 'installed', '—')}", "",
            ]
    path.write_text("\n".join(blocks), encoding="utf-8")


def _write_summary(project, out_dir: Path, profile, *,
                   model_name: str = "",
                   result: dict | None = None,
                   error_title: str = "",
                   error_detail: str = "") -> None:
    """summary.md：识别/翻译/写回统计（与 runner 记录同构）。"""
    store = project.store
    counts = _status_counts(store)
    confidences = _confidence_counts(store)
    files = store.get_files()
    text_files = sum(1 for f in files
                     if _meta_of(f).get("format") not in (None, ""))
    name = _game_name(project, profile)
    blocks = [
        f"# {name} 手动汉化记录", "",
        f"- 游戏目录：{project.game_dir}",
        f"- 时间：{_now()}",
        f"- 记录类型：GUI 手动汉化写回后自动生成（数据快照 + 待办清单）",
        "",
        "## 1 识别",
        f"- 文件：{len(files)}（文本 {text_files} · 二进制 "
        f"{len(files) - text_files}）",
        f"- 识别条目：{sum(counts.values())}",
        "- 状态分布：",
    ]
    for status in ("pending", "translated", "failed", "skipped"):
        blocks.append(f"  - {status}: {counts.get(status, 0)}")
    conf_text = " · ".join(
        f"{k}: {v}" for k, v in sorted(confidences.items()))
    blocks += ["- 置信度分布：", f"  - {conf_text or '—'}", ""]
    # 哨兵（审计 P2-9）：异常跳过/回显豁免比例显式告警——用户第一眼
    # 可见，不再等实测发现问题（哑信号 → 可查可告警闭环）。
    sentinels = _exemption_sentinels(store)
    if sentinels:
        blocks += ["- ⚠️ 哨兵告警："]
        blocks += [f"  - {w}" for w in sentinels]
        blocks += [""]
    blocks += ["## 2 翻译", f"- 总条目：{sum(counts.values())}"]
    if error_title:
        blocks.append(f"- 状态：翻译已中断（{error_title}）")
    blocks += [
        f"- 完成：{counts.get('translated', 0)} · "
        f"失败：{counts.get('failed', 0)} · "
        f"跳过：{counts.get('skipped', 0)}",
        f"- 翻译模型：{model_name or '—'}", "",
        "## 3 写回",
    ]
    if error_title:
        blocks.append(f"- 失败：{error_title}")
        if error_detail:
            blocks.append(f"- 详情：{_format_detail(error_detail)}")
    elif result is not None:
        verification = result.get("verification") or {}
        font_level = verification.get("font_level")
        font_label = {
            "runtime_fallback": "运行时中文回退",
            "disabled": "未启用",
            "unavailable": "不可验证",
        }.get(str(font_level), str(font_level))
        blocks += [
            f"- 文本文件：{result.get('text_files', '—')} · "
            f"写入译文：{verification.get('written_translations', '—')}",
            f"- 输入保护：{verification.get('input_protected')} · "
            f"重开验证：{verification.get('reopen_verified')} · "
            f"变更文件：{verification.get('changed_files')}",
            f"- 总体闸门：{verification.get('overall')} · "
            f"字体：{font_label}",
        ]
    else:
        blocks.append("- 未执行")
    blocks += ["", "## 4 分析（待办）",
               "- [ ] 成功文本质量抽检（译文是否得当/是否无关文本）",
               "- [ ] 失败文本根因系统彻查（同类问题全解）",
               "- [ ] 跳过文本逐条判定（该翻→识别修复；不该翻→记录判定）",
               "- [ ] 写回问题根源修复",
               "- [ ] 修复后用升级版本重跑本游戏全流程（闭环）",
               "- [ ] 闭环后删除汉化输出目录", "",
               "记录文件：",
               "- text/translated.txt / text/failed.txt / text/skipped.txt",
               "- writeback/writeback.txt",
               "- analysis/analysis-final.md / fix record/fix-record.md / "
               "final report/final-report.md", "",
    ]
    (out_dir / "summary.md").write_text("\n".join(blocks), encoding="utf-8")


def _write_auto_docs(project, out_dir: Path, profile, *,
                     result: dict | None = None,
                     error_title: str = "",
                     error_detail: str = "") -> None:
    """三份分析文档：自动数据快照 + 待办清单（标注生成方式）。"""
    store = project.store
    name = _game_name(project, profile)
    counts = _status_counts(store)
    confidences = _confidence_counts(store)
    failures = store.get_entries(status="failed")
    categories = _failure_categories(store)

    # ── analysis/analysis-final.md ──
    analysis_dir = out_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    blocks = [
        f"# {name} 分析报告（工具自动生成数据快照）", "",
        f"- 游戏目录：{project.game_dir}",
        f"- 记录时间：{_now()}",
        "- 生成方式：GUI 手动汉化写回后自动导出；实质分析由后续会话补充",
        "",
        "## 1 识别快照",
        f"- 文件：{len(store.get_files())} · "
        f"识别条目：{sum(counts.values())}",
        "- 状态分布：",
    ]
    for status in ("pending", "translated", "failed", "skipped"):
        blocks.append(f"  - {status}: {counts.get(status, 0)}")
    conf_text = " · ".join(
        f"{k}: {v}" for k, v in sorted(confidences.items()))
    blocks += ["- 置信度分布：", f"  - {conf_text or '—'}", "",
               "## 2 翻译快照",
               f"- 完成：{counts.get('translated', 0)} · "
               f"失败：{counts.get('failed', 0)} · "
               f"跳过：{counts.get('skipped', 0)}",
               "- 失败原因分类：",
    ]
    if categories:
        blocks += [f"  - {cat}：{n}" for cat, n in categories]
    else:
        blocks.append("  - —")
    blocks += ["", "## 3 写回快照",
    ]
    if error_title:
        blocks += [f"- 失败：{error_title}"]
        if error_detail:
            blocks.append(f"- 详情：{_format_detail(error_detail)}")
    elif result is not None:
        verification = result.get("verification") or {}
        blocks += [
            f"- 变更文件：{verification.get('changed_files')} · "
            f"写入译文：{verification.get('written_translations')}",
            f"- 总体闸门：{verification.get('overall')} · "
            f"字体：{verification.get('font_level')}",
        ]
    else:
        blocks.append("- 未执行")
    blocked = _route_blocked_steps(result)
    if blocked:
        blocks += ["- 阻断步骤：", *[f"  - {b}" for b in blocked]]
    blocks += ["", "## 4 待办分析（后续会话补充）",
               "- [ ] 成功文本质量抽检（译文是否得当/是否无关文本）",
               "- [ ] 失败文本根因系统彻查（同类问题全解）",
               "- [ ] 跳过文本逐条判定（该翻→识别修复；不该翻→记录判定）",
               "- [ ] 写回问题根源修复",
               "- [ ] 修复后用升级版本重跑本游戏全流程（闭环）",
               "- [ ] 闭环后删除汉化输出目录", "",
    ]
    (analysis_dir / "analysis-final.md").write_text(
        "\n".join(blocks), encoding="utf-8")

    # ── fix record/fix-record.md ──
    fix_dir = out_dir / "fix record"
    fix_dir.mkdir(parents=True, exist_ok=True)
    shown = failures[:_MAX_FAILED_DETAILS]
    blocks = [
        f"# {name} 修复记录（工具自动生成数据快照）", "",
        f"- 生成时间：{_now()}",
        f"- 游戏目录：{project.game_dir}",
        f"- 失败条目：{len(failures)}（以下明细最多列出 "
        f"{_MAX_FAILED_DETAILS} 条）", "",
        "## 1 失败条目明细", "",
    ]
    for index, row in enumerate(shown, start=1):
        meta = _meta_of(row)
        quality = _quality_text(meta)
        detail = meta.get("request_error_detail")
        blocks += [
            _SEPARATOR,
            f"[{index}] 来源：{meta.get('source') or row['file_id']}"
            f" · 键位：{row.get('key_path', '')}",
            f"原文：{row.get('original', '')}",
            f"译文：{row.get('translation', '') or '（无）'}",
            f"原因：{meta.get('reason') or '—'}",
            f"质量：{quality}（passed={meta.get('quality_passed')}）",
            f"角色：{meta.get('role') or '—'}",
        ]
        if detail:
            blocks.append(f"失败详情：{_format_detail(detail)}")
        blocks.append("")
    if len(failures) > _MAX_FAILED_DETAILS:
        blocks.append(
            f"（其余 {len(failures) - _MAX_FAILED_DETAILS} 条见 "
            f"text/failed.txt 全量记录）")
        blocks.append("")
    blocks += ["", "## 2 失败原因分类", ""]
    if categories:
        blocks += [f"- {cat}：{n}" for cat, n in categories]
    else:
        blocks.append("- —")
    blocks += ["", "## 3 待办修复（后续会话补充）",
               "- [ ] 失败文本根因系统彻查（同类问题全解）",
               "- [ ] 修复后重跑本游戏全流程验证（闭环）",
               "- [ ] 闭环后删除汉化输出目录", "",
    ]
    (fix_dir / "fix-record.md").write_text(
        "\n".join(blocks), encoding="utf-8")

    # ── final report/final-report.md ──
    report_dir = out_dir / "final report"
    report_dir.mkdir(parents=True, exist_ok=True)
    if error_title:
        verdict = "FAILED（写回失败）"
    elif result is not None:
        verification = result.get("verification") or {}
        overall = str(verification.get("overall") or "")
        verdict = "PASS（写回验证通过）" if overall in {"PASS", "WARN"} \
            else f"{overall}（写回未通过验证）"
    else:
        verdict = "—（未写回）"
    blocks = [
        f"# {name} 最终报告（工具自动生成数据快照）", "",
        f"- 生成时间：{_now()}",
        f"- 游戏目录：{project.game_dir}",
        f"- 输出目录：{project.out_dir}",
        "- 生成方式：GUI 手动汉化写回后自动导出；实质分析由后续会话补充",
        "", "## 1 流程结果",
        f"- 识别 → 翻译 → 写回：完成" if not error_title
        else "- 识别 → 翻译 → 写回：写回中断",
        f"- 最终结论：{verdict}",
        f"- 翻译：完成 {counts.get('translated', 0)} · "
        f"失败 {counts.get('failed', 0)} · 跳过 {counts.get('skipped', 0)}",
        "", "## 2 写回验证",
    ]
    if error_title:
        blocks += [f"- 失败：{error_title}"]
        if error_detail:
            blocks.append(f"- 详情：{_format_detail(error_detail)}")
    elif result is not None:
        verification = result.get("verification") or {}
        blocks += [f"- {line}" for line in _verification_block(verification)]
        for warning in verification.get("warnings") or []:
            blocks.append(f"- 警告：{warning}")
    else:
        blocks.append("- 未执行")
    blocked = _route_blocked_steps(result)
    if blocked:
        blocks += ["", "## 3 阻断步骤", *[f"- {b}" for b in blocked]]
    blocks += ["", "## 4 后续",
               "- [ ] 实机运行验证（用户实测报告问题→按流程修复闭环）",
               "- [ ] 闭环后删除汉化输出目录", "",
    ]
    (report_dir / "final-report.md").write_text(
        "\n".join(blocks), encoding="utf-8")


def export_records(project, out_root: Path | None = None, *,
                   write_result: dict | None = None,
                   error_title: str = "",
                   error_detail: str = "",
                   model_name: str = "") -> Path | None:
    """GUI 手动汉化写回后自动生成完整记录文档。

    成功路径传 write_result；失败路径传 error_title/error_detail
    （二者均有写回清单/摘要落盘，保证失败也有依据）。返回记录目录。
    """
    try:
        profile = project.store.get_profile()
        out_dir = _record_root(project, profile, out_root)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "text").mkdir(parents=True, exist_ok=True)
        (out_dir / "writeback").mkdir(parents=True, exist_ok=True)
        writeback_status = _writeback_status_of(write_result)
        _export_text_records(
            project, out_dir / "text", profile,
            model_name=model_name,
            writeback_status=writeback_status,
            error_title=error_title, error_detail=error_detail)
        _export_writeback(
            project, out_dir / "writeback", profile,
            result=write_result,
            error_title=error_title, error_detail=error_detail)
        _write_summary(
            project, out_dir, profile, model_name=model_name,
            result=write_result,
            error_title=error_title, error_detail=error_detail)
        _write_auto_docs(
            project, out_dir, profile,
            result=write_result,
            error_title=error_title, error_detail=error_detail)
        return out_dir
    except (OSError, AttributeError, ValueError):
        # AttributeError：调用方（测试/未完整初始化的 Project）无 store
        # 等字段——记录导出是附属功能，缺数据时静默跳过，不影响主流程。
        return None
