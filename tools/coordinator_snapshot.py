"""Generate a read-only, evidence-based project task dashboard from GitHub."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REGISTRY = Path("docs/agents/task-registry.json")


def github_get(repo: str, route: str, token: str):
    if not repo or repo.count("/") != 1 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./" for c in repo):
        raise ValueError("Invalid repository")
    request = Request(
        "https://api.github.com/repos/" + repo + "/" + route,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MCM-Coordinator-Live-View",
            **({"Authorization": "Bearer " + token} if token else {}),
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def refresh_entry(entry: dict, repo: str, fetch):
    """Leave historical records untouched; append observable current GitHub state."""
    out = dict(entry)
    pr_number = entry.get("pr")
    if not pr_number:
        out["live"] = {"state": "NO_PR", "source": "registry-only"}
        return out
    try:
        pr = fetch(repo, f"pulls/{pr_number}")
        sha = pr["head"]["sha"]
        branch = pr["head"]["ref"]
        runs = fetch(repo, f"actions/runs?event=pull_request&head_sha={sha}&per_page=100")["workflow_runs"]
        relevant = [
            r for r in runs if r.get("name") == "Python tests"
            and r.get("head_sha") == sha and r.get("head_branch") == branch
            and r.get("event") == "pull_request"
        ]
        relevant.sort(key=lambda r: (r.get("created_at") or "", r.get("id") or 0))
        ci = relevant[-1] if relevant else None
        reviews = fetch(repo, f"pulls/{pr_number}/reviews?per_page=100")
        reviewed = [
            r for r in reviews
            if r.get("commit_id") == sha
            and r.get("state") in ("APPROVED", "CHANGES_REQUESTED")
            and r.get("user", {}).get("login") not in (None, "", pr.get("user", {}).get("login"))
        ]
        reviewed.sort(key=lambda r: r.get("submitted_at") or "")
        review = reviewed[-1] if reviewed else None
        ci_pass = bool(ci and ci.get("status") == "completed" and ci.get("conclusion") == "success")
        ci_failed = bool(ci and ci.get("status") == "completed" and ci.get("conclusion") != "success")
        if pr.get("merged"):
            status = "MERGED_RECORDED"
        elif pr.get("state") == "closed":
            status = "CLOSED_UNMERGED"
        elif ci_failed or (review and review["state"] == "CHANGES_REQUESTED"):
            status = "NEEDS_FIX_AUTH"
        elif not ci_pass:
            status = "AWAIT_CI"
        elif review is None:
            status = "AWAIT_REVIEW"
        else:
            status = "OWNER_DECISION_REQUIRED"
        out["live"] = {
            "state": status,
            "pr_url": pr.get("html_url") or f"https://github.com/{repo}/pull/{pr_number}",
            "pr_draft": bool(pr.get("draft")),
            "head_sha": sha,
            "head_branch": branch,
            "ci": {"status": ci.get("status") if ci else "not_found",
                   "conclusion": ci.get("conclusion") if ci else None,
                   "url": ci.get("html_url") if ci else None},
            "review": {"state": review.get("state") if review else "not_verified",
                       "url": review.get("html_url") if review else None},
            "isolated_ai_reviewer_verified": False,
            "can_auto_merge": False,
            "can_auto_dispatch": False,
            "source": "GitHub API; PR/CI/reviews at collection time",
        }
    except (HTTPError, URLError, ValueError, KeyError, TypeError, TimeoutError) as err:
        out["live"] = {"state": "FETCH_BLOCKED", "error": type(err).__name__, "source": "GitHub API"}
    return out


def collect(registry: dict, repo: str, fetch):
    return {
        "schema_version": 1,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": repo,
        "project_name": registry.get("project"),
        "project_session": registry.get("project_session"),
        "mode": "on-demand-github-snapshot-not-cursor-live-sync",
        "entries": [refresh_entry(x, repo, fetch) for x in registry["entries"]],
        "security": {"extra_billed_usd": 0, "auto_cloud_dispatch": False, "auto_merge": False},
    }


def render_markdown(data: dict):
    lines = [
        "# MCM Development Coordinator — GitHub snapshot",
        "",
        f"Collected (UTC): \`{data['collected_at_utc']}\`",
        "",
        "This is a GitHub-derived **snapshot**, not live Cursor sessions or independent AI review.",
        "",
        "| Task | Role | GitHub state | PR CI | Cursor session | Next gate |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for x in data["entries"]:
        live = x["live"]
        task = str(x["task_id"]).replace("|", "\\|")
        session = f"[Open]({x['session']})" if x.get("session") else "Not evidenced"
        ci = live.get("ci") or {}
        ci_status = f"{ci.get('status')}/{ci.get('conclusion')}" if ci else "—"
        gate = x.get("next_gate", "owner decision").replace("|", "/").replace("\n", " ")
        lines.append(f"| {task} | {x.get('role')} | {live['state']} | {ci_status} | {session} | {gate} |")
    lines += ["", "No unapproved Cloud Agent, auto-fix, deployment or merge is started by this report.", ""]
    return "\n".join(lines)


def render_html(data: dict):
    rows = []
    for x in data["entries"]:
        live = x["live"]
        ci = live.get("ci") or {}
        session = (
            f'<a href="{escape(x["session"], quote=True)}" target="_blank" rel="noopener noreferrer">Open session</a>'
            if x.get("session") else '<span class="muted">Not recorded</span>'
        )
        pr = (
            f'<a href="{escape(live["pr_url"], quote=True)}" target="_blank" rel="noopener noreferrer">PR #{x["pr"]}</a>'
            if live.get("pr_url") else escape(str(x.get("pr") or "—"))
        )
        rows.append(
            "<tr>"
            f'<td><strong>{escape(str(x["task_id"]))}</strong><small>{escape(str(x.get("role") or "—"))}</small></td>'
            f'<td>{escape(str(live["state"]))}</td>'
            f'<td>{pr}<small>{escape(str(live.get("head_sha") or "—")[:12])}</small></td>'
            f'<td>{escape(str(ci.get("status") or "—"))} / {escape(str(ci.get("conclusion") or "—"))}</td>'
            f'<td>{session}</td>'
            f'<td>{escape(str(x.get("next_gate") or "—"))}</td>'
            "</tr>"
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>MCM Coordinator Status</title>'
        '<style>body{font:15px system-ui,sans-serif;max-width:1400px;margin:35px auto;padding:0 24px;color:#203047;background:#f7f9fc}'
        'h1{font-size:28px}p{color:#596779}table{border-collapse:collapse;width:100%;background:#fff;border-radius:12px;overflow:hidden}'
        'th,td{text-align:left;padding:16px 12px;border-bottom:1px solid #e5eaf1;vertical-align:top}'
        'th{background:#e9eef6}small{display:block;color:#758299;margin-top:6px;word-break:break-all}'
        'a{color:#155bb3}.muted{color:#8a93a3}footer{margin:20px 0;color:#68768c}</style>'
        '<main><h1>MCM C Agent — Development Coordination</h1>'
        '<p>Generated at ' + escape(data["collected_at_utc"]) +
        '. GitHub snapshot only; Cursor runs are linked historical evidence, not automatically synchronized.</p>'
        '<table><thead><tr><th>Task / Role</th><th>State</th><th>PR / HEAD</th><th>CI</th>'
        '<th>Cursor Session</th><th>Next Gate</th></tr></thead><tbody>' +
        "".join(rows) + '</tbody></table>'
        '<footer>No automatic Cloud dispatch, paid API calls, code fixes or merges. '
        'This does not assert independent reviewer isolation.</footer></main></html>'
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--registry", type=Path, default=REGISTRY)
    p.add_argument("--out", type=Path, default=Path("coordinator-view"))
    args = p.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    token = os.getenv("GH_TOKEN", "")
    data = collect(registry, args.repo, lambda repo, route: github_get(repo, route, token))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "tasks.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (args.out / "index.html").write_text(render_html(data), encoding="utf-8")
    summary = render_markdown(data)
    (args.out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(summary)
    print(summary)


if __name__ == "__main__":
    main()
