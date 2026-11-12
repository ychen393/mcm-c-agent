"""Phase 1 local project store: save, reopen, continue, history, invalidation."""

from __future__ import annotations

import hashlib
import json

import pytest

from core.foundation import build_initialized_state, foundation_input_signature, selection_token
from core.graph import build_foundation_graph
from core.lifecycle import RECOMPUTE_PROMPT, distinguish_status, lifecycle_from_state
from core.project_store import (
    LocalProjectStore,
    make_approval,
    open_project_store,
)
from tools.dataset_bundle import build_dataset_bundle

GOLD = (
    b"Date,USD (PM)\n"
    b"9/12/2016,1324.60\n"
    b"9/13/2016,1321.75\n"
    b"9/14/2016,\n"
    b"9/15/2016,1308.35\n"
)
BITCOIN = (
    b"Date,Value\n"
    b"9/11/2016,621.65\n"
    b"9/12/2016,609.67\n"
    b"9/13/2016,610.92\n"
    b"9/14/2016,608.82\n"
    b"9/15/2016,610.12\n"
)
PROBLEM = "2022 MCM Problem C Trading Strategies"


def _state_for(uploads, *, project_id="mcm-2022-c", problem=PROBLEM, revision=0):
    if uploads:
        bundle = build_dataset_bundle(uploads, project_id=project_id)
        selection = "ready"
    else:
        bundle = None
        selection = "empty"
    state = build_initialized_state(
        project_id=project_id,
        project_name="2022 MCM Problem C",
        problem_text=problem,
        bundle=bundle,
        selection_status=selection,
        llm_config_revision=revision,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    result = build_foundation_graph().invoke(state)
    token = selection_token(
        uploads,
        fingerprint=bundle.fingerprint if bundle is not None else None,
        rejected=False,
    )
    signature = foundation_input_signature(
        project_id=project_id,
        project_name="2022 MCM Problem C",
        problem_text=problem,
        selection_token_value=token,
        llm_config_revision=revision,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    return result, signature, bundle


def test_init_then_upload_and_upload_then_init_both_record_two_files(tmp_path):
    store = LocalProjectStore(tmp_path / "projects")
    uploads = [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)]

    # upload-then-init path: state already has files
    state, signature, _ = _state_for(uploads)
    project, run, saved = store.save_project_state(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        state=state,
        input_signature=signature,
    )
    assert len(saved["uploaded_files"]) == 2
    assert [item["file_name"] for item in saved["uploaded_files"]] == [
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    ]
    assert saved["lifecycle"] == "datasets_recorded"
    assert run.run_id.startswith("run_")
    assert project.active_run_id == run.run_id

    # init-then-upload: first empty, then with files (new signature → new version)
    empty, empty_sig, _ = _state_for([], project_id="mcm-init-first")
    store.save_project_state(
        project_id="mcm-init-first",
        project_name="Init First",
        state=empty,
        input_signature=empty_sig,
    )
    loaded_empty = store.load_active_state("mcm-init-first")
    assert loaded_empty is not None
    assert loaded_empty["uploaded_files"] == []
    assert loaded_empty["lifecycle"] == "project_initialized"

    with_files, with_sig, _ = _state_for(uploads, project_id="mcm-init-first")
    _project, run2, saved2 = store.save_project_state(
        project_id="mcm-init-first",
        project_name="Init First",
        state=with_files,
        input_signature=with_sig,
    )
    assert len(saved2["uploaded_files"]) == 2
    assert run2.version == 2
    history = store.history("mcm-init-first")
    assert len(history) == 2
    assert history[0].status == "active"
    assert history[1].status == "stale"


def test_restart_restores_project_and_legal_history(tmp_path):
    root = tmp_path / "projects"
    store = LocalProjectStore(root)
    uploads = [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)]
    state, signature, _ = _state_for(uploads)
    store.save_project_state(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        state=state,
        input_signature=signature,
    )
    # Simulate process restart: new store instance on the same root.
    restarted = LocalProjectStore(root)
    restored = restarted.load_active_state("mcm-2022-c")
    assert restored is not None
    assert restored["project_id"] == "mcm-2022-c"
    assert len(restored["uploaded_files"]) == 2
    assert restored["uploaded_files"][0]["sha256"] == hashlib.sha256(GOLD).hexdigest()
    history = restarted.history("mcm-2022-c")
    assert len(history) == 1
    assert history[0].dataset_count == 2
    # No raw bytes in persisted JSON.
    dump = json.dumps(restored)
    assert "1324.60" not in dump
    assert "raw_bytes" not in dump


def test_replace_reupload_does_not_reuse_approved_stale_results(tmp_path):
    store = LocalProjectStore(tmp_path / "projects")
    uploads = [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)]
    state, signature, _ = _state_for(uploads)
    project, run, saved = store.save_project_state(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        state=state,
        input_signature=signature,
    )
    store.add_approval(
        make_approval(
            project_id=project.project_id,
            run_id=run.run_id,
            gate="chart_plan",
            status="approved",
            subject_sha256=saved["uploaded_files"][0]["sha256"],
            notes="approved on original files",
        )
    )
    # Replace bitcoin file → new signature → previous run stale, approval invalidated.
    replaced = [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN + b"\n9/16/2016,611.00\n")]
    state2, signature2, _ = _state_for(replaced)
    _p2, run2, saved2 = store.save_project_state(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        state=state2,
        input_signature=signature2,
    )
    assert run2.run_id != run.run_id
    assert run2.version == 2
    history = store.history("mcm-2022-c")
    by_id = {entry.run_id: entry for entry in history}
    assert by_id[run.run_id].status == "stale"
    assert by_id[run2.run_id].status == "active"
    approvals_path = tmp_path / "projects" / "mcm-2022-c" / "runs" / run.run_id / "approvals.json"
    approvals = json.loads(approvals_path.read_text(encoding="utf-8"))
    assert approvals[0]["status"] == "invalidated"
    stale = store.continue_run("mcm-2022-c", run.run_id)
    assert stale is not None
    assert any(err.get("code") == "stale_run" for err in stale["errors"])
    assert store.mark_stale_if_signature_changed("mcm-2022-c", signature) is True
    assert RECOMPUTE_PROMPT
    assert saved2["uploaded_files"][1]["sha256"] != saved["uploaded_files"][1]["sha256"]


def test_disconnect_problem_or_model_config_invalidates(tmp_path):
    store = LocalProjectStore(tmp_path / "projects")
    uploads = [("LBMA-GOLD.csv", GOLD)]
    state, signature, _ = _state_for(uploads)
    store.save_project_state(
        project_id="mcm-cfg",
        project_name="Config Test",
        state=state,
        input_signature=signature,
    )
    # Problem text change
    state2, signature2, _ = _state_for(uploads, problem="revised problem statement")
    _p, run2, _ = store.save_project_state(
        project_id="mcm-cfg",
        project_name="Config Test",
        state=state2,
        input_signature=signature2,
    )
    assert run2.version == 2
    # Model config revision change
    state3, signature3, _ = _state_for(uploads, problem="revised problem statement", revision=3)
    _p, run3, _ = store.save_project_state(
        project_id="mcm-cfg",
        project_name="Config Test",
        state=state3,
        input_signature=signature3,
    )
    assert run3.version == 3
    assert len(store.history("mcm-cfg")) == 3


def test_lifecycle_distinctions():
    empty, _, _ = _state_for([])
    assert lifecycle_from_state(empty) == "project_initialized"
    board = distinguish_status(empty)
    assert board["project_init"] == "success"
    assert board["data_analysis"] == "not done"
    assert "NOT COMPLETE" in board["research_task"]

    uploads = [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)]
    with_files, _, _ = _state_for(uploads)
    assert lifecycle_from_state(with_files) == "datasets_recorded"
    board2 = distinguish_status(with_files)
    assert board2["data_analysis"] == "datasets recorded"
    assert "NOT COMPLETE" in board2["research_task"]


def test_open_project_store_falls_back_to_local(tmp_path):
    store = open_project_store(
        database_url="postgresql+psycopg://nobody:bad@127.0.0.1:1/missing",
        projects_root=tmp_path / "projects",
        prefer_postgres=True,
    )
    info = store.info()
    assert info.backend == "local"
    assert "PostgreSQL unavailable" in info.detail or "local" in info.detail.lower()


def test_persisted_state_rejects_api_keys(tmp_path):
    store = LocalProjectStore(tmp_path / "projects")
    state, signature, _ = _state_for([("LBMA-GOLD.csv", GOLD)])
    dirty = dict(state)
    dirty["llm_api_key"] = "sk-secret"
    dirty["dataset_metadata"] = dict(dirty.get("dataset_metadata") or {})
    project, run, saved = store.save_project_state(
        project_id="mcm-safe",
        project_name="Safe Persist",
        state=dirty,
        input_signature=signature,
    )
    dump = json.dumps(saved)
    assert "sk-secret" not in dump
    assert "llm_api_key" not in saved
    reloaded = store.load_active_state("mcm-safe")
    assert reloaded is not None
    assert "llm_api_key" not in reloaded


@pytest.mark.parametrize("backend", ["local"])
def test_core_models_round_trip(tmp_path, backend):
    store = LocalProjectStore(tmp_path / "projects")
    state, signature, bundle = _state_for(
        [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)]
    )
    project, run, saved = store.save_project_state(
        project_id="mcm-models",
        project_name="Model Round Trip",
        state=state,
        input_signature=signature,
    )
    assert project.project_id == "mcm-models"
    assert run.run_id == saved["run_id"]
    assert bundle is not None
    assert len(saved["uploaded_files"]) == 2
    artifact = store.add_artifact(
        __import__("core.project_store", fromlist=["make_artifact"]).make_artifact(
            project_id=project.project_id,
            run_id=run.run_id,
            kind="eda_report",
            uri=f"outputs/{project.project_id}/eda/report.json",
            sha256=hashlib.sha256(b"report").hexdigest(),
            label="eda",
        )
    )
    assert artifact.artifact_id.startswith("art_")
    assert len(store.list_artifacts(project.project_id)) == 1
