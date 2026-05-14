"""Unit tests for purging utils behavior."""

from __future__ import annotations

import pandas as pd
import pytest
from tests.helpers import inbox_frame, registry_frame

from file_discovery.purging_utils import (
    prune_inbox_by_path,
    prune_inbox_with_conflicts,
    series_equal_na,
)


def test_series_equal_na_treats_matching_missing_values_as_equal() -> None:
    """Verify series equal NA treats matching missing values as equal."""
    left = pd.Series(["x", pd.NA, "1"])
    right = pd.Series(["x", pd.NA, "2"])

    result = series_equal_na(left, right)

    assert result.tolist() == [True, True, False]


def test_prune_inbox_by_path_removes_rows_already_present_in_curated() -> None:
    """Verify prune inbox by path removes rows already present in curated."""
    inbox = inbox_frame(
        [
            {"Path": "existing/file.spc", "Current Filename": "existing"},
            {"Path": "new/file.spc", "Current Filename": "new"},
        ]
    )
    curated = registry_frame([{"Path": " existing/file.spc "}])

    result = prune_inbox_by_path(inbox, curated)

    assert result["Path"].tolist() == ["new/file.spc"]


def test_prune_inbox_by_path_rejects_duplicate_curated_paths() -> None:
    """Verify prune inbox by path rejects duplicate curated paths."""
    inbox = inbox_frame([{"Path": "existing/file.spc"}])
    curated = registry_frame(
        [
            {"Path": "existing/file.spc"},
            {"Path": " existing/file.spc "},
        ]
    )

    with pytest.raises(ValueError, match="Duplicate Path"):
        prune_inbox_by_path(inbox, curated)


def test_prune_inbox_with_conflicts_prunes_exact_matches() -> None:
    """Verify prune inbox with conflicts prunes exact matches."""
    inbox = inbox_frame(
        [
            {
                "Path": "registered/file.spc",
                "Current Filename": "file",
                "Date": "01.06.2024",
                "nm": "785.0",
            }
        ]
    )
    curated = registry_frame(
        [
            {
                "Path": "registered/file.spc",
                "Current Filename": "file",
                "Date": "01.06.2024",
                "nm": "785",
            }
        ]
    )

    result = prune_inbox_with_conflicts(inbox, curated)

    assert result.empty


def test_prune_inbox_with_conflicts_keeps_rows_and_annotates_exact_conflict_labels() -> None:
    """Verify prune inbox with conflicts keeps rows and annotates exact conflict labels."""
    inbox = inbox_frame(
        [
            {
                "Path": "registered/file.spc",
                "Current Filename": "file_from_inbox",
                "Date": "02.06.2024",
                "nm": "785",
                "Comments": "ignored inbox comment",
                "conflicts": "existing",
            }
        ]
    )
    curated = registry_frame(
        [
            {
                "Path": "registered/file.spc",
                "Current Filename": "file_from_curated",
                "Date": "01.06.2024",
                "nm": "532",
                "Comments": "ignored curated comment",
            }
        ]
    )

    result = prune_inbox_with_conflicts(inbox, curated)

    assert len(result) == 1
    assert result.loc[0, "Path"] == "registered/file.spc"
    assert result.loc[0, "conflicts"] == "Current Filename|nm|Date"
    assert "Comments" not in result.loc[0, "conflicts"]


def test_prune_inbox_with_conflicts_does_not_emit_empty_separator_artifacts() -> None:
    """Verify prune inbox with conflicts does not emit empty separator artifacts."""
    inbox = inbox_frame(
        [
            {
                "Path": "registered/file.spc",
                "Current Filename": "same",
                "Date": "02.06.2024",
            }
        ]
    )
    curated = registry_frame(
        [
            {
                "Path": "registered/file.spc",
                "Current Filename": "same",
                "Date": "01.06.2024",
            }
        ]
    )

    result = prune_inbox_with_conflicts(inbox, curated)

    assert result.loc[0, "conflicts"] == "Date"
    assert "|" not in result.loc[0, "conflicts"]


def test_prune_inbox_with_conflicts_preserves_existing_conflicts_for_unmatched_paths() -> None:
    """Verify prune inbox with conflicts preserves existing conflicts for unmatched paths."""
    inbox = inbox_frame(
        [
            {
                "Path": "unmatched/file.spc",
                "Current Filename": "file",
                "conflicts": "existing",
            }
        ]
    )
    curated = registry_frame([{"Path": "registered/file.spc"}])

    result = prune_inbox_with_conflicts(inbox, curated)

    assert len(result) == 1
    assert result.loc[0, "Path"] == "unmatched/file.spc"
    assert result.loc[0, "conflicts"] == "existing"


def test_prune_inbox_with_conflicts_rejects_duplicate_curated_paths() -> None:
    """Verify prune inbox with conflicts rejects duplicate curated paths."""
    inbox = inbox_frame([{"Path": "registered/file.spc"}])
    curated = registry_frame(
        [
            {"Path": "registered/file.spc"},
            {"Path": " registered/file.spc "},
        ]
    )

    with pytest.raises(ValueError, match="Duplicate Path"):
        prune_inbox_with_conflicts(inbox, curated)
