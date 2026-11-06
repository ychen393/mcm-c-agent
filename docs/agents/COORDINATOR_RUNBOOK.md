# Coordinator operating procedure — MCM development

**Purpose:** one place to understand "why does this conversation exist?", "who owns it?", and "what happens next?" without pretending Cursor's current UI has a custom agent dashboard.

## Entry point and ownership

- Repository: `ychen393/mcm-c-agent`. Source of truth: actual issue/PR/commit/CI and current GitHub state.
- Existing Cursor Project: `Cursor Subagent Workflow` (user's UI). This repository **cannot** reconfigure or rename the Project, reparent historical sessions or prove that its built-in Coordinator is connected.
- Scope: development organization only. Product LangGraph Agents are a separate layer.
- Main Coordinator: scope work, select a role, track outstanding gates, and return a decision package to owner; it is not a paid background agent.
- Registry links: `docs/agents/agent-registry.json` / `docs/agents/task-registry.json`.

## One task = one traceable identity

Before work: create an Issue with objective, risk, acceptance checks and non-goals. Record:
`task_id, issue, parent, role, branch, base, session, pr, head_sha, CI run, review evidence, owner authorization, blockers, next_gate`.
Use `null` for unknown/absent fields. Never manufacture a Task ID, model identity, Cloud run or reviewer approval.

Lifecycle:
```text
PROPOSED → OWNER_SCOPE_APPROVED → READY_FOR_BUILDER
         → BUILDING → DRAFT_PR → AWAIT_CI
         → AWAIT_REVIEW → OWNER_DECISION
failure → NEEDS_FIX_AUTH → FIXING → AWAIT_CI (max two authorized fixes)
unsafe/cost/no isolated reviewer → BLOCKED
```
These are **process statuses**, not proof of an implemented orchestrator.

## Dispatch / handoff contract

1. Coordinator reads `AGENTS.md`, `docs/AUTONOMY_POLICY.md`, issue, branch and source of truth.
2. Choose one existing role from agent-registry.json and one owned branch. A role in `.cursor/agents` is just instructions until the runtime successfully calls it.
3. For any Cloud invocation, owner separately checks costs, included quota and approvals. No automatic dispatch. Never use an invalid custom Task type that the current Cursor runtime rejects.
4. Builder supplies exact task/session ID if available, branch, commit SHA, PR, test URL and known failures.
5. GitHub Actions runs PR CI and the read-only readiness report. The reporter's JSON is evidence, not approval and not automatically updated after its execution. Check newest PR HEAD before relying on it.
6. Independent reviewer must use separately verifiable read-only access; unavailable means `BLOCKED`. Bugbot findings are not the same as a permission-isolated reviewer or mathematical validation.
7. Coordinator decides whether to prepare a **fix proposal** (not execute) or an owner decision package. Fix invocations need fresh owner authorization, at most two within the event ledger. No auto-merge.
8. Update task inventory only with actually observed information and leave historical runs unchanged.

## Session naming conventions (future sessions only)

`MCM | ISSUE-<n> | <ROLE> | <objective> | <branch>`

Examples:
- `MCM | ISSUE-15 | BUILDER | fix review loop | feature/15-bounded-review-loop`
- `MCM | PR-16 | REVIEWER | exact SHA review | blocked-until-authorized`

A conversation title is **metadata**, not role proof. Store the actual Cloud session link/Task ID in the inventory after the run. Do not try to rename or move historical sessions without product support.

## Owner decision package

Include: role and actual runtime, scope, exact PR and HEAD, real tests/check IDs, reviewer identity and access evidence, changes requested, unresolved research/privacy/cost risks, specific decision and rollback. Never describe `AWAIT_INDEPENDENT_REVIEW` as PASS or an Actions read-only check as AI review.

## Integration order

1. Adopt this documentation via owner-reviewed Draft PR; maintain registry.
2. If Project UI supports it, select existing `Cursor Subagent Workflow` as the single home and reference the registry.
3. Verify actual supported Cloud Project task dispatch and task IDs in a separately owner-authorized zero-extra-cost pilot.
4. Only then consider an event-based, owner-gated orchestration. Until then, the record is a traceability layer, not a functioning autonomous dispatcher.

## Cost and research safeguards

Never create unapproved Cloud Agent calls, paid API, recurring automation, auto-fix, credential changes, deployment or `main` merge. Do not edit MCM Phase B checkpoint, chart execution, Phase C or research semantic decisions without approval.
