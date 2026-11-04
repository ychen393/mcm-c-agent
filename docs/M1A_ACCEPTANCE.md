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


## M1-A Phase A — Chart Plan / Labels / Evidence Metadata (2026-11-04)
Status: Implemented on feature branch; awaiting full-project CI and manual review.

Scope:
- Typed ChartSpec and ChartPlan, with required title, figure label, axis labels, caption, analytical question and rationale.
- Deterministic fallback Chart Catalog (histogram, time series) to preserve existing M1-A outputs.
- ChartPlan Validator rejects missing columns, invalid numeric axes, duplicate IDs/labels and insufficient temporal data.
- Deterministic executor supports histogram, time series, bar, scatter and box plot using an approved ChartSpec; no LLM-generated arbitrary code.
- JSON/Markdown artifacts include chart plan, provenance, actual computed metrics and image paths.
- Streamlit renders each chart with its caption, figure label, analytical question and metrics; narrative insight is explicitly marked pending Phase C.

Phase A acceptance:
- [ ] ChartSpec rejects invalid or empty required labels.
- [ ] Validator rejects unknown fields and unsupported field/chart combinations.
- [ ] Duplicate chart IDs and labels are rejected.
- [ ] All generated figures save under dataset-hash-scoped output paths.
- [ ] Each chart result records source SHA-256, plotted rows, source columns and computed metrics.
- [ ] Fallback outputs preserve previous tests (two histograms for two numeric columns).
- [ ] Time series charts retain chronology and report actual first/last values.
- [ ] Full pytest suite and GitHub Actions complete.
- [ ] User reviews label/caption visibility in Streamlit and report downloads.

Limitations: This is Phase A (deterministic). The LLM chart planner (B), evidence-grounded Insight Analyst/Reviewer (C), and expanded presentation/quality evaluation (D) are not implemented. No chart-specific narrative inference is claimed.


## M1-A Phase A Revision — Presentation & Dataset Context (2026-11-04)
Status: Implemented on feature branch; automated CI pending final revision commit and user re-check.

Changes:
- Dataset context fields: optional source, user-declared frequency, estimated frequency, detected date range and column-unit mapping.
- Frequency estimation is explicitly labeled as an estimate and based on median gaps between unique dates; it must not be represented as confirmed source metadata.
- Unit mapping is user-provided in the format `column_name = unit`; unknown column names and malformed lines are rejected in the UI.
- Unit metadata is attached to column profiles and used in chart axis labels where applicable.
- Chart cards display visible Figure numbering, LaTeX figure label, caption, analytical question, axes, source columns and dataset hash.
- Key chart statistics are shown as metric cards; raw metrics JSON is moved into a technical-details expander.
- Markdown and JSON exports include data context, unit metadata, chart provenance and a clear Phase A statement that narrative Insights are not yet generated.

Revision acceptance checklist:
- [ ] User can optionally enter data source, frequency and per-column units.
- [ ] Date range is detected and displayed where a valid date column exists.
- [ ] Estimated frequency is explicitly identified as an estimate.
- [ ] Invalid unit mappings and unknown column names produce clear errors.
- [ ] Unit appears in column profile and relevant chart axis label.
- [ ] Figure number and LaTeX label are visible for every chart.
- [ ] Chart statistics are displayed as readable metric cards, with raw JSON collapsed.
- [ ] Markdown and JSON preserve source hash, chart ID, source columns and computed metrics.
- [ ] New tests for dataset context, frequency estimation, units, chart provenance and Markdown report pass.
- [ ] Full GitHub Actions test suite passes.
- [ ] User re-runs the app and confirms the revised UI.

Important: Source, frequency and units are not guessed from the data. Users may provide them; date range and approximate frequency are inferred from observed date values and labeled accordingly. Phase B/C remain separate milestones.
