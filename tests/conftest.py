from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from tests.helpers import registry_frame, write_registry_csv


@pytest.fixture()
def curated_df() -> pd.DataFrame:
    return registry_frame()


@pytest.fixture()
def curated_csv(tmp_path: Path) -> Path:
    return tmp_path / "measured_files.csv"


@pytest.fixture()
def roots(tmp_path: Path) -> dict[str, Path]:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir()
    target_root.mkdir()
    return {"source_root": source_root, "target_root": target_root}


@pytest.fixture()
def write_curated() -> Callable[[Sequence[Mapping[str, Any]] | pd.DataFrame, Path], pd.DataFrame]:
    def _write(
        rows: Sequence[Mapping[str, Any]] | pd.DataFrame,
        path: Path,
    ) -> pd.DataFrame:
        return write_registry_csv(path, rows)

    return _write
