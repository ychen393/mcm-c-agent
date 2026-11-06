"""Budget-gated two-fix Builder -> Review loop. Never launches Cursor or merges."""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_FIXES = 2
SHA = re.compile(r"^[0-9a-f]{40}$")

class LoopError(ValueError):
    pass

def sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise LoopError("Full lower-case 40-character SHA required")
    return value

def evidence(url):
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        raise LoopError("Real GitHub evidence URL required")
    return url

def replay(events, *, owner, builder):
    """Idempotent state machine: at most two authorized fix commits."""
    if not owner or not builder or owner == builder:
        raise LoopError("Distinct owner and builder required")
    state = {"stage":"NEEDS_BUILD_AUTH","head":None,"fixes":0,"reviewer":None,
             "max_fixes":MAX_FIXES,"can_auto_launch_cursor":False,
             "can_merge":False,"audit":[]}
    seen = {}
    for item in events:
        if not isinstance(item, dict):
            raise LoopError("Event must be an object")
        key, kind, actor = item.get("id"), item.get("kind"), item.get("actor")
        if not isinstance(key, str) or not 0 < len(key) <= 100 or not actor:
            raise LoopError("Every event needs a bounded id and an actor")
        canonical = json.dumps(item, sort_keys=True)
        if key in seen:
            if seen[key] != canonical: raise LoopError("Conflicting duplicate event")
            continue
        seen[key] = canonical
        phase = state["stage"]
        if phase in {"READY_FOR_OWNER","EXHAUSTED","BLOCKED"}:
            raise LoopError("Terminal stage cannot transition")
        if kind == "stop":
            if not item.get("reason"): raise LoopError("Stop requires reason")
            state["stage"] = "BLOCKED"
        elif kind == "authorize":
            if actor != owner or phase not in {"NEEDS_BUILD_AUTH","NEEDS_FIX_AUTH"}:
                raise LoopError("Only owner can authorize build or fix")
            if item.get("extra_spend_usd") != 0 or item.get("single_agent") is not True:
                raise LoopError("Need zero-extra-cost and one-agent attestation")
            state["stage"] = "AWAIT_BUILD" if phase == "NEEDS_BUILD_AUTH" else "AWAIT_FIX"
        elif kind in {"build","fix"}:
            if actor != builder or phase != ("AWAIT_BUILD" if kind == "build" else "AWAIT_FIX"):
                raise LoopError("Builder submission not authorized")
            current = sha(item.get("sha"))
            if current == state["head"]: raise LoopError("Fix needs new SHA")
            if kind == "fix":
                if state["fixes"] >= MAX_FIXES: raise LoopError("Fix cap reached")
                state["fixes"] += 1
            state.update(stage="AWAIT_CI",head=current,reviewer=None)
        elif kind in {"ci_pass","ci_fail"}:
            if phase != "AWAIT_CI" or sha(item.get("sha")) != state["head"]:
                raise LoopError("Stale CI")
            if item.get("ci_event") != "pull_request": raise LoopError("Push-only CI insufficient")
            evidence(item.get("url"))
            state["stage"] = ("AWAIT_REVIEW" if kind == "ci_pass" else
                              "EXHAUSTED" if state["fixes"] == MAX_FIXES else "NEEDS_FIX_AUTH")
        elif kind in {"review_pass","review_fail"}:
            if phase != "AWAIT_REVIEW" or sha(item.get("sha")) != state["head"]:
                raise LoopError("Stale review or missing passing CI")
            if actor == builder: raise LoopError("Builder cannot review own code")
            evidence(item.get("url"))
            state["reviewer"] = actor
            state["stage"] = ("READY_FOR_OWNER" if kind == "review_pass" else
                              "EXHAUSTED" if state["fixes"] == MAX_FIXES else "NEEDS_FIX_AUTH")
        else:
            raise LoopError("Unknown event: " + str(kind))
        state["audit"].append({"id":key,"kind":kind,"actor":actor,"sha":state["head"],
                               "stage":state["stage"],"fixes":state["fixes"]})
    return state

def github_snapshot(pr, reviews, commits, runs):
    """Advisory read-only GitHub evidence snapshot, not an independent AI review."""
    head = sha(pr["head"]["sha"])
    order = [c["sha"] for c in commits]
    if head not in order or any(len(x) > 100 for x in (reviews,commits,runs)):
        raise LoopError("Evidence history incomplete")
    author = pr.get("user",{}).get("login")
    legitimate = [x for x in reviews if x.get("state") in {"APPROVED","CHANGES_REQUESTED"}
                  and x.get("commit_id") in order
                  and x.get("user",{}).get("login") not in {author,None,""}]
    legitimate.sort(key=lambda x:x.get("submitted_at") or "")
    prior = {x["commit_id"] for x in legitimate if x["state"] == "CHANGES_REQUESTED"
             and order.index(x["commit_id"]) < order.index(head)}
    fixes = len(prior)
    matching = [x for x in legitimate if x["commit_id"] == head]
    review = matching[-1] if matching else None
    current = [r for r in runs if r.get("name") == "Python tests"
               and r.get("event") == "pull_request" and r.get("head_sha") == head
               and r.get("head_branch") == pr["head"]["ref"]]
    current.sort(key=lambda r:(r.get("created_at") or "",r.get("id",0)))
    ci = current[-1] if current else None
    passed = bool(ci and ci.get("status") == "completed" and ci.get("conclusion") == "success")
    # Any completed non-successful check is terminal, not still awaiting CI.
    # This includes failure, timed_out, cancelled, startup_failure, and skipped.
    failed = bool(ci and ci.get("status") == "completed" and not passed)
    if fixes > MAX_FIXES:
        stage = "EXHAUSTED"
    elif not passed:
        stage = ("EXHAUSTED" if failed and fixes >= MAX_FIXES else
                 "NEEDS_FIX_AUTH" if failed else "AWAIT_CI")
    elif review and review["state"] == "APPROVED":
        stage = "READY_FOR_OWNER"
    elif review and review["state"] == "CHANGES_REQUESTED":
        stage = "EXHAUSTED" if fixes >= MAX_FIXES else "NEEDS_FIX_AUTH"
    else:
        stage = "AWAIT_REVIEW"
    return {"stage":stage,"pr":pr["number"],"head_sha":head,"observed_fixes":fixes,
            "max_fixes":MAX_FIXES,"ci_url":ci.get("html_url") if ci else None,
            "review_url":review.get("html_url") if review else None,
            "reviewer_isolation":"not_verified","can_merge":False,
            "can_auto_launch_cursor":False,
            "warning":"PR snapshot is advisory. Persisted event ledger is required for authorization; read-only Actions is not an AI reviewer."}

def gh_read(repo, path):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo):
        raise LoopError("Invalid repo")
    token = os.environ.get("GH_TOKEN","")
    headers = {"Accept":"application/vnd.github+json","User-Agent":"mcm-review-loop"}
    if token: headers["Authorization"] = "Bearer " + token
    try:
        with urlopen(Request("https://api.github.com/repos/"+repo+"/"+path,headers=headers),timeout=12) as r:
            return json.load(r)
    except (HTTPError,URLError,TimeoutError) as e:
        raise LoopError("GitHub read failed: "+type(e).__name__) from e

def main(argv=None):
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="mode",required=True)
    ledger = subs.add_parser("replay")
    ledger.add_argument("--events",type=Path,required=True)
    ledger.add_argument("--owner",required=True)
    ledger.add_argument("--builder",required=True)
    online = subs.add_parser("github")
    online.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    online.add_argument("--pr",required=True,type=int)
    a = parser.parse_args(argv)
    try:
        if a.mode == "replay":
            events=json.loads(a.events.read_text(encoding="utf-8"))
            if not isinstance(events,list): raise LoopError("Ledger must be a list")
            result=replay(events,owner=a.owner,builder=a.builder)
        else:
            if not a.repo or a.pr < 1: raise LoopError("Missing repo or PR")
            pr=gh_read(a.repo,f"pulls/{a.pr}")
            reviews=gh_read(a.repo,f"pulls/{a.pr}/reviews?per_page=100")
            commits=gh_read(a.repo,f"pulls/{a.pr}/commits?per_page=100")
            runs=gh_read(a.repo,f"actions/runs?event=pull_request&head_sha={pr['head']['sha']}&per_page=100")["workflow_runs"]
            result=github_snapshot(pr,reviews,commits,runs)
        print(json.dumps(result,indent=2,ensure_ascii=False))
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
                f.write("\n### Build–Review loop (max 2 fixes)\n\nStatus: **"+result["stage"]+"**\n\nCursor auto-dispatch: disabled. Merge: disabled.\n")
        return 0
    except (LoopError,KeyError,ValueError,OSError,TypeError) as e:
        print(json.dumps({"status":"BLOCKED","reason":str(e)}),file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
