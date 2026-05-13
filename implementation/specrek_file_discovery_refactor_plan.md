# SpecReK File-Discovery Refactor Roadmap

## Summary

Refactor the package in small validation-backed phases. Public orchestrator APIs in `file_discovery.__init__` stay unchanged; helper loaders switch to `(df, added_columns)`.

Current inspection confirms the main issues still exist: duplicated `ALL_INBOX_COLS`, duplicated `_apply_query()`, duplicated path validators, `df.attrs["added_columns"]`, hardcoded `sep=";"`, `restructure.py` `"nan"/"<na>"` guards, `stats.__dict__`, duplicated position parsing, no null-byte path validation, and no root containment after resolving. Baseline `python3 -m compileall src/file_discovery` passes; `python3 -m pytest -q` cannot run because `pytest` is not installed.

## Implementation Changes By Phase

- **Phase 0:** Save this plan markdown under `implementation/`, record `git status`, rerun the grep inventory, and treat current parsing behavior as the baseline source of truth.
- **Phase 1 `config.py`:** Add `Final` annotations, define `ALL_INBOX_COLS`, convert extension/config sets to immutable types where behavior is unchanged, add parser-domain constants, add the OPUS numeric-extension comment, keep `EH`, `ID_REGEX`, and `ALLOW_NUMERIC_EXTENSIONS` behavior unchanged.
- **Phase 2 Shared Helpers:** Put dataframe/query helpers in `io_utils.py`; create `path_utils.py` for `validate_relative_posix_path()` and `resolve_under_root()`.
- **Phase 3 `io_utils.py`:** Make `ensure_columns()` return a copy, document `normalize_strings()` as in-place, add `is_blank_series()` and `apply_query()`, use `CSV_SEP`, remove `df.attrs`, return `(df, added_columns)` from loaders, and make `write_csv()` require an existing parent directory.
- **Phase 4 `path_utils.py`:** Validate null bytes, absolute paths, and `..`; resolve paths under roots and reject symlink/root escapes with clear `ValueError`s.
- **Phase 5 `parsing_util.py`:** Extract parser literals to config constants, add `resolve_position()` plus compatibility wrappers, simplify consumed-token logic, keep `parse_measured_material()` fallback and `tokenize()` runtime guard/current token filtering unchanged.
- **Phase 6 `detection_utils.py`:** Import `ALL_INBOX_COLS`, keep `ID_RE` local, preserve explicit Case-1 blank workflow fields, keep Case-2 mapping explicit, and assert/reindex final inbox schema.
- **Phase 7 `compute_new_path.py`:** Use shared query/blank helpers, unpack loader tuples, use bool dtype for `should_write`, check duplicate `new Path` values against the full candidate output, return `asdict(stats)`, and document selected-row date parsing errors.
- **Phase 8 `verify_paths.py`:** Use shared query and path utilities, keep `exists()` report semantics and current status priority, use resolved root containment, and return `asdict(stats)`.
- **Phase 9 `restructure.py`:** Use shared query/path utilities, normalize selected path columns before looping, remove `"nan"/"<na>"` guards, keep `src.is_file()`, preserve report columns/actions, and return `asdict(stats)`.
- **Phase 10 `purging_utils.py`:** Raise `KeyError` for missing merge columns, make `conflicts` fallback explicit, keep numeric `nm` comparison unchanged.
- **Phase 11 `api.py`:** Import `ALL_INBOX_COLS` and `CSV_SEP`, unpack loader tuples, remove attrs access, replace hardcoded separators, and verify every write path has parent validation before `write_csv()`.
- **Phase 12 `validate.py`:** Keep `csv.reader` and `CSV_SEP`; add null-byte header rejection after stripping header names.
- **Phase 13 Final Checks:** Run compile/checks after major groups and final grep sanity checks; run tests if `pytest` is available, otherwise report the missing dependency.

## Interfaces And Compatibility

- Public functions `discover()`, `create_new_path()`, `verify()`, and `restructure()` keep their signatures and return shapes.
- `io_utils.load_csv_or_empty()`, `load_curated()`, and `load_inbox()` return `(DataFrame, list[str])`; all internal and test call sites will be updated.
- New public helper module: `file_discovery.path_utils`.
- `write_csv()` no longer creates parent directories; API validators enforce output-parent existence.

## Test Plan

- Update existing tests for loader tuple returns and add focused tests for pure `ensure_columns()`, null-byte CSV headers, candidate duplicate `new Path`, malformed selected dates, and selected missing-date counts.
- Add path-safety tests for absolute paths, `..`, null bytes, and symlink escapes in verify/restructure.
- Add restructure tests for duplicate selected targets, missing source skip, and directory source not copied.
- Add parsing regression tests for FSU026, MKY-LF, split MKY/LF, PL/default Raman, liquid, Pellet/P-position, numeric OPUS extensions, and current `tokenize()` behavior.
- Final commands: try `python -m compileall src/file_discovery`; if `python` is absent, run `python3 -m compileall src/file_discovery` and report both. Run `python3 -m pytest -q` if available. Run the requested grep checks and explain remaining hits.

## Assumptions And Deliberate Skips

- Leave `ID_REGEX` anchored.
- Leave `ALLOW_NUMERIC_EXTENSIONS` behavior unchanged.
- Leave `parse_measured_material()` fallback unchanged.
- Leave `tokenize()` runtime type guard and current empty-token filtering unchanged.
- Do not rewrite `build_case2_rows()` generically unless exact output equivalence is proven.
- Do not change numeric `nm` conflict comparison.
- Do not change verify `exists()` to `is_file()`.
- Do not globally replace defensive local `.astype("string")` calls.
- Excel/SYLK validation will be reported as CLI encoding/BOM verification unless GUI access is explicitly allowed.
