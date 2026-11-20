"""H2/H3 real feedback loops: two mocked provider calls, actual engine recomputes.

No test invokes a paid model or new datasets; regression protects approval gates,
provenance and version history.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agents.modeling_experiment import run_modeling_experiment
from agents.paper_planner import run_paper_planner
from agents.paper_revision import revise_paper_with_feedback
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from agents.validation_revision import revise_validation_with_feedback
from agents.validation_sensitivity import run_validation_sensitivity
from core.config import get_settings
from core.project_store import LocalProjectStore
from modeling.uploaded_prices import prepare_uploaded_2022_prices
from tools.paper_persistence import persist_paper_into_state
from tools.problem_spec_2022_c import load_2022_c_fixture
from tools.validation_persistence import persist_validation_into_state

GOLD=b"Date,USD (PM)\n2022-01-07,1800\n2022-01-10,1810\n"
BTC=b"Date,Value\n2022-01-06,40000\n2022-01-07,40100\n2022-01-08,40200\n2022-01-09,40300\n2022-01-10,40400\n"


def _study():
    spec=analyze_problem(load_2022_c_fixture(),use_llm=False)
    proposal=synthesize_research_proposal(problem_specification=spec,use_llm=False)
    prepared=prepare_uploaded_2022_prices(GOLD,BTC)
    bars=list(prepared.bars)
    sha={"gold":prepared.gold_sha256,"bitcoin":prepared.bitcoin_sha256}
    state={
        "project_id":"review-2022-test",
        "project_name":"Review regression",
        "project_status":"initialized",
        "lifecycle":"data_analysis_done",
        "analysis_status":"data_analysis_done",
        "uploaded_files":[],"model_artifacts":[],"experiment_logs":[],
        "workspace_phases":{},"citations":[],"errors":[],
        "data_resume":"reupload_required",
        "problem_specification":spec.model_dump(mode="json"),
        "research_proposal":proposal.model_dump(mode="json"),
        "approval_status":{"h1":"approved"},
        "decision_report":{"h1":{"status":"approved","selected_candidate_id":proposal.recommended_candidate_id}},
    }
    experiment=run_modeling_experiment(
        state=state,problem_specification=spec,proposal=proposal,
        strategy_id="buy_hold_bitcoin",price_bars=bars,price_sha256=sha)
    state["decision_report"]["experiment"]=experiment.model_dump(mode="json")
    report=run_validation_sensitivity(
        state=state,problem_specification=spec,proposal=proposal,
        price_bars=bars,price_sha256=sha,use_llm=False)
    state["validation_report"]=report.model_dump(mode="json")
    return state,report,bars,sha


class FakeH2:
    def __init__(self,invalid=False):
        self.calls=[]
        self.invalid=invalid
    def invoke(self,messages):
        self.calls.append(messages)
        if len(self.calls)==1:
            plan={"scenarios":[{"target":"alpha_bitcoin","value":0.03,
                    "rationale":"Test higher Bitcoin transaction fees to address the review"}],
                  "changes_made":"Added a requested Bitcoin commission stress case and recomputed the same historical strategy."}
            if self.invalid: plan["scenarios"][0]["target"]="fake_trade_strategy"
            return SimpleNamespace(content=json.dumps(plan),provider="mock",model="h2-review")
        return SimpleNamespace(content=(
            "Independent H2 critic: the new 3 percent stress scenario was actually computed, "
            "but its in-sample effect does not demonstrate out-of-sample advantage or optimality."
        ),provider="mock",model="h2-review")


def test_h2_feedback_recomputes_real_data_and_persists_history(tmp_path):
    state,old,bars,sha=_study()
    feedback="Please rerun with a 3 percent Bitcoin fee and compare net portfolio outcomes."
    state["approval_status"]["h2"]="revision_requested"
    state["decision_report"]["h2"]={"status":"revision_requested","notes":feedback}
    mock=FakeH2()
    revised,audit=revise_validation_with_feedback(
        state=state,feedback=feedback,report=old,settings=get_settings(),
        price_bars=bars,price_sha256=sha,llm=mock,language="en")
    assert len(mock.calls)==2
    assert revised.report_id != old.report_id
    assert revised.baseline_run_id == old.baseline_run_id
    assert len(revised.scenarios)==len(old.scenarios)+1
    added=revised.scenarios[-1]
    assert added.perturbations[0].target=="alpha_bitcoin"
    assert added.perturbations[0].scenario_value==0.03
    assert added.metrics and added.invented_results is False
    assert added.scenario_id.startswith("scn_feedback_")
    assert old.scenarios[-1].scenario_id != added.scenario_id

    store=LocalProjectStore(tmp_path/"projects")
    _p,run,saved=store.save_project_state(
        project_id=state["project_id"],project_name=state["project_name"],
        state=state,input_signature="review-sig",note="boot")
    final=persist_validation_into_state(
        store,project_id=state["project_id"],project_name=state["project_name"],
        state=dict(saved,run_id=run.run_id),input_signature="review-sig",
        report=revised,revision_record=audit)
    assert final["approval_status"]["h2"]=="pending"
    assert final["approval_status"]["h3"]=="pending"
    assert final["decision_report"]["h2_revision_history"][-1]["feedback"]==feedback
    assert final["decision_report"]["validation"]["report_id"]==revised.report_id


def test_h2_does_not_claim_recomputation_for_unsupported_requests_or_wrong_csv():
    state,old,bars,sha=_study()
    state["approval_status"]["h2"]="revision_requested"
    state["decision_report"]["h2"]={"status":"revision_requested","notes":"test"}
    mock=FakeH2(invalid=True)
    with pytest.raises(ValueError,match="Unsupported validation change"):
        revise_validation_with_feedback(
            state=state,feedback="Add a totally different algorithm and prove it beats the market.",
            report=old,settings=get_settings(),price_bars=bars,price_sha256=sha,llm=mock)
    assert len(mock.calls)==1
    assert old.report_id==state["validation_report"]["report_id"]
    with pytest.raises(ValueError,match="SHA-256"):
        revise_validation_with_feedback(
            state=state,feedback="Test transaction costs of 3 percent with original data",
            report=old,settings=get_settings(),price_bars=bars,
            price_sha256={**sha,"bitcoin":"0"*64},llm=FakeH2())


class FakeH3:
    def __init__(self,unsupported=False):
        self.calls=[]
        self.unsupported=unsupported
    def invoke(self,messages):
        self.calls.append(messages)
        if len(self.calls)==1:
            if self.unsupported:
                patch={"unsupported_changes":"New experiments must be validated in H2 first"}
            else:
                patch={
                    "edits":[{
                        "section_id":"sec_conclusion",
                        "revised_text":(
                            "The computed trading outcomes should be interpreted as evidence "
                            "for the specific tested historical trading rules rather than as "
                            "a proof of global optimality. The observed fee sensitivity and "
                            "drawdown risks motivate caution. Future research should compare "
                            "additional transparent baselines and out-of-sample performance "
                            "before recommending actual investment decisions."
                        ),
                        "why":"Respond to the reviewer request for a more cautious conclusion backed by available evidence.",
                    }],
                    "changes_made":"Rewrote the conclusion to discuss limitations, fee drag and the need for further validation."
                }
            return SimpleNamespace(content=json.dumps(patch),provider="mock",model="h3-editor")
        return SimpleNamespace(content=(
            "Independent H3 reviewer: revised conclusion is more cautious, but citations "
            "must remain verified and additional out-of-sample evidence is not yet available."
        ),provider="mock",model="h3-editor")


def _paper_study():
    state,validation,bars,sha=_study()
    state["approval_status"]["h2"]="approved"
    state["decision_report"]["h2"]={"status":"approved"}
    package=run_paper_planner(state=state,use_llm=False,attempt_pdf_compile=False)
    state["approval_status"]["h3"]="revision_requested"
    state["decision_report"]["h3"]={"status":"revision_requested","notes":"Rewrite conclusion"}
    state["decision_report"]["paper"]=package.model_dump(mode="json")
    return state,package


def test_h3_rewrites_actual_section_regenerates_tex_and_preserves_citations(tmp_path):
    state,old=_paper_study()
    feedback="Rewrite the conclusion in clearer language; don't claim optimality."
    model=FakeH3()
    new,audit=revise_paper_with_feedback(
        state=state,package=old,feedback=feedback,settings=get_settings(),
        llm=model,language="en")
    assert len(model.calls)==2
    assert new.package_id!=old.package_id
    assert new.outline.outline_id!=old.outline.outline_id
    assert new.latex.tex_source!=old.latex.tex_source
    assert new.latex.outline_id==new.outline.outline_id
    assert new.review.outline_id==new.outline.outline_id
    assert new.outline.bib_entries==old.outline.bib_entries
    assert new.latex.bib_source==old.latex.bib_source
    assert old.outline.validation_report_id==new.outline.validation_report_id
    assert new.invented_citations is False
    assert "not yet available" in audit["critic_feedback"]

    store=LocalProjectStore(tmp_path/"projects")
    _p,run,saved=store.save_project_state(
        project_id=state["project_id"],project_name=state["project_name"],
        state=state,input_signature="review-sig",note="boot")
    final=persist_paper_into_state(
        store,project_id=state["project_id"],project_name=state["project_name"],
        state=dict(saved,run_id=run.run_id),input_signature="review-sig",
        package=new,revision_record=audit)
    assert final["approval_status"]["h3"]=="pending"
    assert final["decision_report"]["h3_revision_history"][-1]["feedback"]==feedback
    assert final["latex_source"]==new.latex.tex_source


def test_h3_requires_human_feedback_and_rejects_unsupported_new_experiments():
    state,old=_paper_study()
    mock=FakeH3(unsupported=True)
    with pytest.raises(ValueError,match="requires new research/validation"):
        revise_paper_with_feedback(
            state=state,package=old,feedback="Run unperformed new optimization experiments",
            settings=get_settings(),llm=mock)
    assert len(mock.calls)==1
    assert state["decision_report"]["paper"]["package_id"]==old.package_id
    with pytest.raises(ValueError,match="12"):
        revise_paper_with_feedback(
            state=state,package=old,feedback="fix",settings=get_settings(),
            llm=FakeH3())


# Actual Streamlit widget acceptance. The provider factory is mocked: clicking
# a review button without separate consent must incur zero provider calls.
from pathlib import Path
from streamlit.testing.v1 import AppTest

PANEL_APP = Path(__file__).resolve().parents[1] / "fixtures" / "revision_gate_app.py"


def _app_with_review_state(tmp_path, monkeypatch, *, gate):
    if gate == "h2":
        state,report,bars,sha = _study()
        feedback = "Please rerun with 3 percent Bitcoin transaction costs using the exact original historical datasets."
        state["approval_status"]["h2"] = "revision_requested"
        state["decision_report"]["h2"] = {
            "status":"revision_requested","notes":feedback
        }
        uploads=[("LBMA-GOLD.csv",GOLD),("BCHAIN-MKPRU.csv",BTC)]
        monkeypatch.setattr("app.validation_h2_panel.get_or_create_store",lambda factory:store)
    else:
        state,package=_paper_study()
        feedback = "Rewrite the conclusion for readers and avoid unsupported claims of global optimality."
        state["decision_report"]["h3"]["notes"] = feedback
        uploads=[]
        monkeypatch.setattr("app.paper_h3_panel.get_or_create_store",lambda factory:store)
    # app has to be seeded from actual saved ResearchState to exercise persistence.
    store=LocalProjectStore(tmp_path / "projects")
    _p,run,saved=store.save_project_state(
        project_id=state["project_id"],project_name=state["project_name"],
        state=state,input_signature="review-gate-ux",note="boot",
    )
    app=AppTest.from_file(str(PANEL_APP),default_timeout=70)
    app.session_state["last_run"]={**saved,"run_id":run.run_id}
    app.session_state["foundation_input_signature"]="review-gate-ux"
    app.session_state["test_review_stage"]=gate
    app.session_state["test_upload_payloads"]=uploads
    return app.run(),feedback


def test_h2_widget_feedback_rerun_requires_consent_and_recalculates(tmp_path,monkeypatch):
    fake=FakeH2()
    created=[]
    def factory(_settings):
        created.append(fake)
        return fake
    monkeypatch.setattr("llm.factory.LLMFactory.create",factory)
    app,feedback=_app_with_review_state(tmp_path,monkeypatch,gate="h2")
    assert not app.exception
    label="Recompute validation from feedback"
    button=next(b for b in app.button if label in b.label)
    app=button.click().run()
    assert not app.exception
    assert not created
    assert app.session_state["last_run"]["approval_status"]["h2"]=="revision_requested"
    consent=next(c for c in app.checkbox if "I authorize two provider-model calls for H2" in c.label)
    app=consent.check().run()
    app=next(b for b in app.button if label in b.label).click().run()
    assert not app.exception
    assert len(created)==1 and len(fake.calls)==2, (
        f"errors={[x.value for x in app.error]} "
        f"warnings={[x.value for x in app.warning]}"
    )
    updated=app.session_state["last_run"]
    assert updated["approval_status"]["h2"]=="pending"
    assert updated["approval_status"]["h3"]=="pending"
    assert updated["decision_report"]["h2_revision_history"][-1]["feedback"]==feedback


def test_h3_widget_feedback_rerun_rewrites_tex_after_consent(tmp_path,monkeypatch):
    fake=FakeH3()
    created=[]
    def factory(_settings):
        created.append(fake)
        return fake
    monkeypatch.setattr("llm.factory.LLMFactory.create",factory)
    app,feedback=_app_with_review_state(tmp_path,monkeypatch,gate="h3")
    assert not app.exception
    label="Rewrite paper from feedback"
    app=next(b for b in app.button if label in b.label).click().run()
    assert not created
    assert app.session_state["last_run"]["approval_status"]["h3"]=="revision_requested"
    consent=next(c for c in app.checkbox if "I authorize two provider-model calls for H3" in c.label)
    app=consent.check().run()
    app=next(b for b in app.button if label in b.label).click().run()
    assert not app.exception
    assert len(created)==1 and len(fake.calls)==2, (
        f"errors={[x.value for x in app.error]}"
    )
    updated=app.session_state["last_run"]
    assert updated["approval_status"]["h3"]=="pending"
    history=updated["decision_report"]["h3_revision_history"][-1]
    assert history["feedback"]==feedback
    assert updated["latex_source"]
    assert "not yet available" in history["critic_feedback"]
