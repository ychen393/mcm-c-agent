"""Typed Problem Analyst step.

The foundation graph stays two nodes and does not call a model. This graph is
the explicit transition datasets_recorded → problem_analysis_running →
problem_analysis_ready or problem_analysis_failed. It does not clear EDA,
approvals, or dataset provenance.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.problem_analyst import ProblemAnalyst
from core.state import ResearchState


def build_problem_analysis_graph(analyst: ProblemAnalyst):
    """Compile the in-memory analysis graph. No checkpointer is attached."""

    def mark_running(state: ResearchState) -> ResearchState:
        entry = state.get("lifecycle") or "datasets_recorded"
        if entry == "problem_analysis_running":
            entry = state.get("analyst_entry_lifecycle") or "datasets_recorded"
        return {
            "lifecycle": "problem_analysis_running",
            "current_stage": "problem_analysis_running",
            "analyst_entry_lifecycle": entry,
        }

    def analyze(state: ResearchState) -> ResearchState:
        return analyst.analyze(dict(state))

    builder = StateGraph(ResearchState)
    builder.add_node("mark_running", mark_running)
    builder.add_node("analyze", analyze)
    builder.add_edge(START, "mark_running")
    builder.add_edge("mark_running", "analyze")
    builder.add_edge("analyze", END)
    graph = builder.compile()
    return graph
