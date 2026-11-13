"""Phase 7 validation persistence + H2 gate on attach / paper."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.modeling_experiment import run_modeling_experiment
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from agents.validation_sensitivity import run_validation_sensitivity
from core.project_store import LocalProjectStore
from schemas.persistence import sanitize_state_for_persistence
from schemas.validation import H2Decision
from tools.problem_spec_2022_c import load_2022_c_fixture
from tools.validation_persistence import (
    build_h2_decision,
    compact_validation_report,
    persist_h2_decision_into_state,
    persist_validation_into_state,
)
from validation.gate import paper_allowed, validation_allowed


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
        input_signature="sig-phase7-test",
        note="bootstrap",
    )
    boot = dict(boot)
    boot["run_id"] = run.run_id
    return boot


@pytest.fixture
def validation_bundle(tmp_path: Path):
    store = LocalProjectStore(tmp_path / "projects")
    boot = _boot_state(store)
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    proposal = synthesize_research_proposal(problem_specification=spec, use_llm=False)
    state = dict(boot)
    state["research_proposal"] = proposal.model_dump(mode="json")
    state["problem_specification"] = spec.model_dump(mode="json")
    state["approval_status"] = {"h1": "approved"}
    state["decision_report"] = {
        "h1": {
            "status": "approved",
            "decision_id": "h1d_persist7",
            "selected_candidate_id": proposal.recommended_candidate_id,
            "auto_approved": False,
            "decided_by": "human",
        }
    }
    experiment = run_modeling_experiment(
        state=state,
        problem_specification=spec,
        proposal=proposal,
    )
    state["decision_report"]["experiment"] = experiment.model_dump(mode="json")
    report = run_validation_sensitivity(
        state=state,
        problem_specification=spec,
        proposal=proposal,
    )
    return store, state, report


def test_compact_report_is_persistence_safe(validation_bundle):
    _store, _state, report = validation_bundle
    compact = compact_validation_report(report)
    assert compact["invented_results"] is False
    sanitize_state_for_persistence(
        {
            "project_id": "mcm-c-demo",
            "project_name": "MCM C Demo Project",
            "project_status": "initialized",
            "lifecycle": "project_initialized",
            "uploaded_files": [],
            "validation_report": compact,
            "decision_report": {"validation": compact},
        }
    )


def test_persist_refused_without_gate(tmp_path: Path, validation_bundle):
    store, _state, report = validation_bundle
    blocked = _boot_state(store)
    blocked["approval_status"] = {"h1": "pending"}
    with pytest.raises(PermissionError):
        persist_validation_into_state(
            store,
            project_id="mcm-c-demo",
            project_name="MCM C Demo Project",
            state=blocked,
            input_signature="sig-phase7-test",
            report=report,
        )


def test_persist_sets_h2_pending_and_blocks_paper(validation_bundle):
    store, state, report = validation_bundle
    assert validation_allowed(state) is True
    saved = persist_validation_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=state,
        input_signature="sig-phase7-test",
        report=report,
    )
    assert saved["validation_report"]["report_id"] == report.report_id
    assert saved["approval_status"]["h2"] == "pending"
    assert paper_allowed(saved) is False
    assert saved["workspace_phases"]["h2"] == "pending"
    assert saved["workspace_phases"]["paper_latex"] == "blocked_until_h2"
    assert ((saved.get("decision_report") or {}).get("paper_gate") or {}).get(
        "paper_allowed"
    ) is False


def test_build_h2_decision_accepts_compact_report_dict(validation_bundle):
    """Attach persists report_version; Approve must re-validate that compact dict."""
    _store, _state, report = validation_bundle
    compact = compact_validation_report(report)
    assert "report_version" in compact
    decision = build_h2_decision(
        status="approved",
        report=compact,
        notes="Approve from compact validation payload.",
    )
    assert decision.status == "approved"
    assert decision.auto_approved is False


def test_h2_approve_sets_paper_gate_flag_only(validation_bundle):
    store, state, report = validation_bundle
    saved = persist_validation_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=state,
        input_signature="sig-phase7-test",
        report=report,
    )
    decision = build_h2_decision(
        status="approved",
        report=saved["validation_report"],
        notes="Human H2 approve for test",
    )
    after = persist_h2_decision_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=saved,
        input_signature="sig-phase7-test",
        decision=decision,
    )
    assert after["approval_status"]["h2"] == "approved"
    assert paper_allowed(after) is True
    assert after["workspace_phases"]["paper_latex"] == "h2_approved_phase8_pending"
    assert after.get("research_task_complete") is None
    assert not after.get("paper_outline")


def test_refuse_auto_approved_h2_payload():
    with pytest.raises(Exception):
        H2Decision.model_validate(
            {
                "decision_id": "h2d_bad",
                "status": "approved",
                "validation_report_id": "vrep_x",
                "decided_by": "human",
                "auto_approved": True,
                "decided_at_utc": "2026-11-12T00:00:00Z",
            }
        )
