# Phase B — Visual EDA Agent

Status: **B0 approved by the user; B1 planner service implemented with automated tests in CI.** B2–B4 remain in progress.

## Product goal

Move from deterministic chart templates to problem-aware chart selection. Given an MCM Problem C statement and the Phase A dataset profile, the Visual EDA Planner proposes a concise, ranked set of charts that answer meaningful analytical questions.

The system remains semi-autonomous: the agent proposes; a human reviews and approves; deterministic Python validates and executes.

## Architecture

```text
Problem Statement + Dataset
             |
             v
     Phase A EDA Profiler
             |
             v
    Visual EDA Planner (LLM)
             |
             v
     Typed ChartPlan / ChartSpec
             |
             v
     ChartPlan Validator
             |
       Human Approval
             |
             v
      Python Chart Executor
             |
             v
      EDA Report + Provenance
```

Phase B ends after chart planning, validation, approval and execution. Evidence-grounded Insight Analyst and EDA Reviewer remain Phase C.

## Non-negotiable boundaries

- LLM selects and explains charts; Python computes all numeric metrics and renders figures.
- No LLM-authored Python, SQL, shell commands, or executable expressions.
- The planner may reference only exact columns present in the dataset profile.
- Supported chart types are limited to the current executor catalog: histogram, time_series, bar, scatter, box_plot.
- Units are copied only from user-provided dataset metadata; never inferred from column names.
- The planner must avoid redundant/unsuitable charts and explain meaningful omissions.
- A human approval action is required before executing an AI-proposed plan.
- Missing problem statement, provider failure, invalid model output or validator failure must fall back to deterministic generic EDA, clearly labeled as not problem-aware.
- Preserve source SHA-256, source columns, plotted row count, ChartSpec and computed metrics.

## B0 — Contracts and prompt foundation

- [x] Extend ChartSpec with rank, relevance_score and analytical_role.
- [x] Extend ChartPlan with planning summary, problem alignment and planner/fallback provenance.
- [x] Forbid unknown fields in ChartSpec and ChartPlan.
- [x] Validate unique, ascending chart ranks.
- [x] Update deterministic fallback plans with unique ranks and explicit generic fallback metadata.
- [x] Add versioned Visual EDA Planner system prompt.
- [x] Add unit tests for ranking, relevance score, provenance and strict schema.
- [x] User approved chart ranking, mandatory human approval and deterministic fallback (2026-11-05).

## B1 — Visual EDA Planner

- [x] Implement `agents/visual_eda_agent.py` using the existing `LLMFactory` / `BaseLLM` Multi-LLM adapter.
- [x] Supply problem statement, compact dataset metadata, column profiles, warnings and correlations; do not send full raw dataset rows.
- [x] Parse JSON output into ChartPlan; support one bounded repair attempt for malformed/schema-invalid output.
- [x] Attach provider, model and prompt version to plan provenance.
- [x] Validate against the real DataFrame and declared units before accepting the plan.
- [x] Add mocked-LLM tests for success, malformed output, one repair, invalid columns, provider failure and fallback; no live API credentials required.

## B2 — Selection quality and fallback

- [x] Require explicit ranks beginning at 1 and 0–1 relevance scores; preserve ascending order.
- [x] Reject unknown columns, unsupported types, invalid axes, inadequate sample sizes, invalid units and duplicate chart IDs/labels/ranks.
- [x] Add redundancy checks for repeated analytical intent and duplicate time-series/scatter field pairs.
- [x] Keep deterministic fallback when no problem statement or LLM is unavailable.
- [x] Record fallback reason and never label generic fallback as problem-aware.

## B3 — Streamlit human-review workflow

- [x] Use the MCM problem statement / research-question field in the Dataset Explorer.
- [x] Add explicit AI planner opt-in toggle and show configured provider/model.
- [x] Generate and display a ranked chart-plan preview before chart execution.
- [x] Show chart type, source columns, analytical role, relevance score, question, rationale, priority and caveats.
- [x] Show skipped chart ideas and why they were omitted.
- [x] Require explicit user approval before Python execution; artifact persistence is also blocked without approval when a plan is supplied.
- [x] Preserve deterministic fallback and report the selected planning strategy.

## B4 — Evaluation and acceptance

- [x] Add six chart-planning evaluation cases covering trend, distribution, relationship, categorical counts, insufficient time coverage and missing-context fallback.
- [ ] Measure problem relevance, field correctness, chart suitability, nonredundancy, omission rationale, schema validity and fallback behavior.
- [x] Add automated checks for exact source columns, declared units, chart types, sample sufficiency, duplicate intent and zero fabricated numeric claims in the planner contract.
- [ ] Test missing API key, timeout, malformed JSON, invalid column, duplicate chart and empty plan.
- [ ] Verify chart output provenance and report downloads.
- [ ] Run full pytest and GitHub Actions.
- [ ] User reviews the live Streamlit workflow before Phase B is closed.

## Acceptance criteria

1. With a problem statement and available LLM, the planner returns a schema-valid, ranked plan grounded in the dataset profile.
2. Every chart references existing columns and an executor-supported chart type.
3. The plan explains why each selected chart is useful and why important alternatives were omitted.
4. Duplicate or unsuitable chart plans are rejected before execution.
5. The user can inspect the full plan and must explicitly approve it before figures are generated.
6. LLM/provider failure or missing problem statement results in a clearly labeled deterministic fallback, not a broken workflow.
7. All generated metrics are computed by Python from the actual plotted observations and include dataset SHA-256 provenance.
8. Unit tests cover success and failure paths without live LLM credentials.

## B0 review checklist

- [ ] ChartSpec rank and relevance_score are clear and useful.
- [ ] ChartPlan metadata is sufficient to explain the plan and record provider/fallback status.
- [ ] Prompt boundaries prohibit arbitrary code and unsupported chart types.
- [ ] Human approval is retained as a mandatory execution gate.


## B1 implementation notes — 2026-11-05

- Added `agents/visual_eda_agent.py` with `plan_visual_eda()`.
- The planner uses the existing `LLMFactory` / `BaseLLM` adapter and supports dependency injection for deterministic tests.
- The LLM receives the problem statement, a compact profile derived from EDAReport, and the ChartPlan JSON Schema; it does not receive the full DataFrame or raw CSV/XLSX rows.
- Model output is parsed into ChartPlan and validated against the actual DataFrame and declared column units.
- A single bounded repair attempt is made for malformed JSON or schema/data validation errors.
- Missing problem statement, context preparation failure, provider initialization/invocation failure, or a second invalid response returns a deterministic generic fallback with a recorded reason.
- Added `planner_prompt_version` provenance.
- Strengthened ChartSpec axis-shape constraints and validator checks for time-series valid pairs, categorical bar axes, numeric axes, sample sufficiency and explicitly declared units.
- Added `tests/unit/test_visual_eda_agent.py` for successful planning, context minimization, missing prompt, bounded repair, invalid-column fallback, provider timeout and invalid unit/type cases.

Important integration boundary: B1 provides a tested planner service only. It is intentionally not wired into the current Streamlit EDA execution path yet, because that path auto-executes deterministic charts. B3 must add the user-visible plan preview and explicit approval gate before AI plans can reach the executor. No live API call or UI acceptance is claimed by B1.


## B2/B3/B4 implementation notes — 2026-11-05

- B2: ranking and relevance fields are required (not silently defaulted); validator enforces contiguous ranks, supported chart shapes, numeric/categorical axes, minimum valid observations, explicitly declared units, unique IDs/labels and duplicate analytical-intent / field-pair rejection.
- B3: Streamlit now uses a two-step workflow: Generate chart plan → inspect ranked plan → Approve plan & generate charts. AI planning is opt-in; the UI warns that the problem statement and compact profile are sent to the configured provider, while raw dataset rows are not sent.
- B3: a pending plan is invalidated if the dataset hash, problem statement, project ID, source/frequency/units, AI toggle or configured provider/model changes. User approval is required before chart rendering and artifact persistence.
- B3: EDA JSON/Markdown reports include planning strategy, provider/model, ranking/relevance metadata and approval provenance.
- B4: added six original synthetic chart-planning cases with fixture SHA-256 references and human scoring rubrics. CI validates case schema and fixture hashes. No live model benchmark scores are claimed.
- Remaining acceptance: latest full CI must pass; user must run the Streamlit app locally, inspect the plan/approval flow and confirm the configured provider/key before Phase B can be closed.
