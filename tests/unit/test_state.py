from core.state import new_research_state


def test_new_research_state_has_expected_defaults():
    state = new_research_state('p-001', 'Test Project')
    assert state['project_id'] == 'p-001'
    assert state['project_name'] == 'Test Project'
    assert state['project_status'] == 'created'
    assert state['uploaded_files'] == []
    assert state['analysis_status'] == 'not_started'
    assert state['errors'] == []
