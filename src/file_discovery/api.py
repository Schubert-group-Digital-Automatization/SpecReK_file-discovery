"""Public API for measurement file discovery and restructuring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .compute_new_path import create_new_path as _create_new_path
from .config import (
    ALL_INBOX_COLS,
    CREATE_NEW_PATH_REQUIRED_COLS,
    CSV_SEP,
    CURATED_REQUIRED_COLS,
    RESTRUCTURE_REQUIRED_COLS,
    VERIFY_REQUIRED_COLS,
)
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
from .validate import (
    validate_csv_file,
    validate_csv_has_required_columns,
    validate_dir_exists,
    validate_output_parent_exists,
)

__all__ = (
    "discover",
    "create_new_path",
    "verify",
    "restructure",
)


def discover(
    base_dir_path: str | Path,
    curated_csv: str | Path,
    discovery_output_path: str | Path,
    decode_filename: bool = True,
    find_conflicts: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Discover measurement files and update the discovery-output CSV.

    Parameters
    ----------
    base_dir_path
        Base directory to scan recursively.
    curated_csv
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
    curated_path = Path(curated_csv)
    inbox_path = Path(discovery_output_path)

    # Validate inputs before any IO/parsing/scan logic.
    validate_dir_exists(base_dir, name="base_dir_path")
    validate_csv_file(curated_path, name="curated_csv")
    validate_csv_has_required_columns(
        curated_path,
        required=CURATED_REQUIRED_COLS,
        name="curated_csv",
        sep=CSV_SEP,
    )
    validate_output_parent_exists(inbox_path, name="discovery_output_path")

    curated, curated_added_columns = load_curated(curated_path)
    inbox, inbox_added_columns = load_inbox(inbox_path)

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
    inbox = inbox.reindex(columns=list(ALL_INBOX_COLS))

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
    query: str | None = None,
    overwrite: bool = False,
    save_output: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Populate the ``new Path`` column in a curated registry.

    Parameters
    ----------
    curated_csv
        Path to the curated registry CSV.
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
    out_path = Path(save_output) if save_output is not None else None

    # Validate inputs before any pandas work inside the implementation.
    validate_csv_file(curated_path, name="curated_csv")
    validate_csv_has_required_columns(
        curated_path,
        required=CREATE_NEW_PATH_REQUIRED_COLS,
        name="curated_csv",
        sep=CSV_SEP,
    )
    if out_path is not None:
        validate_output_parent_exists(out_path, name="save_output")

    df, stats = _create_new_path(
        curated_csv=curated_path,
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
    curated_path = Path(curated_csv)
    source = Path(source_root)
    target = Path(target_root)
    out_path = Path(save_output) if save_output is not None else None

    # Validate inputs before any pandas work inside the implementation.
    validate_dir_exists(source, name="source_root")
    validate_dir_exists(target, name="target_root")
    validate_csv_file(curated_path, name="curated_csv")
    validate_csv_has_required_columns(
        curated_path,
        required=VERIFY_REQUIRED_COLS,
        name="curated_csv",
        sep=CSV_SEP,
    )
    if out_path is not None:
        validate_output_parent_exists(out_path, name="save_output")

    report, stats = _verify(
        curated_csv=curated_path,
        source_root=source,
        target_root=target,
        query=query,
        create_target_dirs=create_target_dirs,
        save_output=out_path,
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
    curated_path = Path(curated_csv)
    source = Path(source_root)
    target = Path(target_root)
    report_path = Path(save_report) if save_report is not None else None

    # Validate inputs before any pandas/IO work inside the implementation.
    validate_dir_exists(source, name="source_root")
    validate_dir_exists(target, name="target_root")
    validate_csv_file(curated_path, name="curated_csv")
    validate_csv_has_required_columns(
        curated_path,
        required=RESTRUCTURE_REQUIRED_COLS,
        name="curated_csv",
        sep=CSV_SEP,
    )
    if report_path is not None:
        validate_output_parent_exists(report_path, name="save_report")

    report, stats = _restructure(
        curated_csv=curated_path,
        source_root=source,
        target_root=target,
        query=query,
        overwrite=overwrite,
        create_target_dirs=create_target_dirs,
        save_report=report_path,
    )
    return report, stats
