"""Meaningful bilingual explanation and evidence-driven agent handoff tests."""
from __future__ import annotations

import pandas as pd

from agents.debate_critic import critique_research_proposal
from agents.problem_analyst import analyze_problem
from agents.research_strategy import synthesize_research_proposal
from app.eda_interpretation import analyze_market_frame, bundle_insights
from app.problem_narrative import is_2022_trading_spec, trading_research_brief
from tools.dataset_bundle import build_dataset_bundle
from tools.problem_spec_2022_c import load_2022_c_fixture


GOLD = b"Date,USD (PM)\n2022-01-07,1800\n2022-01-10,1700\n2022-01-11,\n2022-01-12,1500\n"
BTC = b"Date,Value\n2022-01-07,40000\n2022-01-08,43000\n2022-01-09,41000\n2022-01-10,38000\n"


def test_eda_agent_reports_observed_missing_prices_dates_and_drawdown():
    frame = pd.read_csv(pd.io.common.BytesIO(GOLD))
    insight = analyze_market_frame(frame, name="LBMA-GOLD.csv")
    assert insight["rows"] == 4
    assert insight["missing_by_column"]["USD (PM)"] == 1
    assert insight["valid_prices"] == 3
    assert insight["date_start"] == "2022-01-07"
    assert insight["date_end"] == "2022-01-12"
    assert insight["change_pct"] < -16
    assert insight["max_drawdown_pct"] < -16
    assert insight["duplicate_dates"] == 0


def test_multimarket_insight_remains_compact_and_provenance_identified():
    bundle = build_dataset_bundle(
        [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BTC)],
        project_id="evidence-driven",
    )
    insight = bundle_insights(bundle)
    assert len(insight["datasets"]) == 2
    assert not insight["jointly_modeled"]
    assert insight["bundle_fingerprint"] == bundle.fingerprint
    assert all(len(row["sha256"]) == 64 for row in insight["datasets"])
    assert not any("rows" in row and isinstance(row["rows"], list) for row in insight["datasets"])


def test_problem_brief_translates_research_interpretation_without_changing_spec():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False).model_dump(mode="json")
    assert is_2022_trading_spec(spec)
    zh = trading_research_brief("zh")
    en = trading_research_brief("en")
    assert len(zh["tasks"]) == len(en["tasks"]) == 5
    assert len(zh["models"]) == len(en["models"]) == 4
    assert "手续费" in zh["thesis"]
    assert "transaction-cost" in en["thesis"]


def test_strategy_and_independent_critic_ground_their_claims_in_eda():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    bundle = build_dataset_bundle(
        [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BTC)],
        project_id="evidence-driven",
    )
    eda_report = {"interpreted_findings": bundle_insights(bundle)}
    proposal = synthesize_research_proposal(
        problem_specification=spec, eda_report=eda_report, use_llm=False
    )
    assert proposal.eda_context_present
    assert proposal.recommended_candidate_id is not None
    assert any("Observed EDA evidence" in note for note in proposal.analysis_notes)
    assert any(
        p.kind == "eda_report" for cand in proposal.candidates for p in cand.provenance
    )
    critique = critique_research_proposal(
        proposal=proposal,
        problem_specification=spec,
        eda_report=eda_report,
        use_llm=False,
    )
    assert any(
        f.kind in {"data_gap", "weak_assumption"} and any(
            ref.kind == "eda_report" for ref in f.evidence_refs
        )
        for f in critique.findings
    )
    assert not critique.invented_sources
