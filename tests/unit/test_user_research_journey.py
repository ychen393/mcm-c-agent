"""End-user research path: interpret → explain EDA → save → Strategist/Critic."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from tools.problem_spec_2022_c import load_2022_c_fixture

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"

GOLD = (
    b"Date,USD (PM)\n9/12/2016,1324.60\n9/13/2016,1321.75\n"
    b"9/14/2016,\n9/15/2016,1308.35\n"
)
BTC = (
    b"Date,Value\n9/11/2016,621.65\n9/12/2016,609.67\n"
    b"9/13/2016,610.92\n9/14/2016,608.82\n9/15/2016,610.12\n"
)


def _button(at, text):
    return next(b for b in at.button if text in b.label)


def test_full_offline_problem_to_eda_to_research_team_is_navigable():
    app = AppTest.from_file(str(APP_PATH), default_timeout=90).run()
    assert not app.exception
    problem_input = next(a for a in app.text_area if "problem statement" in a.label.lower())
    app = problem_input.set_value(load_2022_c_fixture()).run()
    app = app.file_uploader[0].set_value([
        ("LBMA-GOLD.csv", GOLD, "text/csv"),
        ("BCHAIN-MKPRU.csv", BTC, "text/csv"),
    ]).run()
    app = _button(app, "Initialize project").click().run()
    assert not app.exception

    app = _button(app, "Analyze problem").click().run()
    assert not app.exception
    assert app.session_state["last_run"]["problem_specification"]
    assert not app.session_state["last_run"].get("research_proposal")

    app = _button(app, "Continue to Stage 2").click().run()
    assert not app.exception
    assert app.session_state["guided_stage_preview"] == 1
    assert app.session_state["eda_insights"]["datasets"][0]["valid_prices"] == 3
    assert len(app.session_state["eda_insights"]["datasets"]) == 2

    app = _button(app, "Finish EDA").click().run()
    assert not app.exception
    saved = app.session_state["last_run"]
    assert saved["eda_report"]["interpreted_findings"]["datasets"][0]["valid_prices"] == 3
    assert saved["workspace_phases"]["independent_eda"] == "done"

    app = _button(app, "Run research team").click().run()
    assert not app.exception
    assert app.session_state.get("research_proposal_draft")
    assert app.session_state.get("debate_critique_draft")
    assert app.session_state["last_run"]["approval_status"].get("h1") != "approved"
