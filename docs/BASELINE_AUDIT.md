# Phase 0 — Product Baseline Audit

**Audit date:** 2026-11-12  
**Auditor role:** Builder (Phase 0 only)  
**Repo:** `ychen393/mcm-c-agent`  
**Binding product baseline:** PRD v1.2 (Approved Baseline)  
**Roadmap:** End-to-End Implementation Roadmap v2.0 — Phase 0 only  
**Constraint:** Do **not** merge to `main`. Do **not** deploy. Do **not** change secrets/billing.

## Verdict

**Primary product baseline = verified Draft PR #25 chain tip.**

| Item | Value |
| --- | --- |
| Unified baseline branch | `cursor/phase0-unified-baseline-ad8e` |
| **Fixed baseline SHA** | `20c827ba3ffe9b638e209f54743e2cc42d4ee1ad` |
| Product code tip (pre–Phase 0 docs) | `37dbabcfc8778ed512a4607dbf860db71c7d342f` (`cursor/slice3-safe-join-preview-a465`) |
| Competing fork (not adopted) | Draft PR #24 / `feature/mvp-relationship-20261109` @ `4cab04db2f69e0edc622a3c5f7c32636c4e1c692` |
| Frozen `main` (unchanged) | `c6fbb597f719ebe515bfe1720d511498505040af` |

Phase 0 adds audit/dependency/research-preservation docs on top of the #25 tip. It does **not** rewrite product code from #14/#22/#25 and does **not** merge #24.

## Open Draft PR audit (product path)

| PR | Title | Head → Base | CI (last known) | Role |
| --- | --- | --- | --- | --- |
| [#1](https://github.com/ychen393/mcm-c-agent/pull/1) | M1-A Data-to-EDA | `feature/m1a-data-eda` → `main` | SUCCESS | Foundation |
| [#2](https://github.com/ychen393/mcm-c-agent/pull/2) | M1-B Visual EDA | `feature/m1b-visual-eda` → `feature/m1a-data-eda` | SUCCESS | Visual planner + API Settings |
| [#14](https://github.com/ychen393/mcm-c-agent/pull/14) | Slice 1 multi-dataset registry | `feature/11-dataset-bundle` → `feature/m1b-visual-eda` | SUCCESS | Offline 1–5 file bundle |
| [#22](https://github.com/ychen393/mcm-c-agent/pull/22) | Slice 2 multi-file UI | `cursor/multi-upload-independent-eda-d360` → `feature/11-dataset-bundle` | SUCCESS | Independent EDA UI |
| [#25](https://github.com/ychen393/mcm-c-agent/pull/25) | Slice 3 safe join preview | `cursor/slice3-safe-join-preview-a465` → `cursor/multi-upload-independent-eda-d360` | SUCCESS | **Selected tip** |
| [#24](https://github.com/ychen393/mcm-c-agent/pull/24) | MVP relationship / join | `feature/mvp-relationship-20261109` → `feature/11-dataset-bundle` | SUCCESS | **Competing duplicate** of Slice 2+3 |

Ancestry check (2026-11-12):

- `#25` contains `#22` and `#14` (ancestor of tip).
- `#24` also contains `#22` / `#14` (same merge-base with `#25`: `cc9f0a448599ed5772b7bc8562f6695bade6323f`).
- `#24` and `#25` diverge after that SHA with **parallel join implementations**, not a linear stack.

## Explicit choice: #25 chain vs #24

**Choice: keep #25 product chain; do not merge #24 into the baseline.**

| Criterion | #25 chain | #24 |
| --- | --- | --- |
| Stack position | Correct stacked base: `#22` → `#25` | Rebases Slice-3 work onto `#14`/`#22` lineage as a **side branch** with duplicate UI/join code |
| Contracts | Typed Pydantic models in `schemas/relationships.py` | Dataclass dicts in `tools/dataset_relationships.py` |
| Modules | `tools/relationship_profiler.py`, `app/relationship_panel.py` | `tools/dataset_relationships.py`, inlined UI in `app/main.py` |
| Safety bounds | Preview ≤100 rows; refuse >5k rows / 60 cols; unit + frequency mismatch blocks | Preview ≤50 rows; refuse >100k rows; coarser frequency guard |
| Tests | 13 profiler + dedicated preview-app tests; CI on `cursor/**` | 8 relationship tests + MVP workflow; also green |
| Size / maintainability | Larger, evidence-oriented API aligned with Slice 1–2 docs | Smaller MVP fork that would force a conflicted merge with `#25` |

**Rationale:** Owner Phase 0 guidance prefers the verified `#25` product chain. `#24` is a useful alternate experiment with overlapping intent, but naively merging it would duplicate core join/relationship logic and fight `#25`’s schema/panel split. Preserve `#24` SHA for archaeology; do not treat it as merge input for Phase 0.

Useful `#24`-only notes to revisit later (optional cherry-picks, not Phase 0):

- Real Streamlit multi-file smoke fixture (`0940cce` and follow-ups).
- Explicit numeric-key equality / mixed datetime rejection hardening (`a5d7b78`).

## Research-state inventory (branch-local)

| Artifact | Present on | Absent from product tip before Phase 0 |
| --- | --- | --- |
| `docs/RUN_STATE.md` | `docs/mcm-runtime-checkpoint` (PR [#5](https://github.com/ychen393/mcm-c-agent/pull/5)) only | `#25` tip, `#24`, `#14`, `#22`, `main` |
| `docs/NEXT_ACTIONS.md` | same | same |
| `docs/state/mcm_checkpoint.json` | same | same |
| `AGENTS.md`, `docs/AUTONOMY_POLICY.md`, `docs/PROJECT_STATUS.md` | Cursor-dev / governance branches (`feature/m1c-agent-governance` PR [#3](https://github.com/ychen393/mcm-c-agent/pull/3), cowork stack) | Product `#25` tip (intentionally separate) |

Phase 0 copies the PR `#5` research artifacts onto this baseline and freezes byte-identical backups under `docs/research-state/backup-2026-11-05/`. Restore instructions: `docs/research-state/RESTORE.md`.

## Product vs Cursor-development agents

Keep these lanes separate:

| Lane | What it is | Phase 0 treatment |
| --- | --- | --- |
| **Product research agents** | Streamlit Research Lab, EDA, Visual EDA planner, dataset bundle, join preview | Unified into this baseline tip |
| **Cursor development agents** | `AGENTS.md`, autonomy policy, reviewer/cowork Draft PRs `#3`, `#7`–`#10`, `#16`–`#21` | Documented in `docs/PR_DEPENDENCY_MAP.md` only; **not** merged into product code |

Do not conflate MCM research agent runtime with Cursor builder/reviewer orchestration docs.

## What Phase 0 does / does not change

**Does:**

- Freeze a testable tip that already includes M1-A → M1-B → Slice 1 → Slice 2 → Slice 3.
- Publish `docs/BASELINE_AUDIT.md`, `docs/PR_DEPENDENCY_MAP.md`, research backup + restore notes.
- Re-home PR `#5` research checkpoint files onto the product tip so they are no longer branch-orphaned.

**Does not:**

- Merge any Draft PR into `main`.
- Merge `#24` into `#25`.
- Start Phase 1 (Issue `#26` project init / persistence).
- Deploy, rotate secrets, or touch billing.

## Local verification expectations

From this baseline branch after install:

```bash
pytest -q
streamlit run app/main.py
```

Postgres via `docker compose up -d postgres` is optional for the current EDA unit suite; API keys remain session-scoped and must never be committed.

## Local regression evidence (Phase 0 Builder)

| Check | Result | Notes |
| --- | --- | --- |
| `python -m pip install -e ".[dev]"` | OK | Existing `.venv`, Python 3.12 in this VM (project requires ≥3.11; CI uses 3.11) |
| `pytest -q` | **120 passed**, exit 0 | Full suite on tip including Phase 0 docs commit |
| `import app.main` | OK | Streamlit module loads |
| `streamlit run app/main.py --server.port 8502 --server.headless true` | Booted (headless smoke) | No secrets used; interrupted after ready |

Record the final Phase 0 commit SHA in the Draft PR body after push (this file is committed with the same tip).
