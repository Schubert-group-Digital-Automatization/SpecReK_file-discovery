"""
Verify existence of source and target paths for a curated registry.

This module checks:

- source_root / Path
- target_root / new Path

Optionally, it creates target parent directories (YYYY/CW##).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .config import REGISTRY_COLS
from .io_utils import apply_query, ensure_columns, load_curated, normalize_strings, write_csv
from .path_utils import resolve_under_root


def _path_exists(path_str: object) -> bool:
    """Return True if *path_str* is a non-empty path string that exists."""
    if not isinstance(path_str, str):
        return False

    path_str = path_str.strip()

    if not path_str:
        return False

    return Path(path_str).exists()


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
) -> tuple[pd.DataFrame, dict[str, int]]:
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
        value and an existing source path.
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
    df, _added = load_curated(curated_csv)
    df = ensure_columns(df, REGISTRY_COLS)
    normalize_strings(df, ("ID", "Path", "new Path"))

    total = len(df)
    selected = apply_query(df, query).copy()
    selected_count = len(selected)

    rel_src = _as_rel_posix(selected["Path"])
    rel_tgt = _as_rel_posix(selected["new Path"])

    has_src_rel = rel_src.notna() & ~rel_src.eq("")
    has_tgt_rel = rel_tgt.notna() & ~rel_tgt.eq("")

    source_abs = pd.Series(pd.NA, index=selected.index, dtype="string")
    target_abs = pd.Series(pd.NA, index=selected.index, dtype="string")

    source_abs.loc[has_src_rel] = rel_src.loc[has_src_rel].map(
        lambda p: str(resolve_under_root(source_root, str(p), column="Path"))
    )
    target_abs.loc[has_tgt_rel] = rel_tgt.loc[has_tgt_rel].map(
        lambda p: str(resolve_under_root(target_root, str(p), column="new Path"))
    )

    source_exists = source_abs.map(_path_exists)
    target_exists = target_abs.map(_path_exists)

    if create_target_dirs:
        valid_targets = target_abs.loc[has_src_rel & has_tgt_rel & source_exists]

        for p in valid_targets.dropna():
            Path(p).parent.mkdir(parents=True, exist_ok=True)

    status = pd.Series("ok", index=selected.index, dtype="string")

    # Recompute mask_ok before each lower-priority assignment so rows already
    # marked with a higher-priority status cannot be overwritten.
    # Highest priority: missing relative source path
    status.loc[~has_src_rel] = "missing_path"

    # Next: missing relative target path (only where status is still ok)
    mask_ok = status.eq("ok")
    status.loc[mask_ok & ~has_tgt_rel] = "missing_new_path"

    # Next: missing source file (only where status is still ok)
    mask_ok = status.eq("ok")
    status.loc[mask_ok & has_src_rel & ~source_exists] = "missing_source"

    # Next: missing target file (only where status is still ok)
    mask_ok = status.eq("ok")
    status.loc[mask_ok & has_tgt_rel & ~target_exists] = "missing_target"

    report = pd.DataFrame(
        {
            "ID": selected["ID"].astype("string"),
            "Path": rel_src,
            "new Path": rel_tgt,
            "source_abs": source_abs,
            "target_abs": target_abs,
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

    return report, asdict(stats)
