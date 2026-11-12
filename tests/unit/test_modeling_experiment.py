"""Phase 6 Modeling & Experiment agent — H1 gate + deterministic path."""

from __future__ import annotations

import pytest

from agents.modeling_experiment import (
    modeling_experiment_status,
    run_modeling_experiment,
)
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from schemas.experiment import ExperimentReport
from tools.problem_spec_2022_c import load_2022_c_fixture


@pytest.fixture(scope="module")
def approved_state_and_spec():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    proposal = synthesize_research_proposal(
        problem_specification=spec,
        use_llm=False,
    )
    state = {
        "research_proposal": proposal.model_dump(mode="json"),
        "problem_specification": spec.model_dump(mode="json"),
        "approval_status": {"h1": "approved"},
        "decision_report": {
            "h1": {
                "status": "approved",
                "decision_id": "h1d_fixture",
                "selected_candidate_id": proposal.recommended_candidate_id,
                "auto_approved": False,
                "decided_by": "human",
            }
        },
    }
    return state, spec, proposal


def test_status_advertises_h1_and_no_live_trading():
    status = modeling_experiment_status()
    assert status["requires_h1_approved"] is True
    assert status["h1_auto_approve"] is False
    assert status["live_trading_apis"] is False
    assert status["sandboxed_python_executes_arbitrary_code"] is False


def test_run_refused_without_h1(approved_state_and_spec):
    state, spec, proposal = approved_state_and_spec
    blocked = dict(state)
    blocked["approval_status"] = {"h1": "pending"}
    with pytest.raises(PermissionError):
        run_modeling_experiment(
            state=blocked,
            problem_specification=spec,
            proposal=proposal,
            allow_sandboxed_python=False,
        )


def test_run_refused_when_h1_absent(approved_state_and_spec):
    _state, spec, proposal = approved_state_and_spec
    with pytest.raises(PermissionError):
        run_modeling_experiment(
            state={"research_proposal": proposal.model_dump(mode="json")},
            problem_specification=spec,
            proposal=proposal,
        )


def test_run_succeeds_when_h1_approved(approved_state_and_spec):
    state, spec, proposal = approved_state_and_spec
    report = run_modeling_experiment(
        state=state,
        problem_specification=spec,
        proposal=proposal,
        allow_sandboxed_python=False,
    )
    assert isinstance(report, ExperimentReport)
    assert report.h1_approved is True
    assert report.modeling_allowed is True
    assert report.live_trading_api_used is False
    assert report.invented_results is False
    assert report.latest_run_id
    assert report.runs
    run = report.runs[0]
    assert run.status == "completed"
    assert run.proposal_id == proposal.proposal_id
    assert run.selected_candidate_id == proposal.recommended_candidate_id
    assert run.constraints.problem_id == "2022_mcm_c"
    assert run.sandboxed_python_attempted is False


def test_sandbox_flag_records_stub_note_without_exec(approved_state_and_spec):
    state, spec, proposal = approved_state_and_spec
    report = run_modeling_experiment(
        state=state,
        problem_specification=spec,
        proposal=proposal,
        allow_sandboxed_python=True,
    )
    run = report.runs[0]
    assert run.sandboxed_python_attempted is True
    assert run.sandboxed_python_note
    assert "not enabled" in run.sandboxed_python_note.lower() or "unavailable" in (
        run.sandboxed_python_note.lower()
    )
    # Deterministic path still completed.
    assert run.status == "completed"
    assert run.strategy == "deterministic_fixture"
