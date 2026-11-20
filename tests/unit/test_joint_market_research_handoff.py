"""Joint gold/BTC EDA must reach the research Strategist and independent Critic."""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from agents.debate_critic import critique_research_proposal
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from app.eda_interpretation import bundle_insights
from app.joint_eda_panel import calculate_joint_market_insights
from schemas.persistence import assert_safe_for_persistence
from tools.dataset_bundle import build_dataset_bundle
from tools.problem_spec_2022_c import load_2022_c_fixture

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"
GOLD = (
    b"Date,USD (PM)\n"
    b"2016-09-12,100\n2016-09-13,102\n2016-09-14,99\n"
    b"2016-09-15,103\n2016-09-16,101\n2016-09-19,104\n"
)
BTC = (
    b"Date,Value\n"
    b"2016-09-11,600\n2016-09-12,610\n2016-09-13,620\n"
    b"2016-09-14,600\n2016-09-15,650\n2016-09-16,590\n"
    b"2016-09-17,580\n2016-09-18,565\n2016-09-19,630\n"
)


def _bundle_and_findings():
    bundle = build_dataset_bundle(
        [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BTC)],
        project_id="joint-evidence-study",
    )
    gold, btc = [bundle.loaded_dataset(ref.dataset_id).frame for ref in bundle.datasets]
    _prices, joint = calculate_joint_market_insights(gold, btc)
    findings = bundle_insights(bundle)
    findings["joint_market"] = {
        **joint,
        "bundle_fingerprint": bundle.fingerprint,
        "gold_sha256": bundle.datasets[0].sha256,
        "bitcoin_sha256": bundle.datasets[1].sha256,
    }
    return bundle, findings


def test_joined_statistics_are_safe_and_influence_research_and_critic():
    _, findings = _bundle_and_findings()
    assert_safe_for_persistence({"interpreted_findings": findings})
    assert findings["joint_market"]["common_quote_days"] == 6
    assert findings["joint_market"]["bitcoin_only_days"] == 3
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    eda = {"interpreted_findings": findings}
    proposal = synthesize_research_proposal(
        problem_specification=spec,
        eda_report=eda,
        use_llm=False,
    )
    assert proposal.eda_context_present
    assert any("Joint observed-date EDA" in line for line in proposal.analysis_notes)
    assert any(
        any(ref.ref_id and ref.ref_id.startswith("joint_") for ref in candidate.provenance)
        for candidate in proposal.candidates
    )
    critique = critique_research_proposal(
        proposal=proposal,
        problem_specification=spec,
        eda_report=eda,
        use_llm=False,
    )
    assert any("full historical window" in f.statement for f in critique.findings)
    assert any("BTC dates" in f.statement for f in critique.findings)


def _button(app: AppTest, name: str):
    return next(b for b in app.button if name in b.label)


def test_user_joint_eda_saved_and_visible_to_h1_without_storing_merged_rows():
    app = AppTest.from_file(str(APP_PATH), default_timeout=90).run()
    problem = next(a for a in app.text_area if "problem statement" in a.label.lower())
    app = problem.set_value(load_2022_c_fixture()).run()
    app = app.file_uploader[0].set_value([
        ("LBMA-GOLD.csv", GOLD, "text/csv"),
        ("BCHAIN-MKPRU.csv", BTC, "text/csv"),
    ]).run()
    app = _button(app, "Initialize project").click().run()
    app = _button(app, "Analyze problem").click().run()
    app = _button(app, "Continue to Stage 2").click().run()
    assert not app.exception
    assert "joint_market" not in app.session_state["eda_insights"]
    app = _button(app, "Analyze both markets").click().run()
    assert not app.exception
    assert app.session_state["eda_insights"]["joint_market"]["common_quote_days"] == 6
    assert any("Joint market EDA" in tab.label for tab in app.tabs)
    app = _button(app, "Finish EDA").click().run()
    assert not app.exception
    eda = app.session_state["last_run"]["eda_report"]
    joint = eda["interpreted_findings"]["joint_market"]
    assert joint["common_quote_days"] == 6
    assert joint["bitcoin_only_days"] == 3
    assert joint["joined"] is False
    assert eda["raw_rows_included"] is False
    assert eda["joined"] is False
    assert not any(k in joint for k in ("dates", "price_rows", "preview_rows"))
    app = _button(app, "Run research team").click().run()
    assert not app.exception
    assert any("Joint observed-date EDA" in note
               for note in app.session_state["research_proposal_draft"]["analysis_notes"])
