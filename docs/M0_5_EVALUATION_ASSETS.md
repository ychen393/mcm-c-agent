# M0.5 Evaluation Assets — Delivery Note

## Delivered in this slice
- JSON Schema for task-level evaluation records.
- 15 original synthetic task-level prompts partitioned into Dev (8), Holdout (4) and Regression (3).
- 10 citation-policy test records.
- 3 workflow recovery scenarios.
- 5 deterministic synthetic CSV fixtures (missingness, outliers, time trend, categorical values, and relational join inputs) plus golden statistics.
- Corpus Registry CSV template.
- 2027 COMAP compliance checklist template.

## Important limitations
- These are test specifications and synthetic fixtures, not benchmark scores.
- The Holdout split is logically labeled but not access-controlled in a public repository; replace cases if they are used for prompt tuning.
- Citation URLs using example.org/example.invalid are policy fixtures, not claimed live references.
- The competition checklist is a verification aid. Re-check the official rules and fill in the snapshot before contest use.
- No historical award paper full text is included. Rights review is required before any corpus ingestion.

## Next
Add automated schema/fixture validation tests, then start the first baseline run and record the results without tuning prompts.
