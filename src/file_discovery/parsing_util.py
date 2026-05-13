"""Filename tokenizing and parsing utilities.

The functions in this module implement a conservative parser for measurement
filenames. The goal is to extract useful metadata without guessing identities
(IDs) for old naming schemes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .config import (
    ALLOWED_EXTENSIONS,
    ALLOW_NUMERIC_EXTENSIONS,
    COMMENT_EXCLUSION_TOKENS,
    DATE_FORMATS,
    DATE_TOKEN_REGEXES,
    DEFAULT_NM,
    KNOWN_PREFIXES,
)


RE_DATE_TOKENS = tuple(re.compile(pattern) for pattern in DATE_TOKEN_REGEXES)
RE_NM_TOKEN = re.compile(r"^(\d{3})nm$")
RE_POS = re.compile(r"^P\d+S\d+$")
RE_PELLET = re.compile(r"^Pellet(\d+)S(\d+)$")


def is_allowed_file(path: Path) -> bool:
    """Check whether a file should be considered for discovery.

    Parameters
    ----------
    path
        File path.

    Returns
    -------
    bool
        True if the file matches the allowed extension rules.
    """
    suffix = path.suffix.lower()
    if suffix in ALLOWED_EXTENSIONS:
        return True
    return bool(
        ALLOW_NUMERIC_EXTENSIONS
        and suffix.startswith(".")
        and suffix[1:].isdigit()
    )


def tokenize(current_filename: str) -> list[str]:
    """Split a filename stem into underscore-separated tokens.

    Parameters
    ----------
    current_filename
        Filename stem (without extension).

    Returns
    -------
    list of str
        Tokens obtained by splitting on ``_``.
    """
    if not isinstance(current_filename, str):
        return []
    return [token.strip() for token in current_filename.split("_") if token.strip()]


def parse_measured_material(tokens: list[str]) -> str | None:
    """Parse the measured-material token.

    Parameters
    ----------
    tokens
        Token list from the filename.

    Returns
    -------
    str or None
        First token starting with a known material prefix, otherwise the first
        token, or None if no tokens exist.
    """
    for token in tokens:
        if token.startswith(KNOWN_PREFIXES):
            return token
    return tokens[0] if tokens else None


def parse_sample_type(measured_material: str | None) -> str:
    """Parse sample type from measured material.

    Parameters
    ----------
    measured_material
        Measured material token.

    Returns
    -------
    str
        ``"calibration"`` for ``FSU026``, otherwise ``"analyte"``.
    """
    return "calibration" if measured_material == "FSU026" else "analyte"


def parse_operator(tokens: list[str]) -> str | None:
    """Parse operator token.

    Parameters
    ----------
    tokens
        Token list from the filename.

    Returns
    -------
    str or None
        ``"MKY-LF"`` if tokens contain ``MKY-LF`` or ``MKY`` and ``LF``.
        ``"MKY"`` if tokens contain ``MKY``. Otherwise None.
    """
    if "MKY-LF" in tokens or ("MKY" in tokens and "LF" in tokens):
        return "MKY-LF"
    if "MKY" in tokens:
        return "MKY"
    return None


def parse_technique(tokens: list[str]) -> str:
    """Parse technique.

    Parameters
    ----------
    tokens
        Token list from the filename.

    Returns
    -------
    str
        ``"PL"`` if token ``PL`` is present, otherwise ``"Raman"``.
    """
    return "PL" if "PL" in tokens else "Raman"


def parse_date_token(tokens: list[str]) -> str | None:
    """Find the first date-like token.

    Parameters
    ----------
    tokens
        Token list from the filename.

    Returns
    -------
    str or None
        The first token matching one of ``DATE_TOKEN_REGEXES``, otherwise None.
    """
    for token in tokens:
        if any(pattern.fullmatch(token) for pattern in RE_DATE_TOKENS):
            return token
    return None


def parse_date_and_cw(date_token: str | None) -> tuple[str | None, int | None]:
    """Parse date token and compute ISO calendar week.

    Parameters
    ----------
    date_token
        Date-like token (e.g. ``24-04-2025``).

    Returns
    -------
    tuple[str | None, int | None]
        ``(date_str, calendar_week)`` where ``date_str`` is formatted as
        ``dd.mm.yyyy``. Returns ``(None, None)`` if parsing fails.
    """
    if date_token is None:
        return None, None

    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(date_token, format=fmt, errors="coerce")
        if not pd.isna(parsed):
            return parsed.strftime("%d.%m.%Y"), int(parsed.isocalendar().week)

    return None, None


def parse_nm_token(tokens: list[str]) -> str | None:
    """Find the first wavelength token (e.g. ``785nm``).

    Parameters
    ----------
    tokens
        Token list from the filename.

    Returns
    -------
    str or None
        The first token matching ``NNNnm``, otherwise None.
    """
    for token in tokens:
        if RE_NM_TOKEN.fullmatch(token):
            return token
    return None


def parse_nm(nm_token: str | None, path_rel: str) -> float:
    """Parse wavelength in nm.

    Parameters
    ----------
    nm_token
        Token like ``785nm``.
    path_rel
        Relative path (POSIX) used for folder-based fallbacks.

    Returns
    -------
    float
        Wavelength in nm. Falls back to folder hints (``785nm``/``532nm``) and
        finally to ``DEFAULT_NM``.
    """
    if nm_token is not None:
        match = RE_NM_TOKEN.fullmatch(nm_token)
        if match:
            return float(match.group(1))

    wrapped = f"/{path_rel.strip('/')}/".lower()
    if "/785nm/" in wrapped:
        return 785.0
    if "/532nm/" in wrapped:
        return 532.0

    return float(DEFAULT_NM)


def parse_position(tokens: list[str]) -> str | None:
    """Parse position information.

    Parameters
    ----------
    tokens
        Token list from the filename.

    Returns
    -------
    str or None
        Pellet tokens like ``Pellet1S2`` are converted to ``P1S2``.
        Plain position tokens like ``P1S2`` are returned unchanged.
        If token ``liquid`` exists, returns ``"liquid"``. Otherwise None.
    """
    for token in tokens:
        match = RE_PELLET.fullmatch(token)
        if match:
            return f"P{match.group(1)}S{match.group(2)}"

    for token in tokens:
        if RE_POS.fullmatch(token):
            return token

    return "liquid" if "liquid" in tokens else None


def parse_position_token(tokens: list[str]) -> str | None:
    """Return the filename token that was consumed to produce ``Position``.

    This is used to prevent position tokens (e.g. ``Pellet1S2``) from leaking
    into ``Comments`` after they have been mapped to a canonical position like
    ``P1S2``.

    Parameters
    ----------
    tokens
        Token list from the filename.

    Returns
    -------
    str or None
        The raw token that encodes the position (e.g. ``Pellet1S2`` or ``P1S2``),
        or ``"liquid"`` if that keyword is present. Returns None if no position
        token exists.
    """
    for token in tokens:
        if RE_PELLET.fullmatch(token):
            return token

    for token in tokens:
        if RE_POS.fullmatch(token):
            return token

    return "liquid" if "liquid" in tokens else None


def build_comments(tokens: list[str], used_tokens: set[str]) -> str | None:
    """Build a comments field from unused tokens.

    Parameters
    ----------
    tokens
        Token list from the filename.
    used_tokens
        Tokens that are already represented by explicit columns.

    Returns
    -------
    str or None
        Remaining tokens joined by underscores, or None if nothing remains.
    """
    remaining = [
        t
        for t in tokens
        if t not in COMMENT_EXCLUSION_TOKENS and t not in used_tokens
    ]
    comment = "_".join(remaining)
    return comment if comment else None


def parse_file_row(path_rel: str, current_filename: str) -> dict[str, object]:
    """Parse a discovered file into one registry-style row.

    Parameters
    ----------
    path_rel
        Relative path (POSIX).
    current_filename
        Filename stem (without extension).

    Returns
    -------
    dict
        Row dictionary matching the registry schema. ``Device`` and ``new Path``
        are intentionally left as NA during discovery.
    """
    tokens = tokenize(current_filename)

    measured_material = parse_measured_material(tokens)
    sample_type = parse_sample_type(measured_material)
    technique = parse_technique(tokens)
    operator = parse_operator(tokens)

    date_token = parse_date_token(tokens)
    date_str, calendar_week = parse_date_and_cw(date_token)

    nm_token = parse_nm_token(tokens)
    nm_value = parse_nm(nm_token, path_rel)

    position = parse_position(tokens)
    position_token = parse_position_token(tokens)

    consumed: dict[str, set[str]] = {
        "Measured Material": set(),
        "Date": set(),
        "nm": set(),
        "Position": set(),
    }

    if measured_material is not None:
        consumed["Measured Material"].add(str(measured_material))

    if date_token is not None:
        consumed["Date"].add(str(date_token))

    if nm_token is not None:
        consumed["nm"].add(str(nm_token))

    if position_token is not None:
        consumed["Position"].add(str(position_token))

    if position is not None:
        consumed["Position"].add(str(position))

    used_tokens = {t for tokens_for_field in consumed.values() for t in tokens_for_field}
    comments = build_comments(tokens, used_tokens)

    return {
        "ID": pd.NA,
        "Path": path_rel,
        "Current Filename": current_filename,
        "Measured Material": measured_material if measured_material is not None else pd.NA,
        "Sample Type": sample_type,
        "Technique": technique,
        "nm": nm_value,
        "Date": date_str if date_str is not None else pd.NA,
        "Position": position if position is not None else pd.NA,
        "Location": pd.NA,
        "Operator": operator if operator is not None else pd.NA,
        "Device": pd.NA,
        "Project": pd.NA,
        "Workpackage": pd.NA,
        "Comments": comments if comments is not None else pd.NA,
        "new Path": pd.NA,
        "Calendar Week": calendar_week if calendar_week is not None else pd.NA,
    }
