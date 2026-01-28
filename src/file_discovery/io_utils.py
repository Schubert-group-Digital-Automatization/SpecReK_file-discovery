"""I/O helpers for reading and writing registry CSV files."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd

from .config import INBOX_EXTRA_COLS, REGISTRY_COLS


def ensure_columns(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """Ensure a stable set of columns.

    Parameters
    ----------
    df
        Input dataframe.
    columns
        Column names that must exist in `df`.

    Returns
    -------
    pandas.DataFrame
        The same dataframe with missing columns added as NA.
    """
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def normalize_strings(df: pd.DataFrame, columns: Iterable[str]) -> None:
    """Strip whitespace from string columns.

    Parameters
    ----------
    df
        Dataframe to normalize.
    columns
        Column names to strip (only applied if the column exists).

    Returns
    -------
    None
    """
    for col in columns:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()


def load_csv_or_empty(path: Path, columns: Sequence[str]) -> pd.DataFrame:
    """Load a semicolon-separated CSV or return an empty dataframe.

    Parameters
    ----------
    path
        Path to the CSV file.
    columns
        Columns for the returned dataframe.

    Returns
    -------
    pandas.DataFrame
        Loaded dataframe with at least `columns`. If the file does not exist,
        an empty dataframe with these columns is returned.

    Notes
    -----
    Any missing columns are added as NA. The list of added columns is stored in
    ``df.attrs['added_columns']`` for optional reporting.
    """
    if not path.exists():
        df = pd.DataFrame(columns=list(columns))
        df.attrs["added_columns"] = list(columns)
        return df

    df = pd.read_csv(path, sep=";", dtype="string").dropna(how="all")
    df = df.rename(columns=lambda name: str(name).strip())

    missing = [col for col in columns if col not in df.columns]
    df = ensure_columns(df, columns)
    df.attrs["added_columns"] = missing
    return df


def normalize_curated_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize curated column naming.

    Parameters
    ----------
    df
        Curated dataframe.

    Returns
    -------
    pandas.DataFrame
        Dataframe with normalized column names.

    Notes
    -----
    This maps legacy German column names (e.g. ``Projekt``) to the English schema.
    """
    df = df.rename(columns=lambda name: str(name).strip())
    if "Projekt" in df.columns and "Project" not in df.columns:
        df = df.rename(columns={"Projekt": "Project"})
    return df


def load_curated(path: Path) -> pd.DataFrame:
    """Load the curated registry.

    Parameters
    ----------
    path
        Path to the curated CSV.

    Returns
    -------
    pandas.DataFrame
        Curated registry with a stable schema and normalized key columns.
    """
    df = load_csv_or_empty(path, REGISTRY_COLS)
    df = normalize_curated_columns(df)
    normalize_strings(df, ("ID", "Path", "Current Filename"))
    return df


def load_inbox(path: Path) -> pd.DataFrame:
    """Load the inbox registry.

    Parameters
    ----------
    path
        Path to the inbox CSV.

    Returns
    -------
    pandas.DataFrame
        Inbox registry with a stable schema and normalized key columns.
    """
    df = load_csv_or_empty(path, REGISTRY_COLS + INBOX_EXTRA_COLS)
    normalize_strings(df, ("Path",))
    return df


def write_csv(df: pd.DataFrame, path: Path) -> None:
    """Write a registry dataframe as semicolon-separated CSV.

    Parameters
    ----------
    df
        Dataframe to write.
    path
        Output CSV path.

    Returns
    -------
    None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep=";", index=False, encoding="utf-8")
