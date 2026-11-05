# MCM C Agent — Runtime & Handoff Checkpoint

**Snapshot date:** 2026-11-05 (America/Los_Angeles calendar context; user session also occurred on 2026-11-05).  
**Checkpoint ID:** `mcm-c-2026-11-05-phase-b-live-planner`  
**Purpose:** Preserve the current *confirmed project state*, *current task* and *exact next actions* separately from the PRD and from multi-agent orchestration policy.

> **Important:** This is a point-in-time handoff, NOT a live process monitor. GitHub does not preserve a running Streamlit server, browser session, API key, in-memory pending ChartPlan or local dataset. The status below records verified code and user-reported observations only. NEVER store secrets or private raw datasets in this file.

## 1. Current operational checkpoint

| Item | State | Evidence / limitation |
| --- | --- | --- |
| Product | MCM Problem C Research Lab, Python + Streamlit + Pydantic + Multi-LLM + local artifacts | Repository and PRD |
| Active development baseline | `feature/m1b-visual-eda` at `31bfdb322a86d8f3efe2ea1eb93e4af5794b6efc` | GitHub branch checked 2026-11-05 |
| Stable `main` | `c6fbb597f719ebe515bfe1720d511498505040af` | GitHub; feature PRs remain unmerged |
| Local execution | User ran Streamlit locally on Windows, usually port `8502` | User screenshots, not a remotely managed process |
| LLM | DeepSeek / `deepseek-chat`, configured from in-app API Settings | User screenshot confirmed session config; subsequent AI Plan shows successful provider/model output |
| API credentials | **Session-only; not saved in GitHub or Google Docs** | May need re-entry after restart |
| Latest *confirmed* functional milestone | Real AI planning produced a three-chart proposal with ranked rationale and relevance | User pasted detailed output on 2026-11-05 |
| Latest chart plan | Time Series (98%), Histogram (90%), Box Plot (72%) for a gold-price dataset | User-reported model output; no independent evidence of approved chart execution |
| Chart-plan review / execution | **Human approval and subsequent PNG generation NOT confirmed for this specific 3-chart AI plan** | Must verify rather than assume |
| Visual EDA automated testing | Existing GitHub Actions passed earlier; exact latest targeted run for current baseline should be rechecked before a release claim | See PR #2 / Actions |
| Phase A | Functional; outstanding metadata / Markdown export manual checks | Draft PR #1 and `docs/M1A_ACCEPTANCE.md` |
| Phase B | B0 approved; B1/B2/B3 implemented and live planner response observed; B4 quality evaluation and final acceptance incomplete | Draft PR #2 and `docs/PHASE_B_PLAN.md` |
| Phase C | Not started | Insight Analyst/Reviewer remains proposed |
| Advanced financial EDA | Not implemented | Rolling volatility, returns, drawdown, moving averages require validated derived-feature support |
| Multi-agent CLI orchestration | **Not started** | Governance draft PR #3 exists; no Cursor/Claude/Grok CLI integration or autonomous runner connected |

## 2. What the user has already approved

- Phase B B0 decisions: rank charts by research relevance with 0–1 scores; require explicit human approval before executing AI-proposed charts; use a clearly labeled deterministic fallback on LLM failure.
- Build MCM C Agent as a **demo**, with **mixed** knowledge-base scope, **semi-autonomous** behavior, **LaTeX** paper output target and **Python** stack; local database and multi-provider LLM adapter.
- Current user direction: **freeze/document the MCM state first**; only after that work on CLI multi-agent orchestration. Minimize owner involvement except for consequential decisions.
- These approvals do **not** authorize merging feature PRs, exposing API Settings publicly, additional paid providers, cloud deployment, or autonomous destructive operations.

## 3. Current step (STOP POINT)

**Milestone:** Phase B final verification / handoff, before starting any Phase C work or multi-agent CLI implementation.

**Current research execution:** AI Visual EDA Planner successfully proposed three charts, but the screenshot/pasted output did not establish whether the user clicked `Approve plan & generate charts`, whether three chart files were produced, or whether the latest report exported accurately. This is the precise resumable checkpoint.

**Development activity:** Feature PRs #1 and #2 remain Draft. Multi-agent governance PR #3 was created separately and has CI success, but actual external CLI coordination is intentionally paused.

## 4. Next actions (in priority order)

1. **P0 — Preserve checkpoint:** retain this document and `docs/NEXT_ACTIONS.md`, plus the structured JSON snapshot. Google Docs contains a read-only-human-oriented mirror. No secrets or raw datasets.
2. **P0 — Confirm approved AI chart execution:** on the current `feature/m1b-visual-eda` local Streamlit app, review the 3-chart plan and use `Approve plan & generate charts` if the user agrees. Record actual PNG count, errors and export paths. If the earlier session was lost, recreate the chart plan from the same data.
3. **P0 — Phase B final acceptance:** verify Markdown/JSON exports, explicit approval provenance, three chart labels and units, fallback behavior, and note whether API connectivity succeeded. Run `pytest -q` and check exact GitHub Actions SHA. Collect review evidence; do not automatically close Phase B.
4. **P1 — Decide next research expansion:** scope cross-problem feature engineering / advanced EDA (returns, rolling measures, etc.) as a separate milestone, not as an unannounced Phase B bug fix.
5. **P1 — Resume multi-agent CLI work only after the state checkpoint is saved:** review the governance PR #3, then define a minimal local orchestrator for Cursor builder + Claude Code reviewer + pytest + Draft PR using a bounded pilot. Installation/authentication and paid use require user action.
6. **P2 — Later:** Phase C Insight Analyst/Reviewer, mathematical-modeling stages, literature/knowledge base and LaTeX writing pipeline after the relevant design gates.

## 5. Recovery instructions (Windows)

Project location reported in prior sessions: `C:\Users\yihan\Documents\mcm-c-agent` (verify locally; not confirmed as a path in this environment).

```powershell
cd C:\Users\yihan\Documents\mcm-c-agent
git fetch origin
git switch feature/m1b-visual-eda
git pull --ff-only origin feature/m1b-visual-eda
python -m pip install -e ".[dev]"
pytest -q
python -m streamlit run app/main.py --server.port 8502
```

Then open `http://localhost:8502` and use **API Settings** (re-enter key if session expired) → **Research Lab** → problem statement + gold-price CSV → enable **Use AI Visual EDA Planner** → **Generate chart plan** → review → **Approve plan & generate charts**.

**Do not copy API keys, local `.env` contents, private data rows, or saved Streamlit session files into GitHub/Docs.**

## 6. References and ownership

- Repo: https://github.com/ychen393/mcm-c-agent
- Phase A PR: https://github.com/ychen393/mcm-c-agent/pull/1
- Phase B PR: https://github.com/ychen393/mcm-c-agent/pull/2
- Multi-agent governance draft: https://github.com/ychen393/mcm-c-agent/pull/3
- CLI pilot Issue (blocked): https://github.com/ychen393/mcm-c-agent/issues/4
- Existing PRD: `docs/PRD.md`
- Phase B acceptance: `docs/PHASE_B_PLAN.md`
- Next steps: `docs/NEXT_ACTIONS.md`
- Machine-readable snapshot: `docs/state/mcm_checkpoint.json`
- Independent Google Docs mirror: https://docs.google.com/document/d/16zye72a1xP98hHKQpM6bm1GHvzInckVboni19n5_g_I/edit

**Update protocol:** On every completed milestone or meaningful status change, update this snapshot and `docs/state/mcm_checkpoint.json` in the same PR. Keep the explicit evidence/source links; distinguish “implemented”, “tested”, “user verified”, and “approved”. GitHub is authoritative for code / actual development progress; Google Docs is a human-readable mirror. No claim of continuous synchronization unless a separate workflow is installed.
