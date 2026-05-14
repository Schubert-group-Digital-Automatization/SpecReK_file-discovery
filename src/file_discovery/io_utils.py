"""I/O helpers for reading and writing registry CSV files."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd

from .config import ALL_INBOX_COLS, CSV_SEP, REGISTRY_COLS


def ensure_columns(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """Return a copy of *df* with every column in *columns* present.

    Parameters
    ----------
    df
        Input dataframe.
    columns
        Column names that must exist in `df`.

    Returns
    -------
    pandas.DataFrame
        Copy of the dataframe with missing columns added as ``pd.NA``.

    Notes
    -----
    The original dataframe is not modified. Always use the return value.
    """
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def normalize_strings(df: pd.DataFrame, columns: Iterable[str]) -> None:
    """Strip whitespace from string columns in-place.

    Parameters
    ----------
    df
        Dataframe to normalize.
    columns
        Column names to strip (only applied if the column exists).

    Returns
    -------
    None

    Notes
    -----
    This function modifies *df* in-place. Pass ``df.copy()`` before calling if
    the original dataframe must be preserved.
    """
    for col in columns:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()


def is_blank_series(series: pd.Series) -> pd.Series:
    """Return True for NA or whitespace-only values.

    Parameters
    ----------
    series
        Series to evaluate.

    Returns
    -------
    pandas.Series
        Boolean mask that is True for ``NA`` or strings that are empty after
        whitespace stripping.
    """
    as_str = series.astype("string")
    return as_str.isna() | as_str.str.strip().eq("")


def apply_query(df: pd.DataFrame, query: str | None) -> pd.DataFrame:
    """Apply an optional trusted pandas query string.

    Parameters
    ----------
    df
        Input dataframe.
    query
        Pandas query expression. If ``None`` or empty, *df* is returned
        unchanged.

    Returns
    -------
    pandas.DataFrame
        Filtered dataframe view or the original dataframe.

    Raises
    ------
    ValueError
        If *query* is not a valid pandas query expression.

    Notes
    -----
    ``DataFrame.query`` evaluates an expression string. Do not pass untrusted
    user input to this function.
    """
    if not query:
        return df

    try:
        return df.query(query)
    except Exception as exc:
        raise ValueError(f"Invalid query {query!r}") from exc


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

        raise ValueError(f"Could not parse some values in column {column!r}: {bad_values}")

    df.loc[~missing, column] = parsed.loc[~missing].dt.strftime("%d.%m.%Y").astype("string")


def _validate_no_null_bytes(path: Path) -> None:
    """Raise if a CSV file contains embedded null bytes."""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            if b"\x00" in chunk:
                raise ValueError(f"CSV file contains null byte(s): {path}")


def load_csv_or_empty(path: Path, columns: Sequence[str]) -> tuple[pd.DataFrame, list[str]]:
    """Load a semicolon-separated CSV or return an empty dataframe.

    Parameters
    ----------
    path
        Path to the CSV file.
    columns
        Columns for the returned dataframe.

    Returns
    -------
    tuple[pandas.DataFrame, list[str]]
        Loaded dataframe with at least `columns`, plus the list of columns
        added as ``pd.NA``. If the file does not exist, an empty dataframe with
        these columns is returned and every requested column is reported as
        added.
    """
    if not path.exists():
        df = pd.DataFrame(columns=list(columns))
        return df, list(columns)

    _validate_no_null_bytes(path)

    df = pd.read_csv(
        path,
        sep=CSV_SEP,
        dtype="string",
        encoding="utf-8-sig",
    ).dropna(how="all")
    df = df.rename(columns=lambda name: str(name).strip())

    missing = [col for col in columns if col not in df.columns]
    df = ensure_columns(df, columns)
    return df, missing


def normalize_curated_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize curated column naming.

    Parameters
    ----------
    df
        Curated dataframe.

    Returns
    -------
    pandas.DataFrame
        Dataframe with stripped column names.
    """
    return df.rename(columns=lambda name: str(name).strip())


def load_curated(
    path: Path,
    *,
    normalize_dates: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    """Load the curated registry.

    Parameters
    ----------
    path
        Path to the curated CSV.
    normalize_dates
        If True, normalize and validate the ``Date`` column during loading.

    Returns
    -------
    tuple[pandas.DataFrame, list[str]]
        Curated registry with a stable schema and normalized key columns, plus
        columns added during loading.
    """
    df, added = load_csv_or_empty(path, REGISTRY_COLS)
    df = normalize_curated_columns(df)
    df = ensure_columns(df, REGISTRY_COLS)
    normalize_strings(df, ("ID", "Path", "Current Filename"))
    if normalize_dates:
        normalize_date_column(df, "Date")
    return df, added


def load_inbox(path: Path) -> tuple[pd.DataFrame, list[str]]:
    """Load the inbox registry.

    Parameters
    ----------
    path
        Path to the inbox CSV.

    Returns
    -------
    tuple[pandas.DataFrame, list[str]]
        Inbox registry with a stable schema and normalized key columns, plus
        columns added during loading.
    """
    df, added = load_csv_or_empty(path, ALL_INBOX_COLS)
    normalize_strings(df, ("Path",))
    normalize_date_column(df, "Date")
    return df, added


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

    Notes
    -----
    The parent directory must already exist. Public API functions validate this
    before calling ``write_csv``.
    """
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    df.to_csv(path, sep=CSV_SEP, index=False, encoding="utf-8-sig")
