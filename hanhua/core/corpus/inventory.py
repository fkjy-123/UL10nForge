"""发现显式目录中的 Unity 游戏。"""
from __future__ import annotations

import os
from pathlib import Path

from hanhua.core.corpus.models import CorpusGame, CorpusInventory
from hanhua.core.paths import _is_reparse_point
from hanhua.core.tooling.fingerprint import fingerprint_game


def _regular_file_totals(root: Path) -> tuple[int, int]:
    count = 0
    total_bytes = 0
    pending = [root]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                if _is_reparse_point(Path(entry.path)):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    count += 1
                    total_bytes += entry.stat(follow_symlinks=False).st_size
    return count, total_bytes


def build_inventory(root: str | Path) -> CorpusInventory:
    corpus_root = Path(root).expanduser()
    if not corpus_root.exists():
        raise ValueError(f"语料根目录不存在：{corpus_root}")
    if not corpus_root.is_dir():
        raise ValueError(f"语料根目录不是目录：{corpus_root}")
    corpus_root = corpus_root.resolve()
    game_dirs = sorted(
        (path for path in corpus_root.iterdir()
         if path.is_dir() and not _is_reparse_point(path)),
        key=lambda path: (path.name.casefold(), path.name),
    )
    folded_ids = [path.name.casefold() for path in game_dirs]
    if len(folded_ids) != len(set(folded_ids)):
        raise ValueError("游戏 ID 忽略大小写后重复")
    games: list[CorpusGame] = []
    for game_dir in game_dirs:
        fingerprint = fingerprint_game(game_dir)
        source_root = fingerprint.game_dir
        file_count, total_bytes = _regular_file_totals(game_dir)
        games.append(CorpusGame(
            game_id=game_dir.name,
            source_path=game_dir.resolve(),
            executable_path=(
                fingerprint.executable.relative_to(source_root).as_posix()
                if fingerprint.executable is not None else None),
            data_path=(
                fingerprint.data_dir.relative_to(source_root).as_posix()
                if fingerprint.data_dir is not None else None),
            unity_version=fingerprint.unity_version,
            runtime=fingerprint.runtime,
            metadata_version=fingerprint.metadata_version,
            evidence=fingerprint.evidence,
            capabilities=fingerprint.capabilities,
            file_count=file_count,
            total_bytes=total_bytes,
        ))
    return CorpusInventory(tuple(games))
