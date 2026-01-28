"""
Verify existence of source and target paths for a curated registry.

This module checks:

- source_root / Path
- target_root / new Path

Optionally, it creates target parent directories (YYYY/CW##).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import REGISTRY_COLS
from .io_utils import ensure_columns, load_curated, normalize_strings, write_csv


@dataclass(frozen=True)
class VerifyStats:
    """Statistics from `verify`."""

    rows_total: int
    rows_selected: int
    ok: int
    missing_source: int
    missing_target: int
    missing_path: int
    missing_new_path: int


def _apply_query(df: pd.DataFrame, query: str | None) -> pd.DataFrame:
    """Apply a pandas query string if provided."""
    if not query:
        return df
    return df.query(query)


def _as_rel_posix(series: pd.Series) -> pd.Series:
    """Normalize a path column to string with stripped whitespace."""
    return series.astype("string").str.strip()


def verify(
    curated_csv: Path,
    source_root: Path,
    target_root: Path,
    query: str | None = None,
    create_target_dirs: bool = False,
    save_output: Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Verify source and target filesystem paths for entries in a curated registry.

    Parameters
    ----------
    curated_csv
        Path to the curated registry CSV.
    source_root
        Root directory for the existing source files.
    target_root
        Root directory for the restructured target files.
    query
        Optional pandas query string to restrict which rows are processed.
    create_target_dirs
        If True, create parent directories for targets that have a `new Path`
        value (for example `<target_root>/YYYY/CW##`).
    save_output
        If provided, write the verification report to this path as CSV.

    Returns
    -------
    tuple[pandas.DataFrame, dict]
        A verification report dataframe and a stats dictionary.

    Notes
    -----
    Verification does not create files. Only target parent directories may be
    created when `create_target_dirs=True`.
    """
    df = load_curated(curated_csv)
    df = ensure_columns(df, REGISTRY_COLS)
    normalize_strings(df, ("ID", "Path", "new Path"))

    total = len(df)
    selected = _apply_query(df, query).copy()
    selected_count = len(selected)

    rel_src = _as_rel_posix(selected["Path"])
    rel_tgt = _as_rel_posix(selected["new Path"])

    has_src_rel = rel_src.notna() & ~rel_src.eq("")
    has_tgt_rel = rel_tgt.notna() & ~rel_tgt.eq("")

    source_abs = pd.Series(None, index=selected.index, dtype="object")
    target_abs = pd.Series(None, index=selected.index, dtype="object")

    source_abs.loc[has_src_rel] = rel_src.loc[has_src_rel].map(
        lambda p: str((source_root / p).resolve())
    )
    target_abs.loc[has_tgt_rel] = rel_tgt.loc[has_tgt_rel].map(
        lambda p: str((target_root / p).resolve())
    )

    source_exists = source_abs.map(lambda p: Path(p).exists() if p else False)
    target_exists = target_abs.map(lambda p: Path(p).exists() if p else False)

    if create_target_dirs:
        for p in target_abs.dropna():
            Path(p).parent.mkdir(parents=True, exist_ok=True)

    status = pd.Series("ok", index=selected.index, dtype="string")
    status.loc[~has_src_rel] = "missing_path"
    status.loc[has_src_rel & ~source_exists] = "missing_source"
    status.loc[~has_tgt_rel] = "missing_new_path"
    status.loc[has_tgt_rel & ~target_exists] = "missing_target"
    status.loc[source_exists & target_exists] = "ok"

    report = pd.DataFrame(
        {
            "ID": selected["ID"].astype("string"),
            "Path": rel_src,
            "new Path": rel_tgt,
            "source_abs": source_abs.astype("string"),
            "target_abs": target_abs.astype("string"),
            "source_exists": source_exists.astype(bool),
            "target_exists": target_exists.astype(bool),
            "status": status.astype("string"),
        }
    )

    stats = VerifyStats(
        rows_total=int(total),
        rows_selected=int(selected_count),
        ok=int((status == "ok").sum()),
        missing_source=int((status == "missing_source").sum()),
        missing_target=int((status == "missing_target").sum()),
        missing_path=int((status == "missing_path").sum()),
        missing_new_path=int((status == "missing_new_path").sum()),
    )

    if save_output is not None:
        write_csv(report, save_output)

    return report, stats.__dict__
