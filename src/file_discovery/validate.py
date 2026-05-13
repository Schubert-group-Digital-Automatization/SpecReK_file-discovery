# src/file_discovery/validate.py
"""Validation utilities for file_discovery.

This module provides small, explicit validators for the public API entrypoints.
They are intentionally *fail-fast* and do minimal IO (mostly filesystem metadata
and CSV header inspection).

Design goals
------------
- Clear, deterministic exceptions (no silent fallbacks).
- Minimal dependencies (no pandas needed for validation).
- Error messages that identify *which* input is wrong and *why*.

Notes
-----
These validators are meant to be called by `api.py` before any workflow logic
runs (discover / create_new_path / verify / restructure).

CSV contract
------------
- Header-only CSV files are valid.
- 0-byte (empty) files are rejected.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
import csv

from .config import CSV_SEP


def validate_dir_exists(path: Path, *, name: str) -> None:
    """Validate that `path` exists and is a directory.

    Parameters
    ----------
    path
        Path that must exist and be a directory.
    name
        Human-readable parameter name used in error messages.

    Returns
    -------
    None

    Raises
    ------
    FileNotFoundError
        If `path` does not exist.
    NotADirectoryError
        If `path` exists but is not a directory.
    """
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{name} does not exist: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"{name} must be a directory, got: {resolved}")


def validate_csv_file(path: Path, *, name: str) -> None:
    """Validate that `path` exists, is a non-empty `.csv` file.

    A header-only CSV is considered valid. Only 0-byte files are rejected.

    Parameters
    ----------
    path
        Path to a CSV file.
    name
        Human-readable parameter name used in error messages.

    Returns
    -------
    None

    Raises
    ------
    FileNotFoundError
        If `path` does not exist.
    IsADirectoryError
        If `path` exists but is a directory.
    ValueError
        If suffix is not `.csv` or the file is empty (0 bytes).
    """
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{name} does not exist: {resolved}")
    if resolved.is_dir():
        raise IsADirectoryError(f"{name} must be a file, got directory: {resolved}")
    if resolved.suffix.lower() != ".csv":
        raise ValueError(f"{name} must have '.csv' suffix, got: {resolved}")
    if resolved.stat().st_size == 0:
        raise ValueError(f"{name} is empty (0 bytes): {resolved}")


def validate_csv_has_required_columns(
    path: Path,
    *,
    required: Collection[str],
    name: str,
    sep: str = CSV_SEP,
) -> None:
    """Validate that a CSV file has a parseable header with required columns.

    This function performs a lightweight header inspection (reads only the first
    line) without loading the full CSV into pandas.

    Parameters
    ----------
    path
        Path to an existing CSV file.
    required
        Column names that must be present in the header.
    name
        Human-readable parameter name used in error messages.
    sep
        Column separator used in the CSV (defaults to ``config.CSV_SEP``).

    Returns
    -------
    None

    Raises
    ------
    FileNotFoundError
        If `path` does not exist.
    IsADirectoryError
        If `path` exists but is a directory.
    ValueError
        If the file is empty (0 bytes), has no readable header line, the header
        does not yield any columns when parsed using `sep`, or if any required
        columns are missing.
    """
    validate_csv_file(path, name=name)
    resolved = path.expanduser().resolve()

    header = _read_csv_header(resolved, sep=sep, name=name)
    found = set(header)
    required_set = set(required)

    missing = sorted(required_set - found)
    if missing:
        req_sorted = sorted(required_set)
        found_sorted = sorted(found)
        raise ValueError(
            f"{name} missing required columns at {resolved}. "
            f"Required={req_sorted}, Found={found_sorted}"
        )


def validate_output_parent_exists(path: Path, *, name: str) -> None:
    """Validate that `path.parent` exists and is a directory.

    This enforces a strict "no implicit mkdir" rule for outputs: callers must
    create directories explicitly.

    Parameters
    ----------
    path
        Output file path.
    name
        Human-readable parameter name used in error messages.

    Returns
    -------
    None

    Raises
    ------
    FileNotFoundError
        If `path.parent` does not exist.
    NotADirectoryError
        If `path.parent` exists but is not a directory.
    """
    resolved = path.expanduser().resolve()
    parent = resolved.parent
    if not parent.exists():
        raise FileNotFoundError(f"{name} parent directory does not exist: {parent}")
    if not parent.is_dir():
        raise NotADirectoryError(
            f"{name} parent must be a directory, got: {parent}"
        )


def _read_csv_header(path: Path, *, sep: str, name: str) -> list[str]:
    """Read the first CSV header line and split into columns.

    Parameters
    ----------
    path
        Existing, non-empty CSV file path.
    sep
        Column separator.
    name
        Human-readable parameter name used in error messages.

    Returns
    -------
    list[str]
        Stripped column names.

    Raises
    ------
    ValueError
        If the header line cannot be read, is missing, contains empty or
        duplicate column names, or yields no columns when parsed using `sep`.
    """
    if not sep:
        raise ValueError(f"{name}: CSV separator must not be empty")

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=sep)
            try:
                raw_cols = next(reader)
            except StopIteration:
                raise ValueError(f"{name}: CSV has no header line: {path}") from None
    except OSError as exc:
        raise ValueError(f"{name}: cannot read CSV header from: {path}") from exc

    cols = [str(col).strip() for col in raw_cols]

    null_cols = [col for col in cols if "\x00" in col]
    if null_cols:
        raise ValueError(
            f"{name}: CSV header contains null byte(s) in column name(s): "
            f"{null_cols}"
        )

    if not cols:
        raise ValueError(
            f"{name}: CSV header is empty or not parseable with sep='{sep}': "
            f"{path}"
        )

    empty_positions = [idx + 1 for idx, col in enumerate(cols) if not col]

    if empty_positions:
        raise ValueError(
            f"{name}: CSV header contains empty column name(s) at position(s) "
            f"{empty_positions}: {path}"
        )

    seen = set()
    duplicates = set()

    for col in cols:
        if col in seen:
            duplicates.add(col)
        seen.add(col)

    if duplicates:
        raise ValueError(
            f"{name}: CSV header contains duplicate column name(s): "
            f"{sorted(duplicates)}"
        )

    return cols
