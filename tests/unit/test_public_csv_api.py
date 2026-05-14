"""Unit tests for the public CSV API."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from tests.helpers import assert_columns, read_semicolon_csv

import file_discovery
from file_discovery.config import ALL_INBOX_COLS, REGISTRY_COLS

PUBLIC_CSV_HELPERS = (
    "read_curated_csv",
    "read_inbox_csv",
    "write_curated_csv",
    "write_inbox_csv",
    "validate_curated_csv",
    "validate_inbox_csv",
)


def public_helper(name: str):
    """Return a public helper by name."""
    return getattr(file_discovery, name)


def test_public_csv_helpers_are_exported_from_package() -> None:
    """Verify public CSV helpers are exported from the package."""
    for name in PUBLIC_CSV_HELPERS:
        assert callable(public_helper(name))


def test_read_curated_csv_returns_normalized_schema_complete_frame(tmp_path: Path) -> None:
    """Verify read curated CSV normalizes columns and returns the full schema."""
    path = tmp_path / "measured_files.csv"
    path.write_text(
        " ID ; Path ; Current Filename ; Date ; Extra\n"
        " SPR_AP1_00001 ; a/b/file.spc ; file ; 2024-06-01 ; kept\n",
        encoding="utf-8",
    )

    frame = public_helper("read_curated_csv")(path)

    assert_columns(frame, tuple(REGISTRY_COLS) + ("Extra",))
    assert frame.loc[0, "ID"] == "SPR_AP1_00001"
    assert frame.loc[0, "Path"] == "a/b/file.spc"
    assert frame.loc[0, "Current Filename"] == "file"
    assert frame.loc[0, "Date"] == "01.06.2024"


def test_read_inbox_csv_returns_empty_schema_for_missing_file(tmp_path: Path) -> None:
    """Verify read inbox CSV returns an empty schema for a missing inbox."""
    frame = public_helper("read_inbox_csv")(tmp_path / "new_files.csv")

    assert frame.empty
    assert_columns(frame, ALL_INBOX_COLS)


def test_write_curated_csv_preserves_format_and_schema_order(tmp_path: Path) -> None:
    """Verify write curated CSV preserves package CSV invariants."""
    path = tmp_path / "measured_files.csv"
    frame = pd.DataFrame(
        {
            " Extra ": ["kept"],
            " Path ": [" a/b/file.spc "],
            " ID ": [" SPR_AP1_00001 "],
            " Current Filename ": [" file "],
            " Date ": ["2024-06-01"],
        }
    )

    public_helper("write_curated_csv")(frame, path)

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    on_disk = read_semicolon_csv(path)
    assert_columns(on_disk, tuple(REGISTRY_COLS) + ("Extra",))
    assert on_disk.loc[0, "ID"] == "SPR_AP1_00001"
    assert on_disk.loc[0, "Path"] == "a/b/file.spc"
    assert on_disk.loc[0, "Current Filename"] == "file"
    assert on_disk.loc[0, "Date"] == "01.06.2024"
    assert on_disk.loc[0, "Extra"] == "kept"


def test_write_inbox_csv_preserves_workflow_columns_and_schema_order(tmp_path: Path) -> None:
    """Verify write inbox CSV preserves workflow columns and schema order."""
    path = tmp_path / "new_files.csv"
    frame = pd.DataFrame(
        {
            "Extra": ["kept"],
            "Path": [" a/b/file.spc "],
            "ID": [" SPR_AP1_00001 "],
            "Date": ["01.06.2024"],
            "discovery": ["old_unregistered"],
            "conflicts": ["Date"],
        }
    )

    public_helper("write_inbox_csv")(frame, path)

    on_disk = read_semicolon_csv(path)
    assert_columns(on_disk, tuple(ALL_INBOX_COLS) + ("Extra",))
    assert on_disk.loc[0, "Path"] == "a/b/file.spc"
    assert on_disk.loc[0, "ID"] == "SPR_AP1_00001"
    assert on_disk.loc[0, "discovery"] == "old_unregistered"
    assert on_disk.loc[0, "conflicts"] == "Date"
    assert on_disk.loc[0, "Extra"] == "kept"


@pytest.mark.parametrize("writer_name", ["write_curated_csv", "write_inbox_csv"])
def test_public_csv_writers_reject_missing_output_parent(
    writer_name: str,
    tmp_path: Path,
) -> None:
    """Verify public CSV writers reject missing output parents."""
    with pytest.raises(FileNotFoundError, match="parent directory"):
        public_helper(writer_name)(pd.DataFrame(), tmp_path / "missing" / "out.csv")


@pytest.mark.parametrize("writer_name", ["write_curated_csv", "write_inbox_csv"])
def test_public_csv_writers_reject_invalid_dates(writer_name: str, tmp_path: Path) -> None:
    """Verify public CSV writers reject invalid nonempty dates."""
    path = tmp_path / f"{writer_name}.csv"
    frame = pd.DataFrame(
        {
            "ID": ["SPR_AP1_00001"],
            "Path": ["a/b/file.spc"],
            "Current Filename": ["file"],
            "Date": ["not-a-date"],
        }
    )

    with pytest.raises(ValueError, match="Could not parse"):
        public_helper(writer_name)(frame, path)


def test_validate_curated_csv_accepts_valid_curated_file(tmp_path: Path) -> None:
    """Verify validate curated CSV accepts a valid curated file."""
    path = tmp_path / "measured_files.csv"
    public_helper("write_curated_csv")(
        pd.DataFrame(
            {
                "ID": ["SPR_AP1_00001"],
                "Path": ["a/b/file.spc"],
                "Current Filename": ["file"],
                "Date": ["2024-06-01"],
            }
        ),
        path,
    )

    assert public_helper("validate_curated_csv")(path) is None


def test_validate_curated_csv_rejects_missing_required_columns(tmp_path: Path) -> None:
    """Verify validate curated CSV rejects missing required columns."""
    path = tmp_path / "measured_files.csv"
    path.write_text("ID;Path\nSPR_AP1_00001;a/b/file.spc\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required columns"):
        public_helper("validate_curated_csv")(path)


def test_validate_curated_csv_rejects_bad_dates(tmp_path: Path) -> None:
    """Verify validate curated CSV rejects bad dates."""
    path = tmp_path / "measured_files.csv"
    path.write_text(
        "ID;Path;Current Filename;Date\nSPR_AP1_00001;a/b/file.spc;file;bad-date\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Could not parse"):
        public_helper("validate_curated_csv")(path)


def test_validate_inbox_csv_accepts_missing_inbox_file(tmp_path: Path) -> None:
    """Verify validate inbox CSV accepts a missing inbox file."""
    assert public_helper("validate_inbox_csv")(tmp_path / "new_files.csv") is None


def test_validate_inbox_csv_accepts_valid_inbox_file(tmp_path: Path) -> None:
    """Verify validate inbox CSV accepts a valid inbox file."""
    path = tmp_path / "new_files.csv"
    public_helper("write_inbox_csv")(
        pd.DataFrame({"Path": ["a/b/file.spc"], "Date": ["2024-06-01"]}),
        path,
    )

    assert public_helper("validate_inbox_csv")(path) is None


def test_validate_inbox_csv_rejects_malformed_present_file(tmp_path: Path) -> None:
    """Verify validate inbox CSV rejects malformed present files."""
    path = tmp_path / "new_files.csv"
    path.write_text("ID\nSPR_AP1_00001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required columns"):
        public_helper("validate_inbox_csv")(path)
