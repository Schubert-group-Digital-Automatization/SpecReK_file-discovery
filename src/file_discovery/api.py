"""Public API for measurement file discovery and restructuring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .compute_new_path import create_new_path as _create_new_path
from .config import INBOX_EXTRA_COLS, REGISTRY_COLS
from .detection_utils import (
    append_unique_by_path,
    build_case1_rows,
    build_case2_rows,
    scan_base_dir,
    scan_base_dir_minimal,
)
from .io_utils import ensure_columns, load_curated, load_inbox, write_csv
from .purging_utils import prune_inbox_by_path, prune_inbox_with_conflicts
from .restructure import restructure as _restructure
from .verify_paths import verify as _verify

ALL_INBOX_COLS = list(REGISTRY_COLS) + list(INBOX_EXTRA_COLS)

__all__ = (
    "discover",
    "create_new_path",
    "verify",
    "restructure",
)


def discover(
    base_dir_path: str | Path,
    file_registry_path: str | Path,
    discovery_output_path: str | Path,
    decode_filename: bool = True,
    find_conflicts: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Discover measurement files and update the discovery-output CSV.

    Parameters
    ----------
    base_dir_path
        Base directory to scan recursively.
    file_registry_path
        Path to the curated registry CSV (read-only input).
    discovery_output_path
        Path to the discovery output CSV (inbox) to update in-place.
    decode_filename
        If True, decode metadata from filename tokens. If False, only ``Path`` and
        ``Current Filename`` are populated for newly discovered files.
    find_conflicts
        If True, keep inbox rows when they disagree with curated metadata and
        annotate ``conflicts``. If False, prune by ``Path`` only.

    Returns
    -------
    tuple
        ``(inbox_df, stats)`` where ``stats`` is a small dict with counts.
    """
    base_dir = Path(base_dir_path)
    curated_path = Path(file_registry_path)
    inbox_path = Path(discovery_output_path)

    curated = load_curated(curated_path)
    inbox = load_inbox(inbox_path)

    curated_added_columns = curated.attrs.get("added_columns", [])
    inbox_added_columns = inbox.attrs.get("added_columns", [])

    if decode_filename:
        discovered = scan_base_dir(base_dir)
    else:
        discovered = scan_base_dir_minimal(base_dir)

    case2 = build_case2_rows(discovered, curated)
    case1 = build_case1_rows(discovered, curated)

    case2_paths = set(case2["Path"].astype("string").dropna())
    if case2_paths:
        case1 = case1.loc[~case1["Path"].astype("string").isin(case2_paths)].copy()

    before = len(inbox)
    inbox = append_unique_by_path(inbox, case2)
    inbox = append_unique_by_path(inbox, case1)
    appended = len(inbox) - before

    before_prune = len(inbox)
    if find_conflicts:
        inbox = prune_inbox_with_conflicts(inbox, curated)
    else:
        inbox = prune_inbox_by_path(inbox, curated)
    pruned = before_prune - len(inbox)

    inbox = ensure_columns(inbox, ALL_INBOX_COLS)
    inbox = inbox.reindex(columns=ALL_INBOX_COLS)

    write_csv(inbox, inbox_path)

    stats = {
        "curated_rows": len(curated),
        "discovered_rows": len(discovered),
        "inbox_before": before,
        "appended": appended,
        "pruned": pruned,
        "inbox_after": len(inbox),
        "curated_added_columns": curated_added_columns,
        "inbox_added_columns": inbox_added_columns,
    }
    return inbox, stats


def create_new_path(
    curated_csv: str | Path,
    target_root: str | Path | None = None,
    query: str | None = None,
    overwrite: bool = False,
    save_output: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Populate the ``new Path`` column in a curated registry.

    Parameters
    ----------
    curated_csv
        Path to the curated registry CSV.
    target_root
        Target root directory for the restructured tree. This value is not
        embedded into ``new Path``; it is kept for symmetry and downstream use.
    query
        Optional pandas query string to restrict which rows are processed.
    overwrite
        If True, overwrite non-empty ``new Path`` values.
    save_output
        If provided, write the updated curated registry to this path.

    Returns
    -------
    tuple
        ``(curated_df, stats)``.
    """
    curated_path = Path(curated_csv)
    target = Path(target_root) if target_root is not None else None
    out_path = Path(save_output) if save_output is not None else None

    df, stats = _create_new_path(
        curated_csv=curated_path,
        target_root=target,
        query=query,
        overwrite=overwrite,
        save_output=out_path,
    )
    return df, stats


def verify(
    curated_csv: str | Path,
    source_root: str | Path,
    target_root: str | Path,
    query: str | None = None,
    create_target_dirs: bool = False,
    save_output: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Verify existence of source and target paths for curated entries.

    Parameters
    ----------
    curated_csv
        Path to the curated registry CSV.
    source_root
        Root directory that contains the existing source files.
    target_root
        Root directory for the restructured target tree.
    query
        Optional pandas query string to restrict which rows are processed.
    create_target_dirs
        If True, create parent directories for targets.
    save_output
        If provided, write the verification report to this path.

    Returns
    -------
    tuple
        ``(report_df, stats)``.
    """
    report, stats = _verify(
        curated_csv=Path(curated_csv),
        source_root=Path(source_root),
        target_root=Path(target_root),
        query=query,
        create_target_dirs=create_target_dirs,
        save_output=Path(save_output) if save_output is not None else None,
    )
    return report, stats


def restructure(
    curated_csv: str | Path,
    source_root: str | Path,
    target_root: str | Path,
    query: str | None = None,
    overwrite: bool = False,
    create_target_dirs: bool = True,
    save_report: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Copy files from ``source_root/Path`` to ``target_root/new Path``.

    Parameters
    ----------
    curated_csv
        Path to the curated registry CSV.
    source_root
        Root directory that contains the existing source files.
    target_root
        Root directory for the restructured target tree.
    query
        Optional pandas query string to restrict which rows are processed.
    overwrite
        If True, overwrite existing target files.
    create_target_dirs
        If True, create parent directories for targets.
    save_report
        If provided, write a per-row action report to this path.

    Returns
    -------
    tuple
        ``(report_df, stats)``.
    """
    report, stats = _restructure(
        curated_csv=Path(curated_csv),
        source_root=Path(source_root),
        target_root=Path(target_root),
        query=query,
        overwrite=overwrite,
        create_target_dirs=create_target_dirs,
        save_report=Path(save_report) if save_report is not None else None,
    )
    return report, stats
