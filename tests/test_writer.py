import json
import tempfile
from pathlib import Path

import pytest

from hanhua.core.memory import ProjectStore
from hanhua.core.models import TextEntry
from hanhua.core.scanner import discover
from hanhua.core.extractor import parse_file
from hanhua.core.writer import write_back
from tests.test_tooling_runner import _make_junction


def _project():
    src = Path("tests/fixtures")
    d = Path(tempfile.mkdtemp())
    (d / "Localization").mkdir()
    (d / "Localization" / "game.json").write_text(
        (src / "game.json").read_text(encoding="utf-8"), encoding="utf-8")
    (d / "strings.txt").write_text(
        (src / "strings.txt").read_text(encoding="utf-8"), encoding="utf-8")
    return d


def _build_store(game_dir, db_dir):
    files = discover(game_dir)
    parsed = [parse_file(f) for f in files]
    store = ProjectStore(Path(db_dir) / "p.db")
    store.init_schema()
    for pf in parsed:
        rel = str(Path(pf.rel_path).relative_to(game_dir)).replace("\\", "/")
        store.add_file(pf.file_id, rel, pf.format, pf.encoding, pf.eol, pf.meta)
        store.upsert_entries([{"file_id": e.file_id, "key_path": e.key_path,
                               "original": e.original, "meta": e.meta} for e in pf.entries])
    return store


def test_write_back_output_dir():
    game_dir = _project()
    out_dir = game_dir.parent / (game_dir.name + "_汉化")
    store = _build_store(game_dir, tempfile.mkdtemp())
    store.update_translation("game.json", "title", "谷之回响")
    store.update_translation("strings.txt", "kv/title/1", "回响之谷")
    written = write_back(store, game_dir, out_dir)
    assert written == 2
    out_json = out_dir / "Localization" / "game.json"
    assert json.loads(out_json.read_text(encoding="utf-8"))["title"] == "谷之回响"
    out_txt = out_dir / "strings.txt"
    assert "title=回响之谷" in out_txt.read_text(encoding="utf-8")
    # 原目录未被修改
    assert json.loads((game_dir / "Localization" / "game.json").read_text(encoding="utf-8"))["title"] == "Echoes of the Vale"


def test_write_back_keeps_eol_and_encoding():
    game_dir = _project()
    (game_dir / "crlf.txt").write_bytes("a=hello\r\nb=world\r\n".encode("utf-8"))
    files = discover(game_dir)
    parsed = [parse_file(f) for f in files]
    store = ProjectStore(Path(tempfile.mkdtemp()) / "p.db")
    store.init_schema()
    for pf in parsed:
        rel = str(Path(pf.rel_path).relative_to(game_dir)).replace("\\", "/")
        store.add_file(pf.file_id, rel, pf.format, pf.encoding, pf.eol, pf.meta)
        store.upsert_entries([{"file_id": e.file_id, "key_path": e.key_path,
                               "original": e.original, "meta": e.meta} for e in pf.entries])
    store.update_translation("crlf.txt", "kv/a/0", "你好")
    out_dir = game_dir.parent / (game_dir.name + "_汉化")
    write_back(store, game_dir, out_dir)
    out = (out_dir / "crlf.txt").read_bytes()
    assert out.count(b"\r\n") == 2 and b"\r\n" in out
    assert "你好".encode("utf-8") in out


def test_write_back_rejects_failed_or_low_confidence_translation_candidates():
    game_dir = _project()
    store = _build_store(game_dir, tempfile.mkdtemp())
    failed = next(row for row in store.get_entries()
                  if row["file_id"] == "game.json" and row["key_path"] == "title")
    low = next(row for row in store.get_entries()
               if row["file_id"] == "strings.txt" and row["key_path"] == "kv/title/1")
    store.batch_update_translation_results([
        TextEntry(
            failed["file_id"], failed["key_path"], failed["original"],
            "不合格候选", "failed",
            meta={"quality_passed": False, "quality_reasons": ["glossary_mismatch"]},
        ),
        TextEntry(
            low["file_id"], low["key_path"], low["original"],
            "低置信候选", "translated",
            meta={"quality_passed": True, "confidence": "low"},
            confidence="low",
        ),
    ])
    out_dir = game_dir.parent / (game_dir.name + "_汉化")

    write_back(store, game_dir, out_dir)

    assert json.loads((out_dir / "Localization" / "game.json").read_text(
        encoding="utf-8"))["title"] == "Echoes of the Vale"
    assert "title=Valley of Echoes" in (out_dir / "strings.txt").read_text(
        encoding="utf-8")


def test_text_writer_rejects_rel_path_escape_without_touching_external_file(tmp_path):
    game_dir = tmp_path / "game"
    out_dir = tmp_path / "output"
    game_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("title=ORIGINAL\n", encoding="utf-8")
    store = ProjectStore(tmp_path / "project.db")
    store.init_schema()
    store.add_file("evil", "../outside.txt", "txt", "utf-8", "\n")
    store.upsert_entries([{
        "file_id": "evil",
        "key_path": "kv/title/0",
        "original": "ORIGINAL",
        "meta": {
            "line_no": 0,
            "kind": "kv",
            "prefix": "title=",
            "raw": "title=ORIGINAL",
        },
    }])
    store.set_manual("evil", "kv/title/0", "被篡改")

    with pytest.raises(ValueError, match="不安全的相对路径"):
        write_back(store, game_dir, out_dir)

    assert outside.read_text(encoding="utf-8") == "title=ORIGINAL\n"


def test_text_writer_rechecks_parent_after_mkdir_replaced_by_junction(
        tmp_path, monkeypatch):
    game_dir = tmp_path / "game"
    source_parent = game_dir / "linked"
    source_parent.mkdir(parents=True)
    (source_parent / "file.txt").write_text(
        "title=ORIGINAL\n", encoding="utf-8")
    out_dir = tmp_path / "output"
    outside = tmp_path / "outside"
    outside.mkdir()
    external = outside / "file.txt"
    external.write_text("DO NOT TOUCH", encoding="utf-8")
    store = ProjectStore(tmp_path / "project.db")
    store.init_schema()
    store.add_file("safe", "linked/file.txt", "txt", "utf-8", "\n")
    store.upsert_entries([{
        "file_id": "safe",
        "key_path": "kv/title/0",
        "original": "ORIGINAL",
        "meta": {
            "line_no": 0,
            "kind": "kv",
            "prefix": "title=",
            "raw": "title=ORIGINAL",
        },
    }])
    store.set_manual("safe", "kv/title/0", "被篡改")
    real_mkdir = Path.mkdir

    def replace_parent(path, *args, **kwargs):
        if path == out_dir / "linked" and not path.exists():
            _make_junction(path, outside)
            return None
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", replace_parent)

    with pytest.raises(ValueError, match="reparse|重解析"):
        write_back(store, game_dir, out_dir)

    assert external.read_text(encoding="utf-8") == "DO NOT TOUCH"
