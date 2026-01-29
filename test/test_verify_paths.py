"""Tests for verify."""
# pylint: disable=redefined-outer-name
# pylint: disable=import-error

# ------------------------
# Imports
# ------------------------
from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Callable

import pandas as pd
import pytest

from file_discovery import verify

# ------------------------
# Helpers
# ------------------------


def _read_report(path: Path) -> pd.DataFrame:
    """Read a verification report CSV from disk."""
    return pd.read_csv(path, sep=";", dtype="string")

# ------------------------
# Tests
# ------------------------


def test_verify_returns_report_dataframe(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Verify that the verify function returns a DataFrame report and stats dict."""
    df = curated_df.copy()
    write_curated(df, curated_csv)

    report, stats = verify(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        create_target_dirs=False,
        save_output=None,
    )

    assert isinstance(report, pd.DataFrame)
    assert isinstance(stats, dict)


@pytest.mark.parametrize(
    (
        "scenario",
        "path_value",
        "new_path_value",
        "create_source_file",
        "create_target_file",
        "expected_status",
        "expected_source_exists",
        "expected_target_exists",
    ),
    [
        (
            "missing_path",
            pd.NA,
            "2025/CW01/SPR_AP1_00001.spc",
            False,
            False,
            "missing_path",
            False,
            False,
        ),
        (
            "missing_new_path",
            "a/b/c.spc",
            pd.NA,
            True,
            False,
            "missing_new_path",
            True,
            False,
        ),
        (
            "missing_source",
            "a/b/missing.spc",
            "2025/CW01/SPR_AP1_00003.spc",
            False,
            False,
            "missing_source",
            False,
            False,
        ),
        (
            "missing_target",
            "a/b/source.spc",
            "2025/CW02/SPR_AP1_00004.spc",
            True,
            False,
            "missing_target",
            True,
            False,
        ),
        (
            "ok",
            "a/b/ok.spc",
            "2025/CW03/SPR_AP1_00005.spc",
            True,
            True,
            "ok",
            True,
            True,
        ),
        (
            "missing_source_and_target",
            "a/b/missing2.spc",
            "2025/CW04/SPR_AP1_00006.spc",
            False,
            False,
            "missing_source",
            False,
            False,
        ),
    ],
)
def test_verify_scenarios(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
    scenario: str,
    path_value: Any,
    new_path_value: Any,
    create_source_file: bool,
    create_target_file: bool,
    expected_status: str,
    expected_source_exists: bool,
    expected_target_exists: bool,
) -> None:
    """Test verify status and existence flags across common scenarios."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00001"
    df.loc[0, "Path"] = path_value
    df.loc[0, "new Path"] = new_path_value
    write_curated(df, curated_csv)

    if isinstance(path_value, str) and create_source_file:
        src = roots["source_root"] / path_value
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("content", encoding="utf-8")

    if isinstance(new_path_value, str) and create_target_file:
        tgt = roots["target_root"] / new_path_value
        tgt.parent.mkdir(parents=True, exist_ok=True)
        tgt.write_text("content", encoding="utf-8")

    report, _ = verify(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        create_target_dirs=False,
        save_output=None,
    )

    assert len(report) == 1
    assert report.loc[0, "ID"] == "SPR_AP1_00001"
    assert report.loc[0, "status"] == expected_status
    assert bool(report.loc[0, "source_exists"]) is expected_source_exists
    assert bool(report.loc[0, "target_exists"]) is expected_target_exists

    if pd.isna(path_value):
        assert pd.isna(report.loc[0, "Path"])
    else:
        assert report.loc[0, "Path"] == path_value

    if pd.isna(new_path_value):
        assert pd.isna(report.loc[0, "new Path"])
    else:
        assert report.loc[0, "new Path"] == new_path_value

    source_abs = report.loc[0, "source_abs"]
    target_abs = report.loc[0, "target_abs"]

    if isinstance(path_value, str):
        expected_source_abs = (roots["source_root"] / path_value).as_posix()
        assert source_abs == expected_source_abs
    else:
        assert pd.isna(source_abs)

    if isinstance(new_path_value, str):
        expected_target_abs = (roots["target_root"] / new_path_value).as_posix()
        assert target_abs == expected_target_abs
    else:
        assert pd.isna(target_abs)

    assert scenario  # keep param name used for readability in failures


def test_verify_creates_target_parent_dirs_only(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Test that verify creates target parent directories when requested but not the target file."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00005"
    df.loc[0, "Path"] = "a/b/source.spc"
    df.loc[0, "new Path"] = "2025/CW02/SPR_AP1_00005.spc"
    write_curated(df, curated_csv)

    src = roots["source_root"] / "a/b/source.spc"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("x", encoding="utf-8")

    target_file = roots["target_root"] / "2025/CW02/SPR_AP1_00005.spc"
    assert not target_file.parent.exists()

    report, _ = verify(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        create_target_dirs=True,
    )

    assert report.loc[0, "status"] == "missing_target"
    assert report.loc[0, "ID"] == "SPR_AP1_00005"
    assert report.loc[0, "new Path"] == "2025/CW02/SPR_AP1_00005.spc"
    assert bool(report.loc[0, "target_exists"]) is False
    assert target_file.parent.exists()
    assert not target_file.exists()


def test_verify_save_output_writes_report_csv(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
    tmp_path: Path,
) -> None:
    """Test that verify saves the output report CSV when requested."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00006"
    df.loc[0, "Path"] = "a/b/missing.spc"
    df.loc[0, "new Path"] = "2025/CW01/SPR_AP1_00006.spc"
    write_curated(df, curated_csv)

    out_path = tmp_path / "verify_report.csv"

    report, _ = verify(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        save_output=out_path,
    )

    assert out_path.exists()
    on_disk = _read_report(out_path)
    assert len(on_disk) == len(report)
    assert on_disk.loc[0, "status"] == report.loc[0, "status"]
    assert on_disk.loc[0, "ID"] == report.loc[0, "ID"]
