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


def normalize_date_column(df: pd.DataFrame, column: str = "Date") -> None:
    """Normalize a registry date column to ``dd.mm.yyyy``.

    Parameters
    ----------
    df
        Dataframe whose date column should be normalized.
    column
        Name of the date column to normalize. If the column does not exist,
        the dataframe is left unchanged.

    Returns
    -------
    None

    Notes
    -----
    Accepted input formats are ``dd.mm.yyyy`` and ``yyyy-mm-dd``. Valid dates
    are written back as strings in ``dd.mm.yyyy`` format. Empty values are kept
    as missing values. Invalid non-empty date values raise a ``ValueError``.
    """
    if column not in df.columns:
        return

    values = df[column].astype("string").str.strip()
    missing = values.isna() | values.eq("")

    parsed_de = pd.to_datetime(
        values,
        format="%d.%m.%Y",
        errors="coerce",
    )

    parsed_iso = pd.to_datetime(
        values,
        format="%Y-%m-%d",
        errors="coerce",
    )

    parsed = parsed_de.fillna(parsed_iso)

    invalid = parsed.isna() & ~missing

    if invalid.any():
        bad_values = values.loc[invalid].drop_duplicates().head(20).tolist()

        raise ValueError(
            f"Could not parse some values in column {column!r}: {bad_values}"
        )

    df.loc[~missing, column] = (
        parsed.loc[~missing]
        .dt.strftime("%d.%m.%Y")
        .astype("string")
    )


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

    df = pd.read_csv(path, sep=";", dtype="string", encoding="utf-8-sig").dropna(how="all")
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
    normalize_date_column(df, "Date")
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
    normalize_date_column(df, "Date")
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
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    df.to_csv(path, sep=";", index=False, encoding="utf-8-sig")
