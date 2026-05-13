"""Unit tests for validation utilities (validate.py).

These tests verify that input validation fails fast with clear exceptions and
passes cleanly for valid inputs. 
"""

# pylint: disable=redefined-outer-name
# pylint: disable=import-error

from __future__ import annotations

from pathlib import Path

import pytest

from file_discovery.validate import (
    validate_csv_file,
    validate_csv_has_required_columns,
    validate_dir_exists,
    validate_output_parent_exists,
)

# ------------------------
# Helpers
# ------------------------


def _write_text(path: Path, text: str) -> None:
    """Write UTF-8 text to path, creating the parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ------------------------
# validate_dir_exists
# ------------------------


def test_validate_dir_exists_passes_for_existing_directory(tmp_path: Path) -> None:
    """validate_dir_exists should accept an existing directory."""
    validate_dir_exists(tmp_path, name="base_dir_path")


def test_validate_dir_exists_raises_for_missing_directory(tmp_path: Path) -> None:
    """validate_dir_exists should raise FileNotFoundError for a missing path."""
    missing = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError) as excinfo:
        validate_dir_exists(missing, name="base_dir_path")

    msg = str(excinfo.value)
    assert "base_dir_path" in msg
    assert str(missing.resolve()) in msg


def test_validate_dir_exists_raises_for_file_path(tmp_path: Path) -> None:
    """validate_dir_exists should raise NotADirectoryError if the path is a file."""
    file_path = tmp_path / "not_a_dir.txt"
    _write_text(file_path, "x")

    with pytest.raises(NotADirectoryError) as excinfo:
        validate_dir_exists(file_path, name="base_dir_path")

    msg = str(excinfo.value)
    assert "base_dir_path" in msg
    assert str(file_path.resolve()) in msg


# ------------------------
# validate_csv_file
# ------------------------


def test_validate_csv_file_passes_for_existing_csv_file(tmp_path: Path) -> None:
    """validate_csv_file should accept an existing .csv file."""
    csv_path = tmp_path / "registry.csv"
    _write_text(csv_path, "ID;Path\n") 
    validate_csv_file(csv_path, name="curated_csv")


def test_validate_csv_file_raises_for_missing_file(tmp_path: Path) -> None:
    """validate_csv_file should raise FileNotFoundError if the file does not exist."""
    missing = tmp_path / "missing.csv"
    with pytest.raises(FileNotFoundError) as excinfo:
        validate_csv_file(missing, name="curated_csv")

    msg = str(excinfo.value)
    assert "curated_csv" in msg
    assert str(missing.resolve()) in msg


def test_validate_csv_file_raises_for_directory_path(tmp_path: Path) -> None:
    """validate_csv_file should raise IsADirectoryError when given a directory path."""
    with pytest.raises(IsADirectoryError) as excinfo:
        validate_csv_file(tmp_path, name="curated_csv")

    msg = str(excinfo.value)
    assert "curated_csv" in msg
    assert str(tmp_path.resolve()) in msg


def test_validate_csv_file_raises_for_wrong_suffix(tmp_path: Path) -> None:
    """validate_csv_file should raise ValueError for non-.csv suffixes."""
    not_csv = tmp_path / "registry.txt"
    _write_text(not_csv, "ID;Path\n")

    with pytest.raises(ValueError) as excinfo:
        validate_csv_file(not_csv, name="curated_csv")

    msg = str(excinfo.value)
    assert "curated_csv" in msg
    assert str(not_csv.resolve()) in msg
    assert ".csv" in msg.lower()


def test_validate_csv_file_raises_for_empty_file(tmp_path: Path) -> None:
    """validate_csv_file should raise ValueError for a 0-byte CSV file."""
    csv_path = tmp_path / "empty.csv"
    _write_text(csv_path, "")

    with pytest.raises(ValueError) as excinfo:
        validate_csv_file(csv_path, name="curated_csv")

    msg = str(excinfo.value)
    assert "curated_csv" in msg
    assert str(csv_path.resolve()) in msg
    assert "empty" in msg.lower()


# ------------------------
# validate_csv_has_required_columns
# ------------------------


def test_validate_csv_has_required_columns_passes_for_header_only(tmp_path: Path) -> None:
    """validate_csv_has_required_columns should accept header-only CSVs with required columns."""
    csv_path = tmp_path / "registry.csv"
    _write_text(csv_path, "ID;Path;Current Filename\n")

    validate_csv_has_required_columns(
        csv_path,
        required={"ID", "Path"},
        name="curated_csv",
        sep=";",
    )


def test_validate_csv_has_required_columns_raises_for_empty_file(tmp_path: Path) -> None:
    """validate_csv_has_required_columns should raise ValueError for an empty CSV (no header)."""
    csv_path = tmp_path / "empty.csv"
    _write_text(csv_path, "")  # truly empty (0 bytes or empty content)

    with pytest.raises(ValueError) as excinfo:
        validate_csv_has_required_columns(
            csv_path,
            required={"ID", "Path"},
            name="curated_csv",
            sep=";",
        )

    msg = str(excinfo.value)
    assert "curated_csv" in msg
    assert str(csv_path.resolve()) in msg


@pytest.mark.parametrize(
    "content",
    [
        "\n",  # non-empty file, but header line is blank
        "   \n",  # whitespace-only header
        ";;;\n",  # separators-only header
    ],
)
def test_validate_csv_has_required_columns_raises_for_unparseable_header(
    tmp_path: Path,
    content: str,
) -> None:
    """validate_csv_has_required_columns should raise ValueError for non-parseable headers."""
    csv_path = tmp_path / "bad_header.csv"
    _write_text(csv_path, content)

    with pytest.raises(ValueError) as excinfo:
        validate_csv_has_required_columns(
            csv_path,
            required={"ID", "Path"},
            name="curated_csv",
            sep=";",
        )

    msg = str(excinfo.value)
    assert "curated_csv" in msg
    assert str(csv_path.resolve()) in msg
    assert "header" in msg.lower() or "columns" in msg.lower()


@pytest.mark.parametrize(
    ("header", "required"),
    [
        ("ID;Path\n", {"ID", "Path", "Current Filename"}),  # missing one
        ("ID;Current Filename\n", {"ID", "Path"}),  # missing Path
        ("ID,Path,Current Filename\n", {"ID", "Path"}),  # wrong separator => 1 column
    ],
)
def test_validate_csv_has_required_columns_raises_for_missing_required_columns(
    tmp_path: Path,
    header: str,
    required: set[str],
) -> None:
    """validate_csv_has_required_columns should raise ValueError when required columns are missing."""
    csv_path = tmp_path / "bad_schema.csv"
    _write_text(csv_path, header)

    with pytest.raises(ValueError) as excinfo:
        validate_csv_has_required_columns(
            csv_path,
            required=required,
            name="curated_csv",
            sep=";",
        )

    msg = str(excinfo.value)
    assert "curated_csv" in msg
    assert str(csv_path.resolve()) in msg
    msg_lower = msg.lower()
    assert "required" in msg_lower
    assert "found" in msg_lower

    # Message should help debugging (required vs found).
    # We don't enforce exact phrasing, only that it contains the signal.
    for col in sorted(required):
        assert col in msg


def test_validate_csv_has_required_columns_raises_for_null_byte_header(
    tmp_path: Path,
) -> None:
    """CSV headers with null bytes should fail explicitly."""
    csv_path = tmp_path / "bad_null_header.csv"
    _write_text(csv_path, "ID;Bad\x00Column;Path\n")

    with pytest.raises(ValueError) as excinfo:
        validate_csv_has_required_columns(
            csv_path,
            required={"ID", "Path"},
            name="curated_csv",
            sep=";",
        )

    msg = str(excinfo.value)
    assert "curated_csv" in msg
    assert "null byte" in msg.lower()


# ------------------------
# validate_output_parent_exists
# ------------------------


def test_validate_output_parent_exists_passes_when_parent_exists(tmp_path: Path) -> None:
    """validate_output_parent_exists should accept output paths whose parent directory exists."""
    out_path = tmp_path / "out" / "report.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    validate_output_parent_exists(out_path, name="save_output")


def test_validate_output_parent_exists_raises_when_parent_missing(tmp_path: Path) -> None:
    """validate_output_parent_exists should raise FileNotFoundError when parent directory is missing."""
    out_path = tmp_path / "missing_parent" / "report.csv"

    with pytest.raises(FileNotFoundError) as excinfo:
        validate_output_parent_exists(out_path, name="save_output")

    msg = str(excinfo.value)
    assert "save_output" in msg
    assert str(out_path.parent.resolve()) in msg


def test_validate_output_parent_exists_raises_when_parent_is_file(tmp_path: Path) -> None:
    """validate_output_parent_exists should raise NotADirectoryError if parent path is not a directory."""
    parent_as_file = tmp_path / "parent_is_file"
    _write_text(parent_as_file, "x")

    out_path = parent_as_file / "report.csv"
    with pytest.raises(NotADirectoryError) as excinfo:
        validate_output_parent_exists(out_path, name="save_output")

    msg = str(excinfo.value)
    assert "save_output" in msg
    assert str(parent_as_file.resolve()) in msg
