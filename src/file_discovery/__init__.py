"""SpecReK file discovery and restructuring package."""

from .api import create_new_path, discover, restructure, verify

__all__ = (
    "discover",
    "create_new_path",
    "verify",
    "restructure",
)
