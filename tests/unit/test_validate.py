from __future__ import annotations

from pathlib import Path

import pytest

from file_discovery.validate import (
    validate_csv_file,
    validate_csv_has_required_columns,
    validate_dir_exists,
    validate_output_parent_exists,
)


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_validate_dir_exists_accepts_existing_directory(tmp_path: Path) -> None:
    validate_dir_exists(tmp_path, name="base_dir_path")


def test_validate_dir_exists_rejects_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match="base_dir_path") as excinfo:
        validate_dir_exists(missing, name="base_dir_path")

    assert str(missing.resolve()) in str(excinfo.value)


def test_validate_dir_exists_rejects_file_path(tmp_path: Path) -> None:
    file_path = write_text(tmp_path / "not_a_dir.txt", "x")

    with pytest.raises(NotADirectoryError, match="base_dir_path") as excinfo:
        validate_dir_exists(file_path, name="base_dir_path")

    assert str(file_path.resolve()) in str(excinfo.value)


def test_validate_csv_file_accepts_existing_nonempty_csv(tmp_path: Path) -> None:
    validate_csv_file(write_text(tmp_path / "registry.csv", "ID;Path\n"), name="curated_csv")


@pytest.mark.parametrize(
    ("path_factory", "expected_error", "expected_message"),
    [
        pytest.param(lambda tmp: tmp / "missing.csv", FileNotFoundError, "curated_csv", id="missing"),
        pytest.param(lambda tmp: tmp, IsADirectoryError, "curated_csv", id="directory"),
        pytest.param(lambda tmp: write_text(tmp / "registry.txt", "ID;Path\n"), ValueError, ".csv", id="suffix"),
        pytest.param(lambda tmp: write_text(tmp / "empty.csv", ""), ValueError, "empty", id="empty"),
    ],
)
def test_validate_csv_file_rejects_invalid_paths(
    tmp_path: Path,
    path_factory: object,
    expected_error: type[Exception],
    expected_message: str,
) -> None:
    path = path_factory(tmp_path)  # type: ignore[operator]

    with pytest.raises(expected_error, match=expected_message):
        validate_csv_file(path, name="curated_csv")


def test_validate_csv_has_required_columns_accepts_header_only_csv(tmp_path: Path) -> None:
    csv_path = write_text(tmp_path / "registry.csv", "ID;Path;Current Filename\n")

    validate_csv_has_required_columns(
        csv_path,
        required={"ID", "Path"},
        name="curated_csv",
        sep=";",
    )


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("\n", id="blank-line"),
        pytest.param("   \n", id="whitespace"),
        pytest.param(";;;\n", id="empty-columns"),
    ],
)
def test_validate_csv_has_required_columns_rejects_unparseable_headers(
    tmp_path: Path,
    content: str,
) -> None:
    csv_path = write_text(tmp_path / "bad_header.csv", content)

    with pytest.raises(ValueError, match="curated_csv"):
        validate_csv_has_required_columns(
            csv_path,
            required={"ID", "Path"},
            name="curated_csv",
            sep=";",
        )


@pytest.mark.parametrize(
    ("header", "required"),
    [
        pytest.param("ID;Path\n", {"ID", "Path", "Current Filename"}, id="missing-current-filename"),
        pytest.param("ID;Current Filename\n", {"ID", "Path"}, id="missing-path"),
        pytest.param("ID,Path,Current Filename\n", {"ID", "Path"}, id="wrong-separator"),
    ],
)
def test_validate_csv_has_required_columns_reports_missing_columns(
    tmp_path: Path,
    header: str,
    required: set[str],
) -> None:
    csv_path = write_text(tmp_path / "bad_schema.csv", header)

    with pytest.raises(ValueError, match="Required") as excinfo:
        validate_csv_has_required_columns(
            csv_path,
            required=required,
            name="curated_csv",
            sep=";",
        )

    message = str(excinfo.value)
    assert "Found" in message
    for column in sorted(required):
        assert column in message


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        pytest.param("ID;Bad\x00Column;Path\n", "null byte", id="null-byte"),
        pytest.param("ID;Path;Path\n", "duplicate", id="duplicate"),
    ],
)
def test_validate_csv_has_required_columns_rejects_invalid_header_columns(
    tmp_path: Path,
    header: str,
    expected: str,
) -> None:
    csv_path = write_text(tmp_path / "bad_header.csv", header)

    with pytest.raises(ValueError, match=expected):
        validate_csv_has_required_columns(
            csv_path,
            required={"ID", "Path"},
            name="curated_csv",
            sep=";",
        )


def test_validate_csv_has_required_columns_rejects_empty_separator(tmp_path: Path) -> None:
    csv_path = write_text(tmp_path / "registry.csv", "ID;Path\n")

    with pytest.raises(ValueError, match="separator"):
        validate_csv_has_required_columns(
            csv_path,
            required={"ID", "Path"},
            name="curated_csv",
            sep="",
        )


def test_validate_output_parent_exists_accepts_existing_parent(tmp_path: Path) -> None:
    out_path = tmp_path / "out" / "report.csv"
    out_path.parent.mkdir()

    validate_output_parent_exists(out_path, name="save_output")


def test_validate_output_parent_exists_rejects_missing_parent(tmp_path: Path) -> None:
    out_path = tmp_path / "missing_parent" / "report.csv"

    with pytest.raises(FileNotFoundError, match="save_output") as excinfo:
        validate_output_parent_exists(out_path, name="save_output")

    assert str(out_path.parent.resolve()) in str(excinfo.value)


def test_validate_output_parent_exists_rejects_parent_file(tmp_path: Path) -> None:
    parent_as_file = write_text(tmp_path / "parent_is_file", "x")

    with pytest.raises(NotADirectoryError, match="save_output") as excinfo:
        validate_output_parent_exists(parent_as_file / "report.csv", name="save_output")

    assert str(parent_as_file.resolve()) in str(excinfo.value)
