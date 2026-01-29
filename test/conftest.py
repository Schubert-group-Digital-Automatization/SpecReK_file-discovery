"""Shared pytest fixtures for the file_discovery test suite."""

# pylint: disable=redefined-outer-name
# pylint: disable=import-error


from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

import pandas as pd
import pytest

from file_discovery.config import REGISTRY_COLS
from file_discovery.io_utils import write_csv


# ------------------------
# Helpers
# ------------------------

def _empty_curated_df() -> pd.DataFrame:
    """Create an empty curated registry dataframe with the canonical schema."""
    return pd.DataFrame(columns=list(REGISTRY_COLS)).astype("string")


# ------------------------
# Fixtures
# ------------------------

@pytest.fixture()
def curated_df() -> pd.DataFrame:
    """Return an empty curated registry dataframe using the canonical schema."""
    return _empty_curated_df()


@pytest.fixture()
def curated_csv(tmp_path: Path) -> Path:
    """Return a default path for a curated registry CSV under pytest's tmp_path."""
    return tmp_path / "measured_files.csv"


@pytest.fixture()
def roots(tmp_path: Path) -> dict[str, Path]:
    """Create source/target roots under tmp_path and return them as a mapping."""
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir(parents=True, exist_ok=True)
    target_root.mkdir(parents=True, exist_ok=True)
    return {"source_root": source_root, "target_root": target_root}


@pytest.fixture()
def write_curated() -> Callable:
    """Return a small helper that writes a curated dataframe as a semicolon CSV."""

    def _write(df: pd.DataFrame, path: Path) -> None:
        write_csv(df, path)

    return _write
