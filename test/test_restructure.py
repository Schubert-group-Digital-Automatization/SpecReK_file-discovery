"""Unit tests for restructuring (copy/rename/paste)."""

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

from file_discovery import restructure

# ------------------------
# Helpers
# ------------------------


def _read_report(path: Path) -> pd.DataFrame:
    """Read a restructure report CSV from disk."""
    return pd.read_csv(path, sep=";", dtype="string")


# ------------------------
# Tests
# ------------------------


def test_restructure_copies_file_to_destination(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Test that a source file is copied to the target location."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00001"
    df.loc[0, "Path"] = "a/b/source.spc"
    df.loc[0, "new Path"] = "2025/CW01/SPR_AP1_00001.spc"
    write_curated(df, curated_csv)

    src = roots["source_root"] / "a/b/source.spc"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"hello-world")

    report, stats = restructure(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        overwrite=False,
        create_target_dirs=True,
        save_report=None,
    )

    tgt = roots["target_root"] / "2025/CW01/SPR_AP1_00001.spc"
    assert tgt.exists()
    assert tgt.read_bytes() == b"hello-world"
    assert isinstance(report, pd.DataFrame)
    assert isinstance(stats, dict)

    assert len(report) == 1
    assert report.loc[0, "action"] == "copied"
    assert report.loc[0, "Path"] == "a/b/source.spc"
    assert report.loc[0, "new Path"] == "2025/CW01/SPR_AP1_00001.spc"
    assert set(report.columns) == {"ID", "Path", "new Path", "action", "error"}


def test_restructure_idempotent_overwrite_false(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Test that reruns do not overwrite when overwrite is False."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00002"
    df.loc[0, "Path"] = "x/y/src.jdx"
    df.loc[0, "new Path"] = "2025/CW02/SPR_AP1_00002.jdx"
    write_curated(df, curated_csv)

    src = roots["source_root"] / "x/y/src.jdx"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"v1")

    report1, stats1 = restructure(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        overwrite=False,
        create_target_dirs=True,
        save_report=None,
    )
    tgt = roots["target_root"] / "2025/CW02/SPR_AP1_00002.jdx"
    assert tgt.exists()
    assert tgt.read_bytes() == b"v1"
    assert report1.loc[0, "action"] == "copied"
    assert isinstance(stats1, dict)
    assert stats1.get("errors", 0) == 0

    src.write_bytes(b"v2")
    report2, stats2 = restructure(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        overwrite=False,
        create_target_dirs=True,
        save_report=None,
    )
    assert tgt.read_bytes() == b"v1"
    assert report2.loc[0, "action"] == "skipped_exists"
    assert isinstance(stats2, dict)
    assert stats2.get("errors", 0) == 0


@pytest.mark.parametrize(
    ("row", "expected_action"),
    [
        (
            {
                "ID": "SPR_AP1_00010",
                "Path": pd.NA,
                "new Path": "2025/CW01/SPR_AP1_00010.spc",
            },
            "skipped_missing_path",
        ),
        (
            {
                "ID": "SPR_AP1_00011",
                "Path": "a/b/file.spc",
                "new Path": pd.NA,
            },
            "skipped_missing_new_path",
        ),
        (
            {
                "ID": "SPR_AP1_00012",
                "Path": "missing/source.spc",
                "new Path": "2025/CW03/SPR_AP1_00012.spc",
            },
            "skipped_missing_source",
        ),
    ],
)
def test_restructure_handles_missing_inputs(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
    row: dict[str, Any],
    expected_action: str,
) -> None:
    """Test that missing inputs are reported with the expected action."""
    df = curated_df.copy()
    df.loc[0, "ID"] = row["ID"]
    df.loc[0, "Path"] = row["Path"]
    df.loc[0, "new Path"] = row["new Path"]
    write_curated(df, curated_csv)

    report, _ = restructure(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        overwrite=False,
        create_target_dirs=False,
        save_report=None,
    )

    assert len(report) == 1
    assert report.loc[0, "ID"] == row["ID"]
    assert report.loc[0, "action"] == expected_action

    if pd.isna(row["Path"]):
        assert pd.isna(report.loc[0, "Path"])
    else:
        assert report.loc[0, "Path"] == row["Path"]

    if pd.isna(row["new Path"]):
        assert pd.isna(report.loc[0, "new Path"])
    else:
        assert report.loc[0, "new Path"] == row["new Path"]

    assert set(report.columns) == {"ID", "Path", "new Path", "action", "error"}


def test_restructure_overwrite_true_replaces_target(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Test that overwrite=True replaces existing target content."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00020"
    df.loc[0, "Path"] = "a/b/src.spc"
    df.loc[0, "new Path"] = "2025/CW04/SPR_AP1_00020.spc"
    write_curated(df, curated_csv)

    src = roots["source_root"] / "a/b/src.spc"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"SOURCE")

    tgt = roots["target_root"] / "2025/CW04/SPR_AP1_00020.spc"
    tgt.parent.mkdir(parents=True, exist_ok=True)
    tgt.write_bytes(b"OLD-TARGET")

    report, stats = restructure(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        overwrite=True,
        create_target_dirs=True,
        save_report=None,
    )

    assert tgt.read_bytes() == b"SOURCE"
    assert report.loc[0, "action"] == "copied"
    assert isinstance(stats, dict)
    assert stats.get("errors", 0) == 0
    assert set(report.columns) == {"ID", "Path", "new Path", "action", "error"}


def test_restructure_create_target_dirs_creates_parent_dirs(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Test that missing target parent directories are created when enabled."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00030"
    df.loc[0, "Path"] = "p/q/r.spc"
    df.loc[0, "new Path"] = "2025/CW05/subdir/SPR_AP1_00030.spc"
    write_curated(df, curated_csv)

    src = roots["source_root"] / "p/q/r.spc"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"DATA")

    tgt = roots["target_root"] / "2025/CW05/subdir/SPR_AP1_00030.spc"
    assert not tgt.parent.exists()

    report, stats = restructure(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        overwrite=False,
        create_target_dirs=True,
        save_report=None,
    )

    assert tgt.parent.exists()
    assert tgt.exists()
    assert tgt.read_bytes() == b"DATA"
    assert report.loc[0, "action"] == "copied"
    assert isinstance(stats, dict)
    assert stats.get("errors", 0) == 0
    assert set(report.columns) == {"ID", "Path", "new Path", "action", "error"}


def test_restructure_save_report_writes_csv(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
    tmp_path: Path,
) -> None:
    """Test that a restructure report can be written to CSV."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_00040"
    df.loc[0, "Path"] = "a/b/src.spc"
    df.loc[0, "new Path"] = "2025/CW06/SPR_AP1_00040.spc"
    write_curated(df, curated_csv)

    src = roots["source_root"] / "a/b/src.spc"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"X")

    out_path = tmp_path / "restructure_report.csv"

    report, _ = restructure(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
        overwrite=False,
        create_target_dirs=True,
        save_report=out_path,
    )

    assert out_path.exists()
    on_disk = _read_report(out_path)
    assert len(on_disk) == len(report)
    assert "action" in on_disk.columns
    assert "error" in on_disk.columns
    assert on_disk.loc[0, "action"] == report.loc[0, "action"]
    assert on_disk.loc[0, "ID"] == report.loc[0, "ID"]


def test_restructure_duplicate_selected_new_path_raises(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Duplicate selected target paths should fail before copying."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_02000"
    df.loc[0, "Path"] = "a/source1.spc"
    df.loc[0, "new Path"] = "2025/CW01/duplicate.spc"
    df.loc[1, "ID"] = "SPR_AP1_02001"
    df.loc[1, "Path"] = "a/source2.spc"
    df.loc[1, "new Path"] = "2025/CW01/duplicate.spc"
    write_curated(df, curated_csv)

    with pytest.raises(ValueError, match="Duplicate new Path"):
        restructure(
            curated_csv=curated_csv,
            source_root=roots["source_root"],
            target_root=roots["target_root"],
        )


def test_restructure_directory_source_is_not_copied(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
) -> None:
    """Directory sources should be skipped because only files are copied."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_02002"
    df.loc[0, "Path"] = "a/source_dir"
    df.loc[0, "new Path"] = "2025/CW01/SPR_AP1_02002.spc"
    write_curated(df, curated_csv)

    src_dir = roots["source_root"] / "a/source_dir"
    src_dir.mkdir(parents=True)

    report, stats = restructure(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
    )

    assert report.loc[0, "action"] == "skipped_missing_source"
    assert stats["skipped_missing_source"] == 1
    assert not (roots["target_root"] / "2025/CW01/SPR_AP1_02002.spc").exists()


@pytest.mark.parametrize(
    ("path_col", "path_value", "expected"),
    [
        ("Path", "/absolute/source.spc", "relative"),
        ("Path", "../escape/source.spc", "must not contain"),
        ("Path", "bad\x00source.spc", "null byte"),
        ("new Path", "/absolute/target.spc", "relative"),
        ("new Path", "../escape/target.spc", "must not contain"),
        ("new Path", "bad\x00target.spc", "null byte"),
    ],
)
def test_restructure_rejects_unsafe_registry_paths(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
    path_col: str,
    path_value: str,
    expected: str,
) -> None:
    """Restructure should reject unsafe source and target registry paths."""
    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_02003"
    df.loc[0, "Path"] = "a/source.spc"
    df.loc[0, "new Path"] = "2025/CW01/SPR_AP1_02003.spc"
    df.loc[0, path_col] = path_value
    write_curated(df, curated_csv)

    with pytest.raises(ValueError, match=expected):
        restructure(
            curated_csv=curated_csv,
            source_root=roots["source_root"],
            target_root=roots["target_root"],
        )


def test_restructure_rejects_source_symlink_escape(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
    tmp_path: Path,
) -> None:
    """Resolved source paths may not escape source_root through symlinks."""
    outside = tmp_path / "outside_source"
    outside.mkdir()
    link = roots["source_root"] / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_02004"
    df.loc[0, "Path"] = "link/source.spc"
    df.loc[0, "new Path"] = "2025/CW01/SPR_AP1_02004.spc"
    write_curated(df, curated_csv)

    with pytest.raises(ValueError, match="escapes its root"):
        restructure(
            curated_csv=curated_csv,
            source_root=roots["source_root"],
            target_root=roots["target_root"],
        )


def test_restructure_rejects_target_symlink_escape(
    roots: dict[str, Path],
    curated_csv: Path,
    curated_df: pd.DataFrame,
    write_curated: Callable[[pd.DataFrame, Path], None],
    tmp_path: Path,
) -> None:
    """Resolved target paths may not escape target_root through symlinks."""
    outside = tmp_path / "outside_target"
    outside.mkdir()
    link = roots["target_root"] / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    src = roots["source_root"] / "a/source.spc"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"DATA")

    df = curated_df.copy()
    df.loc[0, "ID"] = "SPR_AP1_02005"
    df.loc[0, "Path"] = "a/source.spc"
    df.loc[0, "new Path"] = "link/target.spc"
    write_curated(df, curated_csv)

    with pytest.raises(ValueError, match="escapes its root"):
        restructure(
            curated_csv=curated_csv,
            source_root=roots["source_root"],
            target_root=roots["target_root"],
        )
