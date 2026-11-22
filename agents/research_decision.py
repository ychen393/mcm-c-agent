"""Deterministic Sprint A plan classification and execution-readiness contracts.

This module describes testable research hypotheses. It never pretends that a
strategy is implemented, never runs backtests and never calls an LLM.
"""
from __future__ import annotations
import hashlib
from typing import Any

from agents.research_evidence import build_research_evidence_packet
from schemas.research import ResearchProposal
from schemas.research_plan_v2 import ExecutableResearchPlan, ResearchDecisionV2

STRATEGY_FAMILIES = {
    "cost_aware_trading", "trend_following", "portfolio_optimization",
    "risk_management", "mean_reversion", "forecasting",
}
BASELINE_FAMILIES = {"simulation_backtest"}
FAMILY_PRIORITY = {
    "cost_aware_trading": 0, "trend_following": 1,
    "risk_management": 2, "portfolio_optimization": 3,
    "mean_reversion": 4, "forecasting": 5,
}
BASELINES = ["cash_hold", "buy_hold_gold", "buy_hold_bitcoin", "periodic_rebalance_5050"]


def classify_method_family(family: str) -> str:
    if family in BASELINE_FAMILIES:
        return "baseline"
    if family in STRATEGY_FAMILIES:
        return "strategy"
    if any(term in family.lower() for term in ("validation", "bootstrap", "sensitivity", "cross_validation")):
        return "validation"
    return "prerequisite"


def _execution_plan(family: str, evidence_sha: str | None) -> ExecutableResearchPlan:
    templates = {
        "cost_aware_trading": (
            "Compare a past-only trading signal with an explicit no-trade band "
            "that accounts for the two asset-specific commission rates.",
            "Signal: use only trailing observations available by decision time; "
            "propose a rebalance only if signal improvement exceeds a fee-aware threshold.",
            "Change allocations only on permitted market days; calculate the cash "
            "required including both buy and sell commissions.",
        ),
        "trend_following": (
            "Test whether past-only trend signals improve the fee-adjusted portfolio.",
            "Signal: for each asset compare a short trailing moving average with a "
            "long trailing moving average, with windows fixed using earlier dates.",
            "Enter or exit when a lagged signal changes; enforce gold market closures "
            "and never execute on a price not yet observable.",
        ),
        "portfolio_optimization": (
            "Study risk-budgeted allocations among cash, gold and Bitcoin.",
            "Signal: trailing volatility and trailing paired-market dependence "
            "estimated only from dates before the trade.",
            "Choose target portfolio weights with a cash allocation and fees; "
            "rebalance only on eligible market days.",
        ),
        "risk_management": (
            "Evaluate past-only volatility-based exposure limits against buy-and-hold.",
            "Signal: trailing realized volatility or trailing drawdown available "
            "before the decision time sets a conservative position limit.",
            "Reduce/restore position according to predeclared thresholds; "
            "respect commissions and gold closures.",
        ),
        "mean_reversion": (
            "Test whether prior deviations from trailing means predict reversions.",
            "Signal: past-only price deviation from a trailing historical average "
            "with out-of-sample chosen entry/exit thresholds.",
            "Apply a bounded contrarian position when signals are available; "
            "only trade on actual executable market dates after fee checks.",
        ),
        "forecasting": (
            "Compare a rolling historical price-signal forecast with non-predictive baselines.",
            "Signal: refit a prespecified forecast on earlier observations only; "
            "use the projected next-interval sign after strictly chronological evaluation.",
            "Act on forecasts only after they exist, using executable market prices "
            "and allowing for gold/BTC transaction costs.",
        ),
    }
    objective, signal, execution = templates.get(family, templates["trend_following"])
    refs = ["eda:" + evidence_sha[:20]] if evidence_sha else []
    return ExecutableResearchPlan(
        objective=objective,
        input_features=[
            "Observed gold USD (PM) quotes with available dates",
            "Observed Bitcoin Value quotes with available dates",
            "Lagged, valid common-quote market statistics where needed",
        ],
        signal_definition=signal,
        decision_timing=(
            "At each decision t use only data confirmed available before t; "
            "define next executable quote timing explicitly. Historical end-of-day "
            "full-window EDA cannot be used as a contemporaneous signal."
        ),
        execution_rule=execution,
        transaction_costs=(
            "Debit gold 1% and Bitcoin 2% per executed buy/sell, subject to "
            "the 2022 MCM C task constraints; no fee for simply holding."
        ),
        parameters=[
            "Historical lookback and signal threshold selected on earlier data",
            "Position limit, eligible rebalance days and no-trade band",
        ],
        risk_controls=[
            "No negative cash or implicit leverage",
            "Gold cannot be bought or sold when gold market is closed",
            "Report strategy-level drawdown alongside net final wealth",
        ],
        baseline_ids=BASELINES,
        validation_design=[
            "Chronological development and held-out dates without future information",
            "Compare cash, individual buy-and-hold and proposed portfolio policy",
            "Report transaction fees, turnover, ending wealth and max portfolio drawdown",
            "Perturb the two transaction commission rates independently",
        ],
        evidence_refs=refs,
        # Existing runner has unresolved same-close execution assumptions and
        # implicit family fallback. Sprint B must implement/verify this precise
        # V2 plan before it may be represented as runnable.
        implementation_status="needs_implementation",
        executable_strategy_id=None,
    )


def with_research_decision(
    proposal: ResearchProposal,
    eda_report: dict[str, Any] | None,
) -> ResearchProposal:
    """Build one main + up to two different-family strategy directions."""
    packet = build_research_evidence_packet(eda_report)
    families = set()
    ranked = []
    candidates = []
    for c in proposal.candidates:
        role = classify_method_family(c.method_family)
        if role == "strategy" and c.method_family not in families:
            families.add(c.method_family)
            ranked.append(c)
        candidates.append(c)
    if not ranked:
        # Non-trading problem: retain old schema instead of fabricating a
        # gold/BTC plan or reclassifying a baseline as an optimal strategy.
        return proposal
    ranked.sort(key=lambda c: (FAMILY_PRIORITY.get(c.method_family, 99), c.candidate_id))
    selected = ranked[:3]
    ids = {c.candidate_id for c in selected}
    rebuilt = []
    for c in candidates:
        payload = c.model_dump(mode="python")
        payload["research_role"] = classify_method_family(c.method_family)
        payload["status"] = "recommended" if c.candidate_id == selected[0].candidate_id else "proposed"
        if c.candidate_id in ids:
            payload["execution_plan"] = _execution_plan(
                c.method_family, packet.get("packet_sha256")
            ).model_dump(mode="python")
        rebuilt.append(payload)
    decision = ResearchDecisionV2(
        primary_candidate_id=selected[0].candidate_id,
        alternate_candidate_ids=[c.candidate_id for c in selected[1:]],
        prerequisite_tasks=[
            "Audit both observed quote series and distinguish market closure from missing values",
            "Choose the information-available and trade-execution convention before modeling",
            "Apply gold/BTC commissions, cash balance and market-day constraints",
        ],
        baseline_strategy_ids=BASELINES,
        validation_tasks=[
            "Chronological holdout and no-lookahead checks",
            "Transaction fee and parameter sensitivity",
            "Compare fee-adjusted ending wealth, turnover and portfolio drawdown",
        ],
        evidence_packet_sha256=packet["packet_sha256"],
        evidence_bundle_fingerprint=packet["bundle_fingerprint"],
        status="draft",
    )
    payload = proposal.model_dump(mode="python")
    payload["version"] = "2.0"
    payload["candidates"] = rebuilt
    payload["research_decision"] = decision.model_dump(mode="python")
    payload["recommended_candidate_id"] = decision.primary_candidate_id
    suffix = hashlib.sha256(
        (proposal.proposal_id + "|" + packet["packet_sha256"] +
         "|" + ",".join([decision.primary_candidate_id, *decision.alternate_candidate_ids]))
        .encode("utf-8")
    ).hexdigest()[:14]
    payload["proposal_id"] = f"prop_{suffix}"
    payload["analysis_notes"] = (
        list(proposal.analysis_notes) +
        ["Sprint A V2 selects one main research hypothesis and at most two "
         "alternates; implementation/readiness remains unverified."]
    )[:32]
    return ResearchProposal.model_validate(payload)
