from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from file_discovery import restructure
from tests.helpers import read_semicolon_csv, touch_file

pytestmark = pytest.mark.integration


def test_restructure_copies_file_to_destination_and_reports_stats(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [{"ID": "SPR_AP1_00001", "Path": "a/b/source.spc", "new Path": "2025/CW01/file.spc"}],
        curated_csv,
    )
    touch_file(roots["source_root"] / "a/b/source.spc", b"hello-world")

    report, stats = restructure(
        curated_csv,
        roots["source_root"],
        roots["target_root"],
        overwrite=False,
        create_target_dirs=True,
    )

    target = roots["target_root"] / "2025/CW01/file.spc"
    assert target.read_bytes() == b"hello-world"
    assert report.loc[0, "action"] == "copied"
    assert set(report.columns) == {"ID", "Path", "new Path", "action", "error"}
    assert stats == {
        "rows_total": 1,
        "rows_selected": 1,
        "copied": 1,
        "skipped_exists": 0,
        "skipped_missing_source": 0,
        "skipped_missing_path": 0,
        "skipped_missing_new_path": 0,
        "errors": 0,
    }


def test_restructure_is_idempotent_when_overwrite_false(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [{"ID": "SPR_AP1_00002", "Path": "x/y/src.jdx", "new Path": "2025/CW02/file.jdx"}],
        curated_csv,
    )
    source = touch_file(roots["source_root"] / "x/y/src.jdx", b"v1")
    target = roots["target_root"] / "2025/CW02/file.jdx"

    first_report, first_stats = restructure(curated_csv, roots["source_root"], roots["target_root"])
    source.write_bytes(b"v2")
    second_report, second_stats = restructure(curated_csv, roots["source_root"], roots["target_root"])

    assert first_report.loc[0, "action"] == "copied"
    assert first_stats["copied"] == 1
    assert target.read_bytes() == b"v1"
    assert second_report.loc[0, "action"] == "skipped_exists"
    assert second_stats["skipped_exists"] == 1


def test_restructure_overwrite_true_replaces_existing_target(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [{"ID": "SPR_AP1_00003", "Path": "a/b/src.spc", "new Path": "2025/CW03/file.spc"}],
        curated_csv,
    )
    touch_file(roots["source_root"] / "a/b/src.spc", b"SOURCE")
    target = touch_file(roots["target_root"] / "2025/CW03/file.spc", b"OLD")

    report, stats = restructure(
        curated_csv,
        roots["source_root"],
        roots["target_root"],
        overwrite=True,
    )

    assert target.read_bytes() == b"SOURCE"
    assert report.loc[0, "action"] == "copied"
    assert stats["copied"] == 1


@pytest.mark.parametrize(
    ("row", "expected_action", "counter"),
    [
        pytest.param(
            {"ID": "SPR_AP1_00004", "Path": pd.NA, "new Path": "2025/CW01/file.spc"},
            "skipped_missing_path",
            "skipped_missing_path",
            id="missing-path",
        ),
        pytest.param(
            {"ID": "SPR_AP1_00005", "Path": "a/b/file.spc", "new Path": pd.NA},
            "skipped_missing_new_path",
            "skipped_missing_new_path",
            id="missing-new-path",
        ),
        pytest.param(
            {"ID": "SPR_AP1_00006", "Path": "missing/source.spc", "new Path": "2025/CW03/file.spc"},
            "skipped_missing_source",
            "skipped_missing_source",
            id="missing-source",
        ),
    ],
)
def test_restructure_reports_missing_inputs_without_copying(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
    row: dict[str, Any],
    expected_action: str,
    counter: str,
) -> None:
    write_curated([row], curated_csv)

    report, stats = restructure(curated_csv, roots["source_root"], roots["target_root"])

    assert len(report) == 1
    assert report.loc[0, "ID"] == row["ID"]
    assert report.loc[0, "action"] == expected_action
    assert stats[counter] == 1
    assert stats["copied"] == 0


def test_restructure_create_target_dirs_controls_parent_directory_creation(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [{"ID": "SPR_AP1_00007", "Path": "p/q/r.spc", "new Path": "2025/CW05/subdir/file.spc"}],
        curated_csv,
    )
    touch_file(roots["source_root"] / "p/q/r.spc", b"DATA")
    target = roots["target_root"] / "2025/CW05/subdir/file.spc"

    report, stats = restructure(
        curated_csv,
        roots["source_root"],
        roots["target_root"],
        create_target_dirs=False,
    )

    assert report.loc[0, "action"] == "error"
    assert stats["errors"] == 1
    assert not target.parent.exists()


def test_restructure_save_report_writes_report_csv(
    roots: dict[str, Path],
    curated_csv: Path,
    tmp_path: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [{"ID": "SPR_AP1_00008", "Path": "a/b/src.spc", "new Path": "2025/CW06/file.spc"}],
        curated_csv,
    )
    touch_file(roots["source_root"] / "a/b/src.spc", b"X")
    output = tmp_path / "restructure_report.csv"

    report, _ = restructure(curated_csv, roots["source_root"], roots["target_root"], save_report=output)
    on_disk = read_semicolon_csv(output)

    assert on_disk.loc[0, "ID"] == report.loc[0, "ID"]
    assert on_disk.loc[0, "action"] == "copied"


def test_restructure_rejects_duplicate_selected_new_paths_before_copying(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [
            {"ID": "SPR_AP1_00009", "Path": "a/source1.spc", "new Path": "2025/CW01/duplicate.spc"},
            {"ID": "SPR_AP1_00010", "Path": "a/source2.spc", "new Path": "2025/CW01/duplicate.spc"},
        ],
        curated_csv,
    )

    with pytest.raises(ValueError, match="Duplicate new Path"):
        restructure(curated_csv, roots["source_root"], roots["target_root"])


def test_restructure_treats_directory_source_as_missing_source(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
) -> None:
    write_curated(
        [{"ID": "SPR_AP1_00011", "Path": "a/source_dir", "new Path": "2025/CW01/file.spc"}],
        curated_csv,
    )
    (roots["source_root"] / "a/source_dir").mkdir(parents=True)

    report, stats = restructure(curated_csv, roots["source_root"], roots["target_root"])

    assert report.loc[0, "action"] == "skipped_missing_source"
    assert stats["skipped_missing_source"] == 1
    assert not (roots["target_root"] / "2025/CW01/file.spc").exists()


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
def test_restructure_rejects_unsafe_registry_paths(
    roots: dict[str, Path],
    curated_csv: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
    path_col: str,
    path_value: str,
    expected: str,
) -> None:
    row = {"ID": "SPR_AP1_00012", "Path": "a/source.spc", "new Path": "2025/CW01/file.spc"}
    row[path_col] = path_value
    write_curated([row], curated_csv)

    with pytest.raises(ValueError, match=expected):
        restructure(curated_csv, roots["source_root"], roots["target_root"])


@pytest.mark.parametrize(
    ("root_key", "link_name", "column", "registry_path"),
    [
        pytest.param("source_root", "source_link", "Path", "source_link/file.spc", id="source"),
        pytest.param("target_root", "target_link", "new Path", "target_link/file.spc", id="target"),
    ],
)
def test_restructure_rejects_symlink_escapes(
    roots: dict[str, Path],
    curated_csv: Path,
    tmp_path: Path,
    write_curated: Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame],
    root_key: str,
    link_name: str,
    column: str,
    registry_path: str,
) -> None:
    outside = tmp_path / f"outside_{root_key}"
    outside.mkdir()
    link = roots[root_key] / link_name
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    touch_file(roots["source_root"] / "a/source.spc", b"DATA")
    row = {"ID": "SPR_AP1_00013", "Path": "a/source.spc", "new Path": "2025/CW01/file.spc"}
    row[column] = registry_path
    write_curated([row], curated_csv)

    with pytest.raises(ValueError, match="escapes its root"):
        restructure(curated_csv, roots["source_root"], roots["target_root"])
