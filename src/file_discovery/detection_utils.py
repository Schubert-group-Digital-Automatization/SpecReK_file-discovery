"""Discovery utilities.

This module scans a base directory for measurement files and classifies rows
into inbox categories.

The functions here do not assign IDs for old naming schemes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .config import ALL_INBOX_COLS, ID_REGEX, REGISTRY_COLS
from .io_utils import ensure_columns, normalize_strings
from .parsing_util import is_allowed_file, parse_file_row


ID_RE = re.compile(ID_REGEX)


def _collect_allowed_files(base_dir: Path) -> list[Path]:
    """Collect all allowed files under a base directory.

    Parameters
    ----------
    base_dir
        Base directory to scan recursively.

    Returns
    -------
    list[pathlib.Path]
        Allowed files sorted by their POSIX path.
    """
    accepted: list[Path] = []
    for path in base_dir.rglob("*"):
        if path.is_file() and is_allowed_file(path):
            accepted.append(path)

    accepted.sort(key=lambda p: p.as_posix())
    return accepted


def scan_base_dir(base_dir: Path) -> pd.DataFrame:
    """Scan a directory and parse all allowed files.

    Parameters
    ----------
    base_dir
        Base directory to scan recursively.

    Returns
    -------
    pandas.DataFrame
        Parsed rows for all discovered files, with at least ``REGISTRY_COLS``.
    """
    rows: list[dict[str, object]] = []
    for path in _collect_allowed_files(base_dir):
        rel_path = path.relative_to(base_dir).as_posix()
        rows.append(parse_file_row(rel_path, path.stem.strip()))

    return ensure_columns(pd.DataFrame(rows), REGISTRY_COLS)


def scan_base_dir_minimal(base_dir: Path) -> pd.DataFrame:
    """Scan a directory without decoding filenames.

    Parameters
    ----------
    base_dir
        Base directory to scan recursively.

    Returns
    -------
    pandas.DataFrame
        Discovered rows with only ``Path`` and ``Current Filename`` filled.
    """
    rows: list[dict[str, object]] = []
    for path in _collect_allowed_files(base_dir):
        rel_path = path.relative_to(base_dir).as_posix()
        rows.append({"Path": rel_path, "Current Filename": path.stem.strip()})

    return ensure_columns(pd.DataFrame(rows), REGISTRY_COLS)


def build_case2_rows(discovered: pd.DataFrame, curated: pd.DataFrame) -> pd.DataFrame:
    """Build inbox rows for ID-named files found on disk.

    Parameters
    ----------
    discovered
        Dataframe produced by :func:`scan_base_dir`.
    curated
        Curated registry dataframe.

    Returns
    -------
    pandas.DataFrame
        Inbox rows with the registry schema plus ``discovery`` and ``conflicts``.

    Notes
    -----
    Case (2) detects files whose stem matches the ID pattern (e.g. ``SPR_AP1_00001``)
    and whose ID exists in the curated registry, but the curated row is missing
    ``Path`` and/or ``Current Filename``.
    """
    is_id_named = discovered["Current Filename"].astype("string").str.fullmatch(ID_RE, na=False)
    candidates = discovered.loc[is_id_named].copy()
    if candidates.empty:
        return pd.DataFrame(columns=list(ALL_INBOX_COLS))

    candidates["ID_candidate"] = candidates["Current Filename"].astype("string")

    curated_norm = curated.copy()
    normalize_strings(curated_norm, ("ID", "Path", "Current Filename"))
    normalize_strings(candidates, ("ID_candidate", "Path", "Current Filename"))

    curated_ids = curated_norm["ID"].astype("string").str.strip()
    curated_ids = curated_ids[curated_ids.notna() & curated_ids.ne("")]
    duplicate_ids = curated_ids[curated_ids.duplicated(keep=False)]

    if not duplicate_ids.empty:
        examples = duplicate_ids.drop_duplicates().head(20).tolist()
        raise ValueError(f"Duplicate ID values in curated registry: {examples}")

    merged = candidates.merge(
        curated_norm,
        left_on="ID_candidate",
        right_on="ID",
        how="inner",
        suffixes=("_disc", "_cur"),
    )
    if merged.empty:
        return pd.DataFrame(columns=list(ALL_INBOX_COLS))

    missing_path = merged["Path_cur"].isna() | (merged["Path_cur"].astype("string").str.strip() == "")
    missing_name = merged["Current Filename_cur"].isna() | (
        merged["Current Filename_cur"].astype("string").str.strip() == ""
    )

    merged = merged.loc[missing_path | missing_name].copy()
    if merged.empty:
        return pd.DataFrame(columns=list(ALL_INBOX_COLS))

    # Keep this mapping explicit because discovered and curated sources differ.
    out = pd.DataFrame(
        {
            "ID": merged["ID_candidate"],
            "Path": merged["Path_disc"],
            "Current Filename": merged["Current Filename_disc"],
            "Measured Material": merged["Measured Material_cur"],
            "Sample Type": merged["Sample Type_cur"],
            "Technique": merged["Technique_cur"],
            "nm": merged["nm_cur"],
            "Date": merged["Date_cur"],
            "Position": merged["Position_cur"],
            "Location": merged["Location_cur"],
            "Operator": merged["Operator_cur"],
            "Device": merged["Device_cur"],
            "Project": merged["Project_cur"],
            "Workpackage": merged["Workpackage_cur"],
            "Comments": merged["Comments_cur"],
            "new Path": merged["new Path_cur"],
            "Calendar Week": merged["Calendar Week_cur"],
            "discovery": "id_file_found_registry_incomplete",
            "conflicts": pd.NA,
        }
    )

    out = ensure_columns(out, ALL_INBOX_COLS)
    return out.loc[:, list(ALL_INBOX_COLS)]


def build_case1_rows(discovered: pd.DataFrame, curated: pd.DataFrame) -> pd.DataFrame:
    """Build inbox rows for unregistered files (old naming scheme).

    Parameters
    ----------
    discovered
        Dataframe produced by :func:`scan_base_dir`.
    curated
        Curated registry dataframe.

    Returns
    -------
    pandas.DataFrame
        Inbox rows for allowed files not present in curated (by Path). The ID is
        left blank and metadata is populated from filename decoding.
    """
    curated_paths_series = curated["Path"].astype("string").str.strip()
    curated_paths_series = curated_paths_series[
        curated_paths_series.notna() & curated_paths_series.ne("")
    ]
    curated_paths = set(curated_paths_series)
    disc_paths = discovered["Path"].astype("string").str.strip()

    out = discovered.loc[~disc_paths.isin(curated_paths)].copy()
    # Case-1 rows are unregistered files; workflow fields are intentionally blank.
    out["ID"] = pd.NA
    out["Project"] = pd.NA
    out["Workpackage"] = pd.NA
    out["discovery"] = "old_unregistered"
    out["conflicts"] = pd.NA

    out = ensure_columns(out, ALL_INBOX_COLS)
    return out.loc[:, list(ALL_INBOX_COLS)]


def append_unique_by_path(inbox: pd.DataFrame, additions: pd.DataFrame) -> pd.DataFrame:
    """Append inbox rows if their paths are not already present.

    Parameters
    ----------
    inbox
        Existing inbox dataframe.
    additions
        Candidate rows to append.

    Returns
    -------
    pandas.DataFrame
        Combined inbox where newly added rows are unique by ``Path``.

    Notes
    -----
    This function is idempotent under repeated runs: passing the same additions
    again will not create duplicates.
    """
    if additions.empty:
        return inbox

    inbox_out = inbox.copy()
    additions_out = additions.copy()

    normalize_strings(inbox_out, ("Path",))
    normalize_strings(additions_out, ("Path",))

    inbox_paths = inbox_out["Path"].astype("string").str.strip()
    inbox_paths = inbox_paths[inbox_paths.notna() & inbox_paths.ne("")]
    additions_paths = additions_out["Path"].astype("string").str.strip()

    existing = set(inbox_paths)
    is_new = additions_paths.notna() & additions_paths.ne("") & ~additions_paths.isin(existing)

    return pd.concat([inbox_out, additions_out.loc[is_new].copy()], ignore_index=True)
