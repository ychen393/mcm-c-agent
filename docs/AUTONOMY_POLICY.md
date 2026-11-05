# Multi-Agent Development Autonomy Policy — v1

**Status:** Proposed governance baseline for owner approval via PR. No external coding agent is connected or authorized by this file alone.

## Principle
Automate routine engineering. Preserve owner control over project direction, irreversible changes, security and spending. Agent claims require independently inspectable evidence.

| Risk | Examples | Agent can do autonomously | Gate |
| --- | --- | --- | --- |
| L0 — documentation / low-risk | typo, comments, developer docs | Draft PR, tests | Reviewer; do not silently merge |
| L1 — reversible engineering | contained bug fix, tests, minor UI, nonbreaking refactor | Issue → own branch → implement → test → Draft PR | CI + independent review; merge only under explicitly enabled automation policy |
| L2 — product / research semantics | model-selection logic, feature engineering formulas, benchmark changes, evaluation thresholds, prompt changes affecting outputs | Design and implement behind feature flag, produce evidence | Owner approves scope and acceptance before merging into shared baseline |
| L3 — security / infrastructure | auth, secret handling, permission changes, database migration, deployment, data export, external tools or new providers | Design-only or Draft PR until approval | Explicit owner authorization before actions with external impact |
| L4 — irreversible or financial | deleting data, changing billing, paid recurring agents, public deployment, main branch merge, contest submission | No autonomous action | Explicit owner approval for the specific action |

## Default behavior
- **Can proceed without a meeting:** read code, propose issue scope, create an isolated branch, write code/tests/docs, run CI, open a Draft PR, request independent review and revise within scope.
- **Must stop and ask:** new paid tool/API, token budgets beyond an approved cap, public network exposure, sending private data to outside models, secrets changes, production changes, destructive operations, architecture pivot or changing competition assumptions, merge to `main`.
- **Important modeling decisions:** research question interpretation, statistical assumptions, calculation formulas, dataset provenance, contest compliance interpretation, scoring methodology and what evidence can enter the final paper are owner-review gates.
- **No self-approval:** A builder's passing tests cannot stand in for an independent review. Reviewer approval cannot override owner gate.
- **No looping indefinitely:** Maximum two autonomous code/review repair loops per Issue; if unresolved, mark blocked and escalate.
- **No auto-merge enabled in this PR.** Even L0/L1 PRs stay open until automation and protections are separately approved and configured.

## Quality gates
1. Issue includes acceptance tests, owner or coordinator, risk tier, and boundaries.
2. Implementation uses a task-specific branch and Draft PR.
3. CI runs; records the exact run link and result. All mandatory checks pass.
4. Independent reviewer leaves a review with findings and any residual uncertainty.
5. Functional changes have a local or automated demo where feasible; data/LLM pipeline changes include evaluation fixtures and provenance.
6. Gate decision is recorded; failed checks or missing reviewer keep the PR unmerged.

## Credentials, data and API costs
- No credentials in commits, PRs, logs, screenshots, or report artifacts.
- App-side session secrets remain local; agents must not capture or copy them.
- No new external model calls, recurring agents, or paid usage beyond separately authorized budgets.
- Synthetic fixtures preferred in tests; private user data requires explicit consent for each external provider.

## Incident/stop conditions
Stop automatic execution, mark the Issue blocked and notify owner if: secret exposure, destructive command request, unbounded API costs, failed rollback, unresolved math correctness, privacy breach, branch protection bypass, or disagreement over a research-critical assumption.

## Decision package (owner-facing)
Each important milestone should contain a concise description, diff/PR, test & evaluation evidence, screenshot/demo if relevant, reviewer findings, unresolved issues, cost/privacy impact, rollback, and one precise approval request.

## External agent onboarding (NOT DONE)
1. Owner connects Cursor's relevant GitHub/agent functionality and authorizes repository access.
2. Owner connects Claude Code GitHub integration/action with the minimum permissions required.
3. Configure least-privilege credentials, trigger rules, concurrency, budget and GitHub rulesets.
4. Run one reversible pilot issue and demonstrate builder → reviewer → CI → owner approval.
5. Only after this pilot may further automation and optional Grok QA be considered.
