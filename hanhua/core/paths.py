"""Safe resolution of untrusted project-relative file paths."""
from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


class UnsafeRelativePathError(ValueError):
    """Raised when a persisted relative path escapes its trusted root."""


def _is_reparse_point(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", lambda: False)
    return path.is_symlink() or is_junction()


def ensure_trusted_root(root: str | Path) -> Path:
    """Return an absolute root after rejecting a symlink/junction root."""
    lexical_root = Path(root).absolute()
    if _is_reparse_point(lexical_root):
        raise UnsafeRelativePathError(
            f"可信根是 reparse point（重解析点）：{lexical_root}")
    return lexical_root


def _reject_existing_reparse_chain(root: Path, candidate: Path) -> None:
    current = root
    if _is_reparse_point(current):
        raise UnsafeRelativePathError(f"可信根是 reparse point（重解析点）：{root}")
    for part in candidate.relative_to(root).parts:
        current = current / part
        if _is_reparse_point(current):
            raise UnsafeRelativePathError(
                f"相对路径包含 reparse point（重解析点）：{current}")


def resolve_relative_under(root: str | Path, relative: str | Path) -> Path:
    """Resolve a persisted relative path while keeping it below *root*."""
    raw = str(relative)
    value = raw.replace("\\", "/")
    windows_path = PureWindowsPath(raw)
    posix_path = PurePosixPath(value)
    parts = value.split("/")
    if (
        not value
        or "\0" in value
        or windows_path.drive
        or windows_path.root
        or posix_path.is_absolute()
        or any(part in {"", ".", ".."} or ":" in part for part in parts)
    ):
        raise UnsafeRelativePathError(f"不安全的相对路径：{relative}")
    lexical_root = ensure_trusted_root(root)
    lexical_candidate = lexical_root.joinpath(*parts)
    _reject_existing_reparse_chain(lexical_root, lexical_candidate)
    trusted_root = lexical_root.resolve()
    candidate = lexical_candidate.resolve(strict=False)
    try:
        candidate.relative_to(trusted_root)
    except ValueError as exc:
        raise UnsafeRelativePathError(f"相对路径逃逸可信根：{relative}") from exc
    return candidate
