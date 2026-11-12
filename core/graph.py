"""Two-node project initialization graph.

``intake`` and ``foundation_check`` record that a project exists and whether
validated dataset provenance is attached. They do not analyze the problem,
join files, call a model, or write a research checkpoint.
"""

from langgraph.graph import END, START, StateGraph

from core.foundation import (
    ANALYSIS_NOT_STARTED,
    PROJECT_STATUS_INITIALIZED,
    STAGE_DATASETS_LOADED,
    STAGE_PROJECT_INITIALIZED,
    cleared_derived_products,
    sanitize_metadata,
    sanitize_uploaded_files,
    workspace_phases,
)
from core.state import ResearchState


def intake_node(state: ResearchState) -> ResearchState:
    return {
        "project_status": PROJECT_STATUS_INITIALIZED,
        "current_stage": STAGE_PROJECT_INITIALIZED,
        "analysis_status": ANALYSIS_NOT_STARTED,
    }


def foundation_check_node(state: ResearchState) -> ResearchState:
    files = sanitize_uploaded_files(state.get("uploaded_files"))
    update: ResearchState = {
        "project_status": PROJECT_STATUS_INITIALIZED,
        "current_stage": STAGE_DATASETS_LOADED if files else STAGE_PROJECT_INITIALIZED,
        "analysis_status": ANALYSIS_NOT_STARTED,
        "workspace_phases": workspace_phases(len(files)),
        "uploaded_files": files,
        "dataset_metadata": sanitize_metadata(state.get("dataset_metadata")),
    }
    update.update(cleared_derived_products())
    return update


def build_foundation_graph():
    """Compile the in-memory initialization graph. No checkpointer is attached."""
    builder = StateGraph(ResearchState)
    builder.add_node("intake", intake_node)
    builder.add_node("foundation_check", foundation_check_node)
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "foundation_check")
    builder.add_edge("foundation_check", END)
    return builder.compile()
