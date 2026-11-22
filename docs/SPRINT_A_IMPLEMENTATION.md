# Sprint A — Research Decision Alignment

Status: **Draft only**, based on feature/ux-guided-research-workflow-20261116.
No merge, deployment, live paid LLM or third-party billable workflows.

## Implementation

1. **Evidence** — agents/research_evidence.py constructs compact, fingerprinted
individual and joint gold/BTC metrics; no raw price rows are transmitted.
Inconsistent bundle and source SHA values fail closed.
2. **Contracts** — schemas/research_plan_v2.py adds optional typed execution
plans, one main research direction and up to two alternatives. Old project
records continue to deserialize as legacy research proposals.
3. **Research decision** — agents/research_decision.py classifies prerequisite,
baseline, strategy and validation. A main and two alternative different-family
strategies receive concrete signals, timing, fees, baseline and test plans.
Historic candidate provenance is retained in developer details.
4. **Agent collaboration** — agents/structured_research_team.py makes two
strictly opt-in calls: a typed Strategist amendment and an independent
Critic reviewing the actual revised proposal. Wrong IDs, unknown evidence
refs, implementation claims and invalid JSON are rejected before persistence.
Mock providers are used for all tests.
5. **Human revisions** — agents/research_revision.py requires any V2 H1
feedback to modify real execution-plan fields, not only narrative.
6. **H1 identity** — tools/research_persistence.py binds Critic and approval
to an exact saved proposal ID/hash; rejects stale versions and unresolved
blocking findings. The UI explicitly submits the draft before human H1.
7. **Model readiness** — modeling/preflight.py, agents/modeling_experiment.py
and app/modeling_panel.py forbid an unimplemented or differently mapped V2
strategy from being silently substituted and executed.

## Boundaries and compatibility

- Sprint A is not a new trading strategy or revised historical backtest.
- V2 strategies intentionally have implementation_status=needs_implementation.
  Sprint B must fix signal timing, executability, exact mapping and baselines.
- Formal V2 is created with source-matched separate AND joint EDA. Missing
  joint evidence retains the old plan as legacy, rather than inventing stats.
- API calls are possible in the UI only following an explicit opt-in. We have
  not enabled or run a paid model during this development.
- Legacy persistence and existing human H1/H2/H3 gates remain available.
  No automatic approval, merge, main write or deployment.

## Acceptance / regression

In a clean isolated worktree of this Sprint A branch run:

~~~powershell
python -m pytest -q tests/unit/test_research_plan_v2.py tests/unit/test_structured_research_team.py
python -m pytest -q tests/unit/test_sprint_a_user_journey.py
python -m pytest -q
python -m streamlit run app/main.py --server.port 8502
~~~

Check:

- EDA fingerprints and both original source hashes prevent stale reuse.
- Research shortlist is one main plus at most two alternatives; other
  prerequisites, baselines and validation methods are separate.
- Each model has data, signal, time convention, execution, commissions,
  parameters, risk limits and validation plans.
- Mocked Strategist updates the official typed proposal and a second mock
  independently challenges its actual revised fields.
- Model-invalid IDs, invented data or dishonest implementation status fail.
- Critic findings have field, severity, suggested action and provenance.
- H1 approval rejects a different or unsaved proposal version, old Critic,
  unresolved blocking errors or an invalid selected method.
- Multi-round human feedback creates new versions and preserves history.
- H1 research approval does not bypass the V2 execution-preflight blocker.
- Automatic tests must use Mock providers; no paid LLM or cloud agent calls.

Final browser acceptance is separate from CI. Keep the PR Draft.
