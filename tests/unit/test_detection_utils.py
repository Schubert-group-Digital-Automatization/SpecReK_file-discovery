from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from file_discovery.config import ALL_INBOX_COLS, REGISTRY_COLS
from file_discovery.detection_utils import (
    append_unique_by_path,
    build_case1_rows,
    build_case2_rows,
    scan_base_dir,
    scan_base_dir_minimal,
)
from tests.helpers import assert_columns, inbox_frame, registry_frame, touch_file


def test_scan_base_dir_returns_allowed_files_in_deterministic_path_order(tmp_path: Path) -> None:
    touch_file(tmp_path / "z" / "TC005_MKY_01-06-2024_785nm.spc")
    touch_file(tmp_path / "a" / "TC006_MKY_01-06-2024_532nm.jdx")
    touch_file(tmp_path / "ignored" / "notes.txt")

    result = scan_base_dir(tmp_path)

    assert result["Path"].tolist() == [
        "a/TC006_MKY_01-06-2024_532nm.jdx",
        "z/TC005_MKY_01-06-2024_785nm.spc",
    ]
    assert result["Measured Material"].tolist() == ["TC006", "TC005"]
    assert_columns(result, REGISTRY_COLS)


def test_scan_base_dir_minimal_only_populates_path_and_current_filename(tmp_path: Path) -> None:
    touch_file(tmp_path / "nested" / "TC005_MKY_01-06-2024_785nm.spc")

    result = scan_base_dir_minimal(tmp_path)

    assert result.loc[0, "Path"] == "nested/TC005_MKY_01-06-2024_785nm.spc"
    assert result.loc[0, "Current Filename"] == "TC005_MKY_01-06-2024_785nm"
    assert pd.isna(result.loc[0, "ID"])
    assert pd.isna(result.loc[0, "Measured Material"])
    assert set(result.columns) == set(REGISTRY_COLS)


def test_build_case2_rows_maps_id_named_files_to_incomplete_curated_rows() -> None:
    discovered = registry_frame(
        [
            {
                "Path": "id_files/SPR_AP1_00001.spc",
                "Current Filename": "SPR_AP1_00001",
            }
        ]
    )
    curated = registry_frame(
        [
            {
                "ID": "SPR_AP1_00001",
                "Path": pd.NA,
                "Current Filename": pd.NA,
                "Measured Material": "TC005",
                "Sample Type": "analyte",
                "Technique": "Raman",
                "nm": "785",
                "Date": "01.06.2024",
                "Position": "P1S1",
                "Location": "Lab",
                "Operator": "MKY",
                "Device": "DeviceA",
                "Project": "ProjectA",
                "Workpackage": "WP1",
                "Comments": "comment",
                "new Path": "2024/CW22/SPR_AP1_00001.spc",
                "Calendar Week": "22",
            }
        ]
    )

    result = build_case2_rows(discovered, curated)

    assert len(result) == 1
    assert_columns(result, ALL_INBOX_COLS)
    assert result.loc[0, "ID"] == "SPR_AP1_00001"
    assert result.loc[0, "Path"] == "id_files/SPR_AP1_00001.spc"
    assert result.loc[0, "Current Filename"] == "SPR_AP1_00001"
    assert result.loc[0, "Measured Material"] == "TC005"
    assert result.loc[0, "Project"] == "ProjectA"
    assert result.loc[0, "discovery"] == "id_file_found_registry_incomplete"
    assert pd.isna(result.loc[0, "conflicts"])


def test_build_case2_rows_returns_empty_for_complete_curated_match() -> None:
    discovered = registry_frame(
        [{"Path": "id_files/SPR_AP1_00001.spc", "Current Filename": "SPR_AP1_00001"}]
    )
    curated = registry_frame(
        [
            {
                "ID": "SPR_AP1_00001",
                "Path": "id_files/SPR_AP1_00001.spc",
                "Current Filename": "SPR_AP1_00001",
            }
        ]
    )

    result = build_case2_rows(discovered, curated)

    assert result.empty
    assert_columns(result, ALL_INBOX_COLS)


def test_build_case2_rows_rejects_duplicate_curated_ids() -> None:
    discovered = registry_frame(
        [{"Path": "id_files/SPR_AP1_00001.spc", "Current Filename": "SPR_AP1_00001"}]
    )
    curated = registry_frame(
        [
            {"ID": "SPR_AP1_00001"},
            {"ID": "SPR_AP1_00001"},
        ]
    )

    with pytest.raises(ValueError, match="Duplicate ID"):
        build_case2_rows(discovered, curated)


def test_build_case1_rows_returns_unregistered_paths_and_blanks_workflow_fields() -> None:
    discovered = registry_frame(
        [
            {
                "ID": "ignored",
                "Path": "new/file.spc",
                "Current Filename": "file",
                "Measured Material": "TC005",
                "Project": "ShouldBeBlanked",
            },
            {"Path": "registered/file.spc", "Current Filename": "registered"},
        ]
    )
    curated = registry_frame([{"Path": "registered/file.spc"}])

    result = build_case1_rows(discovered, curated)

    assert len(result) == 1
    assert result.loc[0, "Path"] == "new/file.spc"
    assert pd.isna(result.loc[0, "ID"])
    assert pd.isna(result.loc[0, "Project"])
    assert pd.isna(result.loc[0, "Workpackage"])
    assert result.loc[0, "Measured Material"] == "TC005"
    assert result.loc[0, "discovery"] == "old_unregistered"
    assert_columns(result, ALL_INBOX_COLS)


def test_append_unique_by_path_appends_only_nonblank_paths_not_already_present() -> None:
    inbox = inbox_frame(
        [
            {"Path": "existing/file.spc", "Current Filename": "file"},
        ]
    )
    additions = inbox_frame(
        [
            {"Path": " existing/file.spc ", "Current Filename": "duplicate"},
            {"Path": "new/file.spc", "Current Filename": "new"},
            {"Path": "   ", "Current Filename": "blank"},
            {"Path": pd.NA, "Current Filename": "missing"},
        ]
    )

    result = append_unique_by_path(inbox, additions)

    assert result["Path"].tolist() == ["existing/file.spc", "new/file.spc"]
    assert result["Current Filename"].tolist() == ["file", "new"]
