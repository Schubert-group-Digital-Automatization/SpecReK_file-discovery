"""Tests for create_new_path."""
# pylint: disable=redefined-outer-name
# pylint: disable=import-error


# ------------------------
# Imports
# ------------------------

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from file_discovery import create_new_path


# ------------------------
# Tests
# ------------------------

def test_create_new_path_populates_when_empty(
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Test that new Path is populated when initially empty."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00001"
    df.loc[0, "Path"] = "some/dir/file.spc"
    df.loc[0, "Date"] = "16.07.2025"
    df.loc[0, "new Path"] = pd.NA

    write_curated(df, curated_csv)

    out_df, stats = create_new_path(
        curated_csv=curated_csv,
        overwrite=False,
        save_output=None,
    )

    assert isinstance(stats, dict)
    assert pd.notna(out_df.loc[0, "new Path"])
    new_path = str(out_df.loc[0, "new Path"])
    assert new_path.endswith("SPR_AP1_00001.spc")
    assert new_path.endswith(".spc")

    assert "2025/CW29/" in new_path


def test_create_new_path_does_not_overwrite_by_default(
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Test that existing new Path is not overwritten by default."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00002"
    df.loc[0, "Path"] = "x/y/z.jdx"
    df.loc[0, "Date"] = "01.01.2025"
    df.loc[0, "new Path"] = "KEEP/THIS/PATH.jdx"

    write_curated(df, curated_csv)

    out_df, stats = create_new_path(
        curated_csv=curated_csv,
        overwrite=False,
        save_output=None,
    )

    assert isinstance(stats, dict)
    new_path = str(out_df.loc[0, "new Path"])
    assert new_path == "KEEP/THIS/PATH.jdx"
    assert new_path.endswith(".jdx")


def test_create_new_path_overwrite_true_replaces_existing(
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Test that existing new Path is replaced when overwrite=True."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00003"
    df.loc[0, "Path"] = "a/b/c.spc"
    df.loc[0, "Date"] = "01.01.2025"
    df.loc[0, "new Path"] = "OLD/PATH.spc"

    write_curated(df, curated_csv)

    out_df, stats = create_new_path(
        curated_csv=curated_csv,
        overwrite=True,
        save_output=None,
    )

    assert isinstance(stats, dict)
    assert pd.notna(out_df.loc[0, "new Path"])
    new_path = str(out_df.loc[0, "new Path"])
    assert new_path != "OLD/PATH.spc"
    assert new_path.endswith("SPR_AP1_00003.spc")
    assert new_path.endswith(".spc")


@pytest.mark.parametrize(
    ("broken_col", "broken_value"),
    [
        ("ID", pd.NA),
        ("Path", pd.NA),
        ("Date", pd.NA),
    ],
)
def test_create_new_path_skips_rows_with_missing_prerequisites(
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
    broken_col: str,
    broken_value: Any,
) -> None:
    """Test that rows missing ID, Path, or Date are skipped."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00004"
    df.loc[0, "Path"] = "a/b/c.spc"
    df.loc[0, "Date"] = "01.01.2025"
    df.loc[0, "new Path"] = pd.NA

    df.loc[0, broken_col] = broken_value

    write_curated(df, curated_csv)

    out_df, stats = create_new_path(
        curated_csv=curated_csv,
        overwrite=False,
        save_output=None,
    )

    assert isinstance(stats, dict)
    assert pd.isna(out_df.loc[0, "new Path"])


def test_create_new_path_query_limits_rows(
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Test that query limits the rows for new Path computation."""
    df = curated_df.copy()

    df.loc[0, "ID"] = "SPR_AP1_00007"
    df.loc[0, "Path"] = "a/a/a.spc"
    df.loc[0, "Date"] = "01.01.2025"
    df.loc[0, "new Path"] = pd.NA
    df.loc[0, "Technique"] = "Raman"

    df.loc[1, "ID"] = "SPR_AP1_00008"
    df.loc[1, "Path"] = "b/b/b.spc"
    df.loc[1, "Date"] = "01.01.2025"
    df.loc[1, "new Path"] = pd.NA
    df.loc[1, "Technique"] = "PL"

    write_curated(df, curated_csv)

    out_df, stats = create_new_path(
        curated_csv=curated_csv,
        query='Technique == "Raman"',
        overwrite=False,
        save_output=None,
    )

    assert isinstance(stats, dict)
    assert stats.get("rows_total") == 2
    assert stats.get("rows_selected") == 1

    assert pd.notna(out_df.loc[0, "new Path"])
    assert pd.isna(out_df.loc[1, "new Path"])


def test_create_new_path_save_output_writes_csv(
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
    tmp_path: Path,
) -> None:
    """Test that save_output writes the output CSV file."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00009"
    df.loc[0, "Path"] = "x/y/z.jdx"
    df.loc[0, "Date"] = "01.01.2025"
    df.loc[0, "new Path"] = pd.NA

    write_curated(df, curated_csv)

    out_path = tmp_path / "measured_files_out.csv"

    out_df, stats = create_new_path(
        curated_csv=curated_csv,
        overwrite=False,
        save_output=out_path,
    )

    assert isinstance(stats, dict)
    assert out_path.exists()
    on_disk = pd.read_csv(out_path, sep=";", dtype="string")
    assert "new Path" in on_disk.columns
    assert pd.notna(on_disk.loc[0, "new Path"])
    new_path = str(on_disk.loc[0, "new Path"])
    assert new_path.endswith(".jdx")
    assert new_path == out_df.loc[0, "new Path"]


def test_create_new_path_counts_missing_dates(
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Rows with missing dates should be skipped and counted."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00010"
    df.loc[0, "Path"] = "a/b/c.spc"
    df.loc[0, "Date"] = pd.NA
    df.loc[0, "new Path"] = pd.NA

    write_curated(df, curated_csv)

    out_df, stats = create_new_path(curated_csv=curated_csv)

    assert pd.isna(out_df.loc[0, "new Path"])
    assert stats["skipped_missing_date"] == 1
    assert stats["updated"] == 0


def test_create_new_path_malformed_selected_date_raises(
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Malformed non-empty dates in selected rows should raise."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00011"
    df.loc[0, "Path"] = "a/b/c.spc"
    df.loc[0, "Date"] = "not-a-date"
    df.loc[0, "new Path"] = pd.NA

    write_curated(df, curated_csv)

    with pytest.raises(ValueError, match="Date"):
        create_new_path(curated_csv=curated_csv)


def test_create_new_path_does_not_validate_dates_outside_query(
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Malformed dates outside the query should not block selected updates."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00012"
    df.loc[0, "Path"] = "a/b/c.spc"
    df.loc[0, "Date"] = "2025-01-01"
    df.loc[0, "new Path"] = pd.NA
    df.loc[0, "Technique"] = "Raman"

    df.loc[1, "ID"] = "SPR_AP1_00013"
    df.loc[1, "Path"] = "a/b/d.spc"
    df.loc[1, "Date"] = "not-a-date"
    df.loc[1, "new Path"] = pd.NA
    df.loc[1, "Technique"] = "PL"

    write_curated(df, curated_csv)

    out_df, stats = create_new_path(
        curated_csv=curated_csv,
        query='Technique == "Raman"',
    )

    assert pd.notna(out_df.loc[0, "new Path"])
    assert pd.isna(out_df.loc[1, "new Path"])
    assert stats["updated"] == 1


def test_create_new_path_duplicate_full_candidate_output_raises(
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Computed paths should be checked against existing full output values."""
    df = curated_df.copy()
    duplicate_path = "2025/CW01/SPR_AP1_00014.spc"

    df.loc[0, "ID"] = "SPR_AP1_00014"
    df.loc[0, "Path"] = "a/b/c.spc"
    df.loc[0, "Date"] = "01.01.2025"
    df.loc[0, "new Path"] = pd.NA

    df.loc[1, "ID"] = "SPR_AP1_99999"
    df.loc[1, "Path"] = "x/y/z.spc"
    df.loc[1, "Date"] = "01.01.2025"
    df.loc[1, "new Path"] = duplicate_path

    write_curated(df, curated_csv)

    with pytest.raises(ValueError, match="Duplicate new Path"):
        create_new_path(curated_csv=curated_csv)
