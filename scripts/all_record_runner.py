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
import json
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from hanhua.core.glossary import GlossaryStore  # noqa: E402
from hanhua.core.local_model import LocalModelManager  # noqa: E402
from hanhua.core.models import TextEntry  # noqa: E402
from hanhua.core.project import Project  # noqa: E402
from hanhua.core.prompts import build_system_prompt  # noqa: E402
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


def _export_text_records(project, out_text: Path, profile) -> None:
    """导出 translated/failed/skipped 三类文本全字段记录。"""
    store = project.store
    categories = {
        "translated": ("成功文本", store.get_entries(status="translated")),
        "failed": ("失败文本", store.get_entries(status="failed")),
        "skipped": ("跳过文本", store.get_entries(status="skipped")),
    }
    for category, (title, rows) in categories.items():
        path = out_text / f"{category}.txt"
        blocks = [
            f"游戏：{profile.game_name or Path(project.game_dir).name}",
            f"导出时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
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
            blocks += [
                _SEPARATOR,
                f"[{index}] {title}",
                f"来源：{source}",
                f"键位：{row.get('key_path', '')}",
                f"原文：{row.get('original', '')}",
                f"译文：{row.get('translation', '') or '（无）'}",
                f"置信度：{confidence}",
                f"原因：{reason or '—'}",
                f"角色：{role or '—'}",
                f"质量评分：{quality_text}（passed={quality_passed}）",
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
        rejected = verification.get("rejected_entries", [])
        if rejected:
            blocks += [f"拒绝条目：{len(rejected)} 条", ""]
            for item in rejected:
                blocks.append(
                    f"- {item.get('locator', '?')}: {item.get('reason', '')}")
            blocks.append("")
        truncated = verification.get("truncated_entries", [])
        if truncated:
            blocks += [f"截断条目：{len(truncated)} 条", ""]
            for item in truncated:
                blocks.append(
                    f"- {item.get('locator', '?')}: {item.get('reason', '')}")
            blocks.append("")
        warnings = verification.get("warnings", [])
        if warnings:
            blocks += [f"警告：{len(warnings)} 条", ""]
            for w in warnings:
                blocks.append(f"- {w}")
            blocks.append("")
    path.write_text("\n".join(blocks), encoding="utf-8")


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

    # 独立项目库（幂等）：固定 app_dir 按游戏 slug 分库，重跑可复用翻译记忆
    if app_dir is None:
        app_dir = Path.home() / ".hanhua_sweep"
    app_dir = Path(app_dir)
    app_dir.mkdir(parents=True, exist_ok=True)

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
        glossary.close()

        system = build_system_prompt(profile, glossary_prompt)
        client = create_client(api)
        lang = f"{profile.source_lang or 'auto'}→{profile.target_lang or 'zh-CN'}"
        batch_size = batch if batch is not None else max(1, int(api.local_batch_size))
        concurrency = runtime.parallel if api.mode == "local" else api.concurrency
        translator = BatchTranslator(
            client, batch_size=batch_size, concurrency=concurrency,
            memory=project.store, model=api.model, lang=lang,
            system_prompt=system,
            glossary=[(row["term"], row["translation"])
                      for row in glossary_rows],
        )
        entries = [_entry_from_row(r) for r in project.store.get_entries()]
        from hanhua.core.models import is_actionable_translation
        pending_count = sum(is_actionable_translation(e) for e in entries)
        print(f"  条目 {len(entries)} · 待翻译 {pending_count}"
              f" · 批量 {batch_size} · 并发 {concurrency}")
        stats = translator.run(entries, progress_cb=None)
        print(f"  完成：{stats.done} 条（记忆 {stats.from_memory}）"
              f" · 失败 {stats.failed} · 请求 {stats.requests}"
              f" · 耗时 {stats.elapsed:.1f}s")
    else:
        print("[2/4] 跳过翻译（--no-translate）")

    # ── 3 导出三类文本记录 ──
    print("[3/4] 导出文本记录…")
    _export_text_records(project, out_text, profile)
    translated = project.store.count("translated")
    failed = project.store.count("failed")
    skipped = project.store.count("skipped")
    print(f"  translated {translated} · failed {failed} · skipped {skipped}")

    # ── 4 写回（真实） ──
    writeback_result = None
    writeback_error = None
    if do_writeback:
        print("[4/4] 写回（真实）…")
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
        print("[4/4] 跳过写回（--no-writeback）")
    _export_writeback_record(project, out_writeback, profile,
                             writeback_result,
                             error_title=("写回失败" if writeback_error else ""),
                             error_detail=writeback_error or "")

    _write_summary(project, report, stats, writeback_result, game_name,
                   out_dir, error=writeback_error)
    print(f"═══ {game_name} 记录完成：{out_dir} ═══")
    if not keep_library:
        _discard_sweep_library(project)
    return 1 if writeback_error else 0


def _discard_sweep_library(project) -> None:
    """清理本游戏的扫描/翻译中间库（仅 sweep 专用目录内）。"""
    try:
        shutil.rmtree(project.app_dir, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass


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
