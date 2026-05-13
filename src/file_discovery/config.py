"""Configuration for the file-discovery package."""

from __future__ import annotations

from typing import Final

# Prefixes used to identify material-type tokens
KNOWN_PREFIXES: Final[tuple[str, ...]] = ("FSU", "UBT", "TC", "BASF", "EH")

# Required columns for validating registry CSV files
CURATED_REQUIRED_COLS: Final[frozenset[str]] = frozenset({"Path", "Current Filename", "ID"})
CREATE_NEW_PATH_REQUIRED_COLS: Final[frozenset[str]] = frozenset({"ID", "Path", "Date"})
VERIFY_REQUIRED_COLS: Final[frozenset[str]] = frozenset({"ID", "Path", "new Path"})
RESTRUCTURE_REQUIRED_COLS: Final[frozenset[str]] = frozenset({"ID", "Path", "new Path"})
INBOX_REQUIRED_COLS: Final[frozenset[str]] = frozenset({"Path"})

CSV_SEP: Final[str] = ";"

CALIBRATION_MATERIAL: Final[str] = "FSU026"
OPERATOR_COMPOUND: Final[str] = "MKY-LF"
OPERATOR_SIMPLE: Final[str] = "MKY"
OPERATOR_MODIFIER: Final[str] = "LF"
TECHNIQUE_PL_TOKEN: Final[str] = "PL"
DEFAULT_TECHNIQUE: Final[str] = "Raman"
LIQUID_POSITION_TOKEN: Final[str] = "liquid"

# Tokens to exclude from the derived Comments field
COMMENT_EXCLUSION_TOKENS: Final[frozenset[str]] = frozenset(
    {
        TECHNIQUE_PL_TOKEN,
        LIQUID_POSITION_TOKEN,
        OPERATOR_SIMPLE,
        OPERATOR_COMPOUND,
        OPERATOR_MODIFIER,
    }
)

ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset({".spc", ".jdx", ".jcamp"})

# OPUS (Bruker) spectroscopy software can save spectra with purely numeric
# extensions such as .0, .1, .2. Set to True to include these files.
ALLOW_NUMERIC_EXTENSIONS: Final[bool] = True

# Format of accepted IDs. Anchors are intentionally kept for compatibility with
# possible external ``re.match`` callers, even though internal checks use fullmatch.
ID_REGEX: Final[str] = r"^SPR_AP\d+_\d+$"

DATE_TOKEN_REGEXES: Final[tuple[str, ...]] = (
    r"^\d{2}-\d{2}-\d{2}(\d{2})?$",
    r"^\d{4}_\d{2}_\d{2}$",
)

DATE_FORMATS: Final[tuple[str, ...]] = (
    "%d-%m-%Y",
    "%d-%m-%y",
    "%Y_%m_%d",
)

# Default Raman wavelength if no wavelength is detected in the filename or path.
DEFAULT_NM: Final[float] = 532.0

REGISTRY_COLS: Final[tuple[str, ...]] = (
    "ID",
    "Path",
    "Current Filename",
    "Measured Material",
    "Sample Type",
    "Technique",
    "nm",
    "Date",
    "Position",
    "Location",
    "Operator",
    "Device",
    "Project",
    "Workpackage",
    "Comments",
    "new Path",
    "Calendar Week",
)

INBOX_EXTRA_COLS: Final[tuple[str, ...]] = ("discovery", "conflicts")
ALL_INBOX_COLS: Final[tuple[str, ...]] = REGISTRY_COLS + INBOX_EXTRA_COLS

PRUNE_EXCLUDE_COLS: Final[frozenset[str]] = frozenset(
    {
        "Path",
        "Comments",
        "Device",
        "new Path",
        "Calendar Week",
        "ID",
        "Project",
        "Workpackage",
    }
)
