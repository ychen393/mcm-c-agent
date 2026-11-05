# MCM C Agent — Next Execution Queue

**Checkpoint:** `mcm-c-2026-11-05-phase-b-live-planner`  
**Status:** Paused at Phase B handoff; multi-agent CLI implementation has **not started**.

| Priority | ID | Task | Acceptance / evidence | Owner gate | State |
| --- | --- | --- | --- | --- | --- |
| P0 | MCM-STATE-01 | Preserve runtime checkpoint in GitHub + Google Docs | Links work, SHA recorded, contains no secrets | None for documentation | Completed; GitHub + Google Docs verified |
| P0 | MCM-B-ACCEPT-01 | Verify approved AI 3-chart execution | Three rendered images OR explain missing; record actual plan approval and exports | Owner approves chart proposal | Not verified |
| P0 | MCM-B-ACCEPT-02 | Verify exported Markdown/JSON, provenance, labels and units | Concrete files/screenshots; pytest & CI link | User final acceptance | Pending |
| P1 | MCM-RESEARCH-01 | Scope generic Feature Engineering & advanced chart capability | Proposal with formulas, data handling, tests, costs and constraints | Owner approval for research semantics | Not started |
| P1 | MCM-AGENT-01 | Review multi-agent governance PR #3 | Risk tiers, scope, no auto-merge; accepted/rejected changes | Owner | Draft review pending |
| P1 | MCM-AGENT-02 | Design and implement local Python CLI orchestrator V1 | Cursor/Claude CLI capability checks, safe dry-run, bounded loops, isolated branches, tests | Owner approval for installation / login / paid credentials | Blocked until snapshot + connection |
| P2 | MCM-AGENT-03 | First safe builder → reviewer → CI pilot | One Draft PR, objective tests, reviewer findings, no main merge | Owner final decision | Pilot #6: Cursor code + Draft PR #7 + isolated CI passed; independent review pending |
| P1 | MCM-AGENT-04 | Add PR-native CI for cursor/** targets | Separate CI workflow change and exact PR-attached green checks | Owner reviews workflow change | Not started; isolated CI run #42008138145 passed |
| P1 | MCM-AGENT-05 | Establish genuinely independent read-only Reviewer | Distinct session/tool permissions + verifiable review record | Owner approves permissions/costs | Blocked; current Cloud Task has no readonly setting |
| P2 | MCM-PHASE-C-01 | Build Insight Analyst + Reviewer | Evidence-grounded findings, limits, cross-check tests | Scope approved later | Not started |

## The next single executable step

**Resume Phase B at the Human Approval gate for the already-produced AI three-chart plan**. It has been proposed and user-shared; execution and exports are not yet evidenced. Check for a surviving pending plan in Streamlit and approve only if the user accepts it.

If the user wants to prioritize multi-agent CLI setup immediately after the status snapshot, work from Issue #4 and PR #3, **without** assuming Phase B has been fully closed. Keep Phase B acceptance open as a separately tracked task.

## Collaboration checkpoint — 2026-11-05

- GitHub Issue #6 directly dispatched Cursor Cloud via `@cursor` (bot acknowledgment verified).
- Cursor wrote tests on `test/6-api-settings-regression`; coordinator opened [Draft PR #7](https://github.com/ychen393/mcm-c-agent/pull/7) and recorded a non-approving code review.
- [Isolated GitHub Actions CI](https://github.com/ychen393/mcm-c-agent/actions/runs/42008138145) passed `pytest -q` with 80 progress dots; this test run is on a validation branch with matching code, **not attached to Draft PR #7**.
- Reviewer gate not satisfied. No merge or deployment. The next collaboration technical step is PR-native CI trigger configuration and an independent read-only review mechanism.
