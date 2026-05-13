"""Tests for CSV and dataframe utility helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from file_discovery.config import REGISTRY_COLS
from file_discovery.io_utils import ensure_columns, load_csv_or_empty, write_csv


def test_ensure_columns_returns_copy_without_mutating_input() -> None:
    """ensure_columns should be pure and require using the return value."""
    original = pd.DataFrame({"A": ["x"]})

    out = ensure_columns(original, ("A", "B"))

    assert "B" not in original.columns
    assert "B" in out.columns
    assert pd.isna(out.loc[0, "B"])


def test_load_csv_or_empty_returns_added_columns_for_missing_file(tmp_path: Path) -> None:
    """Missing CSVs should return an empty schema and explicit added columns."""
    missing = tmp_path / "missing.csv"

    df, added = load_csv_or_empty(missing, REGISTRY_COLS)

    assert list(df.columns) == list(REGISTRY_COLS)
    assert added == list(REGISTRY_COLS)


def test_write_csv_uses_utf8_sig_and_semicolon(tmp_path: Path) -> None:
    """CSV output should keep Excel-friendly UTF-8 BOM and semicolon separator."""
    out_path = tmp_path / "registry.csv"
    df = pd.DataFrame({"ID": ["SPR_AP1_00001"], "Path": ["a/b/file.spc"]})

    write_csv(df, out_path)

    raw = out_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert text.splitlines()[0] == "ID;Path"
