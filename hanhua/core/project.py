from __future__ import annotations
import datetime
import hashlib
import os
import gc
import csv
import io
import inspect
import json
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from hanhua.core.extractor import parse_file
from hanhua.core.formats import read_text
from hanhua.core.formats.csv_format import pick_target_col
from hanhua.core.font_support import (
    FontInstallResult,
    FontProviderCapability,
    install_font_override,
    resolve_font_provider,
)
from hanhua.core.unity.font_replace import install_static_fonts
from hanhua.core.memory import ProjectStore
from hanhua.core.models import FontConfig, GameProfile
from hanhua.core.paths import (_is_reparse_point, ensure_trusted_root,
                               resolve_relative_under)
from hanhua.core.placeholders import is_key_style_identifier, looks_like_key_field
from hanhua.core.quality import is_write_ready
from hanhua.core.scanner import discover
from hanhua.core.tooling.fingerprint import GameFingerprint, fingerprint_game
from hanhua.core.tooling.morphology import classify_morphology
from hanhua.core.tooling.player_layout import discover_player_candidates
from hanhua.core.tooling.il2cpp_dumper import compare_literals, run_il2cpp_dumper
from hanhua.core.tooling.manifest import ToolRegistry, ToolStatus
from hanhua.core.tooling.planner import (
    BackendStep,
    plan_backends,
    plan_is_completable,
    plan_is_unblocked,
)
from hanhua.core.tooling.runner import IsolatedToolRunner
from hanhua.core.unity import extractor as unity_extractor
from hanhua.core.unity import il2cpp as il2cpp_extractor
from hanhua.core.unity.il2cpp import SUPPORTED_LITERAL_RECORD_SIZES
from hanhua.core.unity import mono_dll as mono_extractor
from hanhua.core.unity.writer import (_should_write_entry, copy_game_dir,
                                      write_back_v2)
from hanhua.core.writer import write_back as write_back_text


@dataclass(frozen=True)
class WritebackStage:
    phase: str
    message: str
    current: int = 0
    total: int = 0


def _emit_writeback_stage(
        callback: Callable[[WritebackStage], None] | None,
        phase: str,
        message: str,
        current: int = 0,
        total: int = 0) -> None:
    if callback is None:
        return
    try:
        callback(WritebackStage(phase, message, current, total))
    except Exception:
        # Progress consumers must not invalidate an already verified write.
        return


def _is_owned_backup(backup: Path, out_dir: Path) -> bool:
    try:
        same_parent = backup.parent.resolve() == out_dir.parent.resolve()
    except OSError:
        return False
    prefix = f".{out_dir.name}.backup-"
    suffix = backup.name[len(prefix):] if backup.name.startswith(prefix) else ""
    return (same_parent and len(suffix) == 32
            and all(char in "0123456789abcdef" for char in suffix))


def _schedule_backup_cleanup(
        keep: Path,
        out_dir: Path,
        stage_cb: Callable[[WritebackStage], None] | None) -> None:
    """发布成功后后台清理「更早」的旧版本备份，保留本次备份供回滚。

    文档1 §3.3/§17：发布成功后必须可一键回滚到发布前版本——本次
    备份保留在磁盘（manifest 记录其路径），只删除更早的发布遗留。
    """
    if not _is_owned_backup(keep, out_dir):
        _emit_writeback_stage(
            stage_cb, "cleanup_warning",
            f"旧版本备份路径未通过安全校验，已保留：{keep}")
        return

    _emit_writeback_stage(
        stage_cb, "cleanup_pending",
        f"正在后台清理更早的旧版本（本次备份 {keep.name} 保留供回滚）")

    def cleanup() -> None:
        try:
            candidates = [
                p for p in out_dir.parent.glob(f".{out_dir.name}.backup-*")
                if p != keep and _is_owned_backup(p, out_dir)]
            for old in candidates:
                shutil.rmtree(old)
        except Exception as exc:  # noqa: BLE001 - cleanup failure is non-fatal
            _emit_writeback_stage(
                stage_cb, "cleanup_warning",
                f"旧版本清理失败，已保留：{type(exc).__name__}")
        else:
            _emit_writeback_stage(
                stage_cb, "cleanup_complete",
                "更早的旧版本后台清理完成（本次备份保留）")

    try:
        threading.Thread(
            target=cleanup,
            name=f"hanhua-cleanup-{out_dir.name}",
            daemon=True,
        ).start()
    except RuntimeError:
        _emit_writeback_stage(
            stage_cb, "cleanup_warning", f"无法启动旧版本清理线程，已保留：{keep}")


def _slug(
        game_dir: Path, player_root: Path | None = None,
        player_executable: Path | None = None) -> str:
    if player_root is None and player_executable is None:
        return hashlib.md5(str(game_dir).encode("utf-8")).hexdigest()[:10]
    identity = "\0".join((
        str(game_dir),
        player_root.as_posix() if player_root is not None else "",
        player_executable.as_posix() if player_executable is not None else "",
    ))
    return hashlib.md5(identity.encode("utf-8")).hexdigest()[:10]


def _replace_directory(source: Path, target: Path) -> None:
    """在 Windows 短暂句柄锁下有限重试同卷目录改名。"""
    gc.collect()
    for attempt in range(8):
        try:
            source.replace(target)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.5)


def _reject_store_inside_out_dir(app_dir: Path, out_dir: Path) -> None:
    """发布阶段会把 out_dir 整体改名；若项目数据目录位于其内，SQLite 句柄
    会阻止目录重命名（WinError 5）。提前给出明确错误而非在发布时失败。"""
    try:
        app_dir.resolve().relative_to(out_dir.resolve())
    except ValueError:
        return
    raise RuntimeError(
        "项目数据目录不能位于汉化输出目录内，否则写回发布时无法替换旧输出。"
        "请在设置中把项目数据目录移到输出目录之外。"
    )

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hashes(root: Path) -> dict[str, str]:
    """返回普通文件的稳定相对路径哈希；符号链接与 junction 不作为可写输入跟随。

    rglob 会跟随 Windows junction 下探（islink 为 False），游戏目录中一旦出现
    指向祖先的链接（OneDrive 同步、汉化副本发布残留）会无限递归卡死扫描。
    os.walk + reparse 剪枝保证树遍历终止。
    """
    hashes: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [
            name for name in sorted(dirnames)
            if not _is_reparse_point(Path(dirpath) / name)
        ]
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_file() and not path.is_symlink():
                hashes[path.relative_to(root).as_posix()] = _sha256_file(path)
    return hashes


def _layout_identity(fingerprint: GameFingerprint) -> tuple:
    root = fingerprint.game_dir

    def relative(path: Path | None) -> str | None:
        return path.relative_to(root).as_posix() if path is not None else None

    return (
        fingerprint.layout_kind,
        relative(fingerprint.player_root),
        relative(fingerprint.executable),
        relative(fingerprint.data_dir),
        tuple(relative(path) for path in fingerprint.application_assemblies),
        relative(fingerprint.game_assembly),
        relative(fingerprint.metadata),
    )


def _count_write_ready_translations(
        store: ProjectStore, text_only: bool = False) -> int:
    files = {item["id"]: item for item in store.get_files()}
    count = 0
    for entry in store.get_entries():
        file_record = files.get(entry["file_id"])
        if file_record is None or not is_write_ready(
                entry.get("status", ""), entry.get("translation", ""),
                entry.get("meta", "{}")):
            continue
        if entry["translation"] == entry["original"]:
            continue
        if file_record["format"].startswith("v2_"):
            if text_only:
                continue
            if not _should_write_entry(entry):
                continue
        elif is_key_style_identifier(entry["original"]) or (
                file_record["format"] == "json"
                and looks_like_key_field(entry["key_path"].rsplit("/", 1)[-1])):
            continue
        count += 1
    return count


def _runtime_exact_translations(store: ProjectStore) -> dict[str, str]:
    """返回无歧义、可写且明确用于显示的运行时原文映射。"""
    candidates: dict[str, set[str]] = {}
    for entry in store.get_entries():
        try:
            meta = json.loads(entry.get("meta", "{}") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        original = entry.get("original", "")
        translation = entry.get("translation", "")
        if (
            meta.get("disposition") != "translate"
            or original == translation
            or not is_write_ready(
                entry.get("status", ""), translation, meta)
        ):
            continue
        candidates.setdefault(original, set()).add(translation)
    unambiguous = {
        original: next(iter(translations))
        for original, translations in sorted(candidates.items())
        if len(translations) == 1
    }
    sources = set(unambiguous)
    return {
        original: translation
        for original, translation in unambiguous.items()
        if translation not in sources
    }


def _expected_text_translations(store: ProjectStore) -> dict[str, dict[str, str]]:
    expected: dict[str, dict[str, str]] = {}
    for file_record in store.get_files():
        if file_record["format"].startswith("v2_"):
            continue
        for entry in store.get_entries():
            if entry["file_id"] != file_record["id"] or not is_write_ready(
                    entry.get("status", ""), entry.get("translation", ""),
                    entry.get("meta", "{}")):
                continue
            if entry["translation"] == entry["original"]:
                continue
            if is_key_style_identifier(entry["original"]) or (
                    file_record["format"] == "json"
                    and looks_like_key_field(
                        entry["key_path"].rsplit("/", 1)[-1])):
                continue
            expected.setdefault(file_record["id"], {})[
                entry["key_path"]] = entry["translation"]
    return expected


def _reopen_written_outputs(store: ProjectStore, output_root: Path) -> int:
    """逐 file/key_path 重开核对普通文本译文，返回验证成功的实际补丁数。"""
    files = {item["id"]: item for item in store.get_files()}
    entries = store.get_entries()
    expected_by_file = _expected_text_translations(store)
    verified = 0
    for file_id, expected in expected_by_file.items():
        file_record = files[file_id]
        output = resolve_relative_under(output_root, file_record["rel_path"])
        if not output.is_file():
            raise RuntimeError(f"文本重开验证缺少输出文件：{file_record['rel_path']}")
        if file_record["format"] == "csv":
            delimiter = "\t" if output.suffix.lower() == ".tsv" else ","
            rows = list(csv.reader(io.StringIO(read_text(output)), delimiter=delimiter))
            header = rows[0] if rows else []
            target_col = pick_target_col(header, "zh-CN")
            actual = {}
            for entry in entries:
                if entry["file_id"] != file_id or entry["key_path"] not in expected:
                    continue
                meta = json.loads(entry.get("meta") or "{}")
                row = int(meta.get("row", -1))
                if target_col is not None and 0 <= row < len(rows) \
                        and target_col < len(rows[row]):
                    actual[entry["key_path"]] = rows[row][target_col]
            mismatched = [
                key_path for key_path, translation in expected.items()
                if actual.get(key_path) != translation
            ]
        elif file_record["format"] == "txt":
            # 行号定位 + 行内容检查：txt 的 key_path 是 line/N | plain/N |
            # kv/<key>/N（N 为行号）。整行翻译可能改变行首结构（如去掉前导
            # tab 后重开解析会从 plain 变成 kv），严格 key 匹配会误判未写入；
            # 译文写入文件后，其所在行必然包含该译文文本。
            lines = read_text(output).splitlines()
            mismatched = []
            for key_path, translation in expected.items():
                try:
                    line_no = int(key_path.rsplit("/", 1)[1])
                except (ValueError, IndexError):
                    mismatched.append(key_path)
                    continue
                if line_no >= len(lines) or translation not in lines[line_no]:
                    mismatched.append(key_path)
        else:
            parsed = parse_file(output, file_id=file_id)
            actual = {entry.key_path: entry.original for entry in parsed.entries}
            mismatched = [
                key_path for key_path, translation in expected.items()
                if actual.get(key_path) != translation
            ]
        if mismatched:
            raise RuntimeError(
                f"译文未写入或 locator 重开不一致：{file_record['rel_path']} "
                f"{', '.join(mismatched[:5])}")
        verified += len(expected)
    return verified


def _set_route_status(route: tuple[BackendStep, ...], step_id: str,
                      status: str, reason: str | None = None) -> tuple[BackendStep, ...]:
    return tuple(
        replace(step, status=status,
                confidence="low" if status in {"failed", "blocked"} else step.confidence,
                reason=reason or step.reason)
        if step.step_id == step_id else step
        for step in route
    )


def _is_dumper_version_gap(reason: str, fingerprint: GameFingerprint) -> bool:
    """dumper 失败是否为版本缺口：错误描述不支持 metadata 版本，且 native
    解析器声明支持该版本，且能实际解析成功（三证据齐备才降级）。"""
    lowered = reason.casefold()
    if "not a supported version" not in lowered \
            and "notsupportedexception" not in lowered:
        return False
    if fingerprint.metadata_version not in SUPPORTED_LITERAL_RECORD_SIZES:
        return False
    try:
        raw = fingerprint.metadata.read_bytes()
        il2cpp_extractor.parse_string_literals(raw)
    except Exception:  # noqa: BLE001 native 解析失败则不构成降级证据
        return False
    return True


@dataclass(frozen=True)
class ToolAnalysisResult:
    tool_id: str
    status: str
    required: bool
    cache_hit: bool = False
    elapsed_ms: int = 0
    details: tuple[tuple[str, str], ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class PipelineEvent:
    phase: str
    status: str
    message: str
    current: int = 0
    total: int = 0


@dataclass(frozen=True)
class AnalysisReport:
    fingerprint: GameFingerprint
    tool_statuses: tuple[ToolStatus, ...]
    route: tuple[BackendStep, ...]
    font_capability: FontProviderCapability
    text_files: int = 0
    v2_files: int = 0
    recognized_entries: int = 0
    status_counts: tuple[tuple[str, int], ...] = ()
    confidence_counts: tuple[tuple[str, int], ...] = ()
    tool_results: tuple[ToolAnalysisResult, ...] = ()
    input_protected: bool = True
    unblocked: bool = False
    completable: bool = False
    warnings: tuple[str, ...] = ()
    # 形态覆盖统计：(形态名, 文件数, 条目数)——形态注册表见
    # hanhua/core/tooling/morphology.py（显式清单 + 文本先验）
    morphology_stats: tuple[tuple[str, int, int], ...] = ()


class Project:
    """一个游戏目录 = 一个项目：扫描入库，输出到独立目录。"""

    def __init__(
        self,
        game_dir: Path,
        app_dir: Path,
        font_config: FontConfig | None = None,
        *,
        player_root: Path | None = None,
        player_executable: Path | None = None,
    ):
        self.game_dir = Path(game_dir).expanduser().absolute()
        self.app_dir = Path(app_dir)
        selected = (
            fingerprint_game(
                self.game_dir,
                player_root=player_root,
                player_executable=player_executable,
            )
            if player_root is not None or player_executable is not None
            else None
        )
        self.player_root = (
            selected.player_root.relative_to(selected.game_dir)
            if selected is not None and selected.player_root is not None else None
        )
        self.player_executable = (
            selected.executable.relative_to(selected.game_dir)
            if selected is not None and selected.executable is not None else None
        )
        game_dir = self.game_dir
        self.font_config = (
            replace(font_config) if font_config is not None else FontConfig(enabled=False)
        )
        self.out_dir = game_dir.parent / (game_dir.name + "_汉化")
        self.store = ProjectStore(
            self.app_dir / "projects" /
            _slug(self.game_dir, self.player_root, self.player_executable) /
            "project.db")
        self._last_analysis_report: AnalysisReport | None = None
        self._last_scan_morphology: tuple[tuple[str, int, int], ...] = ()
        self._last_scan_morph_warnings: tuple[str, ...] = ()
        self._last_il2cpp_input_hashes: tuple[str, str] | None = None
        self._last_source_manifest: dict[str, str] | None = None
        # 文本阶段 standalone 扫描时的全树快照：scan_v2 绑定前要求文本
        # 条目与当前树同源，防止陈旧文本条目对新树写回（review 实证）
        self._last_text_scan_manifest: dict[str, str] | None = None
        self._scan_all_active = False

    def _fingerprint(self) -> GameFingerprint:
        return fingerprint_game(
            self.game_dir,
            player_root=self.player_root,
            player_executable=self.player_executable,
        )

    def _selected_player_root(
            self, fingerprint: GameFingerprint | None = None) -> Path:
        current = fingerprint or self._fingerprint()
        if current.player_root is None:
            if "ambiguous_player_layout" in current.evidence:
                raise RuntimeError("Unity player layout is ambiguous")
            return self.game_dir
        return current.player_root

    @staticmethod
    def _excluded_sibling_data_roots(
            fingerprint: GameFingerprint) -> tuple[Path, ...]:
        if (
            fingerprint.layout_kind != "standard"
            or fingerprint.player_root is None
            or fingerprint.data_dir is None
        ):
            return ()
        return tuple(sorted(
            candidate.data_dir
            for candidate in discover_player_candidates(fingerprint.game_dir)
            if candidate.player_root == fingerprint.player_root
            and candidate.executable != fingerprint.executable
        ))

    @staticmethod
    def _excluded_sibling_player_roots(
            fingerprint: GameFingerprint) -> tuple[Path, ...]:
        selected_root = fingerprint.player_root
        if selected_root is None:
            return ()
        excluded: list[Path] = []
        for candidate in discover_player_candidates(fingerprint.game_dir):
            if candidate.player_root == selected_root:
                continue
            try:
                candidate.player_root.relative_to(selected_root)
            except ValueError:
                continue
            excluded.append(candidate.player_root)
        return tuple(sorted(set(excluded)))

    def _structured_scan_root(self, fingerprint: GameFingerprint) -> Path:
        selected_root = self._selected_player_root(fingerprint)
        if self._excluded_sibling_data_roots(fingerprint):
            if fingerprint.data_dir is None:
                raise RuntimeError("selected Unity player has no data directory")
            return fingerprint.data_dir
        return selected_root

    def analyze(self) -> AnalysisReport:
        """只读检测游戏、固定工具完整性和确定性自动路由。"""
        fingerprint = self._fingerprint()
        app_root = Path(__file__).resolve().parents[2]
        registry = ToolRegistry.load(app_root)
        statuses = registry.statuses()
        font_capability = resolve_font_provider(
            self.game_dir, fingerprint.runtime,
            player_root=fingerprint.player_root)
        route = plan_backends(
            fingerprint, {tool_id: status.state
                          for tool_id, status in statuses.items()},
            font_capability=font_capability,
        )
        report = AnalysisReport(
            fingerprint=fingerprint,
            tool_statuses=tuple(statuses[key] for key in sorted(statuses)),
            route=route,
            font_capability=font_capability,
            input_protected=True,
            unblocked=plan_is_unblocked(route),
            completable=plan_is_completable(route),
        )
        return report

    def scan_all(self, event_cb: Callable[[PipelineEvent], None] | None = None
                 ) -> AnalysisReport:
        """统一执行只读检测、原生扫描和受控工具交叉分析。"""
        def emit(phase: str, status: str, message: str,
                 current: int = 0, total: int = 0) -> None:
            if event_cb:
                event_cb(PipelineEvent(phase, status, message, current, total))

        scan_manifest_before = _tree_hashes(self.game_dir)
        self._last_source_manifest = None
        # 建表必须发生在任何提前返回之前（如 ambiguous_player_layout 的
        # blocked 路径）：否则 blocked 项目 DB 无 entries 表，后续
        # get_entries 抛 OperationalError（ned-flanders 真实案例）
        self.store.init_schema()
        base = self.analyze()
        self._last_il2cpp_input_hashes = None
        if (
            base.fingerprint.player_root is None
            and "ambiguous_player_layout" in base.fingerprint.evidence
        ):
            emit("detection", "blocked", "ambiguous_player_layout")
            self._last_analysis_report = base
            return base
        route = base.route
        warnings: list[str] = []
        tool_results: list[ToolAnalysisResult] = []
        protected_paths = tuple(path for path in (
            base.fingerprint.executable,
            base.fingerprint.game_assembly,
            base.fingerprint.metadata,
        ) if path is not None and path.is_file())
        before_hashes = {path: _sha256_file(path) for path in protected_paths}
        emit("detection", "succeeded",
             f"{base.fingerprint.runtime} · Unity {base.fingerprint.unity_version}")

        self._scan_all_active = True
        try:
            text_files = self.scan()
            emit("text_scan", "succeeded", f"结构化文本文件 {text_files} 个")
            v2_files = self.scan_v2()
        finally:
            self._scan_all_active = False
        warnings.extend(self._last_scan_morph_warnings)
        route = _set_route_status(route, "text_scan", "succeeded")
        emit("binary_scan", "succeeded", f"Unity 二进制资源 {v2_files} 个")

        fingerprint = base.fingerprint
        if fingerprint.runtime == "il2cpp":
            status_by_id = {status.tool_id: status for status in base.tool_statuses}
            dumper_status = status_by_id["il2cpp_dumper"]
            if dumper_status.state == "verified":
                started = time.perf_counter()
                try:
                    if fingerprint.game_assembly is None or fingerprint.metadata is None:
                        raise RuntimeError("IL2CPP 规范输入缺失")
                    app_root = Path(__file__).resolve().parents[2]
                    registry = ToolRegistry.load(app_root)
                    run_result, sidecar = run_il2cpp_dumper(
                        IsolatedToolRunner(self.app_dir / "tooling"),
                        registry.specs["il2cpp_dumper"],
                        fingerprint.game_assembly,
                        fingerprint.metadata,
                        app_root / "tools" / "Il2CppDumper" / "config.json",
                    )
                    raw = fingerprint.metadata.read_bytes()
                    native = [raw[pos:pos + length].decode("utf-8")
                              for _, length, pos in il2cpp_extractor.parse_string_literals(raw)]
                    anchors = ("[PICK UP]",) if "[PICK UP]" in native else ()
                    comparison = compare_literals(
                        native, sidecar, required_anchors=anchors)
                    if (comparison.agreement < 0.98 or comparison.sidecar_only != 0
                            or comparison.anchors_missing):
                        raise RuntimeError(
                            "IL2CPP 交叉验证未达到一致率/sidecar-only 安全门")
                    tool_results.append(ToolAnalysisResult(
                        "il2cpp_dumper", "succeeded", True,
                        cache_hit=run_result.cache_hit,
                        elapsed_ms=run_result.elapsed_ms,
                        details=(("native_total", str(comparison.native_total)),
                                 ("sidecar_total", str(comparison.sidecar_total)),
                                 ("intersection", str(comparison.intersection)),
                                 ("agreement", f"{comparison.agreement:.6f}")),
                    ))
                    route = _set_route_status(route, "tool_analysis", "succeeded")
                    emit("tool_analysis", "succeeded", "Il2CppDumper 交叉验证通过")
                except Exception as exc:  # noqa: BLE001 外部工具失败不得丢弃原生结果
                    reason = str(exc) or type(exc).__name__
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    tool_results.append(ToolAnalysisResult(
                        "il2cpp_dumper", "failed", True,
                        elapsed_ms=elapsed_ms, reason=reason))
                    if _is_dumper_version_gap(reason, fingerprint):
                        # dumper 二进制不支持该 metadata 版本，但 native 解析器
                        # 已声明支持且实际解析成功：降级为 skipped 且不再必需
                        # （审计保留 failed 记录），不阻断流水线；升级 dumper
                        # 后自动恢复为 succeeded 交叉验证。
                        route = _set_route_status(route, "tool_analysis", "skipped",
                                                  reason)
                        route = tuple(
                            replace(step, required=False)
                            if step.step_id == "tool_analysis" else step
                            for step in route)
                        warnings.append(
                            f"Il2CppDumper：{reason}（native 解析器已验证 "
                            f"v{fingerprint.metadata_version}，降级为 skipped）")
                        emit("tool_analysis", "skipped", reason)
                    else:
                        route = _set_route_status(route, "tool_analysis", "failed",
                                                  reason)
                        warnings.append(f"Il2CppDumper：{reason}")
                        emit("tool_analysis", "failed", reason)
            else:
                reason = dumper_status.reason or f"工具状态：{dumper_status.state}"
                tool_results.append(ToolAnalysisResult(
                    "il2cpp_dumper", "blocked", True, reason=reason))
                route = _set_route_status(route, "tool_analysis", "blocked", reason)
                warnings.append(f"Il2CppDumper：{reason}")
                emit("tool_analysis", "blocked", reason)
        else:
            emit("tool_analysis", "skipped", "Mono 游戏无需 Il2CppDumper")

        after_hashes = {path: _sha256_file(path) for path in protected_paths}
        scan_manifest_after = _tree_hashes(self.game_dir)
        input_protected = (
            before_hashes == after_hashes
            and scan_manifest_before == scan_manifest_after
        )
        if not input_protected:
            warnings.append("分析期间检测到完整输入文件树变化")
            route = _set_route_status(
                route, "tool_analysis", "failed", "关键输入哈希发生变化")

        self.store.init_schema()
        rows = self.store.get_entries()
        status_counts = tuple((status, sum(row["status"] == status for row in rows))
                              for status in ("pending", "translated", "failed", "skipped"))
        confidence = {"high": 0, "medium": 0, "low": 0}
        for row in rows:
            try:
                meta = json.loads(row.get("meta") or "{}")
            except (json.JSONDecodeError, TypeError):
                meta = {}
            level = meta.get("confidence", "medium")
            if level in confidence and row["status"] != "skipped":
                confidence[level] += 1
        unblocked = input_protected and plan_is_unblocked(route)
        completable = input_protected and plan_is_completable(route)
        emit("complete", "succeeded" if unblocked else "blocked",
             "分析可继续" if unblocked else "存在必需能力阻断")
        report = AnalysisReport(
            fingerprint=fingerprint,
            tool_statuses=base.tool_statuses,
            route=route,
            font_capability=base.font_capability,
            text_files=text_files,
            v2_files=v2_files,
            recognized_entries=sum(row["status"] != "skipped" for row in rows),
            status_counts=status_counts,
            confidence_counts=tuple(confidence.items()),
            tool_results=tuple(tool_results),
            input_protected=input_protected,
            unblocked=unblocked,
            completable=completable,
            warnings=tuple(warnings),
            morphology_stats=self._last_scan_morphology,
        )
        self._last_analysis_report = report
        if report.input_protected and report.unblocked:
            self._last_source_manifest = dict(scan_manifest_after)
        successful_il2cpp = next((
            item for item in report.tool_results
            if item.tool_id == "il2cpp_dumper" and item.status == "succeeded"
        ), None)
        # 版本缺口降级（#183）同样锚定规范输入：native 解析器已实际解析成功
        degraded_il2cpp = next((
            item for item in report.tool_results
            if item.tool_id == "il2cpp_dumper" and item.status == "failed"
            and _is_dumper_version_gap(item.reason or "", fingerprint)
        ), None)
        if (
            report.unblocked
            and (successful_il2cpp is not None or degraded_il2cpp is not None)
            and fingerprint.game_assembly is not None
            and fingerprint.metadata is not None
        ):
            self._last_il2cpp_input_hashes = (
                before_hashes[fingerprint.game_assembly],
                before_hashes[fingerprint.metadata],
            )
        return report

    def scan(self) -> int:
        """扫描并入库，返回保留的文本文件数。规则升级后被淘汰的旧文件自动清理。"""
        standalone_before = None
        prev_manifest = self._last_source_manifest
        if not self._scan_all_active:
            self._last_source_manifest = None
            standalone_before = _tree_hashes(self.game_dir)
        fingerprint = self._fingerprint()
        selected_root = self._structured_scan_root(fingerprint)
        excluded_roots = self._excluded_sibling_player_roots(fingerprint)
        self.store.init_schema()
        files = discover(selected_root, exclude_roots=excluded_roots)
        found_ids: set[str] = set()
        kept = 0
        for f in files:
            rel = str(f.relative_to(self.game_dir)).replace("\\", "/")
            pf = parse_file(f, file_id=rel)
            if pf.noise:
                continue      # 整文件为运行时噪音，不入库
            found_ids.add(rel)
            self.store.add_file(pf.file_id, rel, pf.format, pf.encoding, pf.eol, pf.meta)
            self.store.upsert_entries([
                {"file_id": e.file_id, "key_path": e.key_path,
                 "original": e.original, "status": e.status, "meta": e.meta}
                for e in pf.entries])
            kept += 1
        for old in self.store.get_files():
            if old["format"].startswith("v2_"):
                continue      # v2 文件由 scan_v2 管理，不能在此清理
            if old["id"] not in found_ids:
                self.store.remove_file(old["id"])
        if standalone_before is not None:
            standalone_after = _tree_hashes(self.game_dir)
            has_v2_records = any(
                f["format"].startswith("v2_")
                for f in self.store.get_files())
            if standalone_before == standalone_after:
                # 记录文本阶段全树快照：scan_v2 绑定前用它核对文本条目
                # 与当前树同源（陈旧文本条目对新树写回会错位）
                self._last_text_scan_manifest = dict(standalone_after)
                # _tree_hashes 是全树快照（含二进制资源），源未变即可作为
                # 清单证据。但 store 已存在 v2 文件记录时（先前统一扫描或
                # 手动导入过），只跑文本扫描不更新 v2 条目，store 清单不
                # 完整——必须失效 baseline 直到 scan_v2 完成（test_project
                # 实证）。从未有 v2 记录则绑定：写回只涉及已入库的文本条目，
                # 树 hash 覆盖全部输入。先 scan_v2 后 scan 的顺序（v2 已
                # 绑定且树未变）保持绑定，避免顺序依赖假拒绝。
                if not has_v2_records:
                    self._last_source_manifest = dict(standalone_after)
                elif prev_manifest == standalone_after:
                    # 仅当 v2 条目真实入库（scan_v2 实际扫描过）时才保持
                    # 绑定：手动 add_file 只加文件记录无条目时，文本扫描
                    # 不覆盖这些输入，store 清单不完整——保持失效直到
                    # scan_all（混合定位器 review 实证）
                    v2_file_ids = {
                        f["id"] for f in self.store.get_files()
                        if f["format"].startswith("v2_")}
                    if any(e["file_id"] in v2_file_ids
                           for e in self.store.get_entries()):
                        self._last_source_manifest = dict(standalone_after)
        return kept

    # ── v2：Unity 二进制资源扫描（.assets / DLL / IL2CPP metadata） ──
    def scan_v2(self, progress_cb: Callable | None = None) -> int:
        """扫描二进制资源并入库，返回保留的资源文件数。"""
        standalone_before = None
        if not self._scan_all_active:
            self._last_source_manifest = None
            standalone_before = _tree_hashes(self.game_dir)
        fingerprint = self._fingerprint()
        selected_root = self._structured_scan_root(fingerprint)
        excluded_roots = self._excluded_sibling_player_roots(fingerprint)
        self.store.init_schema()
        found_ids: set[str] = set()
        kept = 0
        sources: list[tuple[Callable, Path, str]] = []
        for f in unity_extractor.find_asset_files(
                selected_root, data_dir=fingerprint.data_dir,
                exclude_roots=excluded_roots):
            rel = str(f.relative_to(self.game_dir)).replace("\\", "/")
            sources.append((unity_extractor.extract_asset_file, f, rel))
        for f in fingerprint.application_assemblies:
            rel = str(f.relative_to(self.game_dir)).replace("\\", "/")
            sources.append((mono_extractor.extract_dll_user_strings, f, rel))
        meta = fingerprint.metadata
        if meta is not None:
            rel = str(meta.relative_to(self.game_dir)).replace("\\", "/")
            sources.append((il2cpp_extractor.extract_metadata_strings, meta, rel))
        # 形态覆盖统计（注册表显式清单）：未知形态 → 显式告警而非静默处理
        morph_files: dict[str, int] = {}
        morph_entries: dict[str, int] = {}
        morph_warnings: list[str] = []
        for i, (fn, f, rel) in enumerate(sources):
            if progress_cb:
                progress_cb(i + 1, len(sources))
            morph = classify_morphology(rel)
            if morph is None:
                morph_warnings.append(
                    f"未知文本形态：{rel}（未注册形态清单，请先登记再接线，"
                    f"见 docs/识别形态覆盖与遗漏处理.md）")
            else:
                morph_files[morph] = morph_files.get(morph, 0) + 1
            pf = fn(f, file_id=rel)
            if pf.noise:
                continue
            found_ids.add(rel)
            if morph is not None:
                morph_entries[morph] = (
                    morph_entries.get(morph, 0) + len(pf.entries))
            self.store.add_file(pf.file_id, rel, pf.format, pf.encoding, pf.eol, pf.meta)
            new_keys = {e.key_path for e in pf.entries}
            # 重扫后不再存在的旧条目（如已被规则过滤的键位置）→ 删除，避免残留写回
            old_keys = [e["key_path"] for e in self.store.get_entries()
                        if e["file_id"] == rel and e["key_path"] not in new_keys]
            self.store.upsert_entries([
                {"file_id": e.file_id, "key_path": e.key_path,
                 "original": e.original, "status": e.status, "meta": e.meta}
                for e in pf.entries])
            if old_keys:
                self.store.remove_entries(rel, old_keys)
            kept += 1
        for old in self.store.get_files():
            if old["format"].startswith("v2_") and old["id"] not in found_ids:
                self.store.remove_file(old["id"])
        if standalone_before is not None:
            standalone_after = _tree_hashes(self.game_dir)
            if standalone_before == standalone_after:
                # scan_v2 只更新 v2 条目，文本条目来源树必须与当前树同源
                # （_last_text_scan_manifest 由 scan() 记录；从未跑过文本
                # 阶段则视为无文本条目）。否则 scan() 绑定后文件被改、再
                # 单独 scan_v2 会用新树覆盖绑定，陈旧文本条目对新树写回
                # ——无条件绑定会绕过 write_all 输入清单闸门（review 实证）
                text_same = (
                    self._last_text_scan_manifest is None
                    or standalone_after == self._last_text_scan_manifest)
                if text_same:
                    self._last_source_manifest = dict(standalone_after)
        self._last_scan_morphology = tuple(sorted(
            (m, morph_files.get(m, 0), morph_entries.get(m, 0))
            for m in morph_files))
        self._last_scan_morph_warnings = tuple(morph_warnings)
        return kept

    # ── 写回（文本 + 二进制资源） ──
    def _validate_write_route(
            self, write_ready: int, font_config: FontConfig,
            ) -> tuple[
                GameFingerprint,
                tuple[BackendStep, ...],
                FontProviderCapability,
            ]:
        """Re-evaluate the core write capability before creating staging."""
        fingerprint = self._fingerprint()
        if (
            self._last_analysis_report is not None
            and _layout_identity(fingerprint) != _layout_identity(
                self._last_analysis_report.fingerprint)
        ):
            raise RuntimeError(
                "Unity player layout/backend inputs changed after scan")
        app_root = Path(__file__).resolve().parents[2]
        statuses = ToolRegistry.load(app_root).statuses()
        font_capability = resolve_font_provider(
            self.game_dir, fingerprint.runtime,
            player_root=fingerprint.player_root)
        route = plan_backends(
            fingerprint,
            {tool_id: status.state for tool_id, status in statuses.items()},
            font_capability=font_capability,
        )
        if fingerprint.runtime == "unknown":
            raise RuntimeError("未识别 Unity 运行时，已拒绝写回")
        if self.store.get_files():
            route = _set_route_status(route, "text_scan", "succeeded")
        if not font_config.enabled:
            route = _set_route_status(
                route, "font", "succeeded", "用户未启用运行时字体覆盖")
        if fingerprint.runtime == "il2cpp" and self._last_analysis_report is not None:
            analyzed_tool = next((
                step for step in self._last_analysis_report.route
                if step.step_id == "tool_analysis"
            ), None)
            if analyzed_tool is not None:
                route = _set_route_status(
                    route, "tool_analysis", analyzed_tool.status, analyzed_tool.reason)
                # 版本缺口降级把 tool_analysis 置为不再必需（#183），
                # 写回预检继承该语义，避免降级被当作未完成先决步骤
                if not analyzed_tool.required:
                    route = tuple(
                        replace(step, required=False)
                        if step.step_id == "tool_analysis" else step
                        for step in route)
        blockers = [
            step for step in route
            if step.required and step.status in {"blocked", "failed"}
        ]
        if blockers:
            summary = "；".join(
                f"{step.step_id}: {step.reason}" for step in blockers)
            raise RuntimeError(f"必需 writer 路由不可用，已拒绝写回：{summary}")
        execution_steps = {"font", "writeback"}
        if fingerprint.runtime == "il2cpp":
            report = self._last_analysis_report
            current_input_hashes = (
                _sha256_file(fingerprint.game_assembly)
                if fingerprint.game_assembly is not None else "",
                _sha256_file(fingerprint.metadata)
                if fingerprint.metadata is not None else "",
            )
            if (
                self._last_il2cpp_input_hashes is not None
                and current_input_hashes != self._last_il2cpp_input_hashes
            ):
                raise RuntimeError(
                    "IL2CPP 交叉验证后的规范输入发生变化，已拒绝写回")
            tool_result = next((
                item for item in (report.tool_results if report else ())
                if item.tool_id == "il2cpp_dumper"
            ), None)
            route_status = next((
                step.status for step in (report.route if report else ())
                if step.step_id == "tool_analysis"
            ), None)
            details = dict(tool_result.details) if tool_result else {}
            try:
                native_total = int(details["native_total"])
                sidecar_total = int(details["sidecar_total"])
                intersection = int(details["intersection"])
                agreement = float(details["agreement"])
            except (KeyError, TypeError, ValueError):
                native_total = sidecar_total = intersection = 0
                agreement = 0.0
            cross_checked = (
                route_status == "succeeded"
                and tool_result is not None
                and tool_result.status == "succeeded"
                and native_total > 0
                and sidecar_total > 0
                and intersection > 0
                and agreement >= 0.98
            )
            # 版本缺口降级（dumper 二进制不支持 metadata 版本，native 解析器
            # 声明支持且实际解析成功）提供等价的写回证据链：#183
            version_gap_degraded = (
                route_status == "skipped"
                and tool_result is not None
                and tool_result.status == "failed"
                and _is_dumper_version_gap(tool_result.reason or "", fingerprint)
            )
            evidence_valid = (
                report is not None
                and report.fingerprint == fingerprint
                and report.input_protected
                and report.unblocked
                and current_input_hashes == self._last_il2cpp_input_hashes
                and (cross_checked or version_gap_degraded)
            )
            if not evidence_valid:
                raise RuntimeError(
                    "IL2CPP 写回缺少本次项目成功的 native/Il2CppDumper 交叉验证证据")
        if write_ready <= 0:
            raise RuntimeError("没有通过质量门的可写译文，已拒绝写回")
        quality_step = next((
            step for step in route if step.step_id == "translation_quality"
        ), None)
        if quality_step is None or quality_step.status not in {"blocked", "failed"}:
            route = _set_route_status(
                route, "translation_quality", "succeeded",
                f"{write_ready} 条译文通过统一质量门",
            )
        pending_prerequisites = [
            step for step in route
            if step.required and step.step_id not in execution_steps
            and step.status != "succeeded"
        ]
        if pending_prerequisites:
            summary = "；".join(
                f"{step.step_id}: {step.reason}" for step in pending_prerequisites)
            raise RuntimeError(f"必需写回先决步骤尚未完成：{summary}")
        return fingerprint, route, font_capability

    def _verify_copied_il2cpp_inputs(
            self, fingerprint: GameFingerprint, staging: Path) -> None:
        if fingerprint.runtime != "il2cpp":
            return
        if (
            fingerprint.game_assembly is None
            or fingerprint.metadata is None
            or self._last_il2cpp_input_hashes is None
        ):
            raise RuntimeError("IL2CPP 写回缺少可复核的规范输入证据")
        game_root = self.game_dir.resolve()
        relative_inputs = (
            fingerprint.game_assembly.relative_to(game_root),
            fingerprint.metadata.relative_to(game_root),
        )
        source_hashes = tuple(_sha256_file(path) for path in (
            fingerprint.game_assembly, fingerprint.metadata))
        staged_hashes = tuple(
            _sha256_file(resolve_relative_under(staging, relative))
            for relative in relative_inputs
        )
        if (
            source_hashes != self._last_il2cpp_input_hashes
            or staged_hashes != self._last_il2cpp_input_hashes
        ):
            raise RuntimeError(
                "IL2CPP 交叉验证后的规范输入发生变化，已拒绝写回")

    @staticmethod
    def _evaluate_writeback_gates(
            *, text_files: int, v2, text_verified: int,
            font, font_level: str, active_font_config: FontConfig,
            rejected: list, truncated: int, allow_partial: bool,
            ready_text_translations: int) -> dict:
        """写回安全闸门 P0-1：把“写回成功”拆成文件/容器/对象/运行时
        四态，禁止单一 succeeded 掩盖后续失败。"""
        def gate(status: str, detail: str = "") -> dict:
            return {"status": status, "detail": detail}

        # 文件级：文本文件已写入并通过重开核对
        if text_files > 0 and text_verified > 0:
            file_gate = gate(
                "PASS", f"{text_files} 个文本文件写回，{text_verified} 条重开核对通过")
        elif ready_text_translations == 0:
            file_gate = gate("N/A", "无待写文本条目")
        else:
            file_gate = gate("BLOCKED", "存在待写文本条目但未通过重开核对")

        # 容器级：每个补丁过的 Unity 容器均已重开验证（验证失败会抛错）
        if v2 is not None and v2.files > 0:
            container_gate = gate(
                "PASS", f"{v2.files} 个容器写回并重开验证通过")
        else:
            container_gate = gate("N/A", "无二进制容器补丁")

        # 对象级：rejected/truncated 条目必须进入报告并阻断默认发布（P0-2）
        if rejected or truncated:
            detail_parts = [f"拒绝 {len(rejected)}", f"截断 {truncated}"]
            if allow_partial:
                object_gate = gate(
                    "WARN",
                    f"存在未完全写入条目（{'、'.join(detail_parts)}），"
                    "用户已确认允许部分发布")
            else:
                object_gate = gate(
                    "BLOCKED",
                    f"存在未完全写入条目（{'、'.join(detail_parts)}），"
                    "默认阻断发布，需用户明确确认")
        else:
            object_gate = gate("PASS", "全部条目完整写入")

        # 运行时级：字体/运行时回退层
        if not active_font_config.enabled:
            runtime_gate = gate("N/A", "用户未启用中文字体")
        elif font.runtime_verified:
            runtime_gate = gate("PASS", font_level)
        elif font.installed or font.payload_deployed:
            runtime_gate = gate("WARN", font_level)
        elif not font.provider_supported:
            runtime_gate = gate("WARN", font.unsupported_reason or font_level)
        else:
            runtime_gate = gate("BLOCKED", "字体运行时回退层不可验证")

        gates = {
            "file": file_gate,
            "container": container_gate,
            "object": object_gate,
            "runtime": runtime_gate,
        }
        statuses = [item["status"] for item in gates.values()]
        if "BLOCKED" in statuses:
            overall = "BLOCKED"
        elif "WARN" in statuses:
            overall = "WARN"
        else:
            overall = "PASS"
        gates["overall"] = gate(overall, "")
        return gates

    @staticmethod
    def _write_publish_manifest(
            out_dir: Path, source_hashes: dict, output_hashes: dict,
            fingerprint: GameFingerprint, gates: dict,
            allow_partial: bool,
            backup_name: str | None = None) -> str | None:
        """P0-3：发布后生成 source/target manifest，列出全部文件 hash
        （含未修改文件）。返回清单文件名；失败返回 None 由调用方记警告。

        backup_name 非 None 时记录备份目录名与恢复步骤（文档1 §15：
        报告须含备份路径/回滚命令）。"""
        rels = sorted(set(source_hashes) | set(output_hashes))
        files = []
        for rel in rels:
            source_hash = source_hashes.get(rel, "")
            target_hash = output_hashes.get(rel, "")
            files.append({
                "path": rel,
                "source_sha256": source_hash,
                "target_sha256": target_hash,
                "changed": source_hash != target_hash,
            })
        source_manifest_hash = hashlib.sha256(
            json.dumps(source_hashes, sort_keys=True).encode("utf-8")
        ).hexdigest()
        manifest = {
            "schema": 1,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "game": {
                "unity_version": fingerprint.unity_version,
                "runtime": fingerprint.runtime,
            },
            "source_manifest_hash": source_manifest_hash,
            "allow_partial": allow_partial,
            "gates": gates,
            "file_count": len(files),
            "changed_files": sum(1 for item in files if item["changed"]),
            "files": files,
        }
        if backup_name:
            # 发布前版本备份（回滚凭据）：恢复 = 将备份目录改名为
            # 输出目录名（旧输出已整体换名，无逐文件覆盖风险）
            manifest["backup"] = {
                "path": backup_name,
                "restore": (
                    f"将 {out_dir.parent / backup_name} 改名为 "
                    f"{out_dir} 即恢复发布前版本"),
            }
        path = out_dir / ".hanhua-manifest.json"
        try:
            path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=1),
                encoding="utf-8")
        except OSError:
            return None
        return ".hanhua-manifest.json"

    def write_all(
        self,
        progress_cb: Callable | None = None,
        *,
        font_config: FontConfig | None = None,
        stage_cb: Callable[[WritebackStage], None] | None = None,
        allow_partial: bool = False,
    ) -> dict:
        """复制游戏目录到输出目录，依次写回文本与二进制资源。

        allow_partial：存在 rejected/truncated 条目时是否允许发布
        （默认 False → BLOCKED 阻断；True → WARN 放行并完整记录）。
        """
        _emit_writeback_stage(stage_cb, "preflight", "正在执行写回预检")
        _reject_store_inside_out_dir(self.app_dir, self.out_dir)
        active_font_config = replace(font_config or self.font_config)
        write_ready = _count_write_ready_translations(self.store)
        runtime_translations = _runtime_exact_translations(self.store)
        for file_record in self.store.get_files():
            resolve_relative_under(self.game_dir, file_record["rel_path"])
            resolve_relative_under(self.out_dir, file_record["rel_path"])
        fingerprint, route, font_capability = self._validate_write_route(
            write_ready, active_font_config)
        if self._last_source_manifest is None:
            raise RuntimeError("缺少成功扫描绑定的完整输入清单，请重新执行统一扫描")
        source_hashes = dict(self._last_source_manifest)
        if _tree_hashes(self.game_dir) != source_hashes:
            raise RuntimeError("成功扫描后的原游戏输入发生变化，已拒绝写回")
        on_copy = None
        if progress_cb:
            def on_copy(done, total):
                progress_cb(done, total + 4)
        parent = self.out_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        staging: Path | None = Path(tempfile.mkdtemp(
            prefix=f".{self.out_dir.name}.staging-", dir=parent))
        backup: Path | None = None
        try:
            ensure_trusted_root(staging)
            _emit_writeback_stage(stage_cb, "copying", "正在复制原游戏")
            copy_total = copy_game_dir(self.game_dir, staging, on_copy)
            progress_total = copy_total + 4
            ensure_trusted_root(staging)
            for file_record in self.store.get_files():
                resolve_relative_under(staging, file_record["rel_path"])
            if (
                _tree_hashes(self.game_dir) != source_hashes
                or _tree_hashes(staging) != source_hashes
            ):
                raise RuntimeError(
                    "复制期间 IL2CPP/其他原游戏输入或未补丁副本发生变化，"
                    "与扫描清单不一致，已拒绝写回")
            self._verify_copied_il2cpp_inputs(fingerprint, staging)
            _emit_writeback_stage(stage_cb, "patching", "正在写入静态译文")
            n_text = write_back_text(self.store, self.game_dir, staging)
            if progress_cb:
                progress_cb(copy_total + 1, progress_total)
            v2 = write_back_v2(self.store, self.game_dir, staging)
            writer_outcome = v2.outcome
            if progress_cb:
                progress_cb(copy_total + 2, progress_total)
            _emit_writeback_stage(stage_cb, "runtime_payload", "正在部署中文字体")
            # 所有运行时（Mono + IL2CPP）都先执行静态字体替换：legacy Font
            # 内嵌 TTF 换中文字体（覆盖 uGUI Text/3D TextMesh）、TMP_FontAsset
            # 按 Unity 版本 bundle 替换。静态替换是覆盖全部游戏的主路径。
            if active_font_config.enabled:
                static = install_static_fonts(
                    staging, active_font_config,
                    unity_version=fingerprint.unity_version)
                static_warnings = (
                    [f"字体替换跳过: {skip}" for skip in static.skipped]
                    + list(static.warnings))
                if static.replaced:
                    font = FontInstallResult(
                        installed=True,
                        filename=active_font_config.filename,
                        payload_deployed=True,
                        runtime_verified=True,
                        architecture=font_capability.architecture,
                        provider_supported=False,
                        unsupported_reason=font_capability.reason,
                        provider_id="static_font_replace",
                        payload_available=True,
                    )
                    if font_capability.provider_supported:
                        # Mono：静态替换成功后再部署运行时插件兜底
                        # （覆盖动态加载字体），插件失败不阻断。
                        try:
                            font_kwargs = {"translations": runtime_translations}
                            install_font_override(
                                self.game_dir, staging, active_font_config,
                                **font_kwargs)
                        except Exception as exc:  # noqa: BLE001
                            static_warnings.append(
                                f"运行时字体插件部署失败（静态替换已生效）: {exc}")
                else:
                    font = None
            else:
                static_warnings = []
                font = None
            if font is None:
                # 静态替换未找到可换对象（或无字体配置）：退回运行时路径。
                # Mono 用 BepInEx 插件；未启用字体时调用保持旧行为
                # （install_font_override 内部对 disabled 安全 no-op）；
                # IL2CPP 无 provider 时记 unsupported。
                if not active_font_config.enabled or font_capability.runtime == "mono":
                    font_kwargs = {"translations": runtime_translations}
                    try:
                        install_params = inspect.signature(
                            install_font_override).parameters
                    except (TypeError, ValueError):
                        install_params = {}
                    if (fingerprint.player_root is not None and (
                            "player_root" in install_params or any(
                                parameter.kind is inspect.Parameter.VAR_KEYWORD
                                for parameter in install_params.values()))):
                        font_kwargs["player_root"] = fingerprint.player_root
                    font = install_font_override(
                        self.game_dir, staging, active_font_config,
                        **font_kwargs)
                else:
                    font = FontInstallResult(
                        installed=False,
                        filename=active_font_config.filename,
                        payload_deployed=False,
                        runtime_verified=False,
                        architecture=font_capability.architecture,
                        provider_supported=False,
                        unsupported_reason=font_capability.reason,
                        provider_id=font_capability.provider_id,
                        payload_available=font_capability.payload_available,
                    )
            if active_font_config.enabled:
                if font.installed:
                    font_reason = (
                        "静态字体替换完成（Font/TMP_FontAsset 换入中文字库）"
                        if font.provider_id == "static_font_replace"
                        else "运行时中文字体回退安装完成")
                    route = _set_route_status(
                        route, "font", "succeeded", font_reason)
                elif not font.provider_supported:
                    route = tuple(
                        replace(
                            step, status="skipped", required=False,
                            reason=font.unsupported_reason)
                        if step.step_id == "font" else step
                        for step in route)
                else:
                    route = _set_route_status(
                        route, "font", "failed",
                        "已启用中文字体，但运行时回退安装未完成")
                    raise RuntimeError("中文字体运行时回退安装失败，已拒绝发布副本")
            if progress_cb:
                progress_cb(copy_total + 3, progress_total)

            _emit_writeback_stage(stage_cb, "verifying", "正在重开并验证汉化输出")
            input_protected = source_hashes == _tree_hashes(self.game_dir)
            if not input_protected:
                raise RuntimeError("写回期间检测到原游戏输入哈希变化，已拒绝发布副本")
            text_verified = _reopen_written_outputs(self.store, staging)
            reopen_verified = True
            output_hashes = _tree_hashes(staging)
            changed_files = sum(
                source_hashes.get(relative) != output_hashes.get(relative)
                for relative in source_hashes.keys() | output_hashes.keys()
            )
            written_translations = text_verified + v2.entries
            if written_translations <= 0:
                raise RuntimeError("没有通过重开验证的实际译文补丁，已拒绝发布副本")
            warnings = list(getattr(v2, "warnings", ()) or ())
            warnings.extend(static_warnings)
            if (active_font_config.enabled and not font.installed
                    and not font.provider_supported):
                warnings.append(font.unsupported_reason)
            elif active_font_config.enabled and not font.installed:
                warnings.append("已启用中文字体，但没有生成可验证的运行时回退层")
            font_level = (
                "runtime_verified" if font.runtime_verified
                else "payload_deployed" if font.payload_deployed
                else "unsupported" if (active_font_config.enabled
                                        and not font.provider_supported)
                else "unavailable" if active_font_config.enabled
                else "disabled"
            )
            # P0-2：rejected/truncated/blocked 条目全量进入报告，
            # 默认（allow_partial=False）阻断发布，用户明确确认才放行
            rejected_entries = [
                {"locator": item.locator, "reason": item.reason}
                for item in writer_outcome.rejected
            ]
            truncated_items = list(getattr(v2, "truncated_items", ()) or ())
            if (rejected_entries or truncated_items) and not allow_partial:
                detail_parts = []
                if rejected_entries:
                    detail_parts.append(f"拒绝 {len(rejected_entries)} 条")
                if truncated_items:
                    detail_parts.append(f"截断 {len(truncated_items)} 条")
                examples = "；".join(
                    f"{item['locator']}: {item['reason']}"
                    for item in rejected_entries[:5])
                raise RuntimeError(
                    f"写回存在未完全写入条目（{'、'.join(detail_parts)}），"
                    f"已阻断默认发布。{examples}"
                    "如需强制发布请在界面勾选“允许部分写入并发布”")
            verification = {
                "input_protected": input_protected,
                "reopen_verified": reopen_verified,
                "changed_files": changed_files,
                "written_translations": written_translations,
                "writer_outcome": {
                    "attempted": writer_outcome.attempted,
                    "written": writer_outcome.written,
                    "rejected": rejected_entries,
                    "truncated": writer_outcome.truncated,
                },
                "rejected_entries": rejected_entries,
                "truncated_entries": truncated_items,
                "blocked_entries": (
                    rejected_entries
                    + [{"locator": f"truncated#{index + 1}",
                        "reason": item}
                       for index, item in enumerate(truncated_items)]),
                "font_level": font_level,
                "font_provider_id": font.provider_id,
                "font_payload_deployed": bool(font.payload_deployed),
                "font_runtime_verified": font.runtime_verified,
                "allow_partial": allow_partial,
                "warnings": warnings,
            }
            # P0-1：四态闸门（文件/容器/对象/运行时），
            # 任一 BLOCKED 都不得发布副本
            gates = self._evaluate_writeback_gates(
                text_files=n_text, v2=v2, text_verified=text_verified,
                font=font, font_level=font_level,
                active_font_config=active_font_config,
                rejected=rejected_entries, truncated=len(truncated_items),
                allow_partial=allow_partial,
                ready_text_translations=_count_write_ready_translations(
                    self.store, text_only=True))
            overall = gates["overall"]["status"]
            verification["gates"] = gates
            verification["overall"] = overall
            if overall == "BLOCKED":
                blocked_parts = [
                    f"{name}={item['status']}"
                    for name, item in gates.items()
                    if item["status"] == "BLOCKED"]
                raise RuntimeError(
                    f"写回闸门 BLOCKED（{'、'.join(blocked_parts)}），"
                    "已拒绝发布副本。详见发布报告")
            route = _set_route_status(
                route, "writeback", "succeeded",
                "写回、输入保护、重开验证与四态闸门通过"
                if overall == "PASS"
                else f"写回完成（overall={overall}），详见发布报告")
            base_report = (
                self._last_analysis_report
                if self._last_analysis_report is not None
                and self._last_analysis_report.fingerprint == fingerprint
                else self.analyze()
            )
            final_report = replace(
                base_report,
                route=route,
                font_capability=replace(
                    font_capability,
                    payload_deployed=bool(font.payload_deployed),
                    runtime_verified=font.runtime_verified,
                ),
                unblocked=plan_is_unblocked(route),
                completable=plan_is_completable(route),
            )
            if not final_report.completable:
                pending = [
                    step.step_id for step in route
                    if step.required and step.status != "succeeded"
                ]
                raise RuntimeError(
                    f"写回完成状态不完整，已拒绝发布副本：{', '.join(pending)}")
            if _tree_hashes(self.game_dir) != source_hashes:
                raise RuntimeError("发布前检测到原游戏输入发生变化，已拒绝替换旧输出")
            _emit_writeback_stage(stage_cb, "publishing", "正在原子发布汉化游戏")
            if self.out_dir.exists():
                backup = parent / f".{self.out_dir.name}.backup-{uuid.uuid4().hex}"
                _replace_directory(self.out_dir, backup)
            _replace_directory(staging, self.out_dir)
            staging = None
            # P0-3：发布后生成 source/target manifest（全量文件 hash，
            # 含未修改文件），写入已发布目录；同时记录发布前版本备份
            # 路径与恢复步骤（一键回滚凭据）
            backup_name = backup.name if backup is not None else None
            manifest_name = self._write_publish_manifest(
                self.out_dir, source_hashes, output_hashes, fingerprint,
                gates, allow_partial, backup_name)
            verification["manifest"] = manifest_name
            verification["backup"] = backup_name
            if manifest_name is None:
                warnings.append("发布清单写入失败（.hanhua-manifest.json）")
                verification["warnings"] = warnings
            self._last_analysis_report = final_report
            if progress_cb:
                progress_cb(progress_total, progress_total)
            result = {
                "text_files": n_text,
                "v2": v2,
                "font": font,
                "verification": verification,
                "analysis_report": final_report,
            }
            _emit_writeback_stage(stage_cb, "published", "汉化游戏已发布")
            if backup is not None:
                cleanup_target = backup
                backup = None
                _schedule_backup_cleanup(
                    cleanup_target, self.out_dir, stage_cb)
            return result
        except Exception:
            if backup is not None and not self.out_dir.exists() and backup.exists():
                try:
                    _replace_directory(backup, self.out_dir)
                except PermissionError as restore_error:
                    raise RuntimeError(
                        f"输出提交失败，旧版本恢复也被文件锁阻止；备份已保留在：{backup}"
                    ) from restore_error
            raise
        finally:
            if staging is not None and staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            if backup is not None and backup.exists() and self.out_dir.exists():
                shutil.rmtree(backup, ignore_errors=True)

    # ── 项目级游戏档案（每个游戏独立） ──
    @property
    def profile(self) -> GameProfile:
        return self.store.get_profile()

    def save_profile(self, profile: GameProfile):
        self.store.set_profile(profile)

    @staticmethod
    def open_game_dir(
        game_dir: str | Path,
        app_dir: str | Path,
        font_config: FontConfig | None = None,
        *,
        player_root: str | Path | None = None,
        player_executable: str | Path | None = None,
    ) -> "Project":
        return Project(
            Path(game_dir), Path(app_dir), font_config=font_config,
            player_root=Path(player_root) if player_root is not None else None,
            player_executable=(
                Path(player_executable)
                if player_executable is not None else None),
        )
