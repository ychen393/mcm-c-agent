"""Real uploaded 2022 MCM C CSV regression — no live network or paid LLM."""
from __future__ import annotations

import pytest

from agents.modeling_experiment import run_modeling_experiment
from agents.paper_planner import run_paper_planner
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from agents.validation_sensitivity import run_validation_sensitivity
from modeling.uploaded_prices import prepare_uploaded_2022_prices
from tools.problem_spec_2022_c import load_2022_c_fixture


GOLD = b"Date,USD (PM)\n2022-01-07,1800\n2022-01-10,1810\n"
BITCOIN = (
    b"Date,Value\n2022-01-06,40000\n2022-01-07,40100\n"
    b"2022-01-08,40200\n2022-01-09,40300\n2022-01-10,40400\n"
)


def _research_state():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    proposal = synthesize_research_proposal(
        problem_specification=spec, use_llm=False
    )
    return spec, proposal, {
        "research_proposal": proposal.model_dump(mode="json"),
        "problem_specification": spec.model_dump(mode="json"),
        "approval_status": {"h1": "approved"},
        "decision_report": {
            "h1": {
                "status": "approved",
                "decision_id": "h1d_real_test",
                "selected_candidate_id": proposal.recommended_candidate_id,
                "auto_approved": False,
                "decided_by": "human",
            }
        },
    }


def _model_and_validate():
    spec, proposal, state = _research_state()
    prepared = prepare_uploaded_2022_prices(GOLD, BITCOIN)
    bars = list(prepared.bars)
    sha = {"gold": prepared.gold_sha256, "bitcoin": prepared.bitcoin_sha256}
    experiment = run_modeling_experiment(
        state=state,
        problem_specification=spec,
        proposal=proposal,
        strategy_id="buy_hold_bitcoin",
        price_bars=bars,
        price_sha256=sha,
    )
    state["decision_report"]["experiment"] = experiment.model_dump(mode="json")
    validation = run_validation_sensitivity(
        state=state,
        problem_specification=spec,
        proposal=proposal,
        price_bars=bars,
        price_sha256=sha,
        use_llm=False,
    )
    return spec, proposal, state, experiment, validation, bars, sha


def test_real_data_model_and_sensitivity_keep_same_provenance():
    spec, proposal, state, experiment, validation, bars, sha = _model_and_validate()
    assert experiment.strategy == "deterministic_uploaded_csv"
    run = experiment.runs[0]
    assert run.strategy == "deterministic_uploaded_csv"
    assert run.params.extra["gold_sha256"] == sha["gold"]
    assert run.params.extra["bitcoin_sha256"] == sha["bitcoin"]
    assert run.params.extra["n_bars"] == 5
    assert any(
        art.kind == "price_upload_ref" and art.payload.get("is_synthetic") is False
        for art in run.artifacts
    )
    assert validation.strategy == "deterministic_uploaded_csv"
    assert validation.baseline_run_id == run.run_id
    assert len(validation.scenarios) >= 4
    assert validation.scenarios[0].baseline_run_id == run.run_id
    assert state["approval_status"].get("h2") != "approved"


def test_real_validation_rejects_missing_or_modified_uploads():
    spec, proposal, state, experiment, validation, bars, sha = _model_and_validate()
    with pytest.raises(ValueError, match="Re-upload"):
        run_validation_sensitivity(
            state=state,
            problem_specification=spec,
            proposal=proposal,
        )
    with pytest.raises(ValueError, match="SHA-256"):
        run_validation_sensitivity(
            state=state,
            problem_specification=spec,
            proposal=proposal,
            price_bars=bars,
            price_sha256={**sha, "bitcoin": "f" * 64},
        )


def test_paper_draft_includes_actual_metrics_and_dataset_hashes():
    spec, proposal, state, experiment, validation, bars, sha = _model_and_validate()
    state["validation_report"] = validation.model_dump(mode="json")
    state["approval_status"]["h2"] = "approved"
    state["decision_report"]["h2"] = {"status": "approved"}
    package = run_paper_planner(
        state=state,
        problem_specification=spec,
        use_llm=False,
        attempt_pdf_compile=False,
    )
    assert package.outline.strategy == "deterministic_uploaded_csv"
    data_section = next(s for s in package.outline.sections if s.kind == "data")
    results_section = next(s for s in package.outline.sections if s.kind == "results")
    assert sha["gold"] in data_section.summary
    assert sha["bitcoin"] in data_section.summary
    assert "Recorded metrics:" in results_section.summary
    assert package.latex is not None
    assert package.outline.h2_approved
    assert state["approval_status"].get("h3") != "approved"


def test_paper_refuses_stale_real_data_validation_for_other_run():
    spec, proposal, state, experiment, validation, bars, sha = _model_and_validate()
    stale = validation.model_dump(mode="json")
    stale["baseline_run_id"] = "erun_unrelated"
    state["validation_report"] = stale
    state["approval_status"]["h2"] = "approved"
    state["decision_report"]["h2"] = {"status": "approved"}
    with pytest.raises(ValueError, match="same baseline experiment"):
        run_paper_planner(
            state=state,
            problem_specification=spec,
            use_llm=False,
            attempt_pdf_compile=False,
        )
