"""UX-A: dynamic lab progress chrome derived from gates / workspace_phases."""

from __future__ import annotations

from app.progress_chrome import (
    STEP_ORDER,
    current_step_from_state,
    derive_progress_chrome,
    completed_steps_from_state,
)


def test_empty_state_is_project_intake():
    chrome = derive_progress_chrome(None)
    assert chrome.current_step == "project"
    assert chrome.milestone_metric == "Project"
    assert "Phase 5" not in chrome.sidebar_badge
    assert "Workflow nodes" not in chrome.progress_metric
    assert "Phase 6 not started" not in chrome.caption
    assert chrome.progress_metric == f"0/{len(STEP_ORDER)} steps"


def test_initialized_without_spec_is_problem_stage():
    state = {
        "run_id": "run_1",
        "project_id": "demo",
        "workspace_phases": {
            "project_initialized": "yes",
            "datasets_loaded": "yes",
            "independent_eda": "ready",
            "relationship_preview": "ready",
            "joint_analysis": "NOT IMPLEMENTED",
            "strategy_modeling": "NOT IMPLEMENTED",
        },
        "problem_specification": {},
    }
    assert current_step_from_state(state) == "problem"
    assert completed_steps_from_state(state) == ("project",)
    chrome = derive_progress_chrome(state)
    assert "Problem" in chrome.sidebar_badge
    assert chrome.progress_metric.startswith("1/")


def test_h1_approved_moves_to_modeling_not_phase5():
    state = {
        "run_id": "run_2",
        "project_id": "demo",
        "workspace_phases": {
            "project_initialized": "yes",
            "datasets_loaded": "yes",
            "independent_eda": "done",
            "literature_evidence": "recorded",
            "research_strategy": "h1_approved",
            "h1": "approved",
            "strategy_modeling": "h1_approved_phase6_pending",
            "joint_analysis": "NOT IMPLEMENTED",
        },
        "problem_specification": {"problem_id": "2022_mcm_c", "title": "Trading"},
        "eda_report": {"report_id": "eda_1"},
        "evidence_report": {"report_id": "ev_1"},
        "research_proposal": {"proposal_id": "rp_1"},
        "approval_status": {"h1": "approved"},
        "decision_report": {"h1": {"status": "approved"}},
    }
    assert current_step_from_state(state) == "modeling"
    assert completed_steps_from_state(state) == (
        "project",
        "problem",
        "eda",
        "literature",
        "h1",
    )
    chrome = derive_progress_chrome(state)
    assert chrome.milestone_metric == "Modeling"
    assert "Modeling" in chrome.sidebar_badge
    assert "Phase 5" not in chrome.sidebar_badge
    assert "Phase 6 not started" not in chrome.caption
    assert "h1_approved_phase6_pending" in chrome.caption


def test_h3_approved_reaches_export():
    state = {
        "run_id": "run_3",
        "project_id": "demo",
        "workspace_phases": {
            "project_initialized": "yes",
            "independent_eda": "done",
            "literature_evidence": "recorded",
            "h1": "approved",
            "strategy_modeling": "experiment_recorded",
            "h2": "approved",
            "paper_latex": "h3_approved",
            "h3": "approved",
            "e2e_acceptance": "h3_approved_phase9_pending",
        },
        "problem_specification": {"problem_id": "p", "title": "t"},
        "eda_report": {"report_id": "eda"},
        "evidence_report": {"report_id": "ev"},
        "research_proposal": {"proposal_id": "rp"},
        "paper_outline": {"outline_id": "out_1"},
        "approval_status": {"h1": "approved", "h2": "approved", "h3": "approved"},
        "decision_report": {
            "h1": {"status": "approved"},
            "h2": {"status": "approved"},
            "h3": {"status": "approved"},
            "experiment": {
                "report_id": "exp_1",
                "latest_run_id": "run_exp",
                "runs": [{"run_id": "run_exp", "status": "completed", "metrics": {"sharpe": 1.0}}],
            },
            "paper": {"package_id": "pkg_1"},
        },
    }
    assert current_step_from_state(state) == "export"
    assert "export" in completed_steps_from_state(state)
    chrome = derive_progress_chrome(state)
    assert chrome.milestone_metric == "Export"
    assert "[x] Export" in chrome.stepper_line or chrome.progress_metric.startswith(
        f"{len(STEP_ORDER)}/"
    )
