"""Phase 7 Validation / Sensitivity agent — H1+experiment gate."""

from __future__ import annotations

import pytest

from agents.modeling_experiment import run_modeling_experiment
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from agents.validation_sensitivity import (
    run_validation_sensitivity,
    validation_sensitivity_status,
)
from tools.problem_spec_2022_c import load_2022_c_fixture


@pytest.fixture
def approved_with_experiment():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    proposal = synthesize_research_proposal(problem_specification=spec, use_llm=False)
    state = {
        "research_proposal": proposal.model_dump(mode="json"),
        "problem_specification": spec.model_dump(mode="json"),
        "approval_status": {"h1": "approved"},
        "decision_report": {
            "h1": {
                "status": "approved",
                "decision_id": "h1d_val",
                "selected_candidate_id": proposal.recommended_candidate_id,
                "auto_approved": False,
                "decided_by": "human",
            }
        },
        "experiment_logs": [],
    }
    experiment = run_modeling_experiment(
        state=state,
        problem_specification=spec,
        proposal=proposal,
    )
    state["decision_report"]["experiment"] = experiment.model_dump(mode="json")
    return spec, proposal, state, experiment


def test_status_advertises_no_auto_approve():
    status = validation_sensitivity_status()
    assert status["requires_h1_approved"] is True
    assert status["requires_experiment_results"] is True
    assert status["h1_auto_approve"] is False
    assert status["h2_auto_approve"] is False
    assert status["paper_requires_h2_approved"] is True
    assert status["live_trading_apis"] is False
    assert status["llm_critique_executes_live_calls"] is False


def test_run_refused_when_h1_absent(approved_with_experiment):
    _spec, _proposal, state, _exp = approved_with_experiment
    state = dict(state)
    state["approval_status"] = {}
    decision = dict(state.get("decision_report") or {})
    decision.pop("h1", None)
    state["decision_report"] = decision
    with pytest.raises(PermissionError):
        run_validation_sensitivity(state=state)


def test_run_refused_when_experiments_missing(approved_with_experiment):
    _spec, proposal, _state, _exp = approved_with_experiment
    state = {
        "research_proposal": proposal.model_dump(mode="json"),
        "approval_status": {"h1": "approved"},
        "decision_report": {"h1": {"status": "approved"}},
        "experiment_logs": [],
    }
    with pytest.raises(PermissionError):
        run_validation_sensitivity(state=state)


def test_run_succeeds_when_gate_open(approved_with_experiment):
    spec, proposal, state, experiment = approved_with_experiment
    report = run_validation_sensitivity(
        state=state,
        problem_specification=spec,
        proposal=proposal,
        use_llm=False,
    )
    assert report.h1_approved is True
    assert report.validation_allowed is True
    assert report.baseline_run_id == experiment.latest_run_id
    assert report.scenarios
    assert report.invented_results is False
