from app.research_guide import STAGES, stage_index


def test_all_existing_steps_map_to_six_user_stages():
    expected = {'project': 0, 'problem': 0, 'eda': 1, 'literature': 2, 'h1': 2, 'modeling': 3, 'h2': 4, 'paper': 5, 'export': 5}
    assert len(STAGES) == 6
    assert {key: stage_index(key) for key in expected} == expected


def test_every_stage_explains_goal_output_and_action():
    assert all(s.title and s.purpose and s.deliverable and s.action for s in STAGES)
