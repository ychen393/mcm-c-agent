import pytest

from core.checkpoint import checkpoint_backend_name
from core.foundation import NOT_IMPLEMENTED
from core.graph import build_foundation_graph
from core.state import new_research_state


def test_foundation_graph_initializes_without_claiming_analysis():
    graph = build_foundation_graph()
    assert graph.checkpointer is None
    assert checkpoint_backend_name() == "in_memory_until_m1"
    result = graph.invoke(new_research_state("p-002", "Graph Test"))
    assert result["project_status"] == "initialized"
    assert result["current_stage"] == "project_initialized"
    assert result["analysis_status"] == "not_started"
    assert result["uploaded_files"] == []
    assert result["workspace_phases"]["datasets_loaded"] == "no"
    assert result["workspace_phases"]["independent_eda"] == "not ready"
    assert result["workspace_phases"]["relationship_preview"] == "not ready"
    assert result["workspace_phases"]["joint_analysis"] == NOT_IMPLEMENTED
    assert result["workspace_phases"]["strategy_modeling"] == NOT_IMPLEMENTED
    assert result["eda_report"] == {}
    assert result["approval_status"] == {}
    assert result["research_proposal"] == {}
    assert result["current_stage"] != "problem_analysis"
    assert result["project_status"] != "ready_for_problem_analysis"


def test_foundation_graph_keeps_provenance_and_clears_stale_products():
    state = new_research_state("p-002", "Graph Test")
    state["uploaded_files"] = [
        {
            "dataset_id": "ds_lbma-gold_abc123abc123",
            "file_name": "LBMA-GOLD.csv",
            "sha256": "a" * 64,
            "row_count": 4,
            "warnings": ["Column 'USD (PM)' has 1 missing values (25.0%)."],
        },
        {
            "dataset_id": "ds_bchain-mkpru_def456def456",
            "file_name": "BCHAIN-MKPRU.csv",
            "sha256": "b" * 64,
            "row_count": 5,
        },
    ]
    state["dataset_metadata"] = {"selection_status": "ready"}
    state["eda_report"] = {"stale": True}
    state["approval_status"] = {"h1": "approved"}
    state["research_proposal"] = {"strategy": "trade gold"}
    state["decision_report"] = {"action": "buy"}
    state["citations"] = [{"title": "stale literature citation"}]
    state["experiment_logs"] = [{"run": "leave this log alone"}]
    result = build_foundation_graph().invoke(state)
    assert result["current_stage"] == "datasets_loaded"
    assert result["analysis_status"] == "not_started"
    assert [item["file_name"] for item in result["uploaded_files"]] == [
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    ]
    assert result["uploaded_files"][0]["joined"] is False
    assert result["dataset_metadata"]["selection_status"] == "ready"
    assert "api_key" not in result["dataset_metadata"]
    assert result["dataset_metadata"]["joined"] is False
    assert result["dataset_metadata"]["raw_rows_included"] is False
    assert result["eda_report"] == {}
    assert result["approval_status"] == {}
    assert result["research_proposal"] == {}
    assert result["decision_report"] == {}
    assert result["citations"] == []
    assert result["experiment_logs"] == [{"run": "leave this log alone"}]
    assert result["workspace_phases"]["independent_eda"] == "ready"
    assert result["workspace_phases"]["relationship_preview"] == "ready"
    assert result["workspace_phases"]["joint_analysis"] == NOT_IMPLEMENTED
    assert result["workspace_phases"]["strategy_modeling"] == NOT_IMPLEMENTED


def test_foundation_graph_clears_stale_phase4_evidence_products():
    """P1: evidence_report + literature citations clear with other derived products."""
    from core.foundation import cleared_derived_products

    cleared = cleared_derived_products()
    assert cleared["evidence_report"] == {}
    assert cleared["citations"] == []
    assert cleared["problem_specification"] == {}
    assert cleared["eda_report"] == {}

    state = new_research_state("p-phase4-clear", "Phase4 Clear Test")
    state["uploaded_files"] = [
        {
            "dataset_id": "ds_lbma-gold_abc123abc123",
            "file_name": "LBMA-GOLD.csv",
            "sha256": "a" * 64,
            "row_count": 4,
        }
    ]
    state["dataset_metadata"] = {"selection_status": "ready"}
    state["problem_specification"] = {"problem_id": "stale_2022_mcm_c"}
    state["eda_report"] = {"stale": True, "mode": "independent_multi"}
    state["evidence_report"] = {
        "problem_id": "stale_lit",
        "cards": [{"card_id": "ec_stale"}],
        "invented_sources": False,
    }
    state["citations"] = [
        {
            "citation_key": "FixtureStale",
            "source_id": "fx_txn_cost_portfolio",
            "verification_status": "verified_fixture",
        }
    ]
    state["experiment_logs"] = [{"run": "keep"}]
    result = build_foundation_graph().invoke(state)
    assert result["problem_specification"] == {}
    assert result["eda_report"] == {}
    assert result["evidence_report"] == {}
    assert result["citations"] == []
    assert result["experiment_logs"] == [{"run": "keep"}]
    assert [item["file_name"] for item in result["uploaded_files"]] == ["LBMA-GOLD.csv"]


def test_foundation_graph_clears_stale_phase5_research_h1_products():
    """Phase 5: proposal / critique / disagreement / H1 clear on foundation rebuild."""
    from core.foundation import cleared_derived_products

    cleared = cleared_derived_products()
    assert cleared["research_proposal"] == {}
    assert cleared["decision_report"] == {}
    assert cleared["disagreement_log"] == []
    assert cleared["approval_status"] == {}

    state = new_research_state("p-phase5-clear", "Phase5 Clear Test")
    state["uploaded_files"] = [
        {
            "dataset_id": "ds_lbma-gold_abc123abc123",
            "file_name": "LBMA-GOLD.csv",
            "sha256": "a" * 64,
            "row_count": 4,
        }
    ]
    state["dataset_metadata"] = {"selection_status": "ready"}
    state["research_proposal"] = {"proposal_id": "prop_stale", "candidates": []}
    state["decision_report"] = {"h1": {"status": "approved", "auto_approved": False}}
    state["disagreement_log"] = [{"finding_id": "cf_stale", "statement": "stale"}]
    state["approval_status"] = {"h1": "approved"}
    state["experiment_logs"] = [{"run": "keep"}]
    result = build_foundation_graph().invoke(state)
    assert result["research_proposal"] == {}
    assert result["decision_report"] == {}
    assert result["disagreement_log"] == []
    assert result["approval_status"] == {}
    assert result["experiment_logs"] == [{"run": "keep"}]


def test_foundation_graph_clears_phase6_model_artifacts_keeps_experiment_logs():
    """Phase 6: model_artifacts clear; experiment_logs stay (Phase 1 durable logs)."""
    from core.foundation import cleared_derived_products

    cleared = cleared_derived_products()
    assert cleared["model_artifacts"] == []
    assert "experiment_logs" not in cleared

    state = new_research_state("p-phase6-clear", "Phase6 Clear Test")
    state["uploaded_files"] = [
        {
            "dataset_id": "ds_lbma-gold_abc123abc123",
            "file_name": "LBMA-GOLD.csv",
            "sha256": "a" * 64,
            "row_count": 4,
        }
    ]
    state["dataset_metadata"] = {"selection_status": "ready"}
    state["model_artifacts"] = [
        {"artifact_id": "art_stale", "kind": "equity_curve_summary", "summary": "stale"}
    ]
    state["experiment_logs"] = [{"run_id": "erun_keep", "status": "completed"}]
    state["decision_report"] = {"experiment": {"report_id": "erep_stale"}}
    state["approval_status"] = {"h1": "approved"}
    result = build_foundation_graph().invoke(state)
    assert result["model_artifacts"] == []
    assert result["experiment_logs"] == [{"run_id": "erun_keep", "status": "completed"}]
    # decision_report / approval clear with derived products (stale H1 cannot survive).
    assert result["decision_report"] == {}
    assert result["approval_status"] == {}


def test_foundation_graph_rejects_secret_bearing_uploaded_files():
    state = new_research_state("p-002", "Graph Test")
    state["uploaded_files"] = [
        {
            "dataset_id": "ds_lbma-gold_abc123abc123",
            "file_name": "LBMA-GOLD.csv",
            "sha256": "a" * 64,
            "authorization": "Bearer secret",
        }
    ]
    with pytest.raises(ValueError, match="forbidden key"):
        build_foundation_graph().invoke(state)
