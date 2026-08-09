from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from hanhua.core.memory import ProjectStore

STARTUP_MEMORY_TIMEOUT_SECONDS = 0.1
REQUIRED_PROJECT_TABLES = frozenset({"files", "entries", "memory", "profile"})


class _IncompleteProjectSchemaError(Exception):
    pass


@dataclass(frozen=True)
class MemoryCleanupFailure:
    project_id: str
    error: str


@dataclass(frozen=True)
class MemoryCleanupSummary:
    discovered_databases: int = 0
    cleared_databases: int = 0
    cleared_entries: int = 0
    cleared_memory: int = 0
    cleared_rows: int = 0
    failures: tuple[MemoryCleanupFailure, ...] = ()
    skipped_databases: int = 0

    @property
    def failed_databases(self) -> int:
        return len(self.failures)


def clear_all_project_records(app_dir: str | Path) -> MemoryCleanupSummary:
    """启动时清空所有项目的识别与翻译记录(files/entries/memory),保留游戏档案。"""
    databases = tuple(sorted((Path(app_dir) / "projects").glob("*/project.db")))
    cleared_entries = 0
    cleared_memory = 0
    cleared_databases = 0
    skipped_databases = 0
    failures: list[MemoryCleanupFailure] = []
    for database in databases:
        try:
            with closing(ProjectStore(
                    database, timeout=STARTUP_MEMORY_TIMEOUT_SECONDS)) as store:
                tables = store.schema_tables()
                if REQUIRED_PROJECT_TABLES <= tables:
                    rows = store.clear_records()
                elif REQUIRED_PROJECT_TABLES.isdisjoint(tables):
                    rows = None
                else:
                    raise _IncompleteProjectSchemaError
        except _IncompleteProjectSchemaError:
            failures.append(MemoryCleanupFailure(
                project_id=database.parent.name,
                error="incomplete project schema",
            ))
        except Exception as exc:  # noqa: BLE001 - one bad project must not block startup
            failures.append(MemoryCleanupFailure(
                project_id=database.parent.name,
                error=str(exc),
            ))
        else:
            if rows is None:
                skipped_databases += 1
            else:
                cleared_entries += rows[0]
                cleared_memory += rows[1]
                cleared_databases += 1
    return MemoryCleanupSummary(
        discovered_databases=len(databases),
        cleared_databases=cleared_databases,
        cleared_entries=cleared_entries,
        cleared_memory=cleared_memory,
        cleared_rows=cleared_entries + cleared_memory,
        failures=tuple(failures),
        skipped_databases=skipped_databases,
    )
