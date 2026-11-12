"""Phase 6 experiment persistence + H1 gate on attach."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.modeling_experiment import run_modeling_experiment
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from core.project_store import LocalProjectStore
from modeling.gate import modeling_allowed
from schemas.persistence import sanitize_state_for_persistence
from tools.experiment_persistence import (
    compact_experiment_report,
    persist_experiment_into_state,
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
        input_signature="sig-phase6-test",
        note="bootstrap",
    )
    boot = dict(boot)
    boot["run_id"] = run.run_id
    return boot


@pytest.fixture
def approved_bundle():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    proposal = synthesize_research_proposal(problem_specification=spec, use_llm=False)
    state = {
        "research_proposal": proposal.model_dump(mode="json"),
        "problem_specification": spec.model_dump(mode="json"),
        "approval_status": {"h1": "approved"},
        "decision_report": {
            "h1": {
                "status": "approved",
                "decision_id": "h1d_persist",
                "selected_candidate_id": proposal.recommended_candidate_id,
                "auto_approved": False,
                "decided_by": "human",
            }
        },
    }
    report = run_modeling_experiment(
        state=state,
        problem_specification=spec,
        proposal=proposal,
    )
    return spec, proposal, state, report


def test_compact_report_is_persistence_safe(approved_bundle):
    _spec, _proposal, _state, report = approved_bundle
    compact = compact_experiment_report(report)
    assert compact["invented_results"] is False
    sanitize_state_for_persistence(
        {
            "project_id": "mcm-c-demo",
            "project_name": "MCM C Demo Project",
            "project_status": "initialized",
            "lifecycle": "project_initialized",
            "uploaded_files": [],
            "decision_report": {"experiment": compact},
        }
    )


def test_persist_refused_without_h1(tmp_path: Path, approved_bundle):
    _spec, _proposal, _state, report = approved_bundle
    store = LocalProjectStore(root=tmp_path / "projects")
    boot = _boot_state(store)
    boot["approval_status"] = {"h1": "pending"}
    boot["research_proposal"] = {"proposal_id": "prop_x"}
    with pytest.raises(PermissionError):
        persist_experiment_into_state(
            store,
            project_id="mcm-c-demo",
            project_name="MCM C Demo Project",
            state=boot,
            input_signature="sig-phase6-test",
            report=report,
        )


def test_persist_attaches_logs_and_artifacts(tmp_path: Path, approved_bundle):
    _spec, _proposal, state, report = approved_bundle
    store = LocalProjectStore(root=tmp_path / "projects")
    boot = _boot_state(store)
    boot.update(state)
    assert modeling_allowed(boot) is True
    saved = persist_experiment_into_state(
        store,
        project_id="mcm-c-demo",
        project_name="MCM C Demo Project",
        state=boot,
        input_signature="sig-phase6-test",
        report=report,
    )
    assert saved["workspace_phases"]["strategy_modeling"] == "experiment_recorded"
    assert saved["workspace_phases"]["modeling_experiment"] == "recorded"
    assert saved["experiment_logs"]
    assert saved["model_artifacts"]
    assert (saved.get("decision_report") or {}).get("experiment")
    assert saved["lifecycle"] != "research_task_complete"
    # Sanitized full state should still pass Phase 1 rules.
    sanitize_state_for_persistence(
        {
            "project_id": saved["project_id"],
            "project_name": saved["project_name"],
            "project_status": saved.get("project_status") or "initialized",
            "lifecycle": saved.get("lifecycle") or "project_initialized",
            "uploaded_files": saved.get("uploaded_files") or [],
            "experiment_logs": saved["experiment_logs"],
            "model_artifacts": saved["model_artifacts"],
            "decision_report": saved["decision_report"],
            "approval_status": saved["approval_status"],
        }
    )
