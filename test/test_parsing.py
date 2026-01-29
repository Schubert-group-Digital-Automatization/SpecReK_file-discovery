"""Unit tests for filename parsing utilities (parsing_util).

These tests exercise the pure parsing logic (no filesystem discovery loops).
They are intentionally strict: if the parser contract changes, tests should fail
loudly rather than silently accepting drift.
"""

# pylint: disable=redefined-outer-name
# pylint: disable=import-error

# ------------------------
# Imports
# ------------------------
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

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
    parse_sample_type,
    parse_technique,
    tokenize,
)
from file_discovery.parsing_util import (
    ALLOWED_EXTENSIONS,
    ALLOW_NUMERIC_EXTENSIONS,
    COMMENT_EXCLUSION_TOKENS,
    DATE_FORMATS,
    DEFAULT_NM,
)


# ------------------------
# Helpers
# ------------------------
def _make_date_token(fmt: str) -> str:
    """Create a date token that should parse with the given DATE_FORMATS entry."""
    # Use a fixed date so expectations are deterministic.
    return date(2025, 1, 1).strftime(fmt)


# ------------------------
# Tests: file validation
# ------------------------
def test_is_allowed_file_accepts_configured_extensions() -> None:
    """Test that is_allowed_file accepts at least one configured extension."""
    assert isinstance(ALLOWED_EXTENSIONS, (set, frozenset, list, tuple))
    assert len(ALLOWED_EXTENSIONS) > 0  # if this ever becomes empty, config changed

    ext = next(iter(ALLOWED_EXTENSIONS))
    path = Path(f"dummy{ext}")
    assert is_allowed_file(path) is True


def test_is_allowed_file_numeric_extensions_respect_flag() -> None:
    """Test numeric-extension handling respects ALLOW_NUMERIC_EXTENSIONS."""
    path = Path("dummy.123")

    if ALLOW_NUMERIC_EXTENSIONS:
        assert is_allowed_file(path) is True
    else:
        assert is_allowed_file(path) is False


# ------------------------
# Tests: tokenization
# ------------------------
def test_tokenize_splits_on_underscores() -> None:
    """Test tokenize splits on '_' and preserves token order."""
    assert tokenize("A_B_C") == ["A", "B", "C"]


def test_tokenize_preserves_empty_tokens_from_double_underscores() -> None:
    """Test tokenize preserves empty tokens for consecutive underscores (current contract)."""
    # parsing_util.tokenize() returns current_filename.split("_") without filtering.
    assert tokenize("A__B") == ["A", "", "B"]


def test_tokenize_non_string_returns_empty_list() -> None:
    """Test tokenize returns [] for non-string input."""
    assert tokenize(None) == []  # type: ignore[arg-type]


# ------------------------
# Tests: individual parsers
# ------------------------
def test_parse_measured_material_prefers_known_prefix_over_first_token() -> None:
    """Test parse_measured_material returns the first token matching KNOWN_PREFIXES."""
    # We avoid assuming a specific prefix; instead, we create tokens such that the
    # first token is a non-matching filler and the second token should match by
    # using a token that starts with one of the configured prefixes.
    # If KNOWN_PREFIXES changes, this test still adapts.
    from file_discovery.parsing_util import KNOWN_PREFIXES  # local import to keep scope tight

    assert len(KNOWN_PREFIXES) > 0
    prefix = KNOWN_PREFIXES[0]
    tokens = ["XXX", f"{prefix}123", "ZZZ"]
    assert parse_measured_material(tokens) == f"{prefix}123"


def test_parse_measured_material_falls_back_to_first_token() -> None:
    """Test parse_measured_material returns the first token if no known prefix matches."""
    assert parse_measured_material(["AAA", "BBB"]) == "AAA"
    assert parse_measured_material([]) is None


def test_parse_sample_type_calibration_only_for_FSU026() -> None:
    """Test sample type mapping is strict: FSU026 => calibration, otherwise analyte."""
    assert parse_sample_type("FSU026") == "calibration"
    assert parse_sample_type("FSU027") == "analyte"
    assert parse_sample_type(None) == "analyte"


def test_parse_operator_mky_lf_and_mky() -> None:
    """Test operator parsing precedence: MKY-LF > MKY."""
    assert parse_operator(["MKY-LF"]) == "MKY-LF"
    assert parse_operator(["MKY", "LF"]) == "MKY-LF"
    assert parse_operator(["MKY"]) == "MKY"
    assert parse_operator(["LF"]) is None


def test_parse_technique_pl_or_raman() -> None:
    """Test technique parsing: PL token forces PL, else Raman."""
    assert parse_technique(["PL"]) == "PL"
    assert parse_technique(["X", "Y"]) == "Raman"


def test_parse_date_token_finds_first_matching_date_like_token() -> None:
    """Test parse_date_token returns the first token matching configured date regexes."""
    assert len(DATE_FORMATS) > 0
    token = _make_date_token(DATE_FORMATS[0])
    tokens = ["AAA", token, "BBB"]
    assert parse_date_token(tokens) == token


def test_parse_date_and_cw_parses_and_formats_dd_mm_yyyy_and_week() -> None:
    """Test parse_date_and_cw outputs dd.mm.yyyy and correct ISO week for a valid token."""
    assert len(DATE_FORMATS) > 0
    token = _make_date_token(DATE_FORMATS[0])

    date_str, cw = parse_date_and_cw(token)

    assert date_str == "01.01.2025"
    assert cw == 1  # 2025-01-01 is ISO week 1


def test_parse_date_and_cw_returns_none_none_on_failure() -> None:
    """Test parse_date_and_cw returns (None, None) if token is None or unparsable."""
    assert parse_date_and_cw(None) == (None, None)
    assert parse_date_and_cw("not-a-date") == (None, None)


def test_parse_nm_token_and_parse_nm_direct_value() -> None:
    """Test wavelength token extraction and direct conversion to float nm."""
    tokens = ["AAA", "785nm", "BBB"]
    nm_token = parse_nm_token(tokens)
    assert nm_token == "785nm"
    assert parse_nm(nm_token, path_rel="x/y/z") == 785.0


def test_parse_nm_folder_fallback_and_default() -> None:
    """Test nm folder fallback logic and DEFAULT_NM fallback."""
    assert parse_nm(None, path_rel="some/785nm/dir/file.spc") == 785.0
    assert parse_nm(None, path_rel="some/532nm/dir/file.spc") == 532.0
    assert parse_nm(None, path_rel="some/other/dir/file.spc") == float(DEFAULT_NM)


def test_parse_position_pellet_pos_and_liquid() -> None:
    """Test position parsing priorities: Pellet -> PxSx, then PxSx, then liquid."""
    assert parse_position(["Pellet1S2"]) == "P1S2"
    assert parse_position(["P3S4"]) == "P3S4"
    assert parse_position(["liquid"]) == "liquid"
    assert parse_position(["X", "Y"]) is None


def test_build_comments_excludes_used_and_config_exclusions() -> None:
    """Test build_comments excludes used tokens and COMMENT_EXCLUSION_TOKENS."""
    tokens = ["A", "B", "C"]
    used = {"B"}
    out = build_comments(tokens, used)
    assert out == "A_C"

    # If config defines exclusion tokens, ensure they are excluded.
    if COMMENT_EXCLUSION_TOKENS:
        exclusion = next(iter(COMMENT_EXCLUSION_TOKENS))
        tokens2 = ["A", exclusion, "B"]
        out2 = build_comments(tokens2, used_tokens=set())
        assert out2 == "A_B"


# ------------------------
# Tests: orchestrator
# ------------------------
def test_parse_file_row_populates_expected_fields_and_keeps_na_for_unset() -> None:
    """Test parse_file_row orchestrates helpers and returns a registry-like row dict."""
    # Use a path that triggers nm folder fallback in case nm token is absent.
    path_rel = "folder/785nm/sub/file.spc"
    # Make filename deterministic and avoid double underscores (tokenize keeps empties).
    # Include: measured material, operator, technique, date, position, and an extra comment token.
    token = _make_date_token(DATE_FORMATS[0])
    current_filename = f"FSU026_MKY_PL_{token}_Pellet1S2_extra"

    row = parse_file_row(path_rel=path_rel, current_filename=current_filename)

    # Presence of all expected keys (strict schema for this function).
    expected_keys = {
        "ID",
        "Path",
        "Current Filename",
        "Measured Material",
        "Sample Type",
        "Technique",
        "nm",
        "Date",
        "Position",
        "Operator",
        "Device",
        "Project",
        "Workpackage",
        "Comments",
        "new Path",
        "Calendar Week",
    }
    assert set(row.keys()) == expected_keys

    # Strict field expectations.
    assert row["ID"] is pd.NA
    assert row["Path"] == path_rel
    assert row["Current Filename"] == current_filename
    assert row["Measured Material"] == "FSU026"
    assert row["Sample Type"] == "calibration"
    assert row["Technique"] == "PL"
    assert row["Operator"] == "MKY"
    assert row["Date"] == "01.01.2025"
    assert row["Calendar Week"] == 1
    assert row["Position"] == "P1S2"
    assert row["nm"] == 785.0

    # Fields intentionally left unset during discovery.
    assert row["Device"] is pd.NA
    assert row["Project"] is pd.NA
    assert row["Workpackage"] is pd.NA
    assert row["new Path"] is pd.NA

    # Comments: should include the remaining "extra" token (and not re-include used ones).
    assert row["Comments"] == "extra"