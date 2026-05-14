# SpecReK File Discovery

## 1. Introduction

`file_discovery` is a small utility package for keeping the SpecReK measurement registry consistent with the files stored in Nextcloud under `_Rohdaten_pre`. It scans a base directory for measurement files, compares the results with a curated registry CSV, and updates an inbox CSV for rows that still need manual review.

The package is intentionally conservative. Legacy filenames (for example `TC003_MKY-LF_P1S3_27-10-25_785nm.0`) are never automatically mapped to an ID. New or ambiguous files are written to the inbox for manual review.

After review, the curated registry can be used to compute a target layout (`new Path`), verify source and target locations on disk, and copy files into a restructured directory where filenames are based on the stable `ID` rather than legacy naming variations.

Public workflow functions: `discover`, `create_new_path`, `verify`, `restructure`.

Public CSV helpers: `read_curated_csv`, `read_inbox_csv`, `write_curated_csv`, `write_inbox_csv`, `validate_curated_csv`, `validate_inbox_csv`.

## 2. Installation

Python `>=3.11` is required.

```bash
python -m pip install git+https://github.com/Schubert-group-Digital-Automatization/SpecReK_file-discovery.git
```

For local development from a checkout, install the test and lint extras:

```bash
python -m pip install -e ".[test,lint]"
```

## 3. Basic workflow

Two semicolon-separated CSV files drive the workflow. `measured_files.csv` is the curated registry. `new_files.csv` is the discovery inbox updated by `discover`.

A typical workflow is to run discovery, review the inbox, move relevant rows into the curated registry, complete missing IDs and metadata, and then rerun discovery. When conflicts are enabled, rows remain in the inbox until the mismatch is resolved.

Once the registry has the required IDs, source paths, and dates, `create_new_path` can fill `new Path` for the target directory layout. `verify` can then check which source files exist and which target files are already present, optionally creating the target parent directories. Finally, `restructure` copies files from the source tree into the target tree using the `ID`-based filenames defined by `new Path`.

## 4. Usage

### 4.1. Discovery

Discovery scans a directory and writes the current inbox back to `discovery_output_path`.

```python
from file_discovery import discover

inbox, stats = discover(
    base_dir_path="./_Rohdaten_pre",
    curated_csv="./measured_files.csv",
    discovery_output_path="./new_files.csv",
    decode_filename=True,
    find_conflicts=True,
)
```

### 4.2. New Path computation

`create_new_path` computes `new Path` values in the curated registry and returns the updated dataframe plus statistics. It only writes to disk when `save_output` is provided. The computed layout is `YYYY/CW##/<ID><suffix>`.

```python
from file_discovery import create_new_path

curated_df, stats = create_new_path(
    curated_csv="./measured_files.csv",
    query='Technique == "Raman" and ID.notna()',
    overwrite=False,
    save_output="./measured_files.csv",
)
```

### 4.3. Verification

`verify` checks whether `source_root / Path` exists and whether `target_root / new Path` exists. With `create_target_dirs=True`, it creates only the required target parent directories. A report is written only when `save_output` is provided.

The report `status` is one of `ok`, `missing_path`, `missing_new_path`, `missing_source`, or `missing_target`.

```python
from file_discovery import verify

report, stats = verify(
    curated_csv="./measured_files.csv",
    source_root="./_Rohdaten_pre",
    target_root="./_Rohdaten_pre_restructured",
    create_target_dirs=True,
    save_output="./verify_report.csv",
)
```

### 4.4. Restructuring

`restructure` copies files from `source_root / Path` to `target_root / new Path`. With `overwrite=False`, repeated runs skip files that already exist at the target location. A report is written only when `save_report` is provided.

The report `action` is one of `copied`, `skipped_exists`, `skipped_missing_source`, `skipped_missing_path`, `skipped_missing_new_path`, or `error`.

```python
from file_discovery import restructure

report, stats = restructure(
    curated_csv="./measured_files.csv",
    source_root="./_Rohdaten_pre",
    target_root="./_Rohdaten_pre_restructured",
    overwrite=False,
    save_report="./restructure_report.csv",
)
```

### 4.5. Notebook and manual CSV editing

For Jupyter or manual pandas work, use the public CSV helpers instead of plain `pandas.read_csv` and `DataFrame.to_csv`. The helpers preserve the package CSV rules: semicolon separation, UTF-8 BOM output, stripped headers, stable schema columns, key-field normalization, and date validation.

```python
from file_discovery import read_inbox_csv, validate_inbox_csv, write_inbox_csv

inbox = read_inbox_csv("./new_files.csv")
# edit inbox in pandas/Jupyter
write_inbox_csv(inbox, "./new_files.csv")
validate_inbox_csv("./new_files.csv")
```

The same pattern is available for the curated registry via `read_curated_csv`, `write_curated_csv`, and `validate_curated_csv`.

## 5. Reference

### 5.1. Inputs and outputs

The workflow is driven by two semicolon-separated CSVs. `measured_files.csv` is the curated registry. `new_files.csv` is the discovery inbox.

Curated registry and inbox share the same base schema:

```text
ID;
Path;
Current Filename;
Measured Material;
Sample Type;
Technique;
nm;
Date;
Position;
Location;
Operator;
Device;
Project;
Workpackage;
Comments;
new Path;
Calendar Week;
```

`Path` is stored as a relative POSIX path from the scan root. `Current Filename` is the filename stem without extension.

With filename decoding enabled, filename tokens populate fields such as `Measured Material`, `Date`, `nm`, `Position`, `Operator`, `Technique`, `Sample Type`, and `Comments`.

`new Path` is a relative path that defines where the file should be placed under a separate `target_root`. The target root is not embedded in this column. In practice, `new Path` should be derived with `create_new_path`, not edited manually.

During verification and copying, `Path` and `new Path` are resolved under their roots. Absolute paths, `..` segments, and symlink escapes are rejected.

The inbox CSV (`new_files.csv`) adds two extra columns:

```text
discovery;
conflicts;
```

`discovery` records why the row was placed in the inbox. `conflicts` lists columns that disagree with curated entries for the same `Path`.

### 5.2. File selection

Discovery considers suffixes defined by `ALLOWED_EXTENSIONS` in `file_discovery/config.py` (typically `.spc`, `.jdx`, `.jcamp`). Numeric Bruker/OPUS-style extensions such as `.0`, `.1`, or `.2` are included when `ALLOW_NUMERIC_EXTENSIONS=True`.

### 5.3. Discovery behavior

Discovery scans `base_dir_path` recursively and classifies discovered files into three cases.

- **Case A** covers legacy or otherwise unregistered files. If a discovered `Path` is missing from `measured_files.csv`, an entry is appended to `new_files.csv`. The `ID` field is left blank. Metadata is derived from filename tokens when decoding is enabled, and `discovery` is set to `old_unregistered`.

- **Case B** covers ID-named files when the curated registry entry is incomplete. If a discovered file has a filename stem that matches the ID pattern (for example `SPR_AP1_01234.spc`), and that ID exists in the curated registry while the curated row is missing `Path` and/or `Current Filename`, an inbox entry is added. The inbox row uses the discovered `Path` and filename, while other metadata is taken from the curated row. `discovery` is set to `id_file_found_registry_incomplete`.

- **Case C** covers fully registered files. If the discovered `Path` exists in the curated registry, nothing is added.

### 5.4. Inbox purging and conflicts

The inbox is unique by `Path`, so rerunning discovery does not create duplicate entries. After scanning and appending new entries, `discover` purges inbox rows that are already covered by the curated registry, optionally with conflict checks.

- With `find_conflicts=False`, purging removes inbox rows whose `Path` exists in the curated registry.

- With `find_conflicts=True`, purging is conservative and removes an inbox row only if its `Path` exists in curated and the canonical metadata matches. The comparison intentionally ignores `Path`, `ID`, `Comments`, `Device`, `Project`, `Workpackage`, `new Path`, and `Calendar Week`.

With conflicts enabled, inbox rows can remain even if their `Path` exists in the curated registry. In such cases, `conflicts` lists the differing columns, for example `Date|Position|nm`.

### 5.5. Pitfalls and limitations

Date handling is deliberately strict. Filename parsing accepts `dd-mm-yyyy`, `dd-mm-yy`, and `yyyy_mm_dd`. Curated CSV date normalization accepts `dd.mm.yyyy` and `yyyy-mm-dd`. `create_new_path` normalizes selected parsed dates to `dd.mm.yyyy` in the returned dataframe.

Missing or unparsable dates prevent `new Path` generation because the target layout is based on year and ISO calendar week.

Operator tokenization depends on separators. `MKY-LF` is treated as one token, while `MKY_LF` splits into `MKY` and `LF`, which can shift meaning between `Operator` and `Comments`. The `MKY_LF` case is handled explicitly.

Restructuring requires `new Path`. If it is empty, the target location is undefined and the copy operation is skipped.

Duplicate curated paths, duplicate curated IDs for ID-named discovery, and duplicate selected `new Path` values raise errors in the relevant workflows. This prevents silent overwrites or ambiguous registry updates.

IDs are never inferred for legacy filenames. This avoids accidental misassignment when multiple files share similar token patterns.

### 5.6. Configuration

Most configuration lives in `file_discovery/config.py`, including allowed extensions, the ID regex, known prefixes, parsing defaults, schema columns, and tokens excluded from generated comments.
