"""Command-line entry point for read-only Unity corpus audits."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any, Iterator, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hanhua.core.corpus import audit_inventory, build_inventory
from hanhua.core.corpus.models import CorpusAudit, CorpusInventory
from hanhua.core.paths import _is_reparse_point


_ABSOLUTE_PATH_PATTERNS = (
    re.compile(
        r"(?i)\\\\\?\\(?:UNC\\[^\\/\s\"']+\\[^\\/\s\"']+|"
        r"[A-Z]:\\)[^\r\n\"']*"),
    re.compile(
        r"(?i)(?<!\\)\\\\(?!\?\\)[^\\/\s\"']+\\[^\\/\s\"']+"
        r"(?:\\[^\r\n\"']*)?"),
    re.compile(r"(?i)[A-Z]:[\\/][^\r\n\"']*"),
    re.compile(
        r"^//[^/\\\s\"']+/[^/\\\s\"']+(?:/[^\r\n\"']*)?"),
    re.compile(
        r"(?<=[\s\"'=/(:,\[])//[^/\\\s\"']+/[^/\\\s\"']+"
        r"(?:/[^\r\n\"']*)?"),
    re.compile(r"^/(?!/)[^\r\n\"']+"),
    re.compile(r"(?<=[\s\"'=/(:,\[])/(?!/)[^\r\n\"']+"),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory or audit an explicit directory of Unity games.")
    parser.add_argument("--games-root", required=True)
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def _validate_safe_location(
        target: Path, corpus_root: Path, *, label: str) -> None:
    lexical_target = target.absolute()
    if any(
        _is_reparse_point(path)
        for path in (lexical_target, *lexical_target.parents)
    ):
        raise ValueError(f"{label} path cannot contain a reparse point")
    try:
        resolved_target = lexical_target.resolve(strict=False)
        resolved_corpus_root = corpus_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"cannot safely resolve {label} path") from exc
    try:
        resolved_target.relative_to(resolved_corpus_root)
    except ValueError:
        return
    raise ValueError(f"{label} cannot be inside the corpus root")


@contextmanager
def _audit_lock(state_path: Path, corpus_root: Path) -> Iterator[Path]:
    lock_path = Path(f"{state_path}.lock")
    _validate_safe_location(lock_path, corpus_root, label="audit lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    _validate_safe_location(lock_path, corpus_root, label="audit lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    acquired = False
    try:
        _validate_safe_location(lock_path, corpus_root, label="audit lock")
        descriptor_stat = os.fstat(descriptor)
        path_stat = os.stat(lock_path, follow_symlinks=False)
        if (
            not stat.S_ISREG(descriptor_stat.st_mode)
            or (descriptor_stat.st_dev, descriptor_stat.st_ino)
            != (path_stat.st_dev, path_stat.st_ino)
        ):
            raise ValueError("audit lock path is not a stable regular file")
        if descriptor_stat.st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("another corpus audit is already running") from exc
        acquired = True
        yield lock_path
    finally:
        if acquired:
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _atomic_write_json(
        payload: dict[str, object], target: Path,
        corpus_root: Path, *, label: str) -> None:
    _validate_safe_location(target, corpus_root, label=label)
    target.parent.mkdir(parents=True, exist_ok=True)
    _validate_safe_location(target, corpus_root, label=label)
    encoded = json.dumps(
        payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor = -1
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        temporary = Path(name)
        with os.fdopen(
            descriptor, "w", encoding="utf-8", newline="\n",
        ) as stream:
            descriptor = -1
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        _validate_safe_location(target, corpus_root, label=label)
        os.replace(temporary, target)
        temporary = None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _portable_audit(audit: CorpusAudit) -> dict[str, object]:
    games: list[dict[str, Any]] = []
    source_strings = {
        str(audit.corpus_root),
        *(str(game.source_path) for game in audit.games),
    }

    def portable_value(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: portable_value(item) for key, item in value.items()
                if key not in {"source_path", "corpus_root"}
            }
        if isinstance(value, list):
            return [portable_value(item) for item in value]
        if isinstance(value, str):
            for source in sorted(source_strings, key=len, reverse=True):
                value = value.replace(source, "<source>")
            for pattern in _ABSOLUTE_PATH_PATTERNS:
                value = pattern.sub("<path>", value)
            return value
        return value

    for game in audit.games:
        games.append(portable_value(game.to_state_dict()))
    return {
        "schema_version": audit.schema_version,
        "report_type": "audit",
        "games": games,
    }


def _inventory_report(inventory: CorpusInventory) -> dict[str, object]:
    payload = inventory.to_portable_dict()
    return {
        "schema_version": payload["schema_version"],
        "report_type": "inventory",
        "games": payload["games"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    state_path = Path(args.state)
    report_path = Path(args.report)
    try:
        if state_path.absolute() == report_path.absolute():
            raise ValueError("state and report paths must be different")
        inventory = build_inventory(args.games_root)
        corpus_root = Path(args.games_root).expanduser().resolve(strict=True)
        _validate_safe_location(
            Path(args.app_dir), corpus_root, label="app directory")
        _validate_safe_location(state_path, corpus_root, label="state")
        _validate_safe_location(report_path, corpus_root, label="report")
        if args.inventory_only:
            _atomic_write_json(
                _inventory_report(inventory), report_path, corpus_root,
                label="report")
            for game in inventory.games:
                print(f"{game.game_id}: inventoried runtime={game.runtime}")
            print(f"summary: inventoried={len(inventory.games)}")
            return 0

        with _audit_lock(state_path, corpus_root):
            audit = audit_inventory(
                inventory,
                app_dir=args.app_dir,
                state_path=state_path,
                force=args.force,
            )
            _atomic_write_json(
                _portable_audit(audit), report_path, corpus_root,
                label="report")
        counts = {status: 0 for status in ("passed", "blocked", "failed")}
        for game in audit.games:
            if game.status in counts:
                counts[game.status] += 1
            print(f"{game.game_id}: {game.status}")
        print(
            "summary: "
            f"passed={counts['passed']} blocked={counts['blocked']} "
            f"failed={counts['failed']}")
        return 0 if counts["blocked"] == counts["failed"] == 0 else 1
    except (OSError, ValueError) as exc:
        print(f"corpus audit error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
