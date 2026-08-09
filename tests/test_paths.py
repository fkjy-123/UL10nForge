from pathlib import Path

import pytest

from hanhua.core.paths import UnsafeRelativePathError, resolve_relative_under
from tests.test_tooling_runner import _make_junction


def test_resolve_relative_under_rejects_parent_traversal(tmp_path):
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(UnsafeRelativePathError, match="相对路径"):
        resolve_relative_under(root, "../escaped.txt")

    assert not (tmp_path / "escaped.txt").exists()


@pytest.mark.parametrize(
    "relative",
    (
        "C:/outside.txt",
        "C:drive-relative.txt",
        "//server/share/outside.txt",
        "/rooted.txt",
        "\\rooted.txt",
        "",
        ".",
        "safe/./file.txt",
        "safe/\0file.txt",
    ),
)
def test_resolve_relative_under_rejects_non_canonical_or_rooted_paths(
        tmp_path, relative):
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(UnsafeRelativePathError):
        resolve_relative_under(root, relative)


def test_resolve_relative_under_rejects_existing_symlink_parent_escape(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"当前 Windows 环境不允许创建测试符号链接：{exc}")

    with pytest.raises(UnsafeRelativePathError, match="逃逸"):
        resolve_relative_under(root, "linked/escaped.txt")

    assert not (outside / "escaped.txt").exists()


def test_resolve_relative_under_returns_canonical_path_for_safe_input(tmp_path):
    root = tmp_path / "root"
    root.mkdir()

    resolved = resolve_relative_under(root, "nested/file.txt")

    assert resolved == (root / "nested" / "file.txt").resolve()


def test_resolve_relative_under_rejects_junction_even_when_target_stays_inside_root(
        tmp_path):
    root = tmp_path / "root"
    target = root / "target"
    root.mkdir()
    target.mkdir()
    _make_junction(root / "linked", target)

    with pytest.raises(UnsafeRelativePathError, match="reparse|重解析"):
        resolve_relative_under(root, "linked/file.txt")
