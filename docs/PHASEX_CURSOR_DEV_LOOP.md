# Phase X — Cursor development agent closed loop

**Branch base:** Phase 9 Evaluator-PASS tip `cursor/phase9-e2e-2022-c-3472` @ `c6ba152` (Draft PR #42)  
**Constraint:** Draft PR only. Do **not** merge to `main`. Do **not** deploy.  
**Lane:** Cursor Cloud **development** Agents — **not** MCM product research Agents.

## Purpose

Document and machine-check the **Cursor Cloud development loop** used to ship roadmap phases safely:

```text
Coordinator → Builder → CI → Independent Evaluator
        → bounded fix (if P0/P1) → re-check
        → auto-advance next phase
```

Owner gates remain mandatory for **merge to `main`**, **deploy**, and product **H1 / H2 / H3**.

Related intent: Issue #8 / #15 style Builder–Reviewer / Cloud co-work orchestration. Project ops sources of truth live in the Project store (`workflows/phase-evaluator-gate.md`, `internal/evaluator-charter.md`, `preferences.md`). This repo mirrors durable invariants under `docs/phasex/` so CI stays offline-green.

## Lane separation (non-negotiable)

| Lane | Role | May change product research runtime? |
| --- | --- | --- |
| **Product research Agents** | Streamlit Research Lab, Problem Analyst, EDA, Literature, Modeling, Validation, Paper | Yes (Phases 0–9 product slices) |
| **Cursor development Agents** | Coordinator, Builder, Independent Evaluator, CI watchers | Docs / tests / governance for this loop only in Phase X; do **not** conflate with research Agents |

**Invariant PX-I4:** Research Agents ≠ Cursor-dev Agents. Never start Cloud development workers from product runtime (`app/`, `agents/`, Streamlit).

**Invariant PX-I5:** Never embed live Cursor Cloud credentials in product code, and never spawn external Cursor Cloud agents from product runtime.

## Closed loop (happy path)

1. **Coordinator** opens/resumes a Builder on the prior Evaluator-PASS tip (exact SHA). Prefer one code Builder at a time.
2. **Builder** implements the phase minimal safe slice on `cursor/<phase>-…`, opens a **Draft** PR stacked on the prior phase branch, runs offline tests, writes store handoff.
3. **CI** must be green (or Builder reports ready + CI pending is explicit). CI green ≠ phase acceptance.
4. **Independent Evaluator** (not the Builder; read-only) reviews feature completeness + bugs at an exact HEAD. Verdict: `PASS` | `PASS_WITH_NOTES` | `FAIL` with P0/P1/P2. Writes `internal/phaseN-independent-review.md` and comments on the PR.
5. On **P0/P1:** Builder does a **bounded** fix cycle; Evaluator re-checks only those items.
6. On **Evaluator PASS** (P0/P1 clear or owner-waived P1): Coordinator **auto-advances** the next phase Builder without a separate owner “accept” chat message, unless a preference / H-gate says otherwise.
7. Notify owner at: next phase started, Evaluator FAIL after fix budget, budget / H-gate blockers. Skip routine chatter.

## Owner gates (never auto)

| Gate | Auto? | Who |
| --- | --- | --- |
| Merge to `main` | **Never** | Owner explicit approval |
| Deploy | **Never** | Owner explicit approval |
| Product **H1** / **H2** / **H3** | **Never** auto-approved | Human in product UI (harness may use simulated-human doubles in tests only) |
| Evaluator PASS → next phase Builder | Allowed | Coordinator per preferences |
| Owner waive of a P1 | Allowed | Owner in chat |

**Invariant PX-I1:** No merge-to-main automation in CI or product/runtime helpers.  
**Invariant PX-I2:** H1 / H2 / H3 are never auto-approved in product paths.  
**Invariant PX-I6:** Owner still required for merge / deploy / H1–H3.

## Evaluator gate

In-repo mirror: [`docs/phasex/PHASE_EVALUATOR_GATE.md`](phasex/PHASE_EVALUATOR_GATE.md).  
Project store (ops): `workflows/phase-evaluator-gate.md` + `internal/evaluator-charter.md`.

**Invariant PX-I3:** Evaluator gate documentation exists in-repo and is referenced by this loop.

## Machine-checkable checklist

Stable IDs live in [`docs/phasex/invariants.json`](phasex/invariants.json). Pytest: `tests/unit/test_phasex_cursor_dev_loop.py`.

| ID | Statement |
| --- | --- |
| PX-I1 | No merge-to-main automation |
| PX-I2 | H1/H2/H3 not auto-approved in product paths |
| PX-I3 | Evaluator gate file exists (in-repo mirror) |
| PX-I4 | Research vs Cursor-dev separation stated |
| PX-I5 | No live Cursor Cloud credentials / agent spawn in product runtime |
| PX-I6 | Owner gates for merge / deploy / H1–H3 documented |

## Handoff templates (optional helpers)

CI-safe markdown templates (no network, no secrets):

- [`docs/phasex/templates/builder_handoff_pr_comment.md`](phasex/templates/builder_handoff_pr_comment.md)
- [`docs/phasex/templates/evaluator_verdict_pr_comment.md`](phasex/templates/evaluator_verdict_pr_comment.md)

Optional renderer: `python -m scripts.phasex.render_handoff_comment --template builder`.

## What Phase X does / does not

**Does:**

- Durable docs for the Cursor Cloud development loop.
- Machine-checkable invariant checklist + pytest.
- Optional handoff comment templates / offline renderer.
- Keep product research Agent behavior unchanged.

**Does not:**

- Merge the stacked product/dev PRs to `main`.
- Deploy.
- Auto-approve H1 / H2 / H3.
- Embed Cursor Cloud API credentials or start external agents from product runtime.
- Replace Project-store evaluator ops files (mirrors only).

## How to verify

```bash
pytest -q tests/unit/test_phasex_cursor_dev_loop.py
# or full suite
pytest -q
```

## Out of scope

- Changing research Agent behavior (Phases 0–9 product code)
- Merging the whole stack to `main`
- Deploying
- Live Cursor Cloud orchestration from this repository’s product path
