from langgraph.graph import END, START, StateGraph
from core.state import ResearchState

def intake_node(state: ResearchState) -> ResearchState:
    return {'project_status': 'initialized', 'current_stage': 'foundation_check'}
def foundation_check_node(state: ResearchState) -> ResearchState:
    return {'project_status': 'ready_for_problem_analysis', 'current_stage': 'problem_analysis'}
def build_foundation_graph():
    builder = StateGraph(ResearchState)
    builder.add_node('intake', intake_node); builder.add_node('foundation_check', foundation_check_node)
    builder.add_edge(START, 'intake'); builder.add_edge('intake', 'foundation_check'); builder.add_edge('foundation_check', END)
    return builder.compile()
