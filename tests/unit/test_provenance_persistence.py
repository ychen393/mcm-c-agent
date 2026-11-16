"""Persistence must bind historic inputs to the run and invalidate downstream gates."""
from __future__ import annotations

from agents.modeling_experiment import run_modeling_experiment
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from agents.validation_sensitivity import run_validation_sensitivity
from core.project_store import LocalProjectStore
from modeling.uploaded_prices import prepare_uploaded_2022_prices
from tools.experiment_persistence import persist_experiment_into_state
from tools.problem_spec_2022_c import load_2022_c_fixture
from tools.validation_persistence import persist_validation_into_state

GOLD = b"Date,USD (PM)\n2022-01-07,1800\n2022-01-10,1810\n"
BTC = b"Date,Value\n2022-01-07,40000\n2022-01-08,41000\n2022-01-09,42000\n2022-01-10,43000\n"


def _state(store):
    baseline = {
        "project_id": "real-csv-regression",
        "project_name": "Historical CSV regression",
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
    _project, run, saved = store.save_project_state(
        project_id="real-csv-regression",
        project_name="Historical CSV regression",
        state=baseline, input_signature="real-data-hash-regression", note="init",
    )
    saved = dict(saved)
    saved["run_id"] = run.run_id
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    proposal = synthesize_research_proposal(problem_specification=spec, use_llm=False)
    saved["problem_specification"] = spec.model_dump(mode="json")
    saved["research_proposal"] = proposal.model_dump(mode="json")
    saved["approval_status"] = {"h1": "approved", "h2": "approved", "h3": "approved"}
    saved["validation_report"] = {"report_id": "old_validation"}
    saved["paper_outline"] = {"outline_id": "old_paper"}
    saved["latex_source"] = "old latex"
    saved["decision_report"] = {
        "h1": {"status": "approved", "selected_candidate_id": proposal.recommended_candidate_id,
               "decided_by": "human", "auto_approved": False},
        "h2": {"status": "approved"},
        "h3": {"status": "approved"},
        "paper": {"package_id": "old"},
    }
    return saved, spec, proposal


def test_real_experiment_persisted_with_hashes_and_h2_h3_reset(tmp_path):
    store = LocalProjectStore(tmp_path / "projects")
    state, spec, proposal = _state(store)
    prices = prepare_uploaded_2022_prices(GOLD, BTC)
    sha = {"gold": prices.gold_sha256, "bitcoin": prices.bitcoin_sha256}
    experiment = run_modeling_experiment(
        state=state, problem_specification=spec, proposal=proposal,
        price_bars=list(prices.bars), price_sha256=sha, strategy_id="buy_hold_bitcoin",
    )
    saved = persist_experiment_into_state(
        store, project_id="real-csv-regression", project_name="Historical CSV regression",
        state=state, input_signature="real-data-hash-regression", report=experiment,
    )
    assert saved["approval_status"]["h2"] == "pending"
    assert saved["approval_status"]["h3"] == "pending"
    assert saved.get("validation_report") is None
    assert saved.get("paper_outline") is None
    assert "paper" not in saved["decision_report"]
    assert saved["decision_report"]["experiment"]["strategy"] == "deterministic_uploaded_csv"
    assert saved["decision_report"]["experiment"]["runs"][0]["params"]["extra"]["gold_sha256"] == sha["gold"]

    validation = run_validation_sensitivity(
        state=saved, problem_specification=spec, proposal=proposal,
        price_bars=list(prices.bars), price_sha256=sha, use_llm=False,
    )
    saved["approval_status"]["h3"] = "approved"
    saved["decision_report"]["h3"] = {"status": "approved"}
    saved["paper_outline"] = {"outline_id": "stale"}
    validated = persist_validation_into_state(
        store, project_id="real-csv-regression", project_name="Historical CSV regression",
        state=saved, input_signature="real-data-hash-regression", report=validation,
    )
    assert validated["approval_status"]["h2"] == "pending"
    assert validated["approval_status"]["h3"] == "pending"
    assert validated.get("paper_outline") is None
    assert "h3" not in validated["decision_report"]
    assert validated["validation_report"]["strategy"] == "deterministic_uploaded_csv"
