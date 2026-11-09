# M1-B.2 Slice 1 — Offline multi-dataset registry

Status: data-layer registry. Slice 2 adds the Streamlit uploader that calls this registry; see `docs/M1B2_SLICE2_MULTI_UPLOAD.md`. The contracts below still do not join files.

## What this slice does

- Accepts an ordered list of 1 to 5 CSV or XLSX uploads through `build_dataset_bundle`.
- Loads every file with the existing `load_dataset` checks: CSV/XLSX only, 20 MiB per file, 500,000 rows, 500 columns, and rejection of blank or duplicate headers.
- Assigns a stable dataset ID from the file name and the SHA-256 of the bytes. Reordering the same files does not change those IDs.
- Gives each file a display name. When two uploads share a file name and their bytes differ, the display name adds a short content hash so the names cannot collide.
- Qualifies every column as `dataset_id.column_name`. Profiles and in-memory frames keep the original column names. Same-named columns in two files stay distinct.
- Computes a bundle fingerprint from the ordered dataset IDs, content hashes, file metadata, and column names. The same ordered uploads always produce the same fingerprint. A different order produces a different fingerprint.
- Rejects an empty list, more than 5 files, two uploads with identical bytes, a combined payload over 50 MiB, and any file `load_dataset` rejects. Identical content is rejected rather than kept under a second alias, so each hash appears once.
- Maps each dataset ID to its own `EDAReport` with `build_bundle_profiles`. Every report uses the bundle project ID and that file's own metadata. A single upload produces the same report body as calling `build_eda_report` on that file alone.
- Profile contracts and `model_context()` omit the data frame and the raw file bytes.

## What this slice does not do

- No automatic merge, concatenation, or join.
- No date alignment, resampling, or shared-key inference.
- No chart that reads more than one dataset.
- No extra LLM call and no joint prompt.
- No multi-sheet workbook selection. One XLSX file is one dataset, and only the first worksheet is read.
- Streamlit multi-file upload is Slice 2. This module still does not join files.

Those behaviors are later slices of #11 and #12. This registry never silently joins files.

## Validation hardening (2026-11-05)

- File paths from Windows and POSIX uploads are reduced to base names; non-ASCII file names remain visible while internal dataset IDs use ASCII-only slugs plus SHA-256.
- Stream reads are bounded by remaining per-file and aggregate budgets; generators are capped before materialization.
- The PR test workflow now includes `feature/**` target branches. Push-event success and PR-event success are separately reported.
