from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

import hanhua.core.corpus.audit as audit_module
from hanhua.core.corpus.audit import audit_inventory
from hanhua.core.corpus.models import CorpusGame, CorpusInventory
from hanhua.core.tooling.fingerprint import FingerprintError
from tests.test_tooling_runner import _make_junction


def _inventory(tmp_path: Path, *game_ids: str) -> CorpusInventory:
    games = []
    for game_id in game_ids:
        source = tmp_path / "games" / game_id
        source.mkdir(parents=True)
        (source / "content.bin").write_bytes(game_id.encode("utf-8"))
        games.append(CorpusGame(
            game_id=game_id,
            source_path=source.resolve(),
            executable_path=f"{game_id}.exe",
            data_path=f"{game_id}_Data",
            unity_version="2021.3.1f1",
            runtime="mono",
            metadata_version=None,
            evidence=("managed_assembly",),
            capabilities=("native_mono_literal_extract",),
            file_count=1,
            total_bytes=len(game_id.encode("utf-8")),
        ))
    return CorpusInventory(tuple(games))


class _Store:
    def __init__(self, entries=(), close_error=None):
        self._entries = entries if isinstance(entries, BaseException) else list(entries)
        self.close_error = close_error
        self.closed = False

    def get_entries(self):
        if isinstance(self._entries, BaseException):
            raise self._entries
        return list(self._entries)

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _Project:
    def __init__(self, outcome, entries=()):
        self.outcome = outcome
        self.store = _Store(entries)

    def scan_all(self):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        if callable(self.outcome):
            self.outcome()
        return SimpleNamespace(unblocked=bool(self.outcome))


def test_audit_isolates_failure_and_checkpoints_each_terminal_game(tmp_path):
    inventory = _inventory(tmp_path, "broken", "healthy")
    projects = {
        "broken": _Project(RuntimeError("parse failed")),
        "healthy": _Project(True),
    }
    snapshots = []

    def factory(source_path, app_dir):
        del app_dir
        return projects[Path(source_path).name]

    result = audit_inventory(
        inventory,
        tmp_path / "app",
        tmp_path / "state.json",
        project_factory=factory,
        checkpoint=lambda path: snapshots.append(json.loads(
            path.read_text(encoding="utf-8"))),
    )

    assert [game.status for game in result.games] == ["failed", "passed"]
    assert result.games[0].failure_category == "scan_exception"
    assert result.games[1].failure_category is None
    assert len(snapshots) == 2
    assert snapshots[0]["games"][0]["status"] == "failed"
    assert snapshots[1]["games"][1]["status"] == "passed"
    assert all(project.store.closed for project in projects.values())


def test_audit_resumes_passed_game_when_input_fingerprint_is_unchanged(tmp_path):
    inventory = _inventory(tmp_path, "stable")
    audit_inventory(
        inventory,
        tmp_path / "app",
        tmp_path / "state.json",
        project_factory=lambda source, app: _Project(True),
    )

    def must_not_open(source, app):
        raise AssertionError(f"resumed game was reopened: {source} {app}")

    resumed = audit_inventory(
        inventory,
        tmp_path / "app",
        tmp_path / "state.json",
        project_factory=must_not_open,
    )

    assert resumed.games[0].status == "passed"


def test_audit_atomically_recovers_all_stale_running_before_resume(
        tmp_path, monkeypatch):
    game_ids = ("blocked", "pending", "failed", "stale-a", "stale-b", "passed")
    inventory = _inventory(tmp_path, *game_ids)
    state_path = tmp_path / "state.json"
    audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: _Project(True),
    )
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    statuses = ("blocked", "pending", "failed", "running", "running", "passed")
    for game, status in zip(payload["games"], statuses, strict=True):
        game["status"] = status
    payload["games"][2]["failure_category"] = "scan_exception"
    payload["games"][2]["diagnostic"] = {
        "type": "RuntimeError", "status": None, "message": "old failure",
    }
    original_records = json.loads(json.dumps(payload["games"]))
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    writes = []
    terminal_callbacks = []
    factory_calls = []
    original_write = audit_module._write_state

    def capture_write(state, target):
        original_write(state, target)
        writes.append(json.loads(target.read_text(encoding="utf-8")))

    def factory(source, app):
        del app
        factory_calls.append(Path(source).name)
        on_disk = json.loads(state_path.read_text(encoding="utf-8"))
        if len(factory_calls) == 1:
            assert on_disk["games"][3]["status"] == "pending"
            assert on_disk["games"][4]["status"] == "pending"
        assert sum(game["status"] == "running" for game in on_disk["games"]) <= 1
        return _Project(True)

    monkeypatch.setattr(audit_module, "_write_state", capture_write)

    result = audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=factory,
        checkpoint=lambda path: terminal_callbacks.append(json.loads(
            path.read_text(encoding="utf-8"))),
    )

    assert len(writes) >= 1
    recovered = writes[0]["games"]
    for index in (0, 1, 2, 5):
        assert recovered[index] == original_records[index]
    for index in (3, 4):
        assert recovered[index] == {
            "game_id": game_ids[index],
            "source_path": str(inventory.games[index].source_path),
            "status": "pending",
            "input_fingerprint": None,
            "source_manifest": None,
            "status_counts": None,
            "role_counts": None,
            "confidence_counts": None,
            "reason_counts": None,
            "disposition_counts": None,
            "failure_category": None,
            "diagnostic": None,
        }
    assert all(
        sum(game["status"] == "running" for game in snapshot["games"]) <= 1
        for snapshot in writes[1:]
    )
    assert factory_calls == list(game_ids[:-1])
    assert len(terminal_callbacks) == len(factory_calls)
    assert [game.status for game in result.games] == ["passed"] * len(game_ids)


def test_audit_recovery_write_failure_preserves_state_and_stops_work(
        tmp_path, monkeypatch):
    inventory = _inventory(tmp_path, "stale", "passed")
    state_path = tmp_path / "state.json"
    audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: _Project(True),
    )
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["games"][0]["status"] = "running"
    original = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    state_path.write_bytes(original)
    factory_calls = []

    def fail_replace(source, target):
        raise PermissionError(f"cannot replace {source} with {target}")

    monkeypatch.setattr(audit_module.os, "replace", fail_replace)

    with pytest.raises(PermissionError, match="cannot replace"):
        audit_inventory(
            inventory, tmp_path / "app", state_path,
            project_factory=lambda source, app: factory_calls.append(source),
        )

    assert state_path.read_bytes() == original
    assert not list(tmp_path.glob(f".{state_path.name}.*.tmp"))
    assert factory_calls == []


def test_audit_resume_without_running_state_does_not_write(tmp_path, monkeypatch):
    inventory = _inventory(tmp_path, "passed")
    state_path = tmp_path / "state.json"
    audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: _Project(True),
    )
    original = state_path.read_bytes()
    original_mtime = state_path.stat().st_mtime_ns

    def unexpected_write(state, target):
        raise AssertionError(f"no-running resume rewrote {target}: {state}")

    monkeypatch.setattr(audit_module, "_write_state", unexpected_write)

    result = audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: (_ for _ in ()).throw(
            AssertionError("unchanged passed game was reopened")),
    )

    assert result.games[0].status == "passed"
    assert state_path.read_bytes() == original
    assert state_path.stat().st_mtime_ns == original_mtime


def test_audit_reruns_passed_game_after_source_change_or_with_force(tmp_path):
    inventory = _inventory(tmp_path, "changing")
    state_path = tmp_path / "state.json"
    calls = []

    def factory(source, app):
        del app
        calls.append(Path(source))
        return _Project(True)

    audit_inventory(inventory, tmp_path / "app", state_path, project_factory=factory)
    (inventory.games[0].source_path / "content.bin").write_bytes(b"changed")
    audit_inventory(inventory, tmp_path / "app", state_path, project_factory=factory)
    audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=factory, force=True,
    )

    assert calls == [inventory.games[0].source_path] * 3


def test_audit_detects_source_drift_and_closes_store(tmp_path):
    inventory = _inventory(tmp_path, "drifting")
    source_file = inventory.games[0].source_path / "content.bin"
    project = _Project(lambda: source_file.write_bytes(b"mutated during scan"))

    result = audit_inventory(
        inventory, tmp_path / "app", tmp_path / "state.json",
        project_factory=lambda source, app: project,
    )

    assert result.games[0].status == "failed"
    assert result.games[0].failure_category == "source_drift"
    assert project.store.closed is True


def test_audit_reports_blocked_and_summarizes_entry_evidence(tmp_path):
    inventory = _inventory(tmp_path, "blocked")
    entries = [
        {"status": "pending", "meta": json.dumps({
            "role": "display", "confidence": "high",
            "reason": "natural_language", "disposition": "translate",
        })},
        {"status": "skipped", "meta": json.dumps({
            "role": "structural", "confidence": "low",
            "reason": "identifier", "disposition": "structural",
        })},
    ]

    result = audit_inventory(
        inventory, tmp_path / "app", tmp_path / "state.json",
        project_factory=lambda source, app: _Project(False, entries),
    )

    game = result.games[0]
    assert game.status == "blocked"
    assert game.status_counts == {"pending": 1, "skipped": 1}
    assert game.role_counts == {"display": 1, "structural": 1}
    assert game.confidence_counts == {"high": 1, "low": 1}
    assert game.reason_counts == {"identifier": 1, "natural_language": 1}
    assert game.disposition_counts == {"structural": 1, "translate": 1}


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (FingerprintError("bad fingerprint"), "fingerprint"),
        (PermissionError("denied"), "permission"),
        (sqlite3.DatabaseError("bad db"), "project_store"),
        (RuntimeError("analysis failed"), "analysis_exception"),
    ],
)
def test_audit_maps_factory_failures_without_stopping(failure, expected, tmp_path):
    inventory = _inventory(tmp_path, "first", "second")

    def factory(source, app):
        del app
        if Path(source).name == "first":
            raise failure
        return _Project(True)

    result = audit_inventory(
        inventory, tmp_path / "app", tmp_path / "state.json",
        project_factory=factory,
    )

    assert [game.status for game in result.games] == ["failed", "passed"]
    assert result.games[0].failure_category == expected
    assert set(result.games[0].diagnostic) == {"type", "status", "message"}
    assert "Traceback" not in json.dumps(result.games[0].diagnostic)


def test_audit_closes_store_when_evidence_summary_fails(tmp_path):
    inventory = _inventory(tmp_path, "summary-error")
    project = _Project(True)
    project.store = _Store(sqlite3.DatabaseError("query failed"))

    result = audit_inventory(
        inventory, tmp_path / "app", tmp_path / "state.json",
        project_factory=lambda source, app: project,
    )

    assert result.games[0].failure_category == "project_store"
    assert project.store.closed is True


def test_audit_isolates_store_close_failure(tmp_path):
    inventory = _inventory(tmp_path, "close-error", "healthy")
    broken = _Project(True)
    broken.store = _Store(close_error=sqlite3.DatabaseError("close failed"))

    result = audit_inventory(
        inventory, tmp_path / "app", tmp_path / "state.json",
        project_factory=lambda source, app: (
            broken if Path(source).name == "close-error" else _Project(True)
        ),
    )

    assert [game.status for game in result.games] == ["failed", "passed"]
    assert result.games[0].failure_category == "project_store"
    assert broken.store.closed is True


def test_audit_clears_stale_failure_after_successful_retry(tmp_path):
    inventory = _inventory(tmp_path, "retry")
    state_path = tmp_path / "state.json"
    audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: _Project(RuntimeError("first run")),
    )

    retried = audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: _Project(True),
    )

    assert retried.games[0].status == "passed"
    assert retried.games[0].failure_category is None
    assert retried.games[0].diagnostic is None


@pytest.mark.parametrize("mutation", ["schema", "root", "ids", "json"])
def test_audit_rejects_invalid_resume_state(tmp_path, mutation):
    inventory = _inventory(tmp_path, "stable")
    state_path = tmp_path / "state.json"
    audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: _Project(True),
    )
    if mutation == "json":
        state_path.write_text("{broken", encoding="utf-8")
    else:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        if mutation == "schema":
            payload["schema_version"] = 999
        elif mutation == "root":
            payload["corpus_root"] = str(tmp_path / "somewhere-else")
        else:
            payload["games"][0]["game_id"] = "different"
        state_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="状态|schema|根目录|游戏 ID"):
        audit_inventory(
            inventory, tmp_path / "app", state_path,
            project_factory=lambda source, app: _Project(True),
        )


def test_audit_rejects_state_inside_source_tree_before_any_source_mutation(tmp_path):
    inventory = _inventory(tmp_path, "protected")
    source = inventory.games[0].source_path
    before = {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*") if path.is_file()
    }

    with pytest.raises(ValueError, match="状态文件|源目录"):
        audit_inventory(
            inventory,
            tmp_path / "app",
            source / "audit-state.json",
            project_factory=lambda source_path, app: _Project(True),
        )

    after = {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*") if path.is_file()
    }
    assert after == before


def test_audit_ignores_predictable_temp_symlink_without_altering_sentinel(tmp_path):
    inventory = _inventory(tmp_path, "safe-temp")
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_bytes(b"do not alter")
    state_path = tmp_path / "state.json"
    temporary = state_path.with_name(state_path.name + ".tmp")
    try:
        os.symlink(sentinel, temporary)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")

    result = audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: _Project(True),
    )

    assert result.games[0].status == "passed"
    assert sentinel.read_bytes() == b"do not alter"
    assert temporary.is_symlink()
    assert not list(tmp_path.glob(f".{state_path.name}.*.tmp"))


def test_audit_ignores_predictable_temp_name_collision(tmp_path):
    inventory = _inventory(tmp_path, "temp-collision")
    state_path = tmp_path / "state.json"
    predictable = state_path.with_name(state_path.name + ".tmp")
    predictable.write_bytes(b"unrelated sentinel")

    result = audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: _Project(True),
    )

    assert result.games[0].status == "passed"
    assert predictable.read_bytes() == b"unrelated sentinel"
    assert not list(tmp_path.glob(f".{state_path.name}.*.tmp"))


def test_audit_removes_owned_random_temp_when_replace_fails(tmp_path, monkeypatch):
    inventory = _inventory(tmp_path, "replace-failure")
    state_path = tmp_path / "state.json"

    def fail_replace(source, target):
        raise PermissionError(f"cannot replace {source} with {target}")

    monkeypatch.setattr(audit_module.os, "replace", fail_replace)

    with pytest.raises(PermissionError):
        audit_inventory(
            inventory, tmp_path / "app", state_path,
            project_factory=lambda source, app: _Project(True),
        )

    assert not state_path.exists()
    assert not list(tmp_path.glob(f".{state_path.name}.*.tmp"))


def test_audit_rejects_state_target_symlink_without_altering_sentinel(tmp_path):
    inventory = _inventory(tmp_path, "safe-target")
    sentinel = tmp_path / "target-sentinel.txt"
    sentinel.write_bytes(b"do not alter")
    state_path = tmp_path / "state.json"
    try:
        os.symlink(sentinel, state_path)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")

    with pytest.raises(ValueError, match="reparse|重解析"):
        audit_inventory(
            inventory, tmp_path / "app", state_path,
            project_factory=lambda source, app: _Project(True),
        )

    assert sentinel.read_bytes() == b"do not alter"


def test_audit_rejects_state_parent_junction_without_altering_sentinel(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows junction test")
    inventory = _inventory(tmp_path, "safe-parent")
    outside = tmp_path / "outside-state"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"do not alter")
    junction = tmp_path / "state-junction"
    _make_junction(junction, outside)
    try:
        with pytest.raises(ValueError, match="reparse|重解析"):
            audit_inventory(
                inventory, tmp_path / "app", junction / "state.json",
                project_factory=lambda source, app: _Project(True),
            )
        assert sentinel.read_bytes() == b"do not alter"
        assert not (outside / "state.json").exists()
    finally:
        os.rmdir(junction)


@pytest.mark.parametrize(
    "mutation",
    [
        "top_extra", "top_missing", "game_extra", "game_missing",
        "source_path", "status", "fingerprint_type", "fingerprint_format",
        "manifest_hash", "counts_shape", "counts_negative", "counts_bool",
        "failure_category", "diagnostic_type", "diagnostic_fields",
        "diagnostic_value",
    ],
)
def test_audit_strictly_rejects_malformed_passed_resume_record(tmp_path, mutation):
    inventory = _inventory(tmp_path, "strict-resume")
    state_path = tmp_path / "state.json"
    audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: _Project(True),
    )
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    game = payload["games"][0]
    if mutation == "top_extra":
        payload["unexpected"] = True
    elif mutation == "top_missing":
        del payload["corpus_root"]
    elif mutation == "game_extra":
        game["unexpected"] = True
    elif mutation == "game_missing":
        del game["status_counts"]
    elif mutation == "source_path":
        game["source_path"] = str(tmp_path / "different")
    elif mutation == "status":
        game["status"] = "passed-ish"
    elif mutation == "fingerprint_type":
        game["input_fingerprint"] = 123
    elif mutation == "fingerprint_format":
        game["input_fingerprint"] = "not-sha256"
    elif mutation == "manifest_hash":
        game["source_manifest"]["content.bin"] = "bad"
    elif mutation == "counts_shape":
        game["status_counts"] = []
    elif mutation == "counts_negative":
        game["role_counts"] = {"display": -1}
    elif mutation == "counts_bool":
        game["confidence_counts"] = {"high": True}
    elif mutation == "failure_category":
        game["failure_category"] = 123
    elif mutation == "diagnostic_type":
        game["diagnostic"] = "unsafe"
    elif mutation == "diagnostic_fields":
        game["diagnostic"] = {"type": "RuntimeError", "message": "x"}
    else:
        game["diagnostic"] = {
            "type": "RuntimeError", "status": False, "message": "x",
        }
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="状态|记录|字段|摘要|计数|诊断"):
        audit_inventory(
            inventory, tmp_path / "app", state_path,
            project_factory=lambda source, app: (_ for _ in ()).throw(
                AssertionError("malformed passed state must not be resumed")),
        )


def test_audit_persists_only_bounded_redacted_diagnostics(tmp_path):
    inventory = _inventory(tmp_path, "secret-error")
    state_path = tmp_path / "state.json"
    sensitive = RuntimeError(
        "POST https://user:pass@example.com/private?api_key=URLSECRET "
        "Authorization: Bearer AUTHSECRET api_key=sk-LOCALSECRET "
        "token=TOKENSECRET body: BODYSECRET"
    )

    result = audit_inventory(
        inventory, tmp_path / "app", state_path,
        project_factory=lambda source, app: _Project(sensitive),
    )

    serialized = state_path.read_text(encoding="utf-8")
    diagnostic = result.games[0].diagnostic
    assert diagnostic is not None
    assert len(diagnostic["message"]) <= 240
    for forbidden in (
        "http://", "https://", "user:pass", "URLSECRET", "AUTHSECRET",
        "sk-LOCALSECRET", "TOKENSECRET", "BODYSECRET", "Bearer",
    ):
        assert forbidden not in serialized
    assert "Traceback" not in serialized
