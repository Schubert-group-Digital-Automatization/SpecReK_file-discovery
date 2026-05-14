from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from file_discovery import create_new_path
from tests.helpers import read_semicolon_csv

pytestmark = pytest.mark.integration


def test_create_new_path_populates_exact_path_and_stats(
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [
            {
                "ID": "SPR_AP1_00001",
                "Path": "some/dir/file.spc",
                "Date": "16.07.2025",
                "new Path": pd.NA,
            }
        ],
        curated_csv,
    )

    frame, stats = create_new_path(curated_csv=curated_csv)

    assert frame.loc[0, "new Path"] == "2025/CW29/SPR_AP1_00001.spc"
    assert frame.loc[0, "Date"] == "16.07.2025"
    assert stats == {
        "rows_total": 1,
        "rows_selected": 1,
        "updated": 1,
        "skipped_missing_id": 0,
        "skipped_invalid_id": 0,
        "skipped_missing_path": 0,
        "skipped_missing_suffix": 0,
        "skipped_missing_date": 0,
    }


def test_create_new_path_normalizes_iso_date_in_returned_frame_without_saving_source(
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [
            {
                "ID": "SPR_AP1_00002",
                "Path": "a/b/file.jdx",
                "Date": "2025-01-01",
                "new Path": pd.NA,
            }
        ],
        curated_csv,
    )

    frame, stats = create_new_path(curated_csv=curated_csv, save_output=None)
    on_disk = read_semicolon_csv(curated_csv)

    assert frame.loc[0, "Date"] == "01.01.2025"
    assert frame.loc[0, "new Path"] == "2025/CW01/SPR_AP1_00002.jdx"
    assert on_disk.loc[0, "Date"] == "2025-01-01"
    assert pd.isna(on_disk.loc[0, "new Path"])
    assert stats["updated"] == 1


def test_create_new_path_does_not_overwrite_existing_value_by_default(
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [
            {
                "ID": "SPR_AP1_00003",
                "Path": "x/y/z.jdx",
                "Date": "01.01.2025",
                "new Path": "KEEP/THIS/PATH.jdx",
            }
        ],
        curated_csv,
    )

    frame, stats = create_new_path(curated_csv=curated_csv, overwrite=False)

    assert frame.loc[0, "new Path"] == "KEEP/THIS/PATH.jdx"
    assert stats["updated"] == 0


def test_create_new_path_overwrite_true_replaces_existing_value(
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [
            {
                "ID": "SPR_AP1_00004",
                "Path": "a/b/c.spc",
                "Date": "01.01.2025",
                "new Path": "OLD/PATH.spc",
            }
        ],
        curated_csv,
    )

    frame, stats = create_new_path(curated_csv=curated_csv, overwrite=True)

    assert frame.loc[0, "new Path"] == "2025/CW01/SPR_AP1_00004.spc"
    assert stats["updated"] == 1


@pytest.mark.parametrize(
    ("broken_col", "broken_value", "counter"),
    [
        pytest.param("ID", pd.NA, "skipped_missing_id", id="missing-id"),
        pytest.param("ID", "invalid", "skipped_invalid_id", id="invalid-id"),
        pytest.param("Path", pd.NA, "skipped_missing_path", id="missing-path"),
        pytest.param("Path", "a/b/no_suffix", "skipped_missing_suffix", id="missing-suffix"),
        pytest.param("Date", pd.NA, "skipped_missing_date", id="missing-date"),
    ],
)
def test_create_new_path_skips_rows_with_missing_or_invalid_prerequisites(
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
    broken_col: str,
    broken_value: Any,
    counter: str,
) -> None:
    row = {
        "ID": "SPR_AP1_00005",
        "Path": "a/b/c.spc",
        "Date": "01.01.2025",
        "new Path": pd.NA,
    }
    row[broken_col] = broken_value
    write_curated([row], curated_csv)

    frame, stats = create_new_path(curated_csv=curated_csv)

    assert pd.isna(frame.loc[0, "new Path"])
    assert stats["updated"] == 0
    assert stats[counter] == 1


def test_create_new_path_query_limits_processing_and_date_validation(
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [
            {
                "ID": "SPR_AP1_00006",
                "Path": "a/a/a.spc",
                "Date": "2025-01-01",
                "new Path": pd.NA,
                "Technique": "Raman",
            },
            {
                "ID": "SPR_AP1_00007",
                "Path": "b/b/b.spc",
                "Date": "not-a-date",
                "new Path": pd.NA,
                "Technique": "PL",
            },
        ],
        curated_csv,
    )

    frame, stats = create_new_path(curated_csv=curated_csv, query='Technique == "Raman"')

    assert frame.loc[0, "new Path"] == "2025/CW01/SPR_AP1_00006.spc"
    assert frame.loc[0, "Date"] == "01.01.2025"
    assert pd.isna(frame.loc[1, "new Path"])
    assert frame.loc[1, "Date"] == "not-a-date"
    assert stats["rows_total"] == 2
    assert stats["rows_selected"] == 1
    assert stats["updated"] == 1


def test_create_new_path_rejects_malformed_selected_dates(
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [
            {
                "ID": "SPR_AP1_00008",
                "Path": "a/b/c.spc",
                "Date": "not-a-date",
                "new Path": pd.NA,
            }
        ],
        curated_csv,
    )

    with pytest.raises(ValueError, match="Date"):
        create_new_path(curated_csv=curated_csv)


def test_create_new_path_save_output_writes_normalized_result(
    curated_csv: Path,
    tmp_path: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [
            {
                "ID": "SPR_AP1_00009",
                "Path": "x/y/z.jdx",
                "Date": "2025-01-01",
                "new Path": pd.NA,
            }
        ],
        curated_csv,
    )
    output = tmp_path / "measured_files_out.csv"

    frame, stats = create_new_path(curated_csv=curated_csv, save_output=output)
    on_disk = read_semicolon_csv(output)

    assert frame.loc[0, "new Path"] == "2025/CW01/SPR_AP1_00009.jdx"
    assert on_disk.loc[0, "new Path"] == "2025/CW01/SPR_AP1_00009.jdx"
    assert on_disk.loc[0, "Date"] == "01.01.2025"
    assert stats["updated"] == 1


def test_create_new_path_rejects_duplicate_candidate_output(
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [
            {
                "ID": "SPR_AP1_00010",
                "Path": "a/b/c.spc",
                "Date": "01.01.2025",
                "new Path": pd.NA,
            },
            {
                "ID": "SPR_AP1_99999",
                "Path": "x/y/z.spc",
                "Date": "01.01.2025",
                "new Path": "2025/CW01/SPR_AP1_00010.spc",
            },
        ],
        curated_csv,
    )

    with pytest.raises(ValueError, match="Duplicate new Path"):
        create_new_path(curated_csv=curated_csv)
