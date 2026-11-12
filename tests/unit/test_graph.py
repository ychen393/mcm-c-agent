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
            "raw_bytes": b"Date,USD (PM)\n",
            "sample_values": ["1324.60"],
        },
        {
            "dataset_id": "ds_bchain-mkpru_def456def456",
            "file_name": "BCHAIN-MKPRU.csv",
            "sha256": "b" * 64,
            "row_count": 5,
        },
    ]
    state["dataset_metadata"] = {"selection_status": "ready", "api_key": "sk-secret"}
    state["eda_report"] = {"stale": True}
    state["approval_status"] = {"h1": "approved"}
    state["research_proposal"] = {"strategy": "trade gold"}
    state["decision_report"] = {"action": "buy"}
    state["citations"] = [{"title": "leave this log alone"}]
    state["experiment_logs"] = [{"run": "leave this log alone"}]
    result = build_foundation_graph().invoke(state)
    assert result["current_stage"] == "datasets_loaded"
    assert result["analysis_status"] == "not_started"
    assert [item["file_name"] for item in result["uploaded_files"]] == [
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    ]
    blob = repr(result["uploaded_files"])
    assert "1324.60" not in blob
    assert "raw_bytes" not in result["uploaded_files"][0]
    assert "sample_values" not in result["uploaded_files"][0]
    assert result["uploaded_files"][0]["joined"] is False
    assert result["dataset_metadata"]["selection_status"] == "ready"
    assert "api_key" not in result["dataset_metadata"]
    assert result["dataset_metadata"]["joined"] is False
    assert result["dataset_metadata"]["raw_rows_included"] is False
    assert result["eda_report"] == {}
    assert result["approval_status"] == {}
    assert result["research_proposal"] == {}
    assert result["decision_report"] == {}
    assert result["citations"] == [{"title": "leave this log alone"}]
    assert result["experiment_logs"] == [{"run": "leave this log alone"}]
    assert result["workspace_phases"]["independent_eda"] == "ready"
    assert result["workspace_phases"]["relationship_preview"] == "ready"
    assert result["workspace_phases"]["joint_analysis"] == NOT_IMPLEMENTED
    assert result["workspace_phases"]["strategy_modeling"] == NOT_IMPLEMENTED
