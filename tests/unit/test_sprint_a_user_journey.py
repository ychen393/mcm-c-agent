"""Browser-facing Sprint A path (no paid provider calls)."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

from tools.problem_spec_2022_c import load_2022_c_fixture

APP = Path(__file__).resolve().parents[2] / "app" / "main.py"


def _csv():
    dates = [f"2016-09-{d:02d}" for d in range(11, 30)]
    gold_days = [d for d in dates if int(d[-2:]) not in (11, 17, 18, 24, 25)]
    gold = "Date,USD (PM)\n" + "".join(
        f"{day},{1300 + i * 3 + (i % 4) * 2}\n"
        for i, day in enumerate(gold_days)
    )
    btc = "Date,Value\n" + "".join(
        f"{day},{600 + i * 14 - (i % 5) * 18}\n"
        for i, day in enumerate(dates)
    )
    return gold.encode(), btc.encode()


def _button(app, part):
    return next(b for b in app.button if part in b.label)


def test_joint_eda_creates_single_h1_proposal_without_provider_calls(monkeypatch):
    def forbid(*args, **kwargs):
        raise AssertionError("No external provider may be invoked in Sprint A tests")
    monkeypatch.setattr("llm.factory.LLMFactory.create", forbid)
    gold, btc = _csv()
    app = AppTest.from_file(str(APP), default_timeout=90).run()
    problem = next(x for x in app.text_area if "problem statement" in x.label.lower())
    app = problem.set_value(load_2022_c_fixture()).run()
    app = app.file_uploader[0].set_value([
        ("LBMA-GOLD.csv", gold, "text/csv"),
        ("BCHAIN-MKPRU.csv", btc, "text/csv"),
    ]).run()
    app = _button(app, "Initialize project").click().run()
    app = _button(app, "Analyze problem").click().run()
    app = _button(app, "Continue to Stage 2").click().run()
    app = _button(app, "Analyze both markets").click().run()
    assert not app.exception
    joint = app.session_state["eda_insights"]["joint_market"]
    assert joint["common_quote_days"] == 14
    app = _button(app, "Finish EDA").click().run()
    assert not app.exception
    assert app.session_state["last_run"]["eda_report"]["interpreted_findings"]["joint_market"]["common_quote_days"] == 14
    app = _button(app, "Run research team").click().run()
    assert not app.exception
    draft = app.session_state["research_proposal_draft"]
    assert draft["research_decision"]["version"] == "2.0"
    assert 1 <= len(draft["research_decision"]["alternate_candidate_ids"]) + 1 <= 3
    assert app.session_state["last_run"].get("research_proposal") is None  # Explicit submission only
    assert app.session_state["debate_critique_draft"]["proposal_id"] == draft["proposal_id"]
    app = _button(app, "Attach proposal into project state").click().run()
    assert not app.exception
    state = app.session_state["last_run"]
    assert state["research_proposal"]["proposal_id"] == draft["proposal_id"]
    assert state["decision_report"]["critique"]["proposal_id"] == draft["proposal_id"]
    assert state["approval_status"]["h1"] == "pending"
    notes = next(x for x in app.text_area if "Your feedback on this plan" in x.label)
    app = notes.set_value(
        "Please specify how gold market closures alter trading and avoid reusing full-window correlation as a historical signal."
    ).run()
    app = _button(app, "Request revision (H1)").click().run()
    assert not app.exception
    assert app.session_state["last_run"]["approval_status"]["h1"] == "revision_requested"
