# Agents

Agent implementations are introduced incrementally as vertical slices with typed contracts and deterministic fallbacks.

## Phase B — Visual EDA Planner

- **Implementation:** `agents/visual_eda_agent.py` exposes `plan_visual_eda()`.
- **Inputs:** MCM problem statement, EDAReport profile, and actual DataFrame for deterministic validation.
- **LLM context:** problem statement, compact dataset metadata / column profiles / quality warnings / correlations, and ChartPlan JSON Schema. Raw dataset rows are not sent.
- **Output:** ranked Pydantic ChartPlan with analytical roles, relevance scores, rationale, skipped reasons, provider/model and prompt-version provenance.
- **Recovery:** one bounded repair attempt for malformed or invalid output; deterministic generic EDA fallback for missing problem statement, provider errors or repeated invalid output.
- **Safety:** the model proposes chart specifications only. It cannot provide executable code or calculate metrics. Python validates source columns, chart types, sample sufficiency and declared units.

The planner service is connected to the Streamlit Dataset Explorer through an explicit opt-in, ranked plan preview and mandatory approval gate. Mocked-LLM tests cover provider and validation failure paths.

## Phase 2 — Problem Analyst

- **Implementation:** `agents/problem_analyst.py` exposes `analyze_problem()`.
- **Contract:** `schemas/problem_specification.py` (`ProblemSpecification`) with official / inferred / unknown provenance.
- **Default path:** deterministic 2022 MCM C extractor (`tools/problem_spec_2022_c.py`) + fixture under `data/problem_fixtures/`.
- **Optional LLM:** `PROBLEM_ANALYST_USE_LLM` / `use_llm=True`; one structured repair; 2022 C falls back to deterministic on persistent invalid output.
- **UI:** Research Lab Problem Analyst panel shows validated JSON; does not start joint modeling.

## Phase 4 — Literature & Evidence

- **Implementation:** `agents/literature_evidence.py` exposes `gather_literature_evidence()`.
- **Contract:** `schemas/evidence.py` (`EvidenceCard`, `EvidenceGap`, `LiteratureEvidenceReport`).
- **Default path:** offline fixture corpus under `knowledge/fixture_corpus/` (synthetic CI stubs only).
- **Optional live retrieval:** `LITERATURE_LIVE_RETRIEVAL` / `use_live=True` — Phase 4 stub records unavailability and never invents sources.
- **UI:** Research Lab Literature & Evidence panel reviews cards/gaps and attaches sanitized `evidence_report` + `citations`.
- **Phase 5 stub:** `agents/research_strategy_stub.py` re-exports live `research_strategy_status` (`h1_auto_approve=false`).

## Phase 5 — Research Strategy / Debate → H1

- **Implementation:** `agents/research_strategy.py`, `agents/debate_critic.py`.
- **Contract:** `schemas/research.py` (`ResearchProposal`, `DebateCritique`, `H1Decision`, `ModelingGateStatus`).
- **Gate:** `modeling/gate.py` — modeling allowed only when human H1 is `approved` (never auto-approve).
- **UI:** Research Lab H1 panel synthesizes → critiques → human Approve / Request-revision.

## Phase 6 — Mathematical Modeling & Experiment

- **Implementation:** `agents/modeling_experiment.py` exposes `run_modeling_experiment()`.
- **Contract:** `schemas/experiment.py` (`ExperimentParams`, `ExperimentRun`, `ExperimentReport`, metrics/artifacts).
- **Default path:** `modeling/runner.py` deterministic backtest on synthetic fixture prices (`modeling/fixture_data.py`).
- **H1 enforcement:** refuses to run/persist unless `assert_modeling_allowed(state)` passes.
- **Optional sandbox:** `MODELING_ALLOW_SANDBOXED_PYTHON` / UI checkbox — Phase 6 stub does **not** execute arbitrary code.
- **UI:** Modeling & Experiment panel configures/runs deterministic path, shows metrics/artifacts, attaches via `tools/experiment_persistence.py`.

## Planned later agents

- Validation / sensitivity → H2 (Phase 7)
- Insight Analyst and EDA Reviewer (legacy Phase C naming)
- Paper Writer and Reviewer → H3

All agents must use versioned Pydantic contracts, record provider/model and prompt version where applicable, and preserve evidence provenance.
