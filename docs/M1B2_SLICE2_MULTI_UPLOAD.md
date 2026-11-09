# M1-B.2 Slice 2 — Multi-file upload and independent EDA

Status: Streamlit intake on top of the Slice 1 registry. No join and no model call.

## What this slice does

- The Research Lab uploader accepts 1 to 5 CSV or XLSX files (`accept_multiple_files`).
- Every accepted selection is loaded with `build_dataset_bundle`, so the existing per-file 20 MiB limit, 50 MiB aggregate limit, row and column caps, and duplicate-content rejection still apply.
- Each file is shown with its stable dataset ID, display name, SHA-256, and qualified column names (`dataset_id.column_name`).
- Two or more files produce one independent EDA section each: row and column counts, missingness, numeric summaries, quality warnings, and optional source, unit, and frequency notes. Within-dataset correlations stay inside that file's section.
- A pending single-file chart plan is cleared when the uploaded bytes change, when the selection becomes more than one file, or when the API Settings revision changes (existing behavior).
- One file still uses the existing chart-plan, human-approval, and artifact path. The approval identity remains that file's SHA-256.

## What this slice does not do

- No automatic merge, concatenation, join, date alignment, or resampling.
- No chart that reads more than one dataset.
- No LLM call for a multi-file selection. The opt-in Visual EDA Planner remains available only for a single file.
- No multi-sheet workbook selection. One XLSX file is one dataset, and only the first worksheet is read.

Relationship suggestions and user-confirmed integration remain later slices of #11.
