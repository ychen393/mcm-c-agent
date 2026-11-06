# Universal Reviewer V1 — manual-first, reusable cross-project review

**Status: CONFIGURATION ONLY / CLOUD RUNTIME UNVERIFIED.**

This change adds a reusable reviewer prompt and an MCM profile. No Cursor Cloud Agent, scheduled Automation, external reviewer identity, billing configuration, real review or GitHub check is created or authorized by these files.

## Components
- `.cursor/agents/universal-reviewer.md`: generic role prompt and reporting contract.
- `.cursor/review-profiles/mcm.md`: repo-specific math/statistics, evidence and MCM gates.
- Existing `.cursor/agents/reviewer.md` and `.cursor/agents/builder.md` are retained unchanged for backwards compatibility.
- GitHub CI and PR observation stay separate and cannot provide independent AI review.

## How to adopt in another repository
Copy the generic reviewer prompt and create a project-specific `.cursor/review-profiles/<project>.md`. Keep the output contract and separate access checks. Do not apply MCM-only statistical checks to unrelated projects. A shared prompt file is not a cross-repository permission grant or automatic cloud synchronization.

## Cloud onboarding — owner action, not performed here
1. In Cursor's Cloud Agents UI, choose the repo and inspect supported agent roles/commands in the *actual* session. Verify the universal reviewer file is visible in that environment. A repo file is NOT proof that `subagent_type=universal-reviewer` works.
2. Use a separate reviewer session/principal only after the owner explicitly authorizes *that invocation* and confirms that it fits the included plan with **zero extra billed usage**. Auto Top-up OFF is not a verified hard spending cap. No Automation trigger yet.
3. Give reviewer an exact repository, PR, HEAD SHA, issue, scope and profile; enforce read-only GitHub credentials at tool/account level (e.g., `contents:read`, `pull-requests:read`, `actions:read`) AND verify the cloud runtime cannot bypass those permissions using another write-capable connector. If not provable, mark independent isolation BLOCKED.
4. Request one evidence-linked report, not a commit, merge, @cursor mention, fresh workflow run or paid provider call. Review the result against the GitHub original.
5. Only after the permission and cost gates are demonstrated on one small PR should owner consider a manually gated or conditional automation; do not enable event-based recurring Cloud dispatch without an explicit new instruction.

## Minimum reviewer handoff
```text
Role: Universal Reviewer (if supported by actual Cloud runtime)
Repository: ychen393/mcm-c-agent
PR: <number>
HEAD: <40-char SHA>
Profile: .cursor/review-profiles/mcm.md
Scope: inspect exact PR diff + matched PR CI + issue acceptance
Allowed: read + report only
Forbidden: commit, push, comment, approve, merge, deploy, launch tasks, paid API
Stop if: role unavailable, no independently verifiable read-only tools, unclear costs, moved HEAD
Output: PASS / NEEDS_FIX / BLOCKED, detailed findings, evidence URLs, isolation_verified
```

## Current separation of concerns
- Cursor Builder: proposes code on its own isolated branch and PR.
- GitHub Actions: tests the code, read-only observer reports checks.
- Cursor Bugbot (when independently run): bug-oriented review, potentially with separate usage costs.
- Universal Reviewer (this PR): prompt contract only; not a launched or permission-isolated Cloud session.
- Owner: all merges, paid agent runs and MCM research semantics decisions.

## Explicit non-goals
No research code changes, paid model invocation, Cloud Agent launch, Automation creation, scheduled polling, secrets or permissions change, main merge, PR auto approval or GitHub branch protection edits.
