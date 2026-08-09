"""经过文件清单复验的内容寻址工具产物缓存。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from contextlib import contextmanager


_MANIFEST = ".artifact_manifest.json"
_CACHE_KEY = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _is_reparse_point(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", lambda: False)
    return path.is_symlink() or is_junction()


def _remove_path(path: Path) -> None:
    if _is_reparse_point(path):
        if path.is_symlink():
            path.unlink(missing_ok=True)
        else:
            os.rmdir(path)
    elif path.exists():
        shutil.rmtree(path, ignore_errors=True)


class VerifiedArtifactCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.locks_root = self.root / ".locks"
        self.locks_root.mkdir(exist_ok=True)

    @staticmethod
    def _validate_key(key: str) -> None:
        if not isinstance(key, str) or _CACHE_KEY.fullmatch(key) is None:
            raise ValueError("缓存键必须是 64 位小写十六进制 SHA-256")

    @contextmanager
    def _key_lock(self, key: str):
        self._validate_key(key)
        lock = self.locks_root / key
        deadline = time.monotonic() + 30
        while True:
            try:
                lock.mkdir()
                (lock / "owner").write_text(
                    f"{os.getpid()}\n{time.time()}", encoding="ascii")
                break
            except FileExistsError:
                try:
                    if time.time() - lock.stat().st_mtime > 3600:
                        _remove_path(lock)
                        continue
                except OSError:
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"缓存锁超时：{key}")
                time.sleep(0.05)
        try:
            yield
        finally:
            _remove_path(lock)

    def lookup(self, key: str) -> Path | None:
        with self._key_lock(key):
            return self._lookup_unlocked(key)

    def _lookup_unlocked(self, key: str) -> Path | None:
        self._validate_key(key)
        target = self.root / key
        manifest_path = target / _MANIFEST
        try:
            if _is_reparse_point(target):
                raise ValueError("cache target is a reparse point")
            target.resolve(strict=True).relative_to(self.root.resolve(strict=True))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = manifest["files"]
            if manifest.get("schema_version") != 1 or not isinstance(files, dict):
                raise ValueError("bad cache manifest")
            expected = set(files)
            actual = {
                path.relative_to(target).as_posix()
                for path in target.rglob("*")
                if path.is_file() and path.name != _MANIFEST
            }
            if actual != expected:
                raise ValueError("cache file set changed")
            for relative, record in files.items():
                if not isinstance(relative, str) or not isinstance(record, dict):
                    raise ValueError("bad cache record")
                path = target / relative
                if path.is_symlink() or not path.is_file():
                    raise ValueError("unsafe cache artifact")
                if (type(record.get("size")) is not int
                        or path.stat().st_size != record["size"]
                        or _sha256(path) != record.get("sha256")):
                    raise ValueError("cache artifact changed")
            return target
        except (AttributeError, OSError, KeyError, TypeError, ValueError,
                json.JSONDecodeError):
            if target.exists():
                _remove_path(target)
            return None

    def promote(self, key: str, source: Path, logs: tuple[Path, Path]) -> Path:
        self._validate_key(key)
        staging = Path(tempfile.mkdtemp(prefix=f".{key}-", dir=self.root))
        target = self.root / key
        try:
            for item in source.rglob("*"):
                relative = item.relative_to(source)
                destination = staging / relative
                if _is_reparse_point(item):
                    raise ValueError("工具输出不允许符号链接")
                if item.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif item.is_file():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, destination)
            shutil.copy2(logs[0], staging / "stdout.log")
            shutil.copy2(logs[1], staging / "stderr.log")
            records = {}
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    relative = path.relative_to(staging).as_posix()
                    records[relative] = {"size": path.stat().st_size, "sha256": _sha256(path)}
            (staging / _MANIFEST).write_text(json.dumps({
                "schema_version": 1,
                "files": records,
            }, ensure_ascii=False, sort_keys=True), encoding="utf-8")
            with self._key_lock(key):
                existing = self._lookup_unlocked(key)
                if existing is not None:
                    return existing
                staging.replace(target)
                return target
        finally:
            if staging.exists():
                _remove_path(staging)
