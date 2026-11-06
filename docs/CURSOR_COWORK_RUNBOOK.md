# Cursor co-work runbook

Operational guide for Issue #8. This file describes what the current Cloud session can actually run. It does not connect a new account, grant a permission, or approve a merge.

Which layer is a sidebar chat, which layer is a nested Task, and which names are only prompt files: `docs/CURSOR_AGENT_LAYERS.md`. That page repeats the Issue #8 record: overall status `PARTIAL`, reviewer isolation `blocked`.

## Roles

| Role | Who runs it | What they may do |
| --- | --- | --- |
| Coordinator | ChatGPT, via GitHub | Scope the issue, read evidence, accept or reject the handoff. Does not merge from this runbook. |
| Implementer | Cursor Cloud main agent, or a `generalPurpose` task | One scoped branch, tests, draft pull request. |
| Bug review | `bugbot`, only when the Task schema lists it | Review a real diff for bugs. Record the task id or the rejection text. |
| Security review | `security-review`, only for a security-scoped issue and only when listed | Not a default step. |
| CI failure | `ci-investigator`, only after a real failed check | Explain that check. Do not invent a failure. |
| Objective tests | GitHub Actions workflow `Python tests` | `pytest -q` with `contents: read`. |
| Permission boundary | GitHub Actions workflow `Read-only review boundary` | Shows a read-only GitHub job. It is not an AI reviewer. |
| Owner | Repository owner | Merge, deploy, secrets, branch protection, paid APIs, research gates. |

`.cursor/agents/builder.md` and `.cursor/agents/reviewer.md` are prompts. `name: builder` and `name: reviewer` are not launchable Task types. Frontmatter `readonly: true` and `readonly: false` do not change Cloud tool access. The Task schema has no Task-level readonly switch.

## Supported invocation

The main agent calls the Task tool with `subagent_type` set to a name that session lists. Observed rejections, which must not be repeated:

- `subagent_type=builder` — invalid
- `subagent_type=reviewer` — invalid

There is no demonstrated Cloud project chat or agent-messaging product in this repository. Handoff text goes to the draft pull request. Issue comments from the cloud agent token return `Resource not accessible by integration` (`addComment`). That is a blocker for posting on the issue, not a reason to invent another channel.

Do not claim a second model ran unless the task result or run metadata names that model. Do not claim the reviewer was read-only unless the principal below is in place.

## What starts a run

| Event | Workflow | When it runs |
| --- | --- | --- |
| `pull_request` `opened`, `synchronize`, `reopened`, `ready_for_review` | `Python tests` and `Read-only review boundary` | Draft and ready pull requests whose **base** is `main`, `feature/**`, `cursor/**`, or `test/**`. |
| `push` | `Python tests` only | Pushes to those same branch families, including edits to the workflow file before a pull request exists. |

`ready_for_review` does not fire on every push. `pull_request_target` and `workflow_run` are not used. Concurrency cancels an older in-progress run of the same workflow, event, and ref. A push run does not cancel the pull request check. Opening a pull request still produces one push run and one pull request run; that pair is the existing shape, not a retrigger loop.

These workflows do not merge, deploy, or read secrets.

## Sequence

1. Coordinator opens or confirms an issue with acceptance criteria, a risk tier, and non-goals.
2. Implementer branches from the named base. One owner per branch.
3. Implementer runs `pytest -q` locally when the environment has the dev extra.
4. Implementer opens a **draft** pull request. Merge status: do not auto-merge.
5. Wait for the pull request event of `Python tests`. A push run on a different branch does not count.
6. If that check fails, use `ci-investigator` on that run, repair at most twice, and push again.
7. Call `bugbot` on the diff when the session lists it. If the call is rejected, record the error and stop that step. Do not rename `generalPurpose` into a reviewer.
8. Write the machine-readable record in `docs/cowork/` and comment on the draft pull request.
9. Owner merges. This runbook never merges.

## Machine-readable record

`docs/cowork/task-status.schema.json` defines the fields. One record per issue, for example `docs/cowork/issue-8-status.json`, carries:

- issue, branch, base branch, commit SHA, pull request URL
- test command and real check-run URL, event, and conclusion
- implementer identity and capability, including a task id when one exists
- reviewer identity, capability, isolation (`verified`, `unavailable`, or `blocked`), findings, and task id when one exists
- repair attempts (0 to 2), owner approval, next action, overall status, blockers

Do not store credentials, `.env` values, or private dataset contents in that file.

## Reviewer isolation — BLOCKED

Cursor Cloud tools in the builder session can commit and push. A prompt cannot remove that. The Actions job `Read-only review boundary` uses `contents: read`, `pull-requests: read`, and `persist-credentials: false`. That job only checks the diff for secret-like paths. It is not an independent AI reviewer.

### Owner steps that would unblock a separate read-only reviewer

1. Create a distinct Cursor Automation or Cloud Agent principal that is not the builder session.
2. Give that principal a GitHub credential with only contents read and pull requests read. The owner creates and stores that credential. Do not paste it into chat, issues, or the repo.
3. Confirm in the product UI that this principal cannot push and has no Task tool that writes.
4. Point it at `pull_request` for bases `main`, `feature/**`, `cursor/**`, and `test/**`.
5. Record the automation id and a review comment URL in `docs/cowork/`. Until those exist, isolation stays `blocked`.

## Stop conditions

Stop, mark the record blocked, and comment on the draft pull request when any of these appear:

- secret material, a private dataset, or a request to print credentials
- a destructive git command, a force push, or an edit to `main`
- auto-merge, branch protection, or a deploy
- a new paid API, provider, or recurring agent
- ambiguous math, contest interpretation, scoring, or what evidence may enter a paper
- two repair cycles already used on the same problem
- `bugbot` or `security-review` is required and the runtime rejects the type

Maximum two autonomous repair cycles per problem. The third response is a blocker, not another code change.

## Rollback

Close the draft pull request without merging. Delete nothing on the base branch. The feature branch can stay for inspection. Revert is a new commit on the feature branch if a specific commit must be undone. Do not reset published history and do not delete `main`.

## Smoke test

A second isolated branch may change tests only, open its own draft pull request onto a `test/**` or `feature/**` base, and must show its own `pull_request` run of `pytest -q`. It must not change MCM algorithms, Phase B chart behavior, or API settings.
