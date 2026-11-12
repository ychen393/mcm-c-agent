"""Phase 6 deterministic runner + constraint extraction (offline)."""

from __future__ import annotations

import pytest

from agents.problem_analyst import analyze_problem
from modeling.constraints import (
    DEFAULT_ALPHA_BITCOIN,
    DEFAULT_ALPHA_GOLD,
    DEFAULT_INITIAL_CASH,
    extract_problem_constraints,
)
from modeling.fixture_data import PRICE_FIXTURE_ID, load_price_fixture
from modeling.runner import (
    PROMPT_VERSION,
    build_experiment_params,
    execute_experiment_run,
    resolve_strategy_id,
    run_deterministic_backtest,
)
from schemas.research import (
    CandidateMethod,
    HypothesisItem,
    ProvenanceRef,
    ResearchProposal,
)
from tools.problem_spec_2022_c import load_2022_c_fixture


def _minimal_proposal(method_family: str = "trend_following") -> ResearchProposal:
    return ResearchProposal(
        proposal_id="prop_phase6_test",
        problem_id="2022_mcm_c",
        candidates=[
            CandidateMethod(
                candidate_id="cand_trend_a",
                title="Trend stub candidate",
                summary="Deterministic trend-following stub for Phase 6 tests.",
                method_family=method_family,
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


def test_price_fixture_is_synthetic_and_fixed():
    bars = load_price_fixture()
    assert len(bars) >= 10
    # Weekend gold gaps exist.
    assert any(b.gold is None for b in bars)
    assert any(b.gold is not None for b in bars)
    with pytest.raises(ValueError, match="Unknown price fixture"):
        load_price_fixture("fx_live_market_forbidden")


def test_constraints_from_2022_c_spec():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    snap = extract_problem_constraints(spec)
    assert snap.source == "problem_specification"
    assert snap.initial_cash == DEFAULT_INITIAL_CASH
    assert snap.alpha_gold == DEFAULT_ALPHA_GOLD
    assert snap.alpha_bitcoin == DEFAULT_ALPHA_BITCOIN
    assert snap.past_data_only is True
    assert "gold" in snap.assets and "bitcoin" in snap.assets


def test_constraints_defaults_without_spec():
    snap = extract_problem_constraints(None)
    assert snap.source == "defaults_2022_mcm_c"
    assert snap.initial_cash == 1000.0
    assert snap.alpha_gold == 0.01
    assert snap.alpha_bitcoin == 0.02


def test_cash_hold_is_deterministic():
    constraints = extract_problem_constraints(None)
    params = build_experiment_params(constraints=constraints, strategy_id="cash_hold")
    p1, trades1, equity1, _notes1 = run_deterministic_backtest(
        params=params, constraints=constraints
    )
    p2, trades2, equity2, _notes2 = run_deterministic_backtest(
        params=params, constraints=constraints
    )
    assert trades1 == trades2 == []
    assert equity1 == equity2
    assert p1.cash == p2.cash == 1000.0
    assert equity1[-1] == 1000.0


def test_buy_hold_bitcoin_pays_costs_and_is_deterministic():
    constraints = extract_problem_constraints(None)
    params = build_experiment_params(
        constraints=constraints, strategy_id="buy_hold_bitcoin"
    )
    p1, trades1, equity1, _ = run_deterministic_backtest(
        params=params, constraints=constraints
    )
    p2, _, equity2, _ = run_deterministic_backtest(params=params, constraints=constraints)
    assert len(trades1) == 1
    assert p1.n_trades == 1
    assert p1.cost_paid > 0
    assert p1.bitcoin > 0
    assert equity1 == equity2
    assert equity1[-1] != 1000.0


def test_resolve_strategy_maps_family():
    assert resolve_strategy_id(method_family="trend_following") == "trend_follow_bitcoin"
    assert resolve_strategy_id(method_family="risk_management") == "cash_hold"
    assert resolve_strategy_id(method_family="x", explicit="buy_hold_gold") == "buy_hold_gold"


def test_execute_experiment_run_links_proposal():
    proposal = _minimal_proposal("portfolio_optimization")
    run = execute_experiment_run(
        proposal=proposal,
        selected_candidate_id="cand_trend_a",
        problem_specification=analyze_problem(load_2022_c_fixture(), use_llm=False),
        h1_decision_id="h1d_test",
    )
    assert run.status == "completed"
    assert run.proposal_id == "prop_phase6_test"
    assert run.selected_candidate_id == "cand_trend_a"
    assert run.h1_status == "approved"
    assert run.live_trading_api_used is False
    assert run.invented_results is False
    assert run.agent_prompt_version == PROMPT_VERSION
    assert run.params.price_fixture_id == PRICE_FIXTURE_ID
    assert run.constraints.alpha_gold == 0.01
    assert run.metrics
    assert run.artifacts
    kinds = {a.kind for a in run.artifacts}
    assert "equity_curve_summary" in kinds
    assert "constraint_snapshot" in kinds
    assert any(ref.kind == "strategy_id" for ref in run.code_refs)
