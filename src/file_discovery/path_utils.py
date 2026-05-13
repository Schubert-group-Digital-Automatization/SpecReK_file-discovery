"""Path validation helpers for registry paths."""

from __future__ import annotations

from pathlib import Path, PurePosixPath


def validate_relative_posix_path(path_value: str, *, column: str) -> None:
    """Validate that *path_value* is a safe relative POSIX path.

    Parameters
    ----------
    path_value
        Registry path value.
    column
        Name of the registry column, used in error messages.

    Raises
    ------
    ValueError
        If the path contains a null byte, is absolute, or contains ``..``.
    """
    if "\x00" in path_value:
        raise ValueError(f"{column} contains a null byte: {path_value!r}")

    path = PurePosixPath(path_value)
    if path.is_absolute():
        raise ValueError(f"{column} must be relative, got absolute path: {path_value!r}")

    if ".." in path.parts:
        raise ValueError(f"{column} must not contain '..': {path_value!r}")


def resolve_under_root(root: Path, relative_path: str, *, column: str) -> Path:
    """Resolve *relative_path* under *root* and ensure it stays inside root.

    Parameters
    ----------
    root
        Filesystem root.
    relative_path
        Validated relative registry path.
    column
        Column name used in error messages.

    Returns
    -------
    pathlib.Path
        Resolved absolute path.

    Raises
    ------
    ValueError
        If the resolved path escapes *root*, for example through symlinks.
    """
    validate_relative_posix_path(relative_path, column=column)

    root_resolved = root.resolve()
    resolved = (root / relative_path).resolve()

    if not resolved.is_relative_to(root_resolved):
        raise ValueError(
            f"Resolved {column} escapes its root, possibly through a symlink: "
            f"{resolved}"
        )

    return resolved
