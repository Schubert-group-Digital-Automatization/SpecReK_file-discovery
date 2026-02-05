"""Configuration for the file-discovery package."""

# Prefixes to find the Material Type Token
KNOWN_PREFIXES = ("FSU", "UBT", "TC", "BASF")

# For validation to check if cuarted cvs exists and is valid
CURATED_REQUIRED_COLS = {"Path", "Current Filename", "ID"}
CREATE_NEW_PATH_REQUIRED_COLS = {"ID", "Path", "Date"}
VERIFY_REQUIRED_COLS = {"ID", "Path", "new Path"}
RESTRUCTURE_REQUIRED_COLS = {"ID", "Path", "new Path"}
INBOX_REQUIRED_COLS = {"Path"}

CSV_SEP = ";"

# Tokens to exclude from the derived Comments field
COMMENT_EXCLUSION_TOKENS = frozenset(
    {
        "PL", 
        "liquid", 
        "MKY", 
        "MKY-LF", 
        "LF"
    }
)

ALLOWED_EXTENSIONS = {".spc", ".jdx", ".jcamp"}
ALLOW_NUMERIC_EXTENSIONS = True

# Format of accepted IDs
ID_REGEX = r"^SPR_AP\d+_\d+$"

DATE_TOKEN_REGEXES = (
    r"^\d{2}-\d{2}-\d{2}(\d{2})?$",
    r"^\d{4}_\d{2}_\d{2}$",
)

DATE_FORMATS = (
    "%d-%m-%Y",
    "%d-%m-%y",
    "%Y_%m_%d",
)

# Default vlaue if no Wavelength is detected either in filename or path.
DEFAULT_NM = 532.0

REGISTRY_COLS = (
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

INBOX_EXTRA_COLS = ("discovery", "conflicts")

PRUNE_EXCLUDE_COLS = frozenset(
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
