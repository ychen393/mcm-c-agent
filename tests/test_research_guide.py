from app.research_guide import STAGES, stage_index


def test_all_existing_steps_map_to_six_user_stages():
    expected = {'project': 0, 'problem': 0, 'eda': 1, 'literature': 2, 'h1': 2, 'modeling': 3, 'h2': 4, 'paper': 5, 'export': 5}
    assert len(STAGES) == 6
    assert {key: stage_index(key) for key in expected} == expected


def test_every_stage_explains_goal_output_and_action():
    assert all(s.title and s.purpose and s.deliverable and s.action for s in STAGES)


def test_no_stage_is_complete_without_recorded_research_state():
    from app.research_guide import completed_stage_indices
    assert completed_stage_indices(None) == set()
    assert completed_stage_indices({}) == set()


def test_project_alone_is_not_a_completed_problem_stage():
    from app.research_guide import completed_stage_indices
    assert 0 not in completed_stage_indices({'project_id': 'test'})
