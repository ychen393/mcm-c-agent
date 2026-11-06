"""Read-only PR quality-gate report. No agent dispatch, comments or merges."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


TERMINAL_FAILURE = {
    "failure", "cancelled", "timed_out", "startup_failure",
    "action_required", "skipped", "neutral", None,
}


def evaluate(pr: dict, runs: list[dict], reviews: list[dict]) -> dict:
    """Summarize only evidence for the exact PR head, never authorize a merge."""
    head = pr["head"]["sha"]
    number = pr["number"]
    branch = pr["head"]["ref"]
    author = pr.get("user", {}).get("login")
    relevant = [
        run for run in runs
        if run.get("name") == "Python tests"
        and run.get("event") == "pull_request"
        and run.get("head_sha") == head
        and run.get("head_branch") == branch
    ]
    relevant.sort(key=lambda x: (x.get("created_at") or "", x.get("id") or 0))
    ci = relevant[-1] if relevant else None
    status = ci.get("status") if ci else None
    conclusion = ci.get("conclusion") if ci else None
    passed = status == "completed" and conclusion == "success"
    failed = status == "completed" and conclusion != "success"
    qualifying = [
        review for review in reviews
        if review.get("commit_id") == head
        and review.get("state") in {"APPROVED", "CHANGES_REQUESTED"}
        and review.get("user", {}).get("login") not in {author, None, ""}
    ]
    qualifying.sort(key=lambda x: x.get("submitted_at") or "")
    review = qualifying[-1] if qualifying else None
    if failed:
        gate = "NEEDS_FIX_AUTH"
    elif not passed:
        gate = "AWAIT_CI"
    elif review is None:
        gate = "AWAIT_INDEPENDENT_REVIEW"
    elif review["state"] == "CHANGES_REQUESTED":
        gate = "NEEDS_FIX_AUTH"
    else:
        gate = "OWNER_DECISION_REQUIRED"
    return {
        "pr": number,
        "head_sha": head,
        "gate": gate,
        "ci_status": status or "not_found",
        "ci_conclusion": conclusion,
        "ci_url": ci.get("html_url") if ci else None,
        "review_status": review.get("state") if review else "not_verified",
        "review_url": review.get("html_url") if review else None,
        "reviewer_isolation": "not_verified",
        "can_merge": False,
        "can_launch_cursor": False,
        "notes": [
            "Read-only PR report; passing CI is not an AI review.",
            "A GitHub review is not proof of tool-level independent reviewer isolation.",
            "Owner must explicitly authorize every Cloud run, fix and merge.",
            "Cost of Cloud Agent use has not been verified; extra-spend budget USD $0.",
        ],
    }


def read_api(repo: str, route: str, token: str) -> dict | list:
    url = "https://api.github.com/repos/" + repo + "/" + route
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "mcm-pr-gate",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers), timeout=15) as response:
        return json.load(response)


def markdown(report: dict) -> str:
    return (
        "## Automated PR review readiness (read-only)\n\n"
        f"- PR: #{report['pr']}\n"
        f"- Head: \`{report['head_sha']}\`\n"
        f"- Gate: **{report['gate']}**\n"
        f"- PR-attached Python CI: {report['ci_status']} / {report['ci_conclusion']}\n"
        f"- CI evidence: {report['ci_url'] or 'not found'}\n"
        f"- Distinct-account GitHub review: {report['review_status']}\n"
        f"- Review evidence: {report['review_url'] or 'not found'}\n"
        "- AI reviewer tool isolation: **NOT VERIFIED**\n"
        "- Automatic Cloud dispatch: **OFF**; auto-merge: **OFF**\n\n"
        "This is a deterministic status report, **not** an AI code review or merge approval.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("review-readiness.json"))
    args = parser.parse_args()
    try:
        if not args.repo or "/" not in args.repo:
            raise ValueError("Invalid repository")
        event = json.loads(args.event.read_text(encoding="utf-8"))
        number = event["pull_request"]["number"]
        token = os.environ.get("GH_TOKEN", "")
        pr = read_api(args.repo, f"pulls/{number}", token)
        reviews = read_api(args.repo, f"pulls/{number}/reviews?per_page=100", token)
        sha = quote(pr["head"]["sha"], safe="")
        runs = read_api(
            args.repo, f"actions/runs?event=pull_request&head_sha={sha}&per_page=100", token
        )["workflow_runs"]
        report = evaluate(pr, runs, reviews)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        summary = markdown(report)
        print(summary)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write(summary)
        return 0
    except (KeyError, ValueError, OSError, HTTPError, URLError, TypeError) as error:
        print(f"Review readiness BLOCKED: {type(error).__name__}: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
