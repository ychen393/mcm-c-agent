# MCM C Agent — Evaluation Set v0.1 Plan

Status: Approved plan; dataset authoring starts before M1/M2 agent implementation.
Date: 2026-11-04

## Purpose
Create a stable evaluation baseline before adding complex agents. Measure evidence grounding, mathematical soundness, reproducibility and compliance—not fluency alone.

## Dataset partitions
- Dev: used for prompt, schema and workflow iteration.
- Holdout: sealed during development; used for milestone acceptance. Any holdout item used for tuning must be retired and replaced.
- Regression: confirmed failure cases, rerun on every relevant code/prompt change.

## Initial scope
| Suite | Minimum v0.1 size | Coverage |
|---|---:|---|
| Historical Problem C tasks | 3 problem statements | distinct years/topics; decomposition and research planning |
| Task-level cases | 15 | decomposition, data understanding, EDA, retrieval, method selection, debate, validation, paper outline |
| Deterministic data fixtures | 5 | missingness, outliers, time trend, categorical data, joins |
| Citation verification cases | 10 | valid, incomplete, dead/unverifiable and conflicting sources |
| Workflow recovery cases | 3 | process restart, model timeout, tool failure |

## Case schema
Each case contains case_id, suite, split, task_type, difficulty, input prompt/files and immutable hashes, reference answer/checklist, scoring rubric, prohibited critical errors, expected output schema, source provenance/license metadata, reviewer notes and adjudicated score.

## Rubric (0–4 per dimension)
1. Task coverage
2. Evidence grounding
3. Mathematical soundness
4. Reproducibility
5. Communication
6. Competition compliance

0 means absent/incorrect; 1 major deficiencies; 2 partial; 3 good with minor issues; 4 complete and well-supported. Critical errors are reported separately and cannot be averaged away.

## Evaluation protocol
- Run deterministic tests first, then model-assisted scoring.
- Blind human review at least 20% of model-scored cases; all suspected critical math/citation/compliance errors receive human review.
- Report per-dimension scores, critical-error count, failure examples, latency/cost where applicable, and model/prompt version.
- Do not use a single LLM-as-judge aggregate as the sole acceptance signal.
- Compare Debate on/off with identical cases and comparable model budget; report verified issue discovery, false positives, score delta and added cost/time.

## Initial acceptance targets
- Structured output schema validity: >=98% on task-level suite; 100% on deterministic contract tests.
- Fabricated citation count: 0 in citation verification suite.
- Deterministic EDA fixtures: 100% of specified golden statistics within declared tolerance.
- Checkpoint recovery suite: 3/3 scenarios recover from last durable checkpoint; duplicate side effects: 0.
- Human review coverage: >=20% of model-scored cases.
- Critical errors: zero unflagged critical errors in holdout report.

Targets are milestone gates, not claims about current performance. Baseline scores must be measured before tuning.
