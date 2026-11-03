from core.graph import build_foundation_graph
from core.state import new_research_state
def test_foundation_graph_runs_end_to_end():
    result = build_foundation_graph().invoke(new_research_state('p-002', 'Graph Test'))
    assert result['project_status'] == 'ready_for_problem_analysis'
    assert result['current_stage'] == 'problem_analysis'
