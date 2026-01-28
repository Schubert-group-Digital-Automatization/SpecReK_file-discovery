"""
Restructure (copy/rename) files from a source tree into a target tree.

The destination is defined by `new Path` (relative) and the file is copied to:

    target_root / new Path

The filename is assumed to already be `<ID><suffix>` as part of `new Path`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

import pandas as pd

from .config import REGISTRY_COLS
from .io_utils import ensure_columns, load_curated, normalize_strings, write_csv


@dataclass(frozen=True)
class RestructureStats:
    """Statistics from `restructure`."""

    rows_total: int
    rows_selected: int
    copied: int
    skipped_exists: int
    skipped_missing_source: int
    skipped_missing_path: int
    skipped_missing_new_path: int
    errors: int


def _apply_query(df: pd.DataFrame, query: str | None) -> pd.DataFrame:
    """Apply a pandas query string if provided."""
    if not query:
        return df
    return df.query(query)


def restructure(
    curated_csv: Path,
    source_root: Path,
    target_root: Path,
    query: str | None = None,
    overwrite: bool = False,
    create_target_dirs: bool = True,
    save_report: Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Copy files from source_root/Path to target_root/new Path.

    Parameters
    ----------
    curated_csv
        Path to the curated registry CSV.
    source_root
        Root directory for the source files.
    target_root
        Root directory for the target directory structure.
    query
        Optional pandas query string to restrict which rows are processed.
    overwrite
        If True, overwrite existing target files. If False, skip when the target
        already exists.
    create_target_dirs
        If True, create parent directories for target paths.
    save_report
        If provided, write the per-row action report to this path as CSV.

    Returns
    -------
    tuple[pandas.DataFrame, dict]
        A report dataframe and a stats dictionary.

    Notes
    -----
    This function performs file operations. It is designed to be idempotent when
    `overwrite=False`: repeated runs will skip already copied targets.
    """
    df = load_curated(curated_csv)
    df = ensure_columns(df, REGISTRY_COLS)
    normalize_strings(df, ("ID", "Path", "new Path"))

    total = len(df)
    selected = _apply_query(df, query).copy()
    selected_count = len(selected)

    actions: list[dict[str, object]] = []
    copied = 0
    skipped_exists = 0
    skipped_missing_source = 0
    skipped_missing_path = 0
    skipped_missing_new_path = 0
    errors = 0

    for _, row in selected.iterrows():
        rel_src = str(row.get("Path") or "").strip()
        rel_tgt = str(row.get("new Path") or "").strip()
        file_id = row.get("ID")

        if not rel_src:
            actions.append(
                {
                    "ID": file_id,
                    "Path": pd.NA,
                    "new Path": rel_tgt or pd.NA,
                    "action": "skipped_missing_path",
                    "error": pd.NA,
                }
            )
            skipped_missing_path += 1
            continue

        if not rel_tgt:
            actions.append(
                {
                    "ID": file_id,
                    "Path": rel_src,
                    "new Path": pd.NA,
                    "action": "skipped_missing_new_path",
                    "error": pd.NA,
                }
            )
            skipped_missing_new_path += 1
            continue

        src = (source_root / rel_src).resolve()
        dst = (target_root / rel_tgt).resolve()

        if not src.exists():
            actions.append(
                {
                    "ID": file_id,
                    "Path": rel_src,
                    "new Path": rel_tgt,
                    "action": "skipped_missing_source",
                    "error": pd.NA,
                }
            )
            skipped_missing_source += 1
            continue

        if dst.exists() and not overwrite:
            actions.append(
                {
                    "ID": file_id,
                    "Path": rel_src,
                    "new Path": rel_tgt,
                    "action": "skipped_exists",
                    "error": pd.NA,
                }
            )
            skipped_exists += 1
            continue

        try:
            if create_target_dirs:
                dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            actions.append(
                {
                    "ID": file_id,
                    "Path": rel_src,
                    "new Path": rel_tgt,
                    "action": "copied",
                    "error": pd.NA,
                }
            )
            copied += 1
        except OSError as exc:
            actions.append(
                {
                    "ID": file_id,
                    "Path": rel_src,
                    "new Path": rel_tgt,
                    "action": "error",
                    "error": str(exc),
                }
            )
            errors += 1

    report = pd.DataFrame(actions)
    stats = RestructureStats(
        rows_total=int(total),
        rows_selected=int(selected_count),
        copied=int(copied),
        skipped_exists=int(skipped_exists),
        skipped_missing_source=int(skipped_missing_source),
        skipped_missing_path=int(skipped_missing_path),
        skipped_missing_new_path=int(skipped_missing_new_path),
        errors=int(errors),
    )

    if save_report is not None:
        write_csv(report, save_report)

    return report, stats.__dict__
