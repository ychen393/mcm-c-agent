"""Phase 8 paper persistence + H3 gate on attach / E2E."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.literature_evidence import gather_literature_evidence
from agents.paper_planner import run_paper_planner
from agents.problem_analyst import analyze_problem
from core.project_store import LocalProjectStore
from paper.gate import e2e_allowed, paper_allowed
from schemas.paper import H3Decision
from schemas.persistence import sanitize_state_for_persistence
from tools.paper_persistence import (
    build_h3_decision,
    compact_paper_package,
    persist_h3_decision_into_state,
    persist_paper_into_state,
)
from tools.problem_spec_2022_c import load_2022_c_fixture


def _boot_state(store: LocalProjectStore) -> dict:
    state = {
        "project_id": "mcm-c-demo",
        "project_name": "MCM C Demo Project",
        "project_status": "initialized",
        "lifecycle": "data_analysis_done",
        "analysis_status": "data_analysis_done",
        "uploaded_files": [],
        "citations": [],
        "model_artifacts": [],
        "experiment_logs": [],
        "workspace_phases": {},
        "approval_status": {},
        "errors": [],
        "data_resume": "reupload_required",
    }
    _project, run, boot = store.save_project_state(
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=state,
        input_signature="sig-phase8-test",
        note="bootstrap",
    )
    boot = dict(boot)
    boot["run_id"] = run.run_id
    return boot


@pytest.fixture
def paper_bundle(tmp_path: Path):
    store = LocalProjectStore(tmp_path / "projects")
    boot = _boot_state(store)
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    evidence = gather_literature_evidence(
        problem_specification=spec,
        use_live=False,
    )
    state = dict(boot)
    state["problem_specification"] = spec.model_dump(mode="json")
    state["evidence_report"] = evidence.model_dump(mode="json")
    state["validation_report"] = {
        "report_id": "vrep_p8",
        "baseline_run_id": "erun_p8",
        "proposal_id": "prop_p8",
        "scenarios": [{"scenario_id": "scn_a"}],
    }
    state["research_proposal"] = {"proposal_id": "prop_p8"}
    state["approval_status"] = {"h1": "approved", "h2": "approved"}
    state["decision_report"] = {
        "h2": {"status": "approved", "auto_approved": False, "decided_by": "human"},
        "experiment": {
            "report_id": "erep_p8",
            "latest_run_id": "erun_p8",
        },
    }
    package = run_paper_planner(state=state, problem_specification=spec)
    return store, state, package


def test_compact_package_is_persistence_safe(paper_bundle):
    _store, _state, package = paper_bundle
    compact = compact_paper_package(package)
    assert compact["invented_citations"] is False
    sanitize_state_for_persistence(
        {
            "project_id": "mcm-c-demo",
            "project_name": "MCM C Demo Project",
            "project_status": "initialized",
            "lifecycle": "project_initialized",
            "uploaded_files": [],
            "paper_outline": compact["outline"],
            "latex_source": compact["latex"]["tex_source"],
            "review_report": compact["review"],
            "decision_report": {"paper": compact},
        }
    )


def test_persist_refused_without_h2(tmp_path: Path, paper_bundle):
    store, _state, package = paper_bundle
    blocked = _boot_state(store)
    blocked["approval_status"] = {"h2": "pending"}
    with pytest.raises(PermissionError):
        persist_paper_into_state(
            store,
            project_id="mcm-c-demo",
            project_name="MCM C Demo Project",
            state=blocked,
            input_signature="sig-phase8-test",
            package=package,
        )


def test_persist_sets_h3_pending_and_blocks_e2e(paper_bundle):
    store, state, package = paper_bundle
    assert paper_allowed(state) is True
    saved = persist_paper_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=state,
        input_signature="sig-phase8-test",
        package=package,
    )
    assert saved["approval_status"]["h3"] == "pending"
    assert saved["workspace_phases"]["h3"] == "pending"
    assert saved["workspace_phases"]["e2e_acceptance"] == "blocked_until_h3"
    assert saved["paper_outline"]["outline_id"] == package.outline.outline_id
    assert saved["latex_source"]
    assert e2e_allowed(saved) is False
    assert (saved.get("decision_report") or {}).get("e2e_gate", {}).get(
        "e2e_allowed"
    ) is False


def test_build_h3_decision_accepts_compact_package_dict(paper_bundle):
    """Attach persists report_version; Approve must re-validate that compact dict."""
    _store, _state, package = paper_bundle
    compact = compact_paper_package(package)
    assert "report_version" in compact
    decision = build_h3_decision(
        status="approved",
        package=compact,
        notes="Approve from compact paper payload.",
    )
    assert decision.status == "approved"
    assert decision.auto_approved is False


def test_h3_approve_unlocks_e2e_flag_without_phase9(paper_bundle):
    store, state, package = paper_bundle
    saved = persist_paper_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=state,
        input_signature="sig-phase8-test",
        package=package,
    )
    decision = build_h3_decision(
        status="approved",
        package=(saved.get("decision_report") or {}).get("paper") or package,
        notes="Human H3 approve for tests",
    )
    assert decision.auto_approved is False
    after = persist_h3_decision_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=saved,
        input_signature="sig-phase8-test",
        decision=decision,
    )
    assert after["approval_status"]["h3"] == "approved"
    assert e2e_allowed(after) is True
    assert after["workspace_phases"]["e2e_acceptance"] == "h3_approved_phase9_pending"
    assert after.get("lifecycle") != "research_task_complete"


def test_refuse_auto_approved_h3(paper_bundle):
    store, state, package = paper_bundle
    saved = persist_paper_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=state,
        input_signature="sig-phase8-test",
        package=package,
    )
    with pytest.raises(Exception):
        persist_h3_decision_into_state(
            store,
            project_id="mcm-c-demo",
            project_name="MCM C Demo Project",
            state=saved,
            input_signature="sig-phase8-test",
            decision=H3Decision(
                decision_id="h3d_bad",
                status="approved",
                package_id=package.package_id,
                auto_approved=True,
                decided_by="human",
                decided_at_utc="2026-01-01T00:00:00Z",
            ),
        )


def test_new_attach_resets_h3(paper_bundle):
    store, state, package = paper_bundle
    saved = persist_paper_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=state,
        input_signature="sig-phase8-test",
        package=package,
    )
    approved = persist_h3_decision_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=saved,
        input_signature="sig-phase8-test",
        decision=build_h3_decision(status="approved", package=package, notes="ok"),
    )
    assert approved["approval_status"]["h3"] == "approved"
    # Re-attach must reset H3 to pending.
    again = persist_paper_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=approved,
        input_signature="sig-phase8-test",
        package=package,
    )
    assert again["approval_status"]["h3"] == "pending"
    assert e2e_allowed(again) is False
