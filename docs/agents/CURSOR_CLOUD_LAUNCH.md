# Cursor Cloud Project bootstrap — owner-authorized pilot

**Prepared 2026-11-06.** This is a TASK HANDOFF, not proof that a Cloud Agent has launched.
**Authorization context:** Owner explicitly authorized starting a Cursor Cloud Agent to integrate MCM development coordination with Cursor. This authorizes one scoped project-organization pilot, **not** recurring agent runs, new paid APIs, auto-merge, auto-deployment, unbounded retry, or billed usage beyond included Cursor Premium allowance. **Updated 2026-11-09:** Owner now authorizes up to **USD $50 cumulative additional billed MCM usage**, including Cloud Agents and Bugbot. The original $0 amount below is superseded. Auto Top-up is reported OFF, but that is not proof of a hard project cap. Before making billable calls, verify the effective account limit and remaining project budget; if unverifiable, BLOCKED_COST_GATE.

## Primary outcome

Use the existing Cursor Project **Cursor Subagent Workflow** and the GitHub repository `ychen393/mcm-c-agent`; make the Coordinator → scoped task → actual execution session → PR/CI → review → owner decision hierarchy legible in that Project. Reuse existing run history, do not create duplicate Project or unneeded agent sessions.

This task is about the **developer-side orchestration only**. Do not change the LangGraph math-research Agent runtime, research checkpoint, model evaluation, APIs, datasets, Phase B / Phase C or model outputs.

## Read first

- `AGENTS.md`
- `docs/AUTONOMY_POLICY.md`
- `docs/agents/AGENT_REGISTRY.md`
- `docs/agents/agent-registry.json`
- `docs/agents/task-registry.json`
- `docs/agents/COORDINATOR_RUNBOOK.md`
- Draft PR #20, stacked on PR #18 / #17; Issue #8 and PR #16

Note that PR #20 lives on `feature/agent-coordination-registry-v1` and is not merged. Select/fetch that branch before claiming the registry files are present.

## Work plan for the single Cloud session

1. **Environment & billing preflight (read only):** Report current repository/branch, exact SHA, visible Cursor Project ID or URL, current supported Cloud Task types, and settings/evidence showing the effective billing mode and remaining room in the cumulative USD $50 MCM budget. If the no-extra-spend guarantee cannot be verified, return `BLOCKED_COST_GATE` without launching child agents, retrying, editing or enabling Automation.
2. **Project discovery:** Identify the actual Cursor Project and available Project-native Coordinator/Task/Agent controls. If API or UI affordances are absent, report limitation; do not invent them, and do not launch workaround agents.
3. **Single-project structure:** Configure the Project to point at the development coordinator instructions and role/task registry if supported. Do not rename/reparent existing sessions unless the product explicitly supports and the owner has separately approved that change.
4. **Visible task mapping:** For confirmed existing sessions only, record which Issue, PR, role and branch they belong to. Unknown IDs must remain `null` or unverified. Do not create fake session links or pretend prompts are running Agents.
5. **Pilot demo:** Show one clearly traceable scoped task, existing Cloud run link, real PR and SHA, PR-native CI and owner gate. Prefer Issue #8 / PR #9 or Issue #15 / PR #16 rather than creating a new coding task. No requirement to start a second agent.
6. **Deliverable:** Provide a concise evidence table of supported and unsupported Cursor Project capabilities; exact Project and session URLs, if exposed; screenshots only if truly captured; and a proposed minimal next step for missing capabilities. Make code/document changes only on this isolated branch after confirming USD $50 cap and effective payment controls.
7. **Stop:** Do not merge PR #20 or other PRs; don't approve your own changes. Report `BLOCKED` if independent permission-isolated Reviewer is unavailable. Reviewer role files are instructions, not guaranteed Cloud Task types.

## Definition of done

- The owner can find a single Project and one task's **why / role / Cloud Session ID / Issue / PR / checks / next gate** without hunting through unrelated conversations.
- Any unsupported features are listed clearly and remain pending.
- No unauthorized charges, agent launches, auto-fixes or merges.
- Actual evidence URL or screenshot required for every statement claiming something was configured in Cursor.

## One-message launch prompt

Paste the following into a **new Cloud session inside the existing Cursor Project** (not a random repository session), after confirming the account won't incur extra billed usage:

```text
MCM Coordinator Pilot — single authorized Cloud session. Work in the existing Cursor Project "Cursor Subagent Workflow" and repo ychen393/mcm-c-agent on branch feature/agent-coordination-registry-v1. Read docs/agents/CURSOR_CLOUD_LAUNCH.md, AGENTS.md, docs/AUTONOMY_POLICY.md, and docs/agents/AGENT_REGISTRY.md first. Implement only the developer-side Coordinator / role / task / real-session traceability inside this existing Project as supported by Cursor. Show exactly where I can see each task and which agent executed it. Never invent missing project APIs or session links. Do not start child agents, paid models, automations or retries, change secrets/billing, merge, deploy or edit main. Additional billed MCM usage must remain within the cumulative $50 budget; auto top-up is reportedly off, not a guaranteed spending cap. If billing constraints are unverified, report BLOCKED_COST_GATE. Return actual Project link, actual session IDs, PR/CI evidence and outstanding limits.
```
