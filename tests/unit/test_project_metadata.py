"""Unit tests for project metadata behavior."""

from __future__ import annotations

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_project_metadata() -> dict[str, object]:
    """Load project metadata."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]


def test_project_metadata_declares_apache_alpha_release() -> None:
    """Verify project metadata declares apache alpha release."""
    project = load_project_metadata()

    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE"]
    assert (PROJECT_ROOT / "LICENSE").is_file()


def test_project_classifiers_match_supported_metadata() -> None:
    """Verify project classifiers match supported metadata."""
    classifiers = set(load_project_metadata()["classifiers"])

    assert not any(classifier.startswith("License ::") for classifier in classifiers)
    assert {
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    } <= classifiers
