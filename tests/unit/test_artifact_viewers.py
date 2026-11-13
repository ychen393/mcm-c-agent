"""UX-B artifact viewer helpers."""

from __future__ import annotations

from app.artifact_viewers import (
    build_h2_scenario_delta_table,
    candidate_display_label,
    resolve_h1_selected_candidate,
)
from agents.problem_analyst import analyze_problem
from modeling.fixture_data import PRICE_FIXTURE_ID
from modeling.runner import execute_experiment_run
from schemas.research import (
    CandidateMethod,
    HypothesisItem,
    ProvenanceRef,
    ResearchProposal,
)
from tools.problem_spec_2022_c import load_2022_c_fixture


def test_candidate_display_label_prefers_title():
    assert (
        candidate_display_label(
            {"candidate_id": "cand_a", "title": "Trend follow BTC"},
        )
        == "Trend follow BTC (cand_a)"
    )
    assert candidate_display_label(None, fallback_id="cand_x") == "cand_x"


def test_resolve_h1_selected_candidate_approved():
    proposal = {
        "recommended_candidate_id": "cand_a",
        "candidates": [
            {
                "candidate_id": "cand_a",
                "title": "Buy and hold gold",
                "summary": "Hold gold",
                "method_family": "buy_hold",
                "strengths": ["simple"],
                "evidence_card_ids": ["c1"],
                "evidence_gap_ids": ["g1", "g2"],
            }
        ],
    }
    recorded = {
        "approval_status": {"h1": "approved"},
        "decision_report": {
            "h1": {"status": "approved", "selected_candidate_id": "cand_a"}
        },
        "research_proposal": proposal,
    }
    status, cand, title = resolve_h1_selected_candidate(recorded, proposal)
    assert status == "approved"
    assert cand is not None and cand["candidate_id"] == "cand_a"
    assert title == "Buy and hold gold"


def test_h2_scenario_delta_table_builds_rows():
    report = {
        "scenarios": [
            {
                "scenario_id": "scn_cost_up",
                "label": "Higher gold cost",
                "kind": "cost",
                "deltas": [
                    {
                        "metric_id": "terminal_value",
                        "label": "Terminal value",
                        "baseline_value": 1000.0,
                        "scenario_value": 980.0,
                        "absolute_delta": -20.0,
                        "relative_delta": -0.02,
                    }
                ],
            }
        ]
    }
    frame = build_h2_scenario_delta_table(report)
    assert len(frame) == 1
    assert frame.iloc[0]["scenario"] == "Higher gold cost"
    assert frame.iloc[0]["relative_delta_pct"] == -2.0


def test_modeling_runner_equity_payload_includes_series():
    proposal = ResearchProposal(
        proposal_id="prop_phase6_test",
        problem_id="2022_mcm_c",
        candidates=[
            CandidateMethod(
                candidate_id="cand_trend_a",
                title="Trend stub candidate",
                summary="Deterministic trend-following stub for Phase 6 tests.",
                method_family="trend_following",
                hypotheses=[
                    HypothesisItem(
                        hypothesis_id="hyp_trend_a",
                        statement="A simple trend rule can trade bitcoin with past prices only.",
                        provenance=[
                            ProvenanceRef(kind="rule_based", summary="phase6 unit fixture")
                        ],
                    )
                ],
                provenance=[ProvenanceRef(kind="rule_based", summary="phase6 unit fixture")],
            )
        ],
        recommended_candidate_id="cand_trend_a",
        problem_specification_present=True,
    )
    run = execute_experiment_run(
        proposal=proposal,
        selected_candidate_id="cand_trend_a",
        problem_specification=analyze_problem(load_2022_c_fixture(), use_llm=False),
        h1_decision_id="h1d_test",
    )
    equity = next(a for a in run.artifacts if a.kind == "equity_curve_summary")
    assert "series" in equity.payload
    assert equity.payload["n_points"] == len(equity.payload["series"])
    assert equity.payload["series"][0]["date"]
    assert any(
        ref.kind == "fixture_id" and ref.value == PRICE_FIXTURE_ID for ref in run.code_refs
    )
