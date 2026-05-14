"""Integration tests for verify workflows."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from tests.helpers import read_semicolon_csv, touch_file

from file_discovery import verify

pytestmark = pytest.mark.integration


def test_verify_returns_empty_report_for_empty_curated_registry(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    """Verify verify returns empty report for empty curated registry."""
    write_curated([], curated_csv)

    report, stats = verify(
        curated_csv=curated_csv,
        source_root=roots["source_root"],
        target_root=roots["target_root"],
    )

    assert report.empty
    assert list(report.columns) == [
        "ID",
        "Path",
        "new Path",
        "source_abs",
        "target_abs",
        "source_exists",
        "target_exists",
        "status",
    ]
    assert stats == {
        "rows_total": 0,
        "rows_selected": 0,
        "ok": 0,
        "missing_source": 0,
        "missing_target": 0,
        "missing_path": 0,
        "missing_new_path": 0,
    }


@pytest.mark.parametrize(
    (
        "row",
        "create_source_file",
        "create_target_file",
        "expected_status",
        "expected_source_exists",
        "expected_target_exists",
    ),
    [
        pytest.param(
            {"Path": pd.NA, "new Path": "2025/CW01/SPR_AP1_00001.spc"},
            False,
            False,
            "missing_path",
            False,
            False,
            id="missing-path",
        ),
        pytest.param(
            {"Path": "a/b/c.spc", "new Path": pd.NA},
            True,
            False,
            "missing_new_path",
            True,
            False,
            id="missing-new-path",
        ),
        pytest.param(
            {"Path": "a/b/missing.spc", "new Path": "2025/CW01/SPR_AP1_00003.spc"},
            False,
            False,
            "missing_source",
            False,
            False,
            id="missing-source",
        ),
        pytest.param(
            {"Path": "a/b/source.spc", "new Path": "2025/CW02/SPR_AP1_00004.spc"},
            True,
            False,
            "missing_target",
            True,
            False,
            id="missing-target",
        ),
        pytest.param(
            {"Path": "a/b/ok.spc", "new Path": "2025/CW03/SPR_AP1_00005.spc"},
            True,
            True,
            "ok",
            True,
            True,
            id="ok",
        ),
    ],
)
def test_verify_reports_status_and_existence_flags_for_core_scenarios(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
    row: dict[str, Any],
    create_source_file: bool,
    create_target_file: bool,
    expected_status: str,
    expected_source_exists: bool,
    expected_target_exists: bool,
) -> None:
    """Verify verify reports status and existence flags for core scenarios."""
    registry_row = {"ID": "SPR_AP1_00001", **row}
    write_curated([registry_row], curated_csv)
    if isinstance(row["Path"], str) and create_source_file:
        touch_file(roots["source_root"] / row["Path"])
    if isinstance(row["new Path"], str) and create_target_file:
        touch_file(roots["target_root"] / row["new Path"])

    report, stats = verify(curated_csv, roots["source_root"], roots["target_root"])

    assert len(report) == 1
    assert report.loc[0, "ID"] == "SPR_AP1_00001"
    assert report.loc[0, "status"] == expected_status
    assert bool(report.loc[0, "source_exists"]) is expected_source_exists
    assert bool(report.loc[0, "target_exists"]) is expected_target_exists
    assert stats[expected_status] == 1 if expected_status != "ok" else stats["ok"] == 1


def test_verify_prioritizes_missing_source_path_over_missing_target_file(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    """Verify verify prioritizes missing source path over missing target file."""
    write_curated(
        [{"ID": "SPR_AP1_00002", "Path": pd.NA, "new Path": "2025/CW01/file.spc"}],
        curated_csv,
    )

    report, stats = verify(curated_csv, roots["source_root"], roots["target_root"])

    assert report.loc[0, "status"] == "missing_path"
    assert stats["missing_path"] == 1
    assert stats["missing_target"] == 0


def test_verify_creates_target_parent_dirs_without_creating_target_file(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    """Verify verify creates target parent dirs without creating target file."""
    write_curated(
        [
            {
                "ID": "SPR_AP1_00003",
                "Path": "a/b/source.spc",
                "new Path": "2025/CW02/SPR_AP1_00003.spc",
            }
        ],
        curated_csv,
    )
    touch_file(roots["source_root"] / "a/b/source.spc")
    target_file = roots["target_root"] / "2025/CW02/SPR_AP1_00003.spc"

    report, _ = verify(
        curated_csv,
        roots["source_root"],
        roots["target_root"],
        create_target_dirs=True,
    )

    assert report.loc[0, "status"] == "missing_target"
    assert target_file.parent.exists()
    assert not target_file.exists()


def test_verify_save_output_writes_report_csv(
    roots: dict[str, Path],
    curated_csv: Path,
    tmp_path: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    """Verify verify save output writes report CSV."""
    write_curated(
        [{"ID": "SPR_AP1_00004", "Path": "a/b/missing.spc", "new Path": "2025/CW01/file.spc"}],
        curated_csv,
    )
    output = tmp_path / "verify_report.csv"

    report, _ = verify(curated_csv, roots["source_root"], roots["target_root"], save_output=output)
    on_disk = read_semicolon_csv(output)

    assert on_disk.loc[0, "ID"] == report.loc[0, "ID"]
    assert on_disk.loc[0, "status"] == report.loc[0, "status"]


@pytest.mark.parametrize(
    ("path_col", "path_value", "expected"),
    [
        pytest.param("Path", "/absolute/source.spc", "relative", id="absolute-source"),
        pytest.param("Path", "../escape/source.spc", "must not contain", id="parent-source"),
        pytest.param("Path", "bad\x00source.spc", "null byte", id="null-source"),
        pytest.param("new Path", "/absolute/target.spc", "relative", id="absolute-target"),
        pytest.param("new Path", "../escape/target.spc", "must not contain", id="parent-target"),
        pytest.param("new Path", "bad\x00target.spc", "null byte", id="null-target"),
    ],
)
def test_verify_rejects_unsafe_registry_paths(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
    path_col: str,
    path_value: str,
    expected: str,
) -> None:
    """Verify verify rejects unsafe registry paths."""
    row = {"ID": "SPR_AP1_00005", "Path": "a/source.spc", "new Path": "2025/CW01/file.spc"}
    row[path_col] = path_value
    write_curated([row], curated_csv)

    with pytest.raises(ValueError, match=expected):
        verify(curated_csv, roots["source_root"], roots["target_root"])


@pytest.mark.parametrize(
    ("root_key", "link_name", "column", "registry_path"),
    [
        pytest.param("source_root", "source_link", "Path", "source_link/file.spc", id="source"),
        pytest.param("target_root", "target_link", "new Path", "target_link/file.spc", id="target"),
    ],
)
def test_verify_rejects_symlink_escapes(
    roots: dict[str, Path],
    curated_csv: Path,
    tmp_path: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
    root_key: str,
    link_name: str,
    column: str,
    registry_path: str,
) -> None:
    """Verify verify rejects symlink escapes."""
    outside = tmp_path / f"outside_{root_key}"
    outside.mkdir()
    link = roots[root_key] / link_name
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    row = {"ID": "SPR_AP1_00006", "Path": "a/source.spc", "new Path": "2025/CW01/file.spc"}
    row[column] = registry_path
    write_curated([row], curated_csv)

    with pytest.raises(ValueError, match="escapes its root"):
        verify(curated_csv, roots["source_root"], roots["target_root"])
