from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from file_discovery.config import REGISTRY_COLS
from file_discovery.io_utils import (
    apply_query,
    ensure_columns,
    is_blank_series,
    load_csv_or_empty,
    load_curated,
    normalize_curated_columns,
    normalize_date_column,
    normalize_strings,
    write_csv,
)
from tests.helpers import assert_columns, read_semicolon_csv, registry_frame


def test_ensure_columns_returns_copy_without_mutating_input() -> None:
    original = pd.DataFrame({"A": ["x"]})

    result = ensure_columns(original, ("A", "B"))

    assert "B" not in original.columns
    assert_columns(result, ("A", "B"))
    assert pd.isna(result.loc[0, "B"])


def test_normalize_strings_strips_existing_columns_in_place_only() -> None:
    frame = pd.DataFrame({"A": ["  x  ", pd.NA], "B": [" untouched ", " untouched "]})

    normalize_strings(frame, ("A", "missing"))

    assert frame["A"].tolist() == ["x", pd.NA]
    assert frame["B"].tolist() == [" untouched ", " untouched "]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        pytest.param([pd.NA, "", "   ", "x", 1], [True, True, True, False, False], id="mixed"),
        pytest.param(["\t", "\n", " y "], [True, True, False], id="whitespace"),
    ],
)
def test_is_blank_series_treats_na_and_whitespace_as_blank(
    values: list[object],
    expected: list[bool],
) -> None:
    result = is_blank_series(pd.Series(values))

    assert result.tolist() == expected


def test_apply_query_returns_filtered_view_for_valid_query() -> None:
    frame = pd.DataFrame({"Technique": ["Raman", "PL"], "ID": ["one", "two"]})

    result = apply_query(frame, 'Technique == "Raman"')

    assert result["ID"].tolist() == ["one"]


def test_apply_query_wraps_invalid_query() -> None:
    frame = pd.DataFrame({"Technique": ["Raman"]})

    with pytest.raises(ValueError, match="Invalid query"):
        apply_query(frame, "not a valid pandas query !")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("01.06.2024", "01.06.2024", id="german-date"),
        pytest.param("2024-06-01", "01.06.2024", id="iso-date"),
    ],
)
def test_normalize_date_column_formats_supported_dates(raw: str, expected: str) -> None:
    frame = pd.DataFrame({"Date": [raw]})

    normalize_date_column(frame)

    assert frame.loc[0, "Date"] == expected


def test_normalize_date_column_keeps_blank_values_missing() -> None:
    frame = pd.DataFrame({"Date": [pd.NA, ""]})

    normalize_date_column(frame)

    assert pd.isna(frame.loc[0, "Date"])
    assert frame.loc[1, "Date"] == ""


def test_normalize_date_column_rejects_invalid_nonempty_values() -> None:
    frame = pd.DataFrame({"Date": ["not-a-date"]})

    with pytest.raises(ValueError, match="Could not parse"):
        normalize_date_column(frame)


def test_load_csv_or_empty_returns_schema_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"

    frame, added = load_csv_or_empty(missing, REGISTRY_COLS)

    assert_columns(frame, REGISTRY_COLS)
    assert added == list(REGISTRY_COLS)


def test_load_csv_or_empty_strips_headers_adds_missing_columns_and_drops_empty_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "registry.csv"
    path.write_text(" ID ; Path ; Extra \nSPR_AP1_00001;a/b/file.spc;x\n;;\n", encoding="utf-8")

    frame, added = load_csv_or_empty(path, ("ID", "Path", "Date"))

    assert frame.loc[0, "ID"] == "SPR_AP1_00001"
    assert frame.loc[0, "Path"] == "a/b/file.spc"
    assert "Extra" in frame.columns
    assert added == ["Date"]
    assert len(frame) == 1


def test_load_csv_or_empty_rejects_null_bytes(tmp_path: Path) -> None:
    path = tmp_path / "registry.csv"
    path.write_bytes(b"ID;Pa\x00th\n")

    with pytest.raises(ValueError, match="null byte"):
        load_csv_or_empty(path, REGISTRY_COLS)


def test_normalize_curated_columns_strips_names_without_legacy_mapping() -> None:
    frame = pd.DataFrame({" Projekt ": ["Legacy"], " Project ": ["Canonical"]})

    result = normalize_curated_columns(frame)

    assert result.loc[0, "Projekt"] == "Legacy"
    assert result.loc[0, "Project"] == "Canonical"


def test_load_curated_keeps_legacy_projekt_as_extra_column(tmp_path: Path) -> None:
    path = tmp_path / "legacy.csv"
    write_csv(
        pd.DataFrame(
            {
                "ID": [" SPR_AP1_00001 "],
                "Path": [" a/b/file.spc "],
                "Current Filename": [" file "],
                "Projekt": ["LegacyProject"],
            }
        ),
        path,
    )

    frame, added = load_curated(path)

    assert frame.loc[0, "ID"] == "SPR_AP1_00001"
    assert frame.loc[0, "Path"] == "a/b/file.spc"
    assert frame.loc[0, "Current Filename"] == "file"
    assert frame.loc[0, "Projekt"] == "LegacyProject"
    assert pd.isna(frame.loc[0, "Project"])
    assert "Project" in added


def test_write_csv_uses_semicolon_utf8_sig_and_stripped_headers(tmp_path: Path) -> None:
    path = tmp_path / "registry.csv"

    write_csv(pd.DataFrame({" ID ": ["SPR_AP1_00001"], "Path": ["a/b/file.spc"]}), path)

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    on_disk = read_semicolon_csv(path)
    assert_columns(on_disk, ("ID", "Path"))


def test_py_typed_marker_exists() -> None:
    marker = Path(__file__).parents[2] / "src" / "file_discovery" / "py.typed"

    assert marker.exists()
