# M1-A Acceptance — Data-to-EDA Vertical Slice

Status: Implementation in review. Automated and local execution results must be recorded before Pass.

## Scope
- CSV and XLSX upload, maximum 20 MiB.
- Header validation, duplicate/blank header rejection, row/column limits.
- Dataset SHA-256 and immutable input copy.
- Column profiling: inferred dtype, missingness, unique count and sample values.
- Numeric statistics: mean, median, standard deviation, min, quartiles and max.
- IQR outlier flags (review signal only; no automatic row deletion).
- Duplicate row detection, categorical top values, numeric correlations.
- Date-like column inference and numeric time-trend charts.
- JSON + Markdown report and PNG distribution/trend charts.
- Streamlit upload, preview, EDA run and report download.

## Automated acceptance tests
- [ ] CSV load and SHA-256 generation.
- [ ] XLSX load using openpyxl.
- [ ] Reject unsupported extensions, empty files and files over 20 MiB.
- [ ] Reject duplicate and blank headers.
- [ ] Reject unreadable/invalid CSV content.
- [ ] Verify missingness, duplicate rows, numeric summary, IQR flags and correlations on fixed fixture.
- [ ] Infer a date column and record its date range.
- [ ] Save raw input, JSON report, Markdown report and chart files under project/hash directory.
- [ ] Verify report JSON includes generated chart references.
- [ ] Existing evaluation suite remains green.

## Manual acceptance
- [ ] Run Streamlit app locally.
- [ ] Upload evaluation/fixtures/eda/time_trend.csv.
- [ ] Confirm preview shows 10 rows and 2 columns.
- [ ] Run EDA and confirm summary, column profile and warnings render.
- [ ] Confirm distribution and temporal trend charts appear.
- [ ] Download and open JSON and Markdown reports.
- [ ] Confirm artifacts are saved under outputs/<project_id>/eda/<sha256-prefix>/.

## Known limitations in M1-A
- No LLM-generated narrative or causal interpretation.
- No automatic data cleaning or deletion.
- Date inference is limited to datetime-typed columns and column names containing date/time/timestamp.
- Correlation is descriptive, not causal.
- Large-scale profiling and multi-sheet workbook selection are not included in this first slice.
- No database artifact registry yet; artifacts are local filesystem outputs.

## Pass condition
All automated tests pass and all manual acceptance items are verified by the user. Until then, status remains In Review.
