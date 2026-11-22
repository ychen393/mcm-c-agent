"""Sprint A source fingerprint and V2 research selection contracts."""
from copy import deepcopy

import pytest

from agents.research_decision import classify_method_family, with_research_decision
from agents.research_evidence import build_research_evidence_packet
from schemas.research import CandidateMethod, ResearchProposal


def _eda():
    return {"interpreted_findings": {
        "bundle_fingerprint": "bundle_a",
        "datasets": [
            {"name": "LBMA-GOLD.csv", "sha256": "a" * 64, "valid_prices": 40,
             "volatility_pct": 1.2, "max_drawdown_pct": -7.0},
            {"name": "BCHAIN-MKPRU.csv", "sha256": "b" * 64, "valid_prices": 49,
             "volatility_pct": 3.2, "max_drawdown_pct": -21.0},
        ],
        "joint_market": {
            "bundle_fingerprint": "bundle_a",
            "gold_sha256": "a" * 64,
            "bitcoin_sha256": "b" * 64,
            "common_quote_days": 39,
            "paired_return_intervals": 38,
            "paired_return_correlation": 0.24,
            "both_negative_intervals": 8,
            "bitcoin_only_days": 10,
            "rolling_corr_latest": 0.1,
        },
    }}


def _legacy():
    candidates = [
        CandidateMethod(candidate_id="cand_cost", title="Fee-aware trading",
                        summary="A fee-aware historical trading hypothesis",
                        method_family="cost_aware_trading"),
        CandidateMethod(candidate_id="cand_trend", title="Lagged trend strategy",
                        summary="A lagged moving-average hypothesis",
                        method_family="trend_following"),
        CandidateMethod(candidate_id="cand_risk", title="Dynamic risk policy",
                        summary="A volatility-limited position hypothesis",
                        method_family="risk_management"),
        CandidateMethod(candidate_id="cand_baseline", title="Baseline comparison",
                        summary="Simple buy-and-hold historical comparisons",
                        method_family="simulation_backtest"),
    ]
    return ResearchProposal(
        proposal_id="prop_legacy_sprint_a", problem_id="mcm_2022_c",
        candidates=candidates, recommended_candidate_id="cand_cost",
        problem_specification_present=True,
    )


def test_evidence_source_sha_and_joint_packet_are_consistent_and_compact():
    source = _eda()
    packet = build_research_evidence_packet(source)
    assert packet["joint_market"]["common_quote_days"] == 39
    assert packet["joint_market"]["paired_return_correlation"] == 0.24
    assert packet["datasets"][0]["sha256"] == "a" * 64
    assert len(packet["packet_sha256"]) == 64
    assert not any(k in str(packet) for k in ("preview_rows", "price_rows", "raw_bytes"))
    second = deepcopy(source)
    second["interpreted_findings"]["datasets"][0]["volatility_pct"] = 9.8
    assert build_research_evidence_packet(second)["packet_sha256"] != packet["packet_sha256"]
    second["interpreted_findings"]["joint_market"]["gold_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="gold_sha256"):
        build_research_evidence_packet(second)
    third = deepcopy(source)
    third["interpreted_findings"]["joint_market"]["bundle_fingerprint"] = "stale"
    with pytest.raises(ValueError, match="fingerprint"):
        build_research_evidence_packet(third)


def test_sprint_a_shortlist_classification_and_realistic_implementation_status():
    decision = with_research_decision(_legacy(), _eda())
    assert decision.version == "2.0"
    assert decision.research_decision is not None
    assert decision.research_decision.primary_candidate_id == "cand_cost"
    assert len(decision.research_decision.alternate_candidate_ids) == 2
    assert len(decision.candidates) == 4  # prior provenance is retained
    assert next(c for c in decision.candidates if c.candidate_id == "cand_baseline").research_role == "baseline"
    assert classify_method_family("bootstrap_sensitivity") == "validation"
    chosen = next(c for c in decision.candidates
                  if c.candidate_id == decision.recommended_candidate_id)
    plan = chosen.execution_plan
    assert plan is not None
    assert plan.implementation_status == "needs_implementation"
    assert plan.executable_strategy_id is None
    assert "1%" in plan.transaction_costs and "2%" in plan.transaction_costs
    assert "before t" in plan.decision_timing
    assert any("held-out" in v for v in plan.validation_design)
    assert decision.research_decision.evidence_packet_sha256 == build_research_evidence_packet(_eda())["packet_sha256"]


def test_missing_joint_eda_keeps_legacy_history_readable():
    legacy = _legacy()
    without_joint = deepcopy(_eda())
    without_joint["interpreted_findings"].pop("joint_market")
    result = with_research_decision(legacy, without_joint)
    assert result.research_decision is None
    assert result.proposal_id == legacy.proposal_id
