from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from file_discovery.config import (
    ALLOWED_EXTENSIONS,
    ALLOW_NUMERIC_EXTENSIONS,
    COMMENT_EXCLUSION_TOKENS,
    DATE_FORMATS,
    DEFAULT_NM,
    KNOWN_PREFIXES,
)
from file_discovery.parsing_util import (
    build_comments,
    is_allowed_file,
    parse_date_and_cw,
    parse_date_token,
    parse_file_row,
    parse_measured_material,
    parse_nm,
    parse_nm_token,
    parse_operator,
    parse_position,
    parse_position_token,
    parse_sample_type,
    parse_technique,
    tokenize,
)


def test_is_allowed_file_accepts_configured_extensions() -> None:
    extension = sorted(ALLOWED_EXTENSIONS)[0]

    assert is_allowed_file(Path(f"dummy{extension}")) is True


def test_is_allowed_file_numeric_extensions_follow_config_flag() -> None:
    assert is_allowed_file(Path("dummy.123")) is bool(ALLOW_NUMERIC_EXTENSIONS)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        pytest.param("A_B_C", ["A", "B", "C"], id="normal"),
        pytest.param("A__B", ["A", "B"], id="drops-empty"),
        pytest.param(" A _ B ", ["A", "B"], id="strips-tokens"),
    ],
)
def test_tokenize_splits_strips_and_drops_empty_tokens(
    filename: str,
    expected: list[str],
) -> None:
    assert tokenize(filename) == expected


def test_tokenize_returns_empty_list_for_non_string_input() -> None:
    assert tokenize(None) == []  # type: ignore[arg-type]


def test_parse_measured_material_prefers_first_known_prefix_token() -> None:
    prefix = KNOWN_PREFIXES[0]

    assert parse_measured_material(["XXX", f"{prefix}123", "ZZZ"]) == f"{prefix}123"


def test_parse_measured_material_falls_back_to_first_token() -> None:
    assert parse_measured_material(["AAA", "BBB"]) == "AAA"
    assert parse_measured_material([]) is None


@pytest.mark.parametrize(
    ("measured_material", "expected"),
    [
        pytest.param("FSU026", "calibration", id="calibration-material"),
        pytest.param("FSU027", "analyte", id="other-fsu"),
        pytest.param(None, "analyte", id="missing"),
    ],
)
def test_parse_sample_type_is_calibration_only_for_fsu026(
    measured_material: str | None,
    expected: str,
) -> None:
    assert parse_sample_type(measured_material) == expected


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        pytest.param(["MKY-LF"], "MKY-LF", id="compound-token"),
        pytest.param(["MKY", "LF"], "MKY-LF", id="split-compound"),
        pytest.param(["MKY"], "MKY", id="simple"),
        pytest.param(["LF"], None, id="modifier-only"),
    ],
)
def test_parse_operator_handles_compound_simple_and_missing_tokens(
    tokens: list[str],
    expected: str | None,
) -> None:
    assert parse_operator(tokens) == expected


def test_parse_technique_uses_pl_token_or_default_raman() -> None:
    assert parse_technique(["PL"]) == "PL"
    assert parse_technique(["X", "Y"]) == "Raman"


@pytest.mark.parametrize(
    ("token", "expected_date", "expected_week"),
    [
        pytest.param("01-06-2024", "01.06.2024", 22, id="dd-mm-yyyy"),
        pytest.param("01-06-24", "01.06.2024", 22, id="dd-mm-yy"),
        pytest.param("2024_06_01", "01.06.2024", 22, id="yyyy_mm_dd"),
    ],
)
def test_parse_date_and_cw_supports_every_configured_format(
    token: str,
    expected_date: str,
    expected_week: int,
) -> None:
    assert set(DATE_FORMATS) == {"%d-%m-%Y", "%d-%m-%y", "%Y_%m_%d"}
    assert parse_date_and_cw(token) == (expected_date, expected_week)


def test_parse_date_token_returns_first_matching_date_token() -> None:
    assert parse_date_token(["AAA", "01-06-24", "2024_06_01"]) == "01-06-24"


def test_parse_date_and_cw_returns_none_tuple_for_missing_or_invalid_tokens() -> None:
    assert parse_date_and_cw(None) == (None, None)
    assert parse_date_and_cw("not-a-date") == (None, None)


def test_parse_nm_token_and_direct_nm_value() -> None:
    assert parse_nm_token(["AAA", "785nm", "BBB"]) == "785nm"
    assert parse_nm("785nm", path_rel="x/y/z") == 785.0


@pytest.mark.parametrize(
    ("path_rel", "expected"),
    [
        pytest.param("some/785nm/dir/file.spc", 785.0, id="785-folder"),
        pytest.param("some/532nm/dir/file.spc", 532.0, id="532-folder"),
        pytest.param("some/other/dir/file.spc", float(DEFAULT_NM), id="default"),
    ],
)
def test_parse_nm_uses_folder_fallback_then_default(path_rel: str, expected: float) -> None:
    assert parse_nm(None, path_rel=path_rel) == expected


@pytest.mark.parametrize(
    ("tokens", "expected_position", "expected_token"),
    [
        pytest.param(["Pellet1S2"], "P1S2", "Pellet1S2", id="pellet"),
        pytest.param(["P3S4"], "P3S4", "P3S4", id="position"),
        pytest.param(["liquid"], "liquid", "liquid", id="liquid"),
        pytest.param(["X", "Y"], None, None, id="missing"),
    ],
)
def test_parse_position_returns_canonical_position_and_consumed_token(
    tokens: list[str],
    expected_position: str | None,
    expected_token: str | None,
) -> None:
    assert parse_position(tokens) == expected_position
    assert parse_position_token(tokens) == expected_token


def test_build_comments_excludes_used_tokens_and_configured_exclusions() -> None:
    exclusion = next(iter(COMMENT_EXCLUSION_TOKENS))

    assert build_comments(["A", "B", "C"], {"B"}) == "A_C"
    assert build_comments(["A", exclusion, "B"], set()) == "A_B"
    assert build_comments([exclusion], set()) is None


def test_parse_file_row_populates_registry_fields_for_representative_filename() -> None:
    row = parse_file_row(
        path_rel="folder/785nm/sub/FSU026_MKY_PL_01-06-2024_Pellet1S2_extra.spc",
        current_filename="FSU026_MKY_PL_01-06-2024_Pellet1S2_extra",
    )

    assert set(row) == {
        "ID",
        "Path",
        "Current Filename",
        "Measured Material",
        "Sample Type",
        "Technique",
        "nm",
        "Date",
        "Position",
        "Location",
        "Operator",
        "Device",
        "Project",
        "Workpackage",
        "Comments",
        "new Path",
        "Calendar Week",
    }
    assert row["ID"] is pd.NA
    assert row["Path"] == "folder/785nm/sub/FSU026_MKY_PL_01-06-2024_Pellet1S2_extra.spc"
    assert row["Current Filename"] == "FSU026_MKY_PL_01-06-2024_Pellet1S2_extra"
    assert row["Measured Material"] == "FSU026"
    assert row["Sample Type"] == "calibration"
    assert row["Technique"] == "PL"
    assert row["Operator"] == "MKY"
    assert row["Date"] == "01.06.2024"
    assert row["Calendar Week"] == 22
    assert row["Position"] == "P1S2"
    assert row["nm"] == 785.0
    assert row["Comments"] == "extra"
    assert row["Device"] is pd.NA
    assert row["Project"] is pd.NA
    assert row["Workpackage"] is pd.NA
    assert row["new Path"] is pd.NA


def test_parse_file_row_handles_compound_operator_liquid_and_defaults() -> None:
    row = parse_file_row(
        path_rel="folder/532nm/FSU026_MKY-LF_PL_liquid.spc",
        current_filename="FSU026_MKY-LF_PL_liquid_01-06-2024",
    )

    assert row["Measured Material"] == "FSU026"
    assert row["Sample Type"] == "calibration"
    assert row["Operator"] == "MKY-LF"
    assert row["Technique"] == "PL"
    assert row["Position"] == "liquid"
    assert row["Date"] == "01.06.2024"
    assert row["Calendar Week"] == 22
    assert row["nm"] == 532.0
