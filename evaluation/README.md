# Evaluation Assets

This directory contains versioned, provenance-aware evaluation data. It must not contain unlicensed contest papers or full copyrighted problem statements.

## Splits
- dev/: prompt and workflow iteration.
- holdout/: sealed milestone evaluation; do not use for tuning.
- regression/: confirmed failures retained for automated regression.

## Case format
Each JSONL row must validate against schemas/evaluation_case.schema.json. Inputs should be self-contained or reference a fixture by a repository-relative path and SHA-256. References are checklists/rubrics, not necessarily a single exact answer.

## Current v0.1
- 15 original task-level cases: 8 dev, 4 holdout, 3 regression.
- 5 deterministic synthetic CSV fixtures.
- 10 citation-policy test records in citation_cases.jsonl.
- 3 recovery scenarios in recovery_cases.json.

The initial cases are designed test specifications, not measured model results. Holdout cases are committed for reproducibility in this demo repository; restrict their use operationally and replace any item used for tuning.
