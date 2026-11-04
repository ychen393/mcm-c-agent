# Development Plan — PRD v1.1

## Delivery strategy
Build vertical slices that each run end-to-end. Do not implement disconnected agents before proving a thin user journey.

| Slice | Milestone | Scope | Release gate |
|---|---|---|---|
| VS-0 Foundation smoke | M0 | Create project → persist → reload → minimal graph → show status | clean setup and core tests pass |
| VS-1 Data-to-EDA | M1-A | Upload CSV/XLSX → validate → preview → profile → EDA → save report | AC-02/03 |
| VS-2 Knowledge-to-Evidence | M1-B | approved source → retrieve → evidence card → open source → cite summary | corpus/compliance gate + AC-04 |
| VS-3 Parallel research-to-decision | M2 | problem analysis → EDA + literature → synthesis → critic → H1 → resume | AC-05/06/07/11 |
| VS-4 Plan-to-validated model | M3 | approved plan → sandbox → baseline/candidate → validation → H2 | AC-08/09 |
| VS-5 Evidence-to-LaTeX | M4 | evidence map → outline → LaTeX/BibTeX → PDF → review → AI use report → H3 | AC-10/11 |
| VS-6 Historical end-to-end demo | M5 | full historical Problem C run | all P0 gates |

## Milestone tasks

### M0 — Foundation and reliability design
- [ ] Confirm scaffold and run M0 acceptance checklist locally.
- [ ] Add project/run/artifact identifiers and schema version conventions.
- [ ] Add evaluation case schema and deterministic fixtures.
- [ ] Complete ADR-001 spike for PostgreSQL checkpoint and sandbox.
- [ ] Document actual Windows + Docker Desktop/WSL2 setup.
- [ ] Do not mark live API/database/container tests as passed until executed.

### M0.5 — Evaluation and compliance foundation
- [ ] Build Dev/Holdout/Regression directory conventions and case schema.
- [ ] Create first 15 task-level cases, 5 data fixtures and 10 citation cases.
- [ ] Create corpus registry and source-use policy.
- [ ] Freeze a versioned 2027 competition checklist and re-check official rules before contest use.
- [ ] Record baseline evaluation report before prompt tuning.

### M1 — Data and knowledge vertical slices
- [ ] VS-1 Data-to-EDA.
- [ ] VS-2 Knowledge-to-Evidence, only after corpus release gate.
- [ ] Store artifact hashes, source metadata and provenance.

### M2 — Parallel research workflow
- [ ] Problem Analyst, EDA and Literature branches with typed contracts.
- [ ] Research Strategy and evidence-grounded Critic.
- [ ] PostgreSQL checkpoint persistence, interrupt/resume and idempotent side effects.
- [ ] H1 approval and run recovery UI.
- [ ] Compare Debate on/off using holdout protocol.

### M3 — Modeling and validation
- [ ] Method cards and task-to-method mapping.
- [ ] Baseline-first model selection.
- [ ] Isolated Python execution service.
- [ ] Validation, sensitivity and H2 approval.

### M4 — Paper generation
- [ ] Evidence-to-section mapping.
- [ ] LaTeX/BibTeX generation and build checks.
- [ ] Reviewer and AI Usage Ledger / Report on Use of AI.
- [ ] H3 approval and export.

### M5 — End-to-end demo
- [ ] Run one historical Problem C from intake to PDF.
- [ ] Publish benchmark report, known limitations and demo script.

## Definition of done for every slice
- User-visible path works from input to persisted output.
- Unit and integration tests cover success and failure paths.
- State, artifacts, sources and model/prompt versions are traceable.
- Recovery behavior is tested where the slice can be interrupted.
- Documentation and README distinguish implemented, tested and planned functionality.
