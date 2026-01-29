"""Tests for the discovery + inbox workflow."""
# pylint: disable=redefined-outer-name
# pylint: disable=import-error

# ------------------------
# Imports
# ------------------------

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

import pandas as pd
import pytest

from file_discovery import discover
from file_discovery.config import INBOX_EXTRA_COLS, REGISTRY_COLS
from file_discovery.io_utils import load_inbox


# ------------------------
# Helpers
# ------------------------

def _empty_inbox_df() -> pd.DataFrame:
    """Create an empty inbox dataframe with the expected schema."""
    columns = [*REGISTRY_COLS, *INBOX_EXTRA_COLS]
    return pd.DataFrame(columns=columns).astype("string")


def _touch(path: Path, content: str = "x") -> None:
    """Create a small text file at `path`, creating parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ------------------------
# Fixtures
# ------------------------

@pytest.fixture()
def inbox_csv(tmp_path: Path) -> Path:
    """Return a default path for the discovery inbox CSV under pytest's tmp_path."""
    return tmp_path / "new_files.csv"


# ------------------------
# Tests
# ------------------------

# ------------------------
# Tests: Inbox creation / schema
# ------------------------

def test_discover_creates_inbox_with_expected_columns_when_missing(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable,
) -> None:
    """Validate inbox CSV is created with correct columns when initially missing."""
    base_dir = roots["source_root"]

    write_curated(curated_df, curated_csv)
    assert not inbox_csv.exists()

    inbox, stats = discover(
        base_dir_path=base_dir,
        file_registry_path=curated_csv,
        discovery_output_path=inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )

    assert inbox_csv.exists()
    expected_cols = list(REGISTRY_COLS) + list(INBOX_EXTRA_COLS)

    on_disk = load_inbox(inbox_csv)
    assert list(on_disk.columns) == expected_cols
    assert list(inbox.columns) == expected_cols

    assert stats["inbox_after"] == 0
    assert stats["appended"] == 0


# ------------------------
# Tests: Rerun / uniqueness
# ------------------------

def test_discover_append_unique_by_path_on_rerun(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable,
) -> None:
    """Ensure rerunning discovery appends unique files only once, identified by path."""
    base_dir = roots["source_root"]

    write_curated(curated_df, curated_csv)

    f = base_dir / "some_subdir" / "TC005_MKY_P1S1_16-07-25_785nm.spc"
    _touch(f)

    inbox1, stats1 = discover(
        base_dir_path=base_dir,
        file_registry_path=curated_csv,
        discovery_output_path=inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )
    assert len(inbox1) == 1
    assert stats1["appended"] == 1
    assert inbox1.loc[inbox1.index[0], "Path"] == (Path("some_subdir") / f.name).as_posix()
    assert inbox1.loc[inbox1.index[0], "discovery"] == "old_unregistered"

    inbox2, stats2 = discover(
        base_dir_path=base_dir,
        file_registry_path=curated_csv,
        discovery_output_path=inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )
    assert len(inbox2) == 1
    assert stats2["appended"] == 0

    assert inbox2["Path"].nunique(dropna=True) == 1
    assert inbox2["Path"].is_unique


# ------------------------
# Tests: Case A/B/C
# ------------------------

def test_discover_case_a_legacy_file_goes_to_inbox_with_blank_id(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable,
) -> None:
    """Check legacy unregistered files appear in inbox with blank ID."""
    base_dir = roots["source_root"]

    write_curated(curated_df, curated_csv)

    rel = Path("legacy") / "TC005_MKY_P1S1_16-07-25_785nm.spc"
    _touch(base_dir / rel)

    inbox, _ = discover(
        base_dir_path=base_dir,
        file_registry_path=curated_csv,
        discovery_output_path=inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )

    assert len(inbox) == 1
    row = inbox.iloc[0]

    assert row["Path"] == rel.as_posix()
    assert row["Current Filename"] == rel.stem
    assert pd.isna(row["ID"]) or row["ID"] == ""
    assert row["discovery"] == "old_unregistered"
    assert "conflicts" in inbox.columns


def test_discover_case_b_id_named_file_when_registry_incomplete(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable,
) -> None:
    """Validate ID-named files are matched to incomplete registry entries."""
    base_dir = roots["source_root"]

    curated = curated_df.copy()
    curated.loc[0, "ID"] = "SPR_AP1_00001"
    curated.loc[0, "Measured Material"] = "TC005"
    curated.loc[0, "Path"] = pd.NA
    curated.loc[0, "Current Filename"] = pd.NA
    write_curated(curated, curated_csv)

    rel = Path("id_files") / "SPR_AP1_00001.spc"
    _touch(base_dir / rel)

    inbox, _ = discover(
        base_dir_path=base_dir,
        file_registry_path=curated_csv,
        discovery_output_path=inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )

    assert len(inbox) == 1
    row = inbox.iloc[0]

    assert row["ID"] == "SPR_AP1_00001"
    assert row["Path"] == rel.as_posix()
    assert row["Current Filename"] == "SPR_AP1_00001"
    assert row["Measured Material"] == "TC005"
    assert row["discovery"] == "id_file_found_registry_incomplete"
    assert pd.isna(row["conflicts"]) or str(row["conflicts"]).strip() == ""


def test_discover_case_c_registered_file_not_added(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable,
) -> None:
    """Confirm registered files already in registry are not added to inbox."""
    base_dir = roots["source_root"]

    rel = Path("registered") / "SPR_AP1_00002.spc"
    _touch(base_dir / rel)

    curated = curated_df.copy()
    curated.loc[0, "ID"] = "SPR_AP1_00002"
    curated.loc[0, "Path"] = rel.as_posix()
    curated.loc[0, "Current Filename"] = "SPR_AP1_00002"
    write_curated(curated, curated_csv)

    inbox, stats = discover(
        base_dir_path=base_dir,
        file_registry_path=curated_csv,
        discovery_output_path=inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )

    assert len(inbox) == 0
    assert stats["appended"] == 0


# ------------------------
# Tests: Purge / conflicts
# ------------------------

def test_discover_purges_inbox_by_path_when_conflicts_disabled(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable,
) -> None:
    """Test that inbox entries are purged by path when conflict detection is disabled."""
    base_dir = roots["source_root"]

    # curated contains the path
    rel = Path("registered") / "SPR_AP1_00003.spc"
    curated = curated_df.copy()
    curated.loc[0, "ID"] = "SPR_AP1_00003"
    curated.loc[0, "Path"] = rel.as_posix()
    curated.loc[0, "Current Filename"] = "SPR_AP1_00003"
    write_curated(curated, curated_csv)

    # inbox initially contains the same path
    inbox0 = _empty_inbox_df()
    inbox0.loc[0, "Path"] = rel.as_posix()
    inbox0.loc[0, "Current Filename"] = "SPR_AP1_00003"
    inbox0.loc[0, "discovery"] = "old_unregistered"
    write_curated(inbox0, inbox_csv)

    inbox, stats = discover(
        base_dir_path=base_dir,
        file_registry_path=curated_csv,
        discovery_output_path=inbox_csv,
        decode_filename=False,
        find_conflicts=False,
    )

    assert len(inbox) == 0
    assert stats["pruned"] == 1


def test_discover_conflicts_keep_row_and_annotate_conflicts(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable,
) -> None:
    """Verify that conflicts are annotated and rows retained when conflict detection is enabled."""
    base_dir = roots["source_root"]

    rel = Path("registered") / "SPR_AP1_00004.spc"

    curated = curated_df.copy()
    curated.loc[0, "ID"] = "SPR_AP1_00004"
    curated.loc[0, "Path"] = rel.as_posix()
    curated.loc[0, "Current Filename"] = "SPR_AP1_00004"
    curated.loc[0, "Date"] = "01.01.2025"
    curated.loc[0, "Comments"] = "curated_comment"
    write_curated(curated, curated_csv)

    inbox0 = _empty_inbox_df()
    inbox0.loc[0, "ID"] = "SPR_AP1_00004"
    inbox0.loc[0, "Path"] = rel.as_posix()
    inbox0.loc[0, "Current Filename"] = "SPR_AP1_00004"
    inbox0.loc[0, "Date"] = "02.01.2025"  # canonical mismatch
    inbox0.loc[0, "Comments"] = "different_comment"  # excluded from conflict comparison
    inbox0.loc[0, "discovery"] = "old_unregistered"
    write_curated(inbox0, inbox_csv)

    inbox, stats = discover(
        base_dir_path=base_dir,
        file_registry_path=curated_csv,
        discovery_output_path=inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )

    assert len(inbox) == 1
    assert stats["pruned"] == 0

    raw_conflicts = inbox.loc[inbox.index[0], "conflicts"]
    conflicts = "" if pd.isna(raw_conflicts) else str(raw_conflicts)
    assert "Date" in conflicts
    assert "Comments" not in conflicts
