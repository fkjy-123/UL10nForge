#!/usr/bin/env python3
"""地毯式排查单游戏 runner：真实完整流程 + 全环节记录。

与 GUI 走完全相同的代码路径（真实启动 llama-server、真实模型翻译、
真实文件写回），产出 docs/all record/<游戏名>/{summary.md, text/*, writeback/}。

用法:
  python scripts/all_record_runner.py <游戏目录> [--batch N] [--no-translate]
      [--no-writeback] [--keep-library] [--app-dir ~/.hanhua_sweep]

记录结构（docs/all record/<游戏名>/）:
  summary.md              # 排查总结：统计/发现的问题/修复项/闭环状态
  text/translated.txt     # 成功文本：来源/键位/原文/译文/置信度/原因/质量评分
  text/failed.txt         # 失败文本：来源/键位/原文/译文/失败原因/详情
  text/skipped.txt        # 跳过文本：来源/键位/原文/跳过原因/判定结论
  writeback/writeback.txt # 写回逐文件记录：文件/成功失败/详情/验证结果
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from hanhua.core.glossary import GlossaryStore  # noqa: E402
from hanhua.core.knowledge import KnowledgeBase  # noqa: E402
from hanhua.core.local_model import LocalModelManager  # noqa: E402
from hanhua.core.models import TextEntry  # noqa: E402
from hanhua.core.project import Project  # noqa: E402
from hanhua.core.prompts import (build_system_prompt,  # noqa: E402
                                 collect_known_names)
from hanhua.core.settings import SettingsStore  # noqa: E402
from hanhua.core.translator import create_client  # noqa: E402
from hanhua.core.batch_translator import BatchTranslator  # noqa: E402

_SEPARATOR = "─" * 64
DEFAULT_OUT_BASE = PROJECT_ROOT / "docs" / "all record"
REAL_USER_DIR = Path.home() / ".hanhua"


def _safe_name(name: str) -> str:
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip() or "unnamed"


def _load_meta(row: dict) -> dict:
    raw = row.get("meta", {})
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _format_detail(raw) -> str:
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


def _entry_from_row(row: dict) -> TextEntry:
    meta = _load_meta(row)
    reasons = meta.get("quality_reasons", [])
    return TextEntry(
        file_id=row["file_id"], key_path=row["key_path"],
        original=row["original"], translation=row.get("translation", ""),
        status=row.get("status", "pending"),
        locked=bool(row.get("locked", 0)),
        id=row.get("id"), meta=meta,
        confidence=str(meta.get("confidence", "medium")),
        quality_reasons=tuple(str(r) for r in reasons)
        if isinstance(reasons, list) else (),
    )


def _object_label(meta: dict, row: dict) -> str:
    """所属对象/组件类型（Unity 结构定位信息）。"""
    parts = []
    if meta.get("asset_file"):
        parts.append(f"asset_file={meta['asset_file']}")
    if meta.get("obj") is not None:
        parts.append(f"obj={meta['obj']}")
    if meta.get("record_offset") is not None:
        parts.append(f"record_offset={meta['record_offset']}")
    if meta.get("line") is not None:
        parts.append(f"line={meta['line']}")
    kind = meta.get("kind") or ""
    component = {
        "str": "MonoBehaviour str 字段", "rawstr": "MonoBehaviour rawstr 数组",
        "textasset": "TextAsset 脚本", "localization": "Localization 表格",
        "typetree": "Typetree 字段", "us": "DLL #US 字符串",
        "il2cpp": "IL2CPP metadata 字符串", "plain": "纯文本文件行",
    }.get(kind, kind or "—")
    label = "、".join(parts)
    return f"{component}（{label}）" if label else component


def _export_text_records(project, out_text: Path, profile,
                         model_name: str = "",
                         writeback_status: dict[str, str] | None = None) -> None:
    """导出 translated/failed/skipped 三类文本全字段记录。

    writeback_status：{locator: 状态} 映射（written/rejected/回显跳过），
    在写回完成后导出时为每条记录标注实际写回结果（避免「后台显示成功、
    实际未写入」的统计虚高）。
    """
    store = project.store
    categories = {
        "translated": ("成功文本", store.get_entries(status="translated")),
        "failed": ("失败文本", store.get_entries(status="failed")),
        "skipped": ("跳过文本", store.get_entries(status="skipped")),
    }
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for category, (title, rows) in categories.items():
        path = out_text / f"{category}.txt"
        blocks = [
            f"游戏：{profile.game_name or Path(project.game_dir).name}",
            f"导出时间：{now}",
            f"翻译模型：{model_name or '—'}",
            f"{title}：{len(rows)} 条", "",
        ]
        for index, row in enumerate(rows, start=1):
            meta = _load_meta(row)
            reason = meta.get("reason") or ""
            role = meta.get("role") or ""
            confidence = meta.get("confidence") or row.get("confidence", "medium")
            source = meta.get("source") or row["file_id"]
            quality = meta.get("quality_reasons", [])
            quality_text = "、".join(str(r) for r in quality) \
                if isinstance(quality, list) and quality else "—"
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
            blocks += [
                _SEPARATOR,
                f"[{index}] {title}",
                f"来源：{source}",
                f"键位：{row.get('key_path', '')}",
                f"对象：{_object_label(meta, row)}",
                f"原文：{original}",
                f"译文：{translation}",
                f"置信度：{confidence}",
                f"原因：{reason or '—'}",
                f"角色：{role or '—'}",
                f"质量评分：{quality_text}（passed={quality_passed}）",
                f"翻译评价：{'回显保留原文（未实际翻译）' if echoed else '已产出译文' if category == 'translated' else quality_text or '—'}",
                f"需要优化：{'是（回显未翻译）' if echoed else '否'}",
                wb_line,
            ]
            if detail:
                blocks.append(f"失败详情：{_format_detail(detail)}")
            blocks.append("")
        path.write_text("\n".join(blocks), encoding="utf-8")


def _export_writeback_record(project, out_writeback: Path, profile,
                             result: dict | None, error_title: str = "",
                             error_detail: str = "") -> None:
    path = out_writeback / "writeback.txt"
    blocks = [
        f"游戏：{profile.game_name or Path(project.game_dir).name}",
        f"写回时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"输出目录：{project.out_dir}", "",
    ]
    # 逐文件记录（含翻译条目数）
    files = project.store.get_files()
    blocks += [f"文件清单：{len(files)} 个", ""]
    all_rows = project.store.get_entries()
    per_file: dict[str, int] = {}
    for row in all_rows:
        per_file[row["file_id"]] = per_file.get(row["file_id"], 0) + 1
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
        verification = result.get("verification", {})
        gates = verification.get("gates", {})
        gate_lines = [
            f"  {name}={item.get('status', '?')}"
            for name, item in gates.items()
            if isinstance(item, dict) and name != "overall"
        ]
        blocks += [
            _SEPARATOR,
            "写回结果",
            f"文本文件：{result.get('text_files', '—')}",
            f"输入保护：{verification.get('input_protected')}",
            f"重开验证：{verification.get('reopen_verified')}",
            f"变更文件：{verification.get('changed_files')}",
            f"写入译文：{verification.get('written_translations')}",
            f"总体闸门：{verification.get('overall')}",
            f"字体层级：{verification.get('font_level')}",
            f"清单：{verification.get('manifest')}",
            f"备份：{verification.get('backup')}",
            "",
            "四态闸门明细",
            *gate_lines,
            "",
        ]
        # 知识库案例转规则：writeback_case 5 条理论案例 → 可执行规则
        # （规则实现清单见 knowledge.writeback_case_rules，写回链路已启用）
        from hanhua.core.knowledge import writeback_case_rules
        rules = writeback_case_rules()
        blocks += [
            _SEPARATOR,
            f"知识库案例转规则：{len(rules)} 条已启用（writeback_case → 可执行检测）", ""]
        for rule in rules:
            blocks.append(
                f"- [{rule['rule']}] {rule['case'][:34]}（实现：{rule['impl'][:66]}）")
        blocks.append("")
        # 逻辑层审计（§写回逻辑层检查）：写回前敏感形态 / rawstr 扩容 /
        # 反向语义审计回退 / 互斥一致性 / 重开逻辑验证失败。warn 级全列，
        # note 级只列统计与抽样。
        logic_audit = verification.get("logic_audit") or []
        raw_expansions = verification.get("raw_expansions") or []
        logic_mismatches = verification.get("logic_mismatches") or []
        logic_reverted = verification.get("logic_reverted") or 0
        if (logic_audit or raw_expansions or logic_mismatches or logic_reverted):
            blocks += [_SEPARATOR, "逻辑层审计（写回逻辑敏感形态 / 扩容 / 语义回退 / 重开验证）", ""]
        if logic_mismatches:
            blocks += [f"重开逻辑验证失败：{len(logic_mismatches)} 项（写回整体拒绝）", ""]
            for item in logic_mismatches:
                blocks.append(f"- {item}")
            blocks.append("")
        # 反向语义审计：确定性逻辑键自动回退译文（保留原文）——知识库
        # 案例「UnityEvent 绑定断裂」「显示文本当逻辑键」转规则
        semantic_reverts = [
            a for a in logic_audit if a.get("stage") == "semantic_revert"]
        if semantic_reverts:
            blocks += [
                f"逻辑键自动回退（译文保留原文，防断链）：{logic_reverted} 条", ""]
            for item in semantic_reverts[:30]:
                blocks.append(
                    f"- [{item.get('reason')}] {item.get('original', '')[:40]}"
                    f" → {item.get('translation', '')[:40]}"
                    f"（{item.get('locator', '')[:70]}）")
            if len(semantic_reverts) > 30:
                blocks.append(f"…（其余 {len(semantic_reverts) - 30} 条）")
            blocks.append("")
        semantic_reports = [
            a for a in logic_audit if a.get("stage") == "semantic_report"]
        written_total = verification.get("written") or 0
        if semantic_reports:
            blocks += [
                f"疑似逻辑键（report，已写回需复核）：{len(semantic_reports)} 条", ""]
            for item in semantic_reports[:30]:
                blocks.append(
                    f"- [{item.get('reason')}] {item.get('original', '')[:40]}"
                    f" → {item.get('translation', '')[:40]}"
                    f"（{item.get('locator', '')[:70]}）")
            if len(semantic_reports) > 30:
                blocks.append(f"…（其余 {len(semantic_reports) - 30} 条）")
            # 召回率监控（防识别层哑信号）：疑似逻辑键占比超阈值 → 告警。
            # 高占比说明识别层放行了大量「对象角色不明」的标识符/比较词，
            # 游戏按名查找有断链风险，须人工复核而不是默默写回。
            if written_total and len(semantic_reports) / written_total > 0.05:
                blocks.append(
                    f"⚠ 疑似逻辑键占比 {len(semantic_reports)}/{written_total}"
                    f"（{len(semantic_reports) / written_total:.0%}）> 5%——"
                    f"识别层可能漏判逻辑键，建议复核上述条目后决定回退")
            blocks.append("")
        consistencies = [
            a for a in logic_audit if a.get("stage") == "consistency"]
        if consistencies:
            blocks += [f"同原文互斥一致性：{len(consistencies)} 组（全组保留原文防混排）", ""]
            for item in consistencies[:20]:
                blocks.append(
                    f"- {item.get('original', '')[:40]}"
                    f"（对象 {item.get('obj')}，出现 {item.get('count')} 次）"
                    f"：{item.get('reason', '')}")
            if len(consistencies) > 20:
                blocks.append(f"…（其余 {len(consistencies) - 20} 组）")
            blocks.append("")
        form_audits = [a for a in logic_audit if not a.get("stage")]
        warns = [a for a in form_audits if a.get("severity") == "warn"]
        if warns:
            blocks += [f"疑似逻辑字符串（warn，已写回需人工复核）：{len(warns)} 条", ""]
            for item in warns[:30]:
                blocks.append(
                    f"- [{item.get('pattern')}] {item.get('original', '')[:40]}"
                    f" → {item.get('translation', '')[:40]}"
                    f"（{item.get('locator', '')[:70]}）")
            if len(warns) > 30:
                blocks.append(f"…（其余 {len(warns) - 30} 条见 translated.txt 全量对照）")
            blocks.append("")
        notes = [a for a in form_audits if a.get("severity") != "warn"]
        if notes:
            blocks.append(
                f"短词/常见按钮文本（note，正常可译）：{len(notes)} 条"
                f"（抽样：{[n['original'] for n in notes[:8]]}）")
            blocks.append("")
        if raw_expansions:
            blocks += [f"rawstr 扩容写入：{len(raw_expansions)} 条（译文 UTF-8 字节 > 原文）", ""]
            for item in raw_expansions[:20]:
                blocks.append(
                    f"- {item.get('original', '')[:36]} → {item.get('translation', '')[:36]}"
                    f"（{item.get('src_bytes')} → {item.get('dst_bytes')} 字节，"
                    f"+{item.get('delta_bytes')}）")
            if len(raw_expansions) > 20:
                blocks.append(f"…（其余 {len(raw_expansions) - 20} 条）")
            blocks.append("")
        # 逐条明细：rejected/truncated 全量 + 回显跳过清单（written 条数
        # 大时只列统计与抽样，全文对照由 text/translated.txt 的「写回」字段承担）
        rejected = verification.get("rejected_entries", [])
        if rejected:
            blocks += [f"拒绝条目：{len(rejected)} 条", ""]
            for item in rejected:
                blocks.append(
                    f"- {item.get('locator', '?')}: {item.get('reason', '')}")
            blocks.append("")
        truncated = verification.get("truncated_entries", [])
        if truncated:
            blocks += [f"截断条目：{len(truncated)} 条（容量内部分翻译已写入）", ""]
            for item in truncated:
                blocks.append(
                    f"- {item.get('locator', '?')}: {item.get('reason', '')}"
                    if isinstance(item, dict) else f"- {item}")
            blocks.append("")
        # 回显跳过：译文与原文相同（模型保留原文，写回无变化被正确过滤）
        echoed = [
            row for row in all_rows
            if row.get("status") == "translated"
            and row.get("translation") == row.get("original")
        ]
        if echoed:
            blocks += [f"回显跳过（译文==原文，未写入）：{len(echoed)} 条", ""]
            for row in echoed:
                blocks.append(
                    f"- {row['file_id']}:{row.get('key_path', '')}："
                    f"{str(row.get('original', ''))[:60]}")
            blocks.append("")
            blocks.append("")
        warnings = verification.get("warnings", [])
        if warnings:
            blocks += [f"警告：{len(warnings)} 条", ""]
            for w in warnings:
                blocks.append(f"- {w}")
            blocks.append("")
    path.write_text("\n".join(blocks), encoding="utf-8")


def _register_unity_structure(kb: KnowledgeBase, game_name: str,
                              game_dir: Path, report) -> None:
    """登记 unity_structure（Unity 结构库闭环沉淀 §0.4.4-5）。

    每款游戏闭环登记：Unity 版本/runtime（fingerprint）+ 识别形态清单。
    后续遇到结构相似的新游戏 → 六库检索直接命中先验结构方案。"""
    from hanhua.core.tooling.fingerprint import fingerprint_game  # noqa: PLC0415
    try:
        fp = fingerprint_game(Path(game_dir))
        if fp and fp.unity_version and fp.unity_version != "unknown":
            kb.store.upsert(
                "unity_structure", "unity_version",
                f"游戏 {game_name}：Unity {fp.unity_version} · {fp.runtime}",
                action="info",
                map_to="该版本特征/风险见 unity_version 知识；"
                       f"runtime={fp.runtime} 决定写回路径"
                       "（mono→DLL #US，il2cpp→global-metadata）",
                source="auto", game=game_name)
    except Exception:  # noqa: BLE001
        pass  # 指纹识别失败不阻断流程
    for morph, files, entries in report.morphology_stats:
        kb.store.upsert(
            "unity_structure", "detect_method",
            f"游戏 {game_name} 形态 {morph}：{files} 文件 / {entries} 条",
            action="info", map_to=f"{morph} 形态（先验见识别形态清单）",
            source="auto", game=game_name)


def _register_writeback(kb: KnowledgeBase, game_name: str,
                        result: dict | None, error: str = "") -> None:
    """登记 writeback（写回验证库闭环沉淀 §0.4.4-5）。

    每次写回自动登记结果与关键验证指标——同类写回失败 → 六库检索
    直接命中历史写回方案（含四态闸门/字体层级/备份验证要点）。"""
    if error:
        kb.store.upsert(
            "writeback", "writeback_case",
            f"游戏 {game_name} 写回失败：{error[:60]}",
            action="check", map_to="按写回失败分类定位 writer 代码路径，"
                                   "根因修复 + 回归测试（§4 问题分类表）",
            source="auto", game=game_name)
        return
    if result is None:
        return
    verification = result.get("verification", {})
    gates = verification.get("gates", {})
    gate_fails = [name for name, item in gates.items()
                  if isinstance(item, dict) and name != "overall"
                  and item.get("status") == "fail"]
    overall = verification.get("overall")
    if gate_fails:
        map_to = ("验证要点：输入保护/重开验证/四态闸门/字体层级/备份齐全"
                  f"；未通过闸门：{'、'.join(gate_fails)}")
    else:
        map_to = "四态闸门全绿，按 test_flow 流程实测游戏验证"
    kb.store.upsert(
        "writeback", "writeback_case",
        f"游戏 {game_name} 写回完成：总体 {overall} · "
        f"译文 {verification.get('written_translations')} 条 · "
        f"变更文件 {verification.get('changed_files')} 个",
        action="verify", map_to=map_to,
        source="auto", game=game_name)


def run_game(game_dir: Path, *, batch: int | None = None,
             do_translate: bool = True, do_writeback: bool = True,
             keep_library: bool = False,
             app_dir: Path | None = None) -> int:
    """单游戏完整流程。返回退出码：0=流程完成（待分析），2=扫描阻断。"""
    game_dir = Path(game_dir).resolve()
    if not game_dir.is_dir():
        print(f"[错误] 游戏目录不存在：{game_dir}")
        return 3
    game_name = _safe_name(game_dir.name)
    out_dir = Path(DEFAULT_OUT_BASE) / game_name
    out_text = out_dir / "text"
    out_writeback = out_dir / "writeback"
    out_text.mkdir(parents=True, exist_ok=True)
    out_writeback.mkdir(parents=True, exist_ok=True)

    # 独立项目库：固定 app_dir 按游戏 slug 分库。每次运行强制从零开始——
    # store.upsert 的「pending 不覆盖旧状态」断点续传语义会掩盖识别规则升级
    # （0.25.0 实证：DISPLAY_WORDS 修复后重扫，旧 skipped 条目判定未重跑），
    # 地毯式排查要求每次用最新代码重新判定，翻译记忆也一并清除（防记忆伪影）。
    # 注意：多游戏并行时只清理**本游戏**的 slug 目录——删整个 projects/
    # 会把并行 runner 的工作区一并删除（crash/crusty 并行实证：
    # WinError 32 project.db 被占用，后启动方删除先启动方工作区致其崩溃）。
    if app_dir is None:
        app_dir = Path.home() / ".hanhua_sweep"
    app_dir = Path(app_dir)
    projects_dir = app_dir / "projects"
    my_slug = hashlib.md5(
        str(Path(game_dir).expanduser().absolute()).encode("utf-8")
    ).hexdigest()[:10]
    my_dir = projects_dir / my_slug
    if my_dir.exists():
        shutil.rmtree(my_dir, ignore_errors=False)
    app_dir.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)

    settings = SettingsStore(REAL_USER_DIR / "settings.json")
    settings.load()
    api = settings.api

    print(f"═══ 开始游戏：{game_name} ═══")
    print(f"输出：{out_dir}")
    print(f"项目库：{app_dir}")

    # ── 1 扫描 ──
    print("[1/4] 扫描识别…")
    project = Project.open_game_dir(game_dir, app_dir)
    report = project.scan_all()
    profile = project.profile
    print(f"  文本文件 {report.text_files} · v2 文件 {report.v2_files}"
          f" · 识别条目 {report.recognized_entries}")
    for morph, files, entries in report.morphology_stats:
        print(f"  形态 {morph}: {files} 文件 / {entries} 条")
    # 知识库闭环：登记 Unity 结构（版本/runtime/形态）——后续结构相似的
    # 新游戏六库检索直接命中先验（§0.4.4-5 每游戏登记 unity_structure）
    struct_kb = KnowledgeBase(REAL_USER_DIR / "knowledge.db")
    _register_unity_structure(struct_kb, game_name, game_dir, report)
    struct_kb.close()
    for warning in report.warnings:
        print(f"  [警告] {warning}")
    if report.warnings:
        (out_dir / "scan_warnings.txt").write_text(
            "\n".join(report.warnings), encoding="utf-8")
    if not report.unblocked:
        print("[阻断] 扫描未通过，无法继续翻译/写回（见 summary.md）")
        _write_summary(project, report, None, None, game_name, out_dir,
                       blocked=True)
        return 2

    # ── 2 翻译（真实本地模型） ──
    stats = None
    if do_translate:
        print("[2/4] 翻译（真实本地模型）…")
        manager = LocalModelManager(PROJECT_ROOT, startup_timeout=180)
        try:
            runtime = manager.ensure_running(api)
            api = replace(api, base_url=runtime.endpoint,
                          api_key=runtime.api_key, model=runtime.model)
            print(f"  服务就绪：{runtime.backend.upper()} · 端口 {runtime.port}")
        except Exception as exc:  # noqa: BLE001
            print(f"[错误] 本地模型启动失败：{exc}")
            _write_summary(project, report, None, None, game_name, out_dir,
                           error=f"本地模型启动失败：{exc}")
            return 4

        glossary = GlossaryStore(REAL_USER_DIR / "glossary.db")
        glossary.init_schema()
        glossary_prompt = glossary.format_for_prompt()
        glossary_rows = glossary.list_all()

        # 知识库：跨游戏沉淀的特殊情况规则（全大写动作指令/间隔动作词等
        # 「该翻未翻」模式 + 处置策略），注入翻译，跑完 learn 再积累。
        # format_reference_pairs 的译例并入 glossary——native 降级重试
        # （Hy-MT2 无 system prompt）靠 references 的 terms 机制带出译例
        knowledge = KnowledgeBase(REAL_USER_DIR / "knowledge.db")
        knowledge_prompt = knowledge.format_for_prompt()
        knowledge_pairs = knowledge.format_reference_pairs()
        knowledge.close()

        entries = [_entry_from_row(r) for r in project.store.get_entries()]
        collected_names = collect_known_names(
            [str(e.original or "") for e in entries])
        system = build_system_prompt(
            profile, glossary_prompt,
            known_names=glossary.known_names_for(collected_names),
            knowledge_lines=knowledge_prompt,
        )
        client = create_client(api)
        lang = f"{profile.source_lang or 'auto'}→{profile.target_lang or 'zh-CN'}"
        batch_size = batch if batch is not None else max(1, int(api.local_batch_size))
        concurrency = runtime.parallel if api.mode == "local" else api.concurrency
        translator = BatchTranslator(
            client, batch_size=batch_size, concurrency=concurrency,
            memory=project.store, model=api.model, lang=lang,
            system_prompt=system,
            glossary=[(row["term"], row["translation"])
                      for row in glossary_rows] + knowledge_pairs,
        )
        from hanhua.core.models import is_actionable_translation
        pending_count = sum(is_actionable_translation(e) for e in entries)
        print(f"  条目 {len(entries)} · 待翻译 {pending_count}"
              f" · 批量 {batch_size} · 并发 {concurrency}")
        stats = translator.run(entries, progress_cb=None)
        print(f"  完成：{stats.done} 条（记忆 {stats.from_memory}）"
              f" · 失败 {stats.failed} · 请求 {stats.requests}"
              f" · 耗时 {stats.elapsed:.1f}s")
        # 术语库学习：把本游戏确认保留的专名写入全局库，后续游戏自动复用
        learn_glossary = GlossaryStore(REAL_USER_DIR / "glossary.db")
        learn_glossary.init_schema()
        learned = learn_glossary.learn_proper_names(
            entries, collected_names, game_name)
        learn_glossary.close()
        if learned:
            print(f"  术语库学习：新增 {learned} 条专名（累计可跨游戏复用）")
        # 知识库学习：从「该翻未翻」回显条目沉淀新模式（幂等，hits+1）
        learn_knowledge = KnowledgeBase(REAL_USER_DIR / "knowledge.db")
        learned_kb, hits_kb = learn_knowledge.learn(
            entries, game_name, names=set(collected_names))
        learn_knowledge.close()
        if learned_kb or hits_kb:
            print(f"  知识库学习：新增 {learned_kb} 条规则"
                  f" · 累计命中 {hits_kb} 条（特殊情况模式沉淀）")
        # 失败案例自动沉淀：按质量原因组合聚合，同模式每款游戏 1 条
        # （幂等）——「经验大脑」持续积累，修复后再由 knowledge_seed.py
        # 补精确方案；识别层失败（结构规则）由手工案例覆盖
        failed_groups: dict[tuple, list[TextEntry]] = {}
        for e in entries:
            if e.status == "translated" or not e.translation:
                continue
            reasons = tuple(e.meta.get("quality_reasons", ()))
            if not reasons:
                continue
            failed_groups.setdefault(reasons, []).append(e)
        case_kb = KnowledgeBase(REAL_USER_DIR / "knowledge.db")
        case_added = 0
        for reasons, group in failed_groups.items():
            src = str(group[0].original).replace("\n", "\\n")[:48]
            if case_kb.record_case(
                    game=game_name, fail_type="翻译",
                    problem=f"翻译失败模式[{src}…]",
                    root_cause="质量门原因: " + ", ".join(reasons),
                    fix="见本场 fix record（降级链或结构规则）",
                    symptom=f"{len(group)} 条同模式失败",
                    impact="待核", version="", source="auto"):
                case_added += 1
            # 历史案例智能复用：同模式历史案例 → 提示已验证方案（避免重查）
            for past in case_kb.match_case(src, limit=2):
                if "见本场 fix record" in str(past.get("note", "")):
                    continue
                note = past["note"]
                try:
                    parsed = json.loads(note)
                    hint = (f"[知识库] 命中历史案例 {parsed.get('fail_no')} "
                            f"{parsed.get('game')}：{parsed.get('solution', '')[:70]}")
                except (ValueError, TypeError):
                    hint = f"[知识库] 命中历史案例：{note[:90]}"
                print(hint)
            # 质量库联动（死区接入，§0.4.4-5 六库闭环）：质量门拒绝时除
            # fail_case 外还检索 quality 域（scoring_case/common_error/
            # term_consistency 规则知识）——质量规则真实进入失败处理决策，
            # 而非只沉淀不查（用户两次追问知识库不是摆设）
            for past in case_kb.search_keyword(
                    src, domains=("quality",))[:2]:
                print(f"[知识库] 命中质量规则 {past['kind']}："
                      f"{str(past.get('note', ''))[:90]}")
        case_kb.close()
        if case_added:
            print(f"  失败案例沉淀：新增 {case_added} 种失败模式入库")
    else:
        print("[2/4] 跳过翻译（--no-translate）")

    # ── 3 写回（真实）──（先写回再导出，导出才能标注每条实际写回状态）
    writeback_result = None
    writeback_error = None
    if do_writeback:
        print("[3/4] 写回（真实）…")
        try:
            writeback_result = project.write_all(
                font_config=settings.font,
                stage_cb=lambda stage: print(
                    f"  [{stage.phase}] {stage.message}"),
            )
            print(f"  写回成功：{writeback_result.get('text_files')} 文本文件"
                  f" · {writeback_result['verification'].get('written_translations')}"
                  " 条译文 · "
                  f"总体 {writeback_result['verification'].get('overall')}")
        except Exception as exc:  # noqa: BLE001
            writeback_error = str(exc)
            print(f"[错误] 写回失败：{exc}")
    else:
        print("[3/4] 跳过写回（--no-writeback）")
    _export_writeback_record(project, out_writeback, profile,
                             writeback_result,
                             error_title=("写回失败" if writeback_error else ""),
                             error_detail=writeback_error or "")
    # 知识库闭环：写回结果自动登记 writeback 域（§0.4.4-5）
    wb_kb = KnowledgeBase(REAL_USER_DIR / "knowledge.db")
    _register_writeback(wb_kb, game_name, writeback_result, writeback_error)
    # 组件兼容库联动（死区接入）：写回失败时按错误信息检索 component_compat
    # 域（乱码/方块/黑屏/Dropdown 等组件兼容知识）——组件库真实进入写回
    # 失败处理，而非只种不用
    if writeback_error:
        for past in wb_kb.search_keyword(
                writeback_error, domains=("component_compat",))[:3]:
            print(f"[知识库] 命中组件兼容 {past['kind']}："
                  f"{str(past.get('note', ''))[:90]}")
    wb_kb.close()

    # ── 4 导出三类文本记录（含逐条写回状态）──
    print("[4/4] 导出文本记录…")
    writeback_status: dict[str, str] | None = None
    if writeback_result is not None:
        writeback_status = {
            item["locator"]: item["reason"]
            for item in writeback_result["verification"].get(
                "rejected_entries", [])
        }
    _export_text_records(project, out_text, profile,
                         model_name=str(api.model or ""),
                         writeback_status=writeback_status)
    translated = project.store.count("translated")
    failed = project.store.count("failed")
    skipped = project.store.count("skipped")
    print(f"  translated {translated} · failed {failed} · skipped {skipped}")

    _write_summary(project, report, stats, writeback_result, game_name,
                   out_dir, error=writeback_error)
    print(f"═══ {game_name} 记录完成：{out_dir} ═══")
    # 闭环成功 → 删汉化输出目录与发布备份，只保留原版（做完一个删一个）。
    # 写回失败不删（需排查/回滚，备份是回滚依据）。
    if writeback_result is not None and not writeback_error:
        _cleanup_hanhua_output(game_dir)
    if not keep_library:
        _discard_sweep_library(project)
    return 1 if writeback_error else 0


def _rmtree_force(path: Path) -> None:
    """删除目录树，Windows 上先清只读属性再删。

    从游戏目录复制的文件（tool-jobs 的 game.exe/global-metadata.dat）
    常带只读位——shutil.rmtree 遇只读文件 PermissionError，残留累积
    （0.25.0 实证：WinError 5 拒绝访问，每轮残留 tool-jobs 输入副本）。
    """
    def _clear_readonly(func, p, _exc):
        os.chmod(p, 0o777)
        func(p)
    shutil.rmtree(path, onerror=_clear_readonly)


def _cleanup_hanhua_output(game_dir: Path) -> None:
    """闭环后删除汉化输出目录与全部发布备份（只保留原版游戏目录）。

    backup 由写回发布流程生成（`.{name}_汉化.backup-<32hex>`，供失败
    回滚）；闭环成功后无回滚需求，一并删除，避免每轮残留 353MB。
    """
    out = game_dir.parent / (game_dir.name + "_汉化")
    targets = [out] + list(game_dir.parent.glob(
        f".{game_dir.name}_汉化.backup-*"))
    for target in targets:
        try:
            if target.exists():
                _rmtree_force(target)
                print(f"  已清理：{target.name}")
        except Exception as exc:  # noqa: BLE001
            print(f"[警告] 汉化输出清理失败（{target.name}）：{exc}")


def _discard_sweep_library(project) -> None:
    """清理本游戏的扫描/翻译中间库（仅**本游戏 slug** 目录）。

    Windows 上 sqlite 连接未关闭时 rmtree 会因文件句柄失败（0.25.0 实证：
    库残留导致重扫复用旧状态）。先 close 连接，删除失败则显式告警。

    只删本游戏 slug 目录（store.db 的父目录），不删整个 app_dir——
    双游戏并行时删 projects/ 会把并行 runner 的工作区一并删除
    （crash/crusty 并行实证：WinError 32 project.db 被占用；death-trips
    清理时 deepest-sword 库正被使用同证）。启动清理（§run 前 my_dir）
    与本处结束清理必须保持一致的目标目录。
    """
    try:
        project.store.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        _rmtree_force(Path(project.store.db).parent)
    except Exception as exc:  # noqa: BLE001
        print(f"[警告] sweep 库清理失败（残留可能影响下次判定）：{exc}")


def _write_summary(project, report, stats, writeback_result, game_name,
                   out_dir: Path, *, blocked: bool = False,
                   error: str = "") -> None:
    lines = [
        f"# {game_name} 地毯式排查记录",
        "",
        f"- 游戏目录：{project.game_dir}",
        f"- 时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 1 识别",
        f"- 文本文件：{report.text_files} · 二进制资源：{report.v2_files}",
        f"- 识别条目：{report.recognized_entries}",
        "- 形态统计：",
        *[f"  - {m}: {f} 文件 / {e} 条" for m, f, e in report.morphology_stats],
        "- 状态分布：",
        *[f"  - {status}: {count}" for status, count in report.status_counts],
        "- 置信度分布：",
        *[f"  - {confidence}: {count}"
          for confidence, count in report.confidence_counts],
        "- 工具状态：",
        *[f"  - {item.tool_id}: {item.state}" for item in report.tool_statuses],
        "- 阻断步骤：",
        *[f"  - {step.step_id}: {step.status} {step.reason}"
          for step in report.route
          if step.required and step.status != "succeeded"],
    ]
    if report.warnings:
        lines += ["- 警告：", *[f"  - {w}" for w in report.warnings]]
    lines.append("")
    if blocked:
        lines += ["## 状态", "❌ 扫描阻断，未翻译未写回（分析：为什么阻断？）", ""]
    elif error:
        lines += ["## 状态", f"⚠️ 流程异常：{error}", ""]
    elif stats is not None:
        lines += [
            "## 2 翻译",
            f"- 总条目：{stats.total} · 完成：{stats.done}"
            f"（记忆命中 {stats.from_memory}） · 失败：{stats.failed}",
            f"- 请求：{stats.requests} · 输入 {stats.input_tokens} tokens"
            f" · 输出 {stats.output_tokens} tokens",
            f"- 耗时：{stats.elapsed:.1f}s · 吞吐 {stats.rate_per_minute:.0f} 条/分",
            "",
        ]
    else:
        lines += ["## 2 翻译", "- （未翻译）", ""]
    if writeback_result is not None:
        verification = writeback_result.get("verification", {})
        lines += [
            "## 3 写回",
            f"- 文本文件：{writeback_result.get('text_files')}"
            f" · 写入译文：{verification.get('written_translations')}",
            f"- 输入保护：{verification.get('input_protected')}"
            f" · 重开验证：{verification.get('reopen_verified')}"
            f" · 变更文件：{verification.get('changed_files')}",
            f"- 总体闸门：{verification.get('overall')}"
            f" · 字体：{verification.get('font_level')}",
            "",
        ]
    else:
        lines += ["## 3 写回", "- （未写回）", ""]
    lines += [
        "## 4 分析（待办）",
        "- [ ] 成功文本质量抽检（译文是否得当/是否无关文本）",
        "- [ ] 失败文本根因系统彻查（同类问题全解）",
        "- [ ] 跳过文本逐条判定（该翻→识别修复；不该翻→记录判定）",
        "- [ ] 写回问题根源修复",
        "- [ ] 修复后用升级版本重跑本游戏全流程（闭环）",
        "- [ ] 闭环后删除汉化输出目录",
        "",
        "记录文件：",
        "- text/translated.txt / text/failed.txt / text/skipped.txt",
        "- writeback/writeback.txt",
        "",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="地毯式排查单游戏 runner")
    parser.add_argument("game_dir", help="游戏目录")
    parser.add_argument("--batch", type=int, default=None,
                        help="覆盖本地批量大小（默认读 settings）")
    parser.add_argument("--no-translate", action="store_true",
                        help="跳过翻译（只扫描+记录）")
    parser.add_argument("--no-writeback", action="store_true",
                        help="跳过写回")
    parser.add_argument("--keep-library", action="store_true",
                        help="保留扫描中间库（调试）")
    args = parser.parse_args()
    return run_game(
        args.game_dir,
        batch=args.batch,
        do_translate=not args.no_translate,
        do_writeback=not args.no_writeback,
        keep_library=args.keep_library,
    )


if __name__ == "__main__":
    sys.exit(main())
