"""A human can reject H1 with written feedback and review a real revised plan."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from streamlit.testing.v1 import AppTest

from tools.problem_spec_2022_c import load_2022_c_fixture

APP_PATH=Path(__file__).resolve().parents[2] / "app" / "main.py"
GOLD=b"Date,USD (PM)\n9/12/2016,1324.60\n9/13/2016,1321.75\n9/14/2016,\n9/15/2016,1308.35\n"
BTC=b"Date,Value\n9/11/2016,621.65\n9/12/2016,609.67\n9/13/2016,610.92\n9/14/2016,608.82\n9/15/2016,610.12\n"


def button(app, name):
    return next(x for x in app.button if name in x.label)


class ReviewLLM:
    def __init__(self):
        self.calls=[]
    def invoke(self,messages):
        self.calls.append(messages)
        if len(self.calls)==1:
            context=json.loads(messages[1]["content"])
            cid=context["candidates"][0]["id"]
            return SimpleNamespace(
                content=json.dumps({
                    "candidate_id":cid,
                    "revised_summary":"Use past-only trailing averages, forbid gold trades on its closed days, and only trade when the forecasted threshold exceeds 1% or 2% transaction fees. Run cash, gold and Bitcoin buy-and-hold as transparent baselines. Compare net terminal wealth and maximum portfolio drawdown on later held-out dates.",
                    "changes_made":"Addressed the user's demand to model gold closures, separate commission rates and a held-out validation period.",
                    "next_tests":["Fee sensitivity","No-lookahead trade timing"],
                    "remaining_risks":["False trend signals may increase trading churn"],
                }),
                provider="fake",model="review-model",
            )
        return SimpleNamespace(
            content="Independent reviewer questions the trend rule's assumptions, asks for a fee-and-calendar counterexample and chronological holdout validation; human H1 remains required.",
            provider="fake",model="review-model",
        )


def test_user_can_write_feedback_and_revise_after_explicit_model_consent(monkeypatch):
    created=[]
    def factory(_settings):
        p=ReviewLLM()
        created.append(p)
        return p
    monkeypatch.setattr("llm.factory.LLMFactory.create",factory)

    app=AppTest.from_file(str(APP_PATH),default_timeout=90).run()
    area=next(x for x in app.text_area if "problem statement" in x.label.lower())
    app=area.set_value(load_2022_c_fixture()).run()
    app=app.file_uploader[0].set_value([
        ("LBMA-GOLD.csv",GOLD,"text/csv"),
        ("BCHAIN-MKPRU.csv",BTC,"text/csv"),
    ]).run()
    app=button(app,"Initialize project").click().run()
    app=button(app,"Analyze problem").click().run()
    app=button(app,"Continue to Stage 2").click().run()
    app=button(app,"Finish EDA").click().run()
    app=button(app,"Run research team").click().run()
    assert not app.exception
    assert len(created)==0

    app=button(app,"Attach proposal into project state").click().run()
    feedback="You ignored the gold market schedule and BTC fees. Revise the assumptions, trade timing and out-of-sample validation."
    text=next(x for x in app.text_area if "Your feedback on this plan" in x.label)
    app=text.set_value(feedback).run()
    app=button(app,"Request revision (H1)").click().run()
    assert not app.exception
    assert app.session_state["last_run"]["approval_status"]["h1"]=="revision_requested"
    assert app.session_state["last_run"]["decision_report"]["h1"]["notes"]==feedback
    assert len(created)==0
    app=app.run()

    # No consent means no provider call; original rejected proposal is preserved.
    app=button(app,"Regenerate from feedback").click().run()
    assert not app.exception
    assert len(created)==0
    assert app.session_state["last_run"]["approval_status"]["h1"]=="revision_requested"

    consent=next(x for x in app.checkbox if "I approve two configured-model" in x.label)
    app=consent.check().run()
    app=button(app,"Regenerate from feedback").click().run()
    assert not app.exception
    assert len(created)==1 and len(created[0].calls)==2
    state=app.session_state["last_run"]
    assert state["approval_status"]["h1"]=="pending"
    history=state["decision_report"]["revision_history"][-1]
    assert history["feedback"]==feedback
    assert history["before"]!=history["after"]
    assert "counterexample" in history["critic_feedback"]
    assert state["model_artifacts"]==[]
    assert state["experiment_logs"]==[]
