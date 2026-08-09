import sqlite3
from dataclasses import FrozenInstanceError
from time import perf_counter

import pytest

from hanhua.core.memory import ProjectStore
from hanhua.core.models import GameProfile
from hanhua.core.memory_lifecycle import (
    MemoryCleanupFailure,
    MemoryCleanupSummary,
    clear_all_project_records,
)


def _project_store(app_dir, project_id):
    store = ProjectStore(app_dir / "projects" / project_id / "project.db")
    store.init_schema()
    return store


def test_clear_all_project_records_returns_empty_summary(tmp_path):
    summary = clear_all_project_records(tmp_path)

    assert summary.discovered_databases == 0
    assert summary.cleared_databases == 0
    assert summary.cleared_rows == 0
    assert summary.failures == ()
    assert summary.failed_databases == 0


def test_clear_all_project_records_skips_empty_sqlite_without_modifying_it(
        tmp_path):
    database = tmp_path / "projects" / "empty" / "project.db"
    database.parent.mkdir(parents=True)
    sqlite3.connect(database).close()

    summary = clear_all_project_records(tmp_path)

    assert summary.discovered_databases == 1
    assert summary.cleared_databases == 0
    assert summary.skipped_databases == 1
    assert summary.failures == ()
    with sqlite3.connect(database) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'",
        ).fetchall()
    assert tables == []


def test_clear_all_project_records_skips_unrelated_sqlite(tmp_path):
    database = tmp_path / "projects" / "foreign" / "project.db"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE unrelated(value TEXT)")
        connection.execute("INSERT INTO unrelated VALUES ('preserved')")

    summary = clear_all_project_records(tmp_path)

    assert summary.skipped_databases == 1
    assert summary.failures == ()
    with sqlite3.connect(database) as connection:
        value = connection.execute("SELECT value FROM unrelated").fetchone()[0]
    assert value == "preserved"


def test_clear_all_project_records_rejects_partial_project_schema(tmp_path):
    database = tmp_path / "projects" / "partial" / "project.db"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE memory(value TEXT)")
        connection.execute("INSERT INTO memory VALUES ('preserved')")

    summary = clear_all_project_records(tmp_path)

    assert summary.cleared_databases == 0
    assert summary.skipped_databases == 0
    assert summary.failed_databases == 1
    assert summary.failures[0].error == "incomplete project schema"
    with sqlite3.connect(database) as connection:
        value = connection.execute("SELECT value FROM memory").fetchone()[0]
    assert value == "preserved"


def test_memory_cleanup_results_are_immutable():
    failure = MemoryCleanupFailure(project_id="alpha", error="forced")
    summary = MemoryCleanupSummary(failures=(failure,))

    with pytest.raises(FrozenInstanceError):
        failure.error = "changed"
    with pytest.raises(FrozenInstanceError):
        summary.cleared_rows = 1


def test_clear_all_project_records_clears_every_project_database(tmp_path):
    for project_id, rows in (("alpha", 1), ("beta", 2)):
        store = _project_store(tmp_path, project_id)
        for index in range(rows):
            store.add_file(
                f"file-{project_id}-{index}", f"{project_id}/{index}.txt",
                "txt", "utf-8", "lf",
            )
            store.upsert_entries([
                {"file_id": f"file-{project_id}-{index}",
                 "key_path": f"line/{index}", "original": f"source-{index}",
                 "status": "translated", "meta": "{}"},
            ])
            store.add_memory(
                f"source-{project_id}-{index}", f"target-{index}", "m1", "en→zh-CN",
            )
        store.set_profile(GameProfile(game_name=f"{project_id}-game"))
        store.close()

    summary = clear_all_project_records(tmp_path)

    assert summary.discovered_databases == 2
    assert summary.cleared_databases == 2
    assert summary.cleared_entries == 3
    assert summary.cleared_memory == 3
    assert summary.cleared_rows == 6
    assert summary.failures == ()
    for project_id in ("alpha", "beta"):
        store = _project_store(tmp_path, project_id)
        assert store.get_files() == []
        assert store.get_entries() == []
        assert store.get_memory_hits(
            [f"source-{project_id}-0"], "m1", "en→zh-CN",
        ) == {}
        # 游戏档案(语言方向等配置)不是识别/翻译记录,必须保留
        assert store.get_profile().game_name == f"{project_id}-game"
        store.close()


def test_clear_all_project_records_isolates_broken_database(tmp_path):
    broken_database = tmp_path / "projects" / "alpha" / "project.db"
    broken_database.parent.mkdir(parents=True)
    broken_database.write_bytes(b"not a sqlite database")
    valid_store = _project_store(tmp_path, "beta")
    valid_store.add_memory("Hello", "你好", "m1", "en→zh-CN")
    valid_store.close()

    summary = clear_all_project_records(tmp_path)

    assert summary.discovered_databases == 2
    assert summary.cleared_databases == 1
    assert summary.cleared_rows == 1
    assert summary.failed_databases == 1
    assert summary.failures[0].project_id == "alpha"
    assert summary.failures[0].error
    reopened = _project_store(tmp_path, "beta")
    assert reopened.get_memory_hits(["Hello"], "m1", "en→zh-CN") == {}
    reopened.close()


def test_clear_all_project_records_bounds_locked_database_wait(tmp_path):
    store = _project_store(tmp_path, "locked")
    store.add_memory("Hello", "你好", "m1", "en→zh-CN")
    database = store.db
    store.close()
    locker = sqlite3.connect(database)
    locker.execute("BEGIN EXCLUSIVE")

    try:
        started = perf_counter()
        locked_summary = clear_all_project_records(tmp_path)
        elapsed = perf_counter() - started
        assert elapsed < 1.5
        assert locked_summary.failed_databases == 1
        assert locked_summary.cleared_databases == 0
    finally:
        locker.rollback()
        locker.close()

    retry_summary = clear_all_project_records(tmp_path)
    assert retry_summary.failed_databases == 0
    assert retry_summary.cleared_databases == 1
    assert retry_summary.cleared_rows == 1


def test_clear_all_project_records_closes_successful_store(
        tmp_path, monkeypatch):
    database = tmp_path / "projects" / "alpha" / "project.db"
    database.parent.mkdir(parents=True)
    database.touch()
    stores = []

    class RecordingStore:
        def __init__(self, _database, timeout):
            self.closed = False
            self.timeout = timeout
            stores.append(self)

        def schema_tables(self):
            return frozenset({"files", "entries", "memory", "profile"})

        def clear_records(self):
            return 2, 1

        def close(self):
            self.closed = True

    monkeypatch.setattr(
        "hanhua.core.memory_lifecycle.ProjectStore", RecordingStore,
    )

    summary = clear_all_project_records(tmp_path)

    assert summary.cleared_entries == 2
    assert summary.cleared_memory == 1
    assert summary.cleared_rows == 3
    assert len(stores) == 1
    assert stores[0].closed is True


def test_clear_all_project_records_closes_store_when_clear_fails(
        tmp_path, monkeypatch):
    database = tmp_path / "projects" / "alpha" / "project.db"
    database.parent.mkdir(parents=True)
    database.touch()
    stores = []

    class RecordingStore:
        def __init__(self, _database, timeout):
            self.closed = False
            self.timeout = timeout
            stores.append(self)

        def schema_tables(self):
            return frozenset({"files", "entries", "memory", "profile"})

        def clear_records(self):
            raise sqlite3.DatabaseError("forced")

        def close(self):
            self.closed = True

    monkeypatch.setattr(
        "hanhua.core.memory_lifecycle.ProjectStore", RecordingStore,
    )

    summary = clear_all_project_records(tmp_path)

    assert summary.failed_databases == 1
    assert len(stores) == 1
    assert stores[0].closed is True


def test_main_cleans_memory_after_settings_load_before_state_creation(monkeypatch):
    import main as entrypoint

    events = []
    cleanup_summary = object()

    class Signal:
        def connect(self, callback):
            events.append(("connect", callback))

    class Application:
        def __init__(self, _argv):
            self.aboutToQuit = Signal()

        def setApplicationName(self, _name):
            pass

        def setOrganizationName(self, _name):
            pass

        def exec(self):
            return 0

    class Settings:
        def __init__(self, _path):
            pass

        def load(self):
            events.append("settings-loaded")

    class State:
        def __init__(self, _app_dir, _settings, resource_dir, memory_cleanup=None):
            events.append(("state-created", memory_cleanup, resource_dir))

        def close(self):
            pass

    class Window:
        def __init__(self, _state):
            pass

        def show(self):
            pass

    monkeypatch.setattr(entrypoint, "QApplication", Application)
    monkeypatch.setattr(entrypoint, "SettingsStore", Settings)
    monkeypatch.setattr(entrypoint, "AppState", State)
    monkeypatch.setattr(entrypoint, "MainWindow", Window)
    monkeypatch.setattr(entrypoint, "apply_theme", lambda _app: None)
    monkeypatch.setattr(
        entrypoint,
        "clear_all_project_records",
        lambda _app_dir: events.append("memory-cleared") or cleanup_summary,
        raising=False,
    )
    monkeypatch.setattr(entrypoint.sys, "exit", lambda _code: None)

    entrypoint.main()

    assert events[0:2] == ["settings-loaded", "memory-cleared"]
    assert events[2][0:2] == ("state-created", cleanup_summary)
