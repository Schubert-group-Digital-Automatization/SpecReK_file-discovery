"""
Compute and populate the `new Path` column in a curated registry.

The computed `new Path` is a *relative* POSIX path of the form:

    YYYY/CW##/<ID><suffix>

where `suffix` is derived from the `Path` column (source file path).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

import pandas as pd

from .config import ID_REGEX, REGISTRY_COLS
from .io_utils import (
    apply_query,
    ensure_columns,
    is_blank_series,
    load_curated,
    normalize_strings,
    write_csv,
)


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

    Raises
    ------
    ValueError
        If any non-empty date in the selected rows cannot be parsed as
        ``dd.mm.yyyy`` or ``yyyy-mm-dd``. Rows outside the query are not
        validated.
    """

    df, _added = load_curated(curated_csv, normalize_dates=False)
    df = ensure_columns(df, REGISTRY_COLS)
    normalize_strings(df, ("ID", "Path", "Date", "new Path"))

    df_total = len(df)
    selected = apply_query(df, query)
    selected_idx = selected.index

    id_series = df.loc[selected_idx, "ID"].astype("string")
    path_series = df.loc[selected_idx, "Path"].astype("string")
    date_series = df.loc[selected_idx, "Date"].astype("string")
    new_path_series = df.loc[selected_idx, "new Path"].astype("string")

    missing_id = is_blank_series(id_series)
    invalid_id = ~missing_id & ~id_series.str.fullmatch(ID_REGEX, na=False)

    missing_path = is_blank_series(path_series)

    suffix = pd.Series(None, index=selected_idx, dtype="object")
    suffix.loc[~missing_path] = path_series.loc[~missing_path].map(
        lambda p: PurePosixPath(str(p)).suffix
    )

    suffix_str = suffix.astype("string")
    missing_suffix = is_blank_series(suffix_str)

    missing_date = is_blank_series(date_series)

    parsed_de = pd.to_datetime(
        date_series.loc[~missing_date],
        format="%d.%m.%Y",
        errors="coerce",
    )
    parsed_iso = pd.to_datetime(
        date_series.loc[~missing_date],
        format="%Y-%m-%d",
        errors="coerce",
    )

    parsed_selected = parsed_de.fillna(parsed_iso)
    invalid_date = parsed_selected.isna()
    if invalid_date.any():
        bad_values = (
            date_series.loc[~missing_date]
            .loc[invalid_date]
            .drop_duplicates()
            .head(20)
            .tolist()
        )
        raise ValueError(f"Could not parse selected Date values: {bad_values}")

    dt = pd.Series(pd.NaT, index=selected_idx, dtype="datetime64[ns]")
    dt.loc[~missing_date] = parsed_selected

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

    is_currently_empty = is_blank_series(new_path_series)
    should_write = (
        is_currently_empty
        if not overwrite
        else pd.Series(True, index=selected_idx, dtype=bool)
    )

    eligible = ~(missing_id | invalid_id | missing_path | missing_suffix | missing_date)
    to_update = should_write & eligible

    update_idx = to_update[to_update].index
    candidate_new_path = df["new Path"].astype("string").str.strip()
    candidate_new_path.loc[update_idx] = computed.loc[update_idx].astype("string")
    nonempty_new_path = candidate_new_path[
        candidate_new_path.notna() & candidate_new_path.ne("")
    ]
    duplicate_new_paths = nonempty_new_path[
        nonempty_new_path.duplicated(keep=False)
    ]

    if not duplicate_new_paths.empty:
        examples = duplicate_new_paths.drop_duplicates().head(20).tolist()
        raise ValueError(f"Duplicate new Path values after update: {examples}")

    df.loc[update_idx, "new Path"] = computed.loc[update_idx].astype("string")

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

    return df, asdict(stats)
