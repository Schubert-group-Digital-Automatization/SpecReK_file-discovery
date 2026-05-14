"""Unit tests for path utils behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from file_discovery.path_utils import resolve_under_root, validate_relative_posix_path


@pytest.mark.parametrize(
    "path_value",
    [
        pytest.param("a/b/file.spc", id="nested-file"),
        pytest.param("2025/CW01/SPR_AP1_00001.spc", id="target-layout"),
        pytest.param("file.spc", id="single-file"),
    ],
)
def test_validate_relative_posix_path_accepts_safe_relative_paths(path_value: str) -> None:
    """Verify validate relative POSIX path accepts safe relative paths."""
    validate_relative_posix_path(path_value, column="Path")


@pytest.mark.parametrize(
    ("path_value", "expected"),
    [
        pytest.param("/absolute/source.spc", "relative", id="absolute"),
        pytest.param("../escape/source.spc", "must not contain", id="parent-prefix"),
        pytest.param("safe/../escape.spc", "must not contain", id="parent-middle"),
        pytest.param("bad\x00source.spc", "null byte", id="null-byte"),
    ],
)
def test_validate_relative_posix_path_rejects_unsafe_values(
    path_value: str,
    expected: str,
) -> None:
    """Verify validate relative POSIX path rejects unsafe values."""
    with pytest.raises(ValueError, match=expected):
        validate_relative_posix_path(path_value, column="Path")


def test_resolve_under_root_returns_resolved_path_for_safe_relative_path(tmp_path: Path) -> None:
    """Verify resolve under root returns resolved path for safe relative path."""
    root = tmp_path / "root"
    root.mkdir()

    result = resolve_under_root(root, "a/b/file.spc", column="Path")

    assert result == (root / "a/b/file.spc").resolve()


def test_resolve_under_root_rejects_symlink_escape(tmp_path: Path) -> None:
    """Verify resolve under root rejects symlink escape."""
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(ValueError, match="escapes its root"):
        resolve_under_root(root, "link/file.spc", column="Path")
