"""Inbox pruning and conflict annotation.

This module removes inbox entries that are already represented in the curated
registry. Optionally, it can keep rows whose Path exists in curated but whose
core metadata differs, and annotate them via a ``conflicts`` column.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .config import INBOX_EXTRA_COLS, PRUNE_EXCLUDE_COLS, REGISTRY_COLS
from .io_utils import normalize_strings


CANONICAL_COMPARE_COLS = [col for col in REGISTRY_COLS if col not in PRUNE_EXCLUDE_COLS]


def series_equal_na(left: pd.Series, right: pd.Series) -> pd.Series:
    """Compare two Series while treating missing values as equal.

    Parameters
    ----------
    left, right
        Series to compare.

    Returns
    -------
    pandas.Series
        Boolean Series where NA==NA is treated as True.
    """
    return (left.eq(right) | (left.isna() & right.isna())).fillna(False)


def prune_inbox_by_path(inbox: pd.DataFrame, curated: pd.DataFrame) -> pd.DataFrame:
    """Remove inbox rows whose ``Path`` exists in the curated registry.

    Parameters
    ----------
    inbox
        Inbox dataframe (e.g. ``new_files.csv``).
    curated
        Curated registry dataframe (e.g. ``measured_files.csv``).

    Returns
    -------
    pandas.DataFrame
        Pruned inbox.

    Notes
    -----
    This is the simplest pruning strategy: if a Path is present in curated, the
    corresponding inbox row is removed.
    """
    if inbox.empty or curated.empty:
        return inbox

    inbox_out = inbox.copy()
    curated_norm = curated.copy()

    normalize_strings(inbox_out, ("Path",))
    normalize_strings(curated_norm, ("Path",))

    curated_paths_series = curated_norm["Path"].astype("string").str.strip()
    curated_paths_series = curated_paths_series[
        curated_paths_series.notna() & curated_paths_series.ne("")
    ]
    duplicate_paths = curated_paths_series[curated_paths_series.duplicated(keep=False)]

    if not duplicate_paths.empty:
        examples = duplicate_paths.drop_duplicates().head(20).tolist()
        raise ValueError(f"Duplicate Path values in curated registry: {examples}")

    curated_paths = set(curated_paths_series)
    inbox_paths = inbox_out["Path"].astype("string").str.strip()

    keep_mask = ~inbox_paths.isin(curated_paths)
    return inbox_out.loc[keep_mask].copy()


def _conflict_columns(
    joined: pd.DataFrame,
    columns: Iterable[str],
) -> tuple[pd.Series, list[tuple[str, pd.Series]]]:
    """Compute per-column conflict masks for a merged inbox/curated dataframe.

    Parameters
    ----------
    joined
        Dataframe containing ``<col>_in`` and ``<col>_cur`` columns.
    columns
        Base column names to compare.

    Returns
    -------
    tuple[pandas.Series, list[tuple[str, pandas.Series]]]
        ``(any_conflict, conflict_masks)`` where ``any_conflict`` is a boolean
        Series and ``conflict_masks`` is a list of ``(column, mask)`` tuples.
    """
    conflict_masks: list[tuple[str, pd.Series]] = []
    any_conflict = pd.Series(False, index=joined.index, dtype="bool")

    for col in columns:
        left = joined.get(f"{col}_in")
        right = joined.get(f"{col}_cur")

        if left is None or right is None:
            mask = pd.Series(True, index=joined.index, dtype="bool")
            conflict_masks.append((col, mask))
            any_conflict |= mask
            continue

        if col == "nm":
            left_num = pd.to_numeric(left, errors="coerce")
            right_num = pd.to_numeric(right, errors="coerce")
            equal = series_equal_na(left_num, right_num)
        else:
            left_str = left.astype("string").str.strip()
            right_str = right.astype("string").str.strip()
            equal = series_equal_na(left_str, right_str)

        mask = ~equal
        conflict_masks.append((col, mask))
        any_conflict |= mask.fillna(False)

    return any_conflict, conflict_masks


def prune_inbox_with_conflicts(inbox: pd.DataFrame, curated: pd.DataFrame) -> pd.DataFrame:
    """Prune inbox rows that match curated; annotate conflicts for mismatches.

    Parameters
    ----------
    inbox
        Inbox dataframe (e.g. ``new_files.csv``).
    curated
        Curated registry dataframe (e.g. ``measured_files.csv``).

    Returns
    -------
    pandas.DataFrame
        Pruned inbox. Rows whose Path exists in curated but whose canonical
        columns differ are kept and annotated in the ``conflicts`` column.
    """
    if inbox.empty or curated.empty:
        return inbox

    inbox_out = inbox.copy()
    curated_norm = curated.copy()

    normalize_strings(inbox_out, tuple(REGISTRY_COLS) + tuple(INBOX_EXTRA_COLS))
    normalize_strings(curated_norm, REGISTRY_COLS)

    curated_marked = curated_norm.copy()
    curated_marked["_in_curated"] = True

    curated_paths = curated_norm["Path"].astype("string").str.strip()
    curated_paths = curated_paths[curated_paths.notna() & curated_paths.ne("")]
    duplicate_paths = curated_paths[curated_paths.duplicated(keep=False)]

    if not duplicate_paths.empty:
        examples = duplicate_paths.drop_duplicates().head(20).tolist()
        raise ValueError(f"Duplicate Path values in curated registry: {examples}")

    inbox_path_values = inbox_out["Path"].astype("string").str.strip()
    has_path = inbox_path_values.notna() & inbox_path_values.ne("")
    inbox_with_path = inbox_out.loc[has_path].copy()

    joined = inbox_with_path.merge(
        curated_marked,
        on="Path",
        how="left",
        suffixes=("_in", "_cur"),
    )

    found = joined["_in_curated"].fillna(False)
    any_conflict, conflict_masks = _conflict_columns(joined, CANONICAL_COMPARE_COLS)

    prune_mask = found & (~any_conflict)
    conflict_rows = found & any_conflict

    if conflict_rows.any():
        conflict_bits = pd.DataFrame(index=joined.index)
        for col, mask in conflict_masks:
            conflict_bits[col] = col
            conflict_bits.loc[~mask.fillna(False), col] = ""

        conflict_str = conflict_bits.agg("|".join, axis=1).str.strip("|")
        conflict_str = conflict_str.replace("", pd.NA)

        joined.loc[conflict_rows, "conflicts_new"] = conflict_str.loc[conflict_rows]

        conflict_map = (
            joined.loc[conflict_rows, ["Path", "conflicts_new"]]
            .dropna(subset=["conflicts_new"])
            .set_index("Path")["conflicts_new"]
        )

        inbox_out["conflicts"] = inbox_out["Path"].map(conflict_map).fillna(
            inbox_out.get("conflicts", pd.NA)
        )

    prunable_paths = set(joined.loc[prune_mask, "Path"].astype("string"))
    inbox_paths = inbox_out["Path"].astype("string")

    return inbox_out.loc[~inbox_paths.isin(prunable_paths)].copy()
