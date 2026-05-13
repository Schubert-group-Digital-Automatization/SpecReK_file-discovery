"""
Compute and populate the `new Path` column in a curated registry.

The computed `new Path` is a *relative* POSIX path of the form:

    YYYY/CW##/<ID><suffix>

where `suffix` is derived from the `Path` column (source file path).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pandas as pd

from .config import ID_REGEX, REGISTRY_COLS
from .io_utils import ensure_columns, load_curated, normalize_strings, write_csv


@dataclass(frozen=True)
class NewPathStats:
    """Statistics from `create_new_path`."""

    rows_total: int
    rows_selected: int
    updated: int
    skipped_missing_id: int
    skipped_invalid_id: int
    skipped_missing_path: int
    skipped_missing_suffix: int
    skipped_missing_date: int


def _apply_query(df: pd.DataFrame, query: str | None) -> pd.DataFrame:
    """Apply a pandas query string if provided."""
    if not query:
        return df

    try:
        return df.query(query)
    except Exception as exc:
        raise ValueError(f"Invalid query {query!r}") from exc


def _is_empty_string(series: pd.Series) -> pd.Series:
    """Return boolean mask for empty/blank strings (treat NA as False)."""
    as_str = series.astype("string")
    return as_str.str.strip().eq("").fillna(False)


def create_new_path(
    curated_csv: Path,
    query: str | None = None,
    overwrite: bool = False,
    save_output: Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Populate the `new Path` column in a curated registry CSV.

    The computed value is a relative POSIX path:

        YYYY/CW##/<ID><suffix>

    The suffix is taken from the source `Path` column (e.g. `.spc`, `.jdx`).
    The result is stored as a relative path so it can later be combined with a
    target root during verification or copying.

    Parameters
    ----------
    curated_csv
        Path to the curated registry CSV.
    query
        Optional pandas query string to restrict which rows are processed.
        Example: ``Technique == "Raman" and Operator == "MKY"``.
    overwrite
        If True, overwrite non-empty `new Path` values. If False, only fill
        missing/blank entries.
    save_output
        If provided, write the updated curated registry to this path.

    Returns
    -------
    tuple[pandas.DataFrame, dict]
        Updated dataframe and a stats dictionary.

    Notes
    -----
    Rows are skipped when required inputs are missing: `ID`, `Path` suffix, or
    `Date`. No attempt is made to infer missing values.
    """

    df = load_curated(curated_csv)
    df = ensure_columns(df, REGISTRY_COLS)
    normalize_strings(df, ("ID", "Path", "Date", "new Path"))

    df_total = len(df)
    selected = _apply_query(df, query)
    selected_idx = selected.index

    id_series = df.loc[selected_idx, "ID"].astype("string")
    path_series = df.loc[selected_idx, "Path"].astype("string")
    date_series = df.loc[selected_idx, "Date"].astype("string")
    new_path_series = df.loc[selected_idx, "new Path"].astype("string")

    missing_id = id_series.isna() | _is_empty_string(id_series)
    invalid_id = ~missing_id & ~id_series.str.fullmatch(ID_REGEX, na=False)

    missing_path = path_series.isna() | _is_empty_string(path_series)

    suffix = pd.Series(None, index=selected_idx, dtype="object")
    suffix.loc[~missing_path] = path_series.loc[~missing_path].map(
        lambda p: PurePosixPath(str(p)).suffix
    )

    suffix_str = suffix.astype("string")
    missing_suffix = suffix_str.isna() | _is_empty_string(suffix_str)

    missing_date = date_series.isna() | _is_empty_string(date_series)

    dt = pd.Series(pd.NaT, index=selected_idx, dtype="datetime64[ns]")
    dt.loc[~missing_date] = pd.to_datetime(
        date_series.loc[~missing_date],
        format="%d.%m.%Y",
        errors="raise",
    )

    iso = dt.dt.isocalendar()
    year = iso["year"].astype("Int64")
    week = iso["week"].astype("Int64")

    computed = (
        year.astype("string")
        + "/CW"
        + week.astype("string").str.zfill(2)
        + "/"
        + id_series
        + suffix_str
    )

    is_currently_empty = new_path_series.isna() | _is_empty_string(new_path_series)
    should_write = is_currently_empty if not overwrite else pd.Series(True, index=selected_idx)

    eligible = ~(missing_id | invalid_id | missing_path | missing_suffix | missing_date)
    to_update = should_write & eligible

    duplicate_new_paths = computed.loc[to_update]
    duplicate_new_paths = duplicate_new_paths[duplicate_new_paths.duplicated(keep=False)]

    if not duplicate_new_paths.empty:
        examples = duplicate_new_paths.drop_duplicates().head(20).tolist()
        raise ValueError(f"Duplicate computed new Path values: {examples}")

    df.loc[selected_idx[to_update], "new Path"] = computed.loc[to_update].astype("string")

    stats = NewPathStats(
        rows_total=df_total,
        rows_selected=int(len(selected_idx)),
        updated=int(to_update.sum()),
        skipped_missing_id=int(missing_id.sum()),
        skipped_invalid_id=int(invalid_id.sum()),
        skipped_missing_path=int(missing_path.sum()),
        skipped_missing_suffix=int(missing_suffix.sum()),
        skipped_missing_date=int(missing_date.sum()),
    )

    if save_output is not None:
        write_csv(df, save_output)

    return df, stats.__dict__
