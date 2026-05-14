from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.testing import assert_frame_equal

from file_discovery.config import ALL_INBOX_COLS, CSV_SEP, REGISTRY_COLS
from file_discovery.io_utils import write_csv


def registry_frame(
    rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    columns: Sequence[str] = REGISTRY_COLS,
) -> pd.DataFrame:
    frame = pd.DataFrame(list(rows or []))
    for col in columns:
        if col not in frame.columns:
            frame[col] = pd.NA

    ordered_columns = list(columns) + [col for col in frame.columns if col not in columns]
    return frame.loc[:, ordered_columns]


def inbox_frame(rows: Sequence[Mapping[str, Any]] | None = None) -> pd.DataFrame:
    return registry_frame(rows, columns=ALL_INBOX_COLS)


def write_registry_csv(path: Path, rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = rows.copy() if isinstance(rows, pd.DataFrame) else registry_frame(rows)
    write_csv(frame, path)
    return frame


def read_semicolon_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=CSV_SEP, dtype="string", encoding="utf-8-sig")


def touch_file(path: Path, content: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def assert_columns(frame: pd.DataFrame, expected: Sequence[str]) -> None:
    assert list(frame.columns) == list(expected)


def assert_frame_matches(actual: pd.DataFrame, expected: pd.DataFrame) -> None:
    assert_frame_equal(
        actual.reset_index(drop=True),
        expected.reset_index(drop=True),
        check_dtype=False,
        check_like=False,
    )
