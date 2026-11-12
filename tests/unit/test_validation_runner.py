"""Phase 7 deterministic sensitivity runner tests (offline)."""

from __future__ import annotations

from agents.modeling_experiment import run_modeling_experiment
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from tools.problem_spec_2022_c import load_2022_c_fixture
from validation.runner import execute_validation_report


def _baseline_experiment():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    proposal = synthesize_research_proposal(problem_specification=spec, use_llm=False)
    state = {
        "research_proposal": proposal.model_dump(mode="json"),
        "problem_specification": spec.model_dump(mode="json"),
        "approval_status": {"h1": "approved"},
        "decision_report": {
            "h1": {
                "status": "approved",
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
        strategy_id="trend_follow_bitcoin",
        lookback_days=3,
        rebalance_every_n_days=5,
    )
    return spec, proposal, report


def test_execute_validation_report_is_deterministic():
    spec, proposal, experiment = _baseline_experiment()
    exp_dict = experiment.model_dump(mode="json")
    first = execute_validation_report(
        experiment=exp_dict,
        proposal_id=proposal.proposal_id,
        selected_candidate_id=proposal.recommended_candidate_id or proposal.candidates[0].candidate_id,
        problem_specification=spec,
        llm_enabled=False,
    )
    second = execute_validation_report(
        experiment=exp_dict,
        proposal_id=proposal.proposal_id,
        selected_candidate_id=proposal.recommended_candidate_id or proposal.candidates[0].candidate_id,
        problem_specification=spec,
        llm_enabled=False,
    )
    assert first.baseline_run_id == second.baseline_run_id
    assert [s.scenario_id for s in first.scenarios] == [
        s.scenario_id for s in second.scenarios
    ]
    for a, b in zip(first.scenarios, second.scenarios, strict=True):
        assert [m.value for m in a.metrics] == [m.value for m in b.metrics]


def test_scenarios_cover_cost_and_window_kinds():
    spec, proposal, experiment = _baseline_experiment()
    report = execute_validation_report(
        experiment=experiment.model_dump(mode="json"),
        proposal_id=proposal.proposal_id,
        selected_candidate_id=proposal.recommended_candidate_id or proposal.candidates[0].candidate_id,
        problem_specification=spec,
    )
    kinds = {s.kind for s in report.scenarios}
    assert "cost" in kinds
    assert "window" in kinds
    assert "param" in kinds or "combined" in kinds
    assert report.invented_results is False
    assert report.live_trading_api_used is False
    assert report.robustness_notes
    assert all(not s.invented_results for s in report.scenarios)


def test_llm_flag_records_stub_note_without_live_calls():
    spec, proposal, experiment = _baseline_experiment()
    report = execute_validation_report(
        experiment=experiment.model_dump(mode="json"),
        proposal_id=proposal.proposal_id,
        selected_candidate_id=proposal.recommended_candidate_id or proposal.candidates[0].candidate_id,
        problem_specification=spec,
        llm_enabled=True,
    )
    assert report.llm_attempted is True
    assert report.llm_enabled is False
    assert report.llm_note
    assert report.strategy == "deterministic_fixture"
