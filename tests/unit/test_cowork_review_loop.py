import pytest
from tools.cowork_review_loop import replay, github_snapshot, LoopError
O, B, R = "ychen393", "cursor[bot]", "reviewer"
A, C, D = "a"*40, "b"*40, "c"*40
URL = "https://github.com/ychen393/mcm-c-agent/pull/99#review"
def e(i, kind, who, **kw): return {"id":str(i),"kind":kind,"actor":who,**kw}
def start(): return [e(0,"authorize",O,extra_spend_usd=0,single_agent=True),e(1,"build",B,sha=A),
                     e(2,"ci_pass","actions",sha=A,ci_event="pull_request",url=URL)]
def fix(n, sha): return [e(n,"authorize",O,extra_spend_usd=0,single_agent=True),
                         e(n+1,"fix",B,sha=sha),
                         e(n+2,"ci_pass","actions",sha=sha,ci_event="pull_request",url=URL)]
def review(n, sha, ok=False): return e(n,"review_pass" if ok else "review_fail",R,sha=sha,url=URL)

def test_initial_review_pass(): 
    s=replay(start()+[review(3,A,True)],owner=O,builder=B)
    assert s["stage"]=="READY_FOR_OWNER" and s["fixes"]==0 and s["can_merge"] is False
def test_first_fix_review_pass():
    s=replay(start()+[review(3,A)]+fix(4,C)+[review(7,C,True)],owner=O,builder=B)
    assert s["stage"]=="READY_FOR_OWNER" and s["fixes"]==1
def test_second_fix_review_pass():
    log=start()+[review(3,A)]+fix(4,C)+[review(7,C)]+fix(8,D)+[review(11,D,True)]
    s=replay(log,owner=O,builder=B)
    assert s["stage"]=="READY_FOR_OWNER" and s["fixes"]==2
def test_two_fixes_then_fail_exhausts():
    log=start()+[review(3,A)]+fix(4,C)+[review(7,C)]+fix(8,D)+[review(11,D)]
    assert replay(log,owner=O,builder=B)["stage"]=="EXHAUSTED"
    with pytest.raises(LoopError,match="Terminal"):
        replay(log+fix(12,"e"*40),owner=O,builder=B)
def test_failed_ci_spends_fix_slot():
    log=start()[:2]+[e(2,"ci_fail","actions",sha=A,ci_event="pull_request",url=URL)]
    log+=fix(3,C)+[review(6,C)]+fix(7,D)[:2]+[e(9,"ci_fail","actions",sha=D,ci_event="pull_request",url=URL)]
    assert replay(log,owner=O,builder=B)["stage"]=="EXHAUSTED"
def test_no_stale_review():
    with pytest.raises(LoopError,match="Stale"):
        replay(start()+[review(3,C,True)],owner=O,builder=B)
def test_no_push_only_ci():
    with pytest.raises(LoopError,match="Push-only"):
        replay(start()[:2]+[e(2,"ci_pass","actions",sha=A,ci_event="push",url=URL)],owner=O,builder=B)
def test_owner_gate():
    with pytest.raises(LoopError,match="owner"):
        replay([e(0,"authorize",B,extra_spend_usd=0,single_agent=True)],owner=O,builder=B)
    with pytest.raises(LoopError,match="zero-extra"):
        replay([e(0,"authorize",O,extra_spend_usd=1,single_agent=True)],owner=O,builder=B)
def test_builder_cannot_review():
    with pytest.raises(LoopError,match="Builder cannot"):
        replay(start()+[e(3,"review_pass",B,sha=A,url=URL)],owner=O,builder=B)
def test_duplicate_idempotent_and_conflict():
    assert len(replay(start()+[start()[-1]],owner=O,builder=B)["audit"])==3
    with pytest.raises(LoopError,match="Conflicting"):
        replay(start()+[dict(start()[-1],sha=C)],owner=O,builder=B)
def test_stop():
    assert replay([e(0,"stop",O,reason="cost")],owner=O,builder=B)["stage"]=="BLOCKED"
def snapshot(review_state=None,old=False,conclusion="success"):
    pr={"number":99,"head":{"sha":C,"ref":"feature/demo"},"user":{"login":B}}
    commits=[{"sha":A},{"sha":C}]
    reviews=[]
    if old: reviews.append({"commit_id":A,"state":"CHANGES_REQUESTED","user":{"login":R},"submitted_at":"1"})
    if review_state: reviews.append({"commit_id":C,"state":review_state,"user":{"login":R},"submitted_at":"2","html_url":URL})
    runs=[{"name":"Python tests","event":"pull_request","head_sha":C,"head_branch":"feature/demo",
           "status":"completed","conclusion":conclusion,"html_url":URL,"id":1}]
    return github_snapshot(pr,reviews,commits,runs)
def test_snapshot_requires_real_review():
    s=snapshot()
    assert s["stage"]=="AWAIT_REVIEW" and s["can_auto_launch_cursor"] is False
def test_snapshot_review_and_fix():
    assert snapshot("APPROVED")["stage"]=="READY_FOR_OWNER"
    assert snapshot("CHANGES_REQUESTED",old=True)["observed_fixes"]==1
    assert snapshot("CHANGES_REQUESTED",old=True)["stage"]=="NEEDS_FIX_AUTH"
@pytest.mark.parametrize("conclusion", [
    "failure", "timed_out", "cancelled", "startup_failure",
    "action_required", "neutral", "skipped", None,
])
def test_snapshot_completed_non_success_requires_fix_authorization(conclusion):
    # A terminal CI run must never leave the observer waiting indefinitely.
    assert snapshot("APPROVED", conclusion=conclusion)["stage"] == "NEEDS_FIX_AUTH"


@pytest.mark.parametrize("conclusion", [
    "failure", "timed_out", "cancelled", "startup_failure",
    "action_required", "neutral", "skipped", None,
])
def test_snapshot_completed_non_success_exhausts_after_two_fixes(conclusion):
    pr = {"number": 99, "head": {"sha": D, "ref": "feature/demo"}, "user": {"login": B}}
    commits = [{"sha": A}, {"sha": C}, {"sha": D}]
    reviews = [
        {"commit_id": A, "state": "CHANGES_REQUESTED", "user": {"login": R}, "submitted_at": "1"},
        {"commit_id": C, "state": "CHANGES_REQUESTED", "user": {"login": R}, "submitted_at": "2"},
    ]
    runs = [{"name": "Python tests", "event": "pull_request", "head_sha": D,
             "head_branch": "feature/demo", "status": "completed",
             "conclusion": conclusion, "html_url": URL, "id": 1}]
    result = github_snapshot(pr, reviews, commits, runs)
    assert result["stage"] == "EXHAUSTED"
    assert result["observed_fixes"] == 2


@pytest.mark.parametrize("status", ["queued", "in_progress", "requested", "waiting", "pending"])
def test_snapshot_unfinished_ci_still_waits(status):
    pr = {"number": 99, "head": {"sha": C, "ref": "feature/demo"}, "user": {"login": B}}
    runs = [{"name": "Python tests", "event": "pull_request", "head_sha": C,
             "head_branch": "feature/demo", "status": status,
             "conclusion": None, "html_url": URL, "id": 1}]
    assert github_snapshot(pr, [], [{"sha": C}], runs)["stage"] == "AWAIT_CI"
def test_documented_permissions():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    y=(root/".github/workflows/cowork-review-observer.yml").read_text()
    assert "contents: read" in y and "pull-requests: read" in y
    assert "contents: write" not in y and "pull_request_target" not in y
    assert "persist-credentials: false" in y
    assert "@cursor" not in y
