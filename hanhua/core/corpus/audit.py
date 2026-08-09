"""可恢复、只读的 Unity 游戏语料审计。"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Callable

from hanhua.core.corpus.models import (
    CorpusAudit,
    CorpusAuditGame,
    CorpusInventory,
    SCHEMA_VERSION,
)
from hanhua.core.local_model import sanitize_exception
from hanhua.core.paths import _is_reparse_point
from hanhua.core.project import Project
from hanhua.core.tooling.fingerprint import FingerprintError


Checkpoint = Callable[[Path], None]

_AUDIT_FIELDS = {"schema_version", "corpus_root", "games"}
_AUDIT_GAME_FIELDS = {
    "game_id", "source_path", "status", "input_fingerprint",
    "source_manifest", "status_counts", "role_counts", "confidence_counts",
    "reason_counts", "disposition_counts", "failure_category", "diagnostic",
}
_AUDIT_STATUSES = {"pending", "running", "passed", "blocked", "failed"}
_COUNT_FIELDS = (
    "status_counts", "role_counts", "confidence_counts", "reason_counts",
    "disposition_counts",
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")

_DIAGNOSTIC_PATTERNS = (
    (re.compile(r"(?i)\b(?:response\s+)?body\s*[:=].*$"), "body: <redacted>"),
    (re.compile(r"(?i)\bAuthorization\s*[:=]\s*\S+(?:\s+\S+)?"), "<redacted>"),
    (re.compile(r"(?i)\bBearer\s+\S+"), "Bearer <redacted>"),
    (re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
        r"auth[_-]?token|token|secret|password)\b\s*[:=]\s*"
        r"(?:['\"][^'\"]*['\"]|[^\s,;]+)"
    ), "credential=<redacted>"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]+\b"), "<redacted>"),
    (re.compile(r"(?i)\bhttps?://[^\s]+"), "<redacted>"),
)


def source_tree_manifest(root: str | Path) -> dict[str, str]:
    """Hash every regular file below *root* without crossing reparse points."""
    lexical_root = Path(root)
    if _is_reparse_point(lexical_root):
        raise FingerprintError("游戏目录是 reparse point（重解析点）")
    root_path = lexical_root.resolve()
    manifest: dict[str, str] = {}
    pending = [root_path]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                path = Path(entry.path)
                if _is_reparse_point(path):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    digest = hashlib.sha256()
                    with path.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    manifest[path.relative_to(root_path).as_posix()] = digest.hexdigest()
    return dict(sorted(manifest.items()))


def _fingerprint(manifest: dict[str, str]) -> str:
    encoded = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _corpus_root(inventory: CorpusInventory) -> Path:
    if not inventory.games:
        raise ValueError("语料清单为空，无法确定语料根目录")
    parents = {game.source_path.resolve().parent for game in inventory.games}
    if len(parents) != 1:
        raise ValueError("语料清单中的游戏不属于同一个根目录")
    return next(iter(parents))


def _validate_state_location(state_path: Path, inventory: CorpusInventory) -> None:
    lexical_target = state_path.absolute()
    if any(_is_reparse_point(path) for path in (lexical_target, *lexical_target.parents)):
        raise ValueError("审计状态文件路径不能包含 reparse point（重解析点）")
    try:
        resolved_target = lexical_target.resolve(strict=False)
        source_roots = tuple(
            game.source_path.resolve(strict=True) for game in inventory.games)
    except (OSError, RuntimeError) as exc:
        raise ValueError("无法安全解析审计状态文件路径") from exc
    for source_root in source_roots:
        try:
            resolved_target.relative_to(source_root)
        except ValueError:
            continue
        raise ValueError("审计状态文件不能位于游戏源目录内")


def _write_state(state: CorpusAudit, state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        state.to_state_dict(), ensure_ascii=False, indent=2, sort_keys=True,
    ) + "\n"
    file_descriptor = -1
    temporary: Path | None = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{state_path.name}.", suffix=".tmp", dir=state_path.parent,
        )
        temporary = Path(temporary_name)
        with os.fdopen(
            file_descriptor, "w", encoding="utf-8", newline="\n",
        ) as stream:
            file_descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, state_path)
        temporary = None
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _validate_counts(value: object, field: str) -> dict[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not all(
        isinstance(key, str)
        and isinstance(count, int) and not isinstance(count, bool) and count >= 0
        for key, count in value.items()
    ):
        raise ValueError(f"审计状态的 {field} 计数无效")
    return value


def _validate_diagnostic(value: object) -> dict[str, str | int | None] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"type", "status", "message"}:
        raise ValueError("审计状态的诊断字段无效")
    diagnostic_type = value["type"]
    message = value["message"]
    status = value["status"]
    if (
        not isinstance(diagnostic_type, str) or len(diagnostic_type) > 80
        or not isinstance(message, str) or len(message) > 240
        or isinstance(status, bool)
        or not (status is None or isinstance(status, (str, int)))
        or isinstance(status, str) and len(status) > 80
    ):
        raise ValueError("审计状态的诊断值无效")
    return value


def _validate_game_record(record: dict, source) -> None:
    if set(record) != _AUDIT_GAME_FIELDS:
        raise ValueError("审计状态的游戏记录字段不匹配")
    if record["game_id"] != source.game_id:
        raise ValueError("审计状态的游戏 ID 不匹配")
    if record["source_path"] != str(source.source_path):
        raise ValueError("审计状态的游戏源路径不匹配")
    status = record["status"]
    if not isinstance(status, str) or status not in _AUDIT_STATUSES:
        raise ValueError("审计状态的游戏状态无效")
    fingerprint = record["input_fingerprint"]
    if fingerprint is not None and not _valid_sha256(fingerprint):
        raise ValueError("审计状态的输入摘要无效")
    manifest = record["source_manifest"]
    if manifest is not None and (
        not isinstance(manifest, dict)
        or not all(isinstance(path, str) and _valid_sha256(digest)
                   for path, digest in manifest.items())
    ):
        raise ValueError("审计状态的源文件摘要无效")
    for field in _COUNT_FIELDS:
        _validate_counts(record[field], field)
    failure_category = record["failure_category"]
    if failure_category is not None and not isinstance(failure_category, str):
        raise ValueError("审计状态的失败分类无效")
    _validate_diagnostic(record["diagnostic"])
    if status in {"passed", "blocked"} and (
        fingerprint is None or manifest is None
        or any(record[field] is None for field in _COUNT_FIELDS)
        or failure_category is not None or record["diagnostic"] is not None
    ):
        raise ValueError("审计状态的终态游戏记录无效")
    if status == "failed" and (
        failure_category is None or record["diagnostic"] is None
    ):
        raise ValueError("审计状态的失败游戏记录无效")


def _load_state(
    state_path: Path,
    inventory: CorpusInventory,
    corpus_root: Path,
) -> CorpusAudit | None:
    if not state_path.exists():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("审计状态不是有效的 UTF-8 JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _AUDIT_FIELDS:
        raise ValueError("审计状态顶层字段不匹配")
    if (
        not isinstance(payload["schema_version"], int)
        or isinstance(payload["schema_version"], bool)
        or payload["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError("审计状态 schema_version 不受支持")
    try:
        if not isinstance(payload["corpus_root"], str):
            raise TypeError
        stored_root = Path(payload["corpus_root"]).resolve()
        records = payload["games"]
    except (KeyError, TypeError) as exc:
        raise ValueError("审计状态缺少语料根目录或游戏记录") from exc
    if stored_root != corpus_root:
        raise ValueError("审计状态的语料根目录不匹配")
    expected_ids = [game.game_id for game in inventory.games]
    if (
        not isinstance(records, list)
        or not all(isinstance(record, dict) for record in records)
        or [record.get("game_id") for record in records] != expected_ids
    ):
        raise ValueError("审计状态的游戏 ID 不匹配")
    games = []
    for source, record in zip(inventory.games, records, strict=True):
        _validate_game_record(record, source)
        games.append(CorpusAuditGame(
            game_id=source.game_id,
            source_path=source.source_path,
            status=str(record.get("status", "pending")),
            input_fingerprint=record.get("input_fingerprint"),
            source_manifest=record["source_manifest"],
            status_counts=record.get("status_counts"),
            role_counts=record.get("role_counts"),
            confidence_counts=record.get("confidence_counts"),
            reason_counts=record.get("reason_counts"),
            disposition_counts=record.get("disposition_counts"),
            failure_category=record.get("failure_category"),
            diagnostic=record.get("diagnostic"),
        ))
    return CorpusAudit(corpus_root, tuple(games))


def _counts(entries: list[dict]) -> tuple[dict[str, int], ...]:
    fields = ("status", "role", "confidence", "reason", "disposition")
    summaries = {field: {} for field in fields}
    for entry in entries:
        try:
            meta = json.loads(entry.get("meta") or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        values = {"status": entry.get("status", "unknown")}
        values.update({field: meta.get(field, "unknown") for field in fields[1:]})
        for field, value in values.items():
            key = str(value)
            summaries[field][key] = summaries[field].get(key, 0) + 1
    return tuple(dict(sorted(summaries[field].items())) for field in fields)


def _failure_category(exc: BaseException, phase: str) -> str:
    if isinstance(exc, FingerprintError):
        return "fingerprint"
    if isinstance(exc, PermissionError):
        return "permission"
    if isinstance(exc, sqlite3.Error):
        return "project_store"
    return f"{phase}_exception"


def _safe_diagnostic(exc: BaseException) -> dict[str, str | int | None]:
    diagnostic = sanitize_exception(exc)
    message = str(diagnostic.get("message") or "")
    for pattern, replacement in _DIAGNOSTIC_PATTERNS:
        message = pattern.sub(replacement, message)
    message = " ".join(message.split())[:240]
    status = diagnostic.get("status")
    if isinstance(status, str):
        for pattern, replacement in _DIAGNOSTIC_PATTERNS:
            status = pattern.sub(replacement, status)
        status = status[:80]
    elif not isinstance(status, int):
        status = None
    return {
        "type": str(diagnostic.get("type") or type(exc).__name__)[:80],
        "status": status,
        "message": message,
    }


def _recover_stale_running(state: CorpusAudit) -> tuple[CorpusAudit, bool]:
    recovered = tuple(
        CorpusAuditGame(game.game_id, game.source_path)
        if game.status == "running" else game
        for game in state.games
    )
    changed = recovered != state.games
    return (replace(state, games=recovered) if changed else state), changed


def audit_inventory(
    inventory: CorpusInventory,
    app_dir: str | Path,
    state_path: str | Path,
    project_factory=Project.open_game_dir,
    checkpoint: Checkpoint | None = None,
    force: bool = False,
) -> CorpusAudit:
    """Audit every game independently and atomically persist each transition."""
    root = _corpus_root(inventory)
    target = Path(state_path)
    _validate_state_location(target, inventory)

    def persist(current_state: CorpusAudit) -> None:
        _validate_state_location(target, inventory)
        _write_state(current_state, target)

    state = _load_state(target, inventory, root)
    if state is None:
        games = tuple(
            CorpusAuditGame(game.game_id, game.source_path) for game in inventory.games)
        state = CorpusAudit(root, games)
    state, recovered = _recover_stale_running(state)
    if recovered:
        persist(state)

    for index, game in enumerate(inventory.games):
        previous = state.games[index]
        if previous.status == "passed" and not force:
            try:
                current_manifest = source_tree_manifest(game.source_path)
            except (OSError, FingerprintError):
                pass
            else:
                if previous.input_fingerprint == _fingerprint(current_manifest):
                    continue
        current = CorpusAuditGame(
            game_id=game.game_id,
            source_path=game.source_path,
            status="running",
        )
        state = replace(state, games=state.games[:index] + (current,) + state.games[index + 1:])
        persist(state)
        phase = "fingerprint"
        project = None
        before: dict[str, str] | None = None
        close_failure: BaseException | None = None
        try:
            before = source_tree_manifest(game.source_path)
            input_fingerprint = _fingerprint(before)
            phase = "analysis"
            project = project_factory(game.source_path, app_dir)
            phase = "scan"
            report = project.scan_all()
            status, role, confidence, reason, disposition = _counts(
                project.store.get_entries())
            phase = "integrity"
            after = source_tree_manifest(game.source_path)
            if before != after:
                raise RuntimeError("source_drift")
            current = replace(
                current,
                status="passed" if report.unblocked else "blocked",
                input_fingerprint=input_fingerprint,
                source_manifest=after,
                status_counts=status,
                role_counts=role,
                confidence_counts=confidence,
                reason_counts=reason,
                disposition_counts=disposition,
            )
        except Exception as exc:  # noqa: BLE001 单游戏失败不得终止批处理
            category = (
                "source_drift"
                if phase == "integrity" and str(exc) == "source_drift"
                else _failure_category(exc, phase)
            )
            current = replace(
                current,
                status="failed",
                input_fingerprint=_fingerprint(before) if before is not None else None,
                source_manifest=before,
                failure_category=category,
                diagnostic=_safe_diagnostic(exc),
            )
        finally:
            if project is not None:
                try:
                    project.store.close()
                except Exception as exc:  # noqa: BLE001 关闭失败也必须隔离到单游戏
                    close_failure = exc
        if close_failure is not None and current.status != "failed":
            current = replace(
                current,
                status="failed",
                failure_category=_failure_category(close_failure, "scan"),
                diagnostic=_safe_diagnostic(close_failure),
            )
        state = replace(state, games=state.games[:index] + (current,) + state.games[index + 1:])
        persist(state)
        if checkpoint is not None:
            checkpoint(target)
    return state
