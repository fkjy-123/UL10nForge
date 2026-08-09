"""语料清单的不可变数据模型。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CorpusGame:
    game_id: str
    source_path: Path
    executable_path: str | None
    data_path: str | None
    unity_version: str
    runtime: str
    metadata_version: int | None
    evidence: tuple[str, ...]
    capabilities: tuple[str, ...]
    file_count: int
    total_bytes: int

    def to_state_dict(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "source_path": str(self.source_path),
            "executable_path": self.executable_path,
            "data_path": self.data_path,
            "unity_version": self.unity_version,
            "runtime": self.runtime,
            "metadata_version": self.metadata_version,
            "evidence": list(self.evidence),
            "capabilities": list(self.capabilities),
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
        }

    def to_portable_dict(self) -> dict[str, object]:
        payload = self.to_state_dict()
        del payload["source_path"]
        return payload


@dataclass(frozen=True)
class CorpusInventory:
    games: tuple[CorpusGame, ...]
    schema_version: int = SCHEMA_VERSION

    def to_state_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "games": [game.to_state_dict() for game in self.games],
        }

    def to_portable_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "games": [game.to_portable_dict() for game in self.games],
        }


@dataclass(frozen=True)
class CorpusAuditGame:
    game_id: str
    source_path: Path
    status: str = "pending"
    input_fingerprint: str | None = None
    source_manifest: dict[str, str] | None = None
    status_counts: dict[str, int] | None = None
    role_counts: dict[str, int] | None = None
    confidence_counts: dict[str, int] | None = None
    reason_counts: dict[str, int] | None = None
    disposition_counts: dict[str, int] | None = None
    failure_category: str | None = None
    diagnostic: dict[str, Any] | None = None

    def to_state_dict(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "source_path": str(self.source_path),
            "status": self.status,
            "input_fingerprint": self.input_fingerprint,
            "source_manifest": self.source_manifest,
            "status_counts": self.status_counts,
            "role_counts": self.role_counts,
            "confidence_counts": self.confidence_counts,
            "reason_counts": self.reason_counts,
            "disposition_counts": self.disposition_counts,
            "failure_category": self.failure_category,
            "diagnostic": self.diagnostic,
        }


@dataclass(frozen=True)
class CorpusAudit:
    corpus_root: Path
    games: tuple[CorpusAuditGame, ...]
    schema_version: int = SCHEMA_VERSION

    def to_state_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "corpus_root": str(self.corpus_root),
            "games": [game.to_state_dict() for game in self.games],
        }
