from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from file_discovery import discover
from file_discovery.config import ALL_INBOX_COLS
from file_discovery.io_utils import load_inbox
from tests.helpers import assert_columns, inbox_frame, touch_file, write_registry_csv

pytestmark = pytest.mark.integration


@pytest.fixture()
def inbox_csv(tmp_path: Path) -> Path:
    return tmp_path / "new_files.csv"


def test_discover_creates_empty_inbox_with_expected_columns_when_no_files_exist(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated([], curated_csv)

    inbox, stats = discover(
        base_dir_path=roots["source_root"],
        curated_csv=curated_csv,
        discovery_output_path=inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )

    on_disk, added = load_inbox(inbox_csv)
    assert inbox.empty
    assert on_disk.empty
    assert_columns(inbox, ALL_INBOX_COLS)
    assert_columns(on_disk, ALL_INBOX_COLS)
    assert added == []
    assert stats["curated_rows"] == 0
    assert stats["discovered_rows"] == 0
    assert stats["appended"] == 0
    assert stats["pruned"] == 0


def test_discover_appends_unique_paths_across_reruns(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated([], curated_csv)
    discovered = Path("some_subdir") / "TC005_MKY_P1S1_16-07-25_785nm.spc"
    touch_file(roots["source_root"] / discovered)

    inbox1, stats1 = discover(
        roots["source_root"],
        curated_csv,
        inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )
    inbox2, stats2 = discover(
        roots["source_root"],
        curated_csv,
        inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )

    assert inbox1["Path"].tolist() == [discovered.as_posix()]
    assert inbox2["Path"].tolist() == [discovered.as_posix()]
    assert inbox2["Path"].is_unique
    assert stats1["appended"] == 1
    assert stats2["appended"] == 0


def test_discover_decodes_legacy_unregistered_file_when_requested(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated([], curated_csv)
    rel = Path("legacy") / "TC005_MKY_P1S1_01-06-2024_785nm.spc"
    touch_file(roots["source_root"] / rel)

    inbox, stats = discover(
        roots["source_root"],
        curated_csv,
        inbox_csv,
        decode_filename=True,
        find_conflicts=True,
    )

    row = inbox.iloc[0]
    assert len(inbox) == 1
    assert row["Path"] == rel.as_posix()
    assert row["Current Filename"] == rel.stem
    assert pd.isna(row["ID"])
    assert row["Measured Material"] == "TC005"
    assert row["Date"] == "01.06.2024"
    assert row["Calendar Week"] == 22
    assert row["discovery"] == "old_unregistered"
    assert stats["appended"] == 1


def test_discover_uses_case2_for_id_named_file_and_does_not_duplicate_as_case1(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [
            {
                "ID": "SPR_AP1_00001",
                "Path": pd.NA,
                "Current Filename": pd.NA,
                "Measured Material": "TC005",
            }
        ],
        curated_csv,
    )
    rel = Path("id_files") / "SPR_AP1_00001.spc"
    touch_file(roots["source_root"] / rel)

    inbox, stats = discover(
        roots["source_root"],
        curated_csv,
        inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )

    assert len(inbox) == 1
    assert inbox.loc[0, "ID"] == "SPR_AP1_00001"
    assert inbox.loc[0, "Path"] == rel.as_posix()
    assert inbox.loc[0, "Current Filename"] == "SPR_AP1_00001"
    assert inbox.loc[0, "Measured Material"] == "TC005"
    assert inbox.loc[0, "discovery"] == "id_file_found_registry_incomplete"
    assert stats["appended"] == 1


def test_discover_does_not_add_registered_files(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    rel = Path("registered") / "SPR_AP1_00002.spc"
    touch_file(roots["source_root"] / rel)
    write_curated(
        [
            {
                "ID": "SPR_AP1_00002",
                "Path": rel.as_posix(),
                "Current Filename": "SPR_AP1_00002",
            }
        ],
        curated_csv,
    )

    inbox, stats = discover(
        roots["source_root"],
        curated_csv,
        inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )

    assert inbox.empty
    assert stats["appended"] == 0


def test_discover_purges_existing_inbox_by_path_when_conflicts_are_disabled(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    rel = Path("registered") / "SPR_AP1_00003.spc"
    write_curated(
        [{"ID": "SPR_AP1_00003", "Path": rel.as_posix(), "Current Filename": "SPR_AP1_00003"}],
        curated_csv,
    )
    write_registry_csv(
        inbox_csv,
        inbox_frame(
            [
                {
                    "Path": rel.as_posix(),
                    "Current Filename": "SPR_AP1_00003",
                    "discovery": "old_unregistered",
                }
            ]
        ),
    )

    inbox, stats = discover(
        roots["source_root"],
        curated_csv,
        inbox_csv,
        decode_filename=False,
        find_conflicts=False,
    )

    assert inbox.empty
    assert stats["pruned"] == 1


def test_discover_keeps_conflicting_inbox_rows_and_reports_exact_conflicts(
    roots: dict[str, Path],
    curated_csv: Path,
    inbox_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    rel = Path("registered") / "SPR_AP1_00004.spc"
    write_curated(
        [
            {
                "ID": "SPR_AP1_00004",
                "Path": rel.as_posix(),
                "Current Filename": "SPR_AP1_00004",
                "Date": "01.06.2024",
                "Comments": "curated-comment",
            }
        ],
        curated_csv,
    )
    write_registry_csv(
        inbox_csv,
        inbox_frame(
            [
                {
                    "ID": "SPR_AP1_00004",
                    "Path": rel.as_posix(),
                    "Current Filename": "SPR_AP1_00004",
                    "Date": "02.06.2024",
                    "Comments": "ignored-different-comment",
                    "discovery": "old_unregistered",
                }
            ]
        ),
    )

    inbox, stats = discover(
        roots["source_root"],
        curated_csv,
        inbox_csv,
        decode_filename=False,
        find_conflicts=True,
    )

    assert len(inbox) == 1
    assert inbox.loc[0, "conflicts"] == "Date"
    assert stats["pruned"] == 0
