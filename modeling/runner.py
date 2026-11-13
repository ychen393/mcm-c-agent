"""CI-safe deterministic modeling runner for 2022 MCM C trading slice (Phase 6).

No live trading APIs. No unbounded network. Optional sandboxed Python is gated
and remains a non-executing stub in this slice.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from modeling.constraints import extract_problem_constraints
from modeling.fixture_data import (
    PRICE_FIXTURE_ID,
    PRICE_FIXTURE_NOTE,
    PriceBar,
    fixture_metadata,
    load_price_fixture,
)
from schemas.experiment import (
    ExperimentCodeRef,
    ExperimentParams,
    ExperimentRun,
    MetricResult,
    ModelArtifactRef,
    ProblemConstraintSnapshot,
)
from schemas.problem_specification import ProblemSpecification
from schemas.research import ResearchProposal

PROMPT_VERSION = "modeling_experiment_v1"
SANDBOX_UNAVAILABLE_NOTE = (
    "Optional sandboxed Python execution is not enabled for arbitrary strategy "
    "code in this Phase 6 slice. The deterministic fixture runner remains "
    "authoritative. Live trading APIs are forbidden."
)

StrategyId = Literal[
    "cash_hold",
    "buy_hold_bitcoin",
    "buy_hold_gold",
    "trend_follow_bitcoin",
    "periodic_rebalance_5050",
]


STRATEGY_BY_FAMILY: dict[str, StrategyId] = {
    "portfolio_optimization": "periodic_rebalance_5050",
    "trend_following": "trend_follow_bitcoin",
    "mean_reversion": "trend_follow_bitcoin",
    "cost_aware_trading": "buy_hold_bitcoin",
    "forecasting": "trend_follow_bitcoin",
    "risk_management": "cash_hold",
    "simulation_backtest": "periodic_rebalance_5050",
    "general_quantitative": "buy_hold_bitcoin",
}


@dataclass
class Portfolio:
    cash: float
    gold_oz: float = 0.0
    bitcoin: float = 0.0
    cost_paid: float = 0.0
    n_trades: int = 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"[:64]


def _payload_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def resolve_strategy_id(
    *,
    method_family: str | None,
    explicit: str | None = None,
) -> StrategyId:
    if explicit in {
        "cash_hold",
        "buy_hold_bitcoin",
        "buy_hold_gold",
        "trend_follow_bitcoin",
        "periodic_rebalance_5050",
    }:
        return explicit  # type: ignore[return-value]
    if method_family:
        return STRATEGY_BY_FAMILY.get(method_family, "buy_hold_bitcoin")
    return "buy_hold_bitcoin"


def _mark_to_market(portfolio: Portfolio, bar: PriceBar) -> float:
    gold_px = bar.gold if bar.gold is not None else 0.0
    # If gold closed, last known gold price should be used by caller via carry.
    return portfolio.cash + portfolio.gold_oz * gold_px + portfolio.bitcoin * bar.bitcoin


def _buy_bitcoin(portfolio: Portfolio, price: float, alpha: float, fraction: float = 1.0) -> None:
    if price <= 0 or portfolio.cash <= 0 or fraction <= 0:
        return
    spend = portfolio.cash * min(1.0, max(0.0, fraction))
    # Commission is paid on transaction value (purchase).
    units = spend / (price * (1.0 + alpha))
    cost = units * price * alpha
    portfolio.cash -= units * price + cost
    portfolio.bitcoin += units
    portfolio.cost_paid += cost
    portfolio.n_trades += 1


def _sell_bitcoin(portfolio: Portfolio, price: float, alpha: float, fraction: float = 1.0) -> None:
    if price <= 0 or portfolio.bitcoin <= 0 or fraction <= 0:
        return
    units = portfolio.bitcoin * min(1.0, max(0.0, fraction))
    gross = units * price
    cost = gross * alpha
    portfolio.bitcoin -= units
    portfolio.cash += gross - cost
    portfolio.cost_paid += cost
    portfolio.n_trades += 1


def _buy_gold(portfolio: Portfolio, price: float, alpha: float, fraction: float = 1.0) -> None:
    if price <= 0 or portfolio.cash <= 0 or fraction <= 0:
        return
    spend = portfolio.cash * min(1.0, max(0.0, fraction))
    units = spend / (price * (1.0 + alpha))
    cost = units * price * alpha
    portfolio.cash -= units * price + cost
    portfolio.gold_oz += units
    portfolio.cost_paid += cost
    portfolio.n_trades += 1


def _sell_gold(portfolio: Portfolio, price: float, alpha: float, fraction: float = 1.0) -> None:
    if price <= 0 or portfolio.gold_oz <= 0 or fraction <= 0:
        return
    units = portfolio.gold_oz * min(1.0, max(0.0, fraction))
    gross = units * price
    cost = gross * alpha
    portfolio.gold_oz -= units
    portfolio.cash += gross - cost
    portfolio.cost_paid += cost
    portfolio.n_trades += 1


def _btc_ma(bars: list[PriceBar], end_idx: int, lookback: int) -> float | None:
    """Past-data-only moving average using bars[0..end_idx] inclusive."""
    if end_idx < 0:
        return None
    window = bars[max(0, end_idx - lookback + 1) : end_idx + 1]
    if not window:
        return None
    return sum(b.bitcoin for b in window) / len(window)


def run_deterministic_backtest(
    *,
    params: ExperimentParams,
    constraints: ProblemConstraintSnapshot,
) -> tuple[Portfolio, list[dict[str, Any]], list[float], list[str]]:
    """Execute the selected stub strategy on the synthetic fixture.

    Past-data-only: decisions at day i use bars[0..i] only (never future bars).
    """
    bars = load_price_fixture(params.price_fixture_id)
    portfolio = Portfolio(cash=float(constraints.initial_cash))
    trades: list[dict[str, Any]] = []
    equity: list[float] = []
    notes: list[str] = [
        PRICE_FIXTURE_NOTE,
        f"strategy_id={params.strategy_id}",
        f"past_data_only={constraints.past_data_only}",
    ]
    last_gold = next((b.gold for b in bars if b.gold is not None), 0.0) or 0.0
    alpha_g = float(constraints.alpha_gold)
    alpha_b = float(constraints.alpha_bitcoin)
    strategy = params.strategy_id

    for i, bar in enumerate(bars):
        if bar.gold is not None:
            last_gold = bar.gold
        # Carry last gold price into mark-to-market when market closed.
        effective = PriceBar(
            day_index=bar.day_index,
            date=bar.date,
            weekday=bar.weekday,
            gold=last_gold,
            bitcoin=bar.bitcoin,
        )

        gold_open = bar.gold is not None
        if constraints.gold_trade_weekdays_only and not gold_open:
            # Still may trade bitcoin every day.
            pass

        if strategy == "cash_hold":
            pass
        elif strategy == "buy_hold_bitcoin":
            if i == 0 and portfolio.bitcoin == 0 and portfolio.cash > 0:
                before = portfolio.cash
                _buy_bitcoin(portfolio, bar.bitcoin, alpha_b, fraction=1.0)
                trades.append(
                    {
                        "day": bar.date,
                        "asset": "bitcoin",
                        "side": "buy",
                        "price": bar.bitcoin,
                        "cash_before": before,
                    }
                )
        elif strategy == "buy_hold_gold":
            if gold_open and portfolio.gold_oz == 0 and portfolio.cash > 0:
                before = portfolio.cash
                _buy_gold(portfolio, bar.gold or 0.0, alpha_g, fraction=1.0)
                trades.append(
                    {
                        "day": bar.date,
                        "asset": "gold",
                        "side": "buy",
                        "price": bar.gold,
                        "cash_before": before,
                    }
                )
        elif strategy == "trend_follow_bitcoin":
            # Signal uses only past bars through today (inclusive).
            ma = _btc_ma(bars, i, params.lookback_days)
            if ma is not None:
                if bar.bitcoin > ma and portfolio.cash > 1.0:
                    before = portfolio.cash
                    _buy_bitcoin(portfolio, bar.bitcoin, alpha_b, fraction=0.5)
                    trades.append(
                        {
                            "day": bar.date,
                            "asset": "bitcoin",
                            "side": "buy",
                            "price": bar.bitcoin,
                            "signal": "above_ma",
                            "ma": ma,
                            "cash_before": before,
                        }
                    )
                elif bar.bitcoin < ma and portfolio.bitcoin > 0:
                    before = portfolio.bitcoin
                    _sell_bitcoin(portfolio, bar.bitcoin, alpha_b, fraction=0.5)
                    trades.append(
                        {
                            "day": bar.date,
                            "asset": "bitcoin",
                            "side": "sell",
                            "price": bar.bitcoin,
                            "signal": "below_ma",
                            "ma": ma,
                            "units_before": before,
                        }
                    )
        elif strategy == "periodic_rebalance_5050":
            if i % params.rebalance_every_n_days == 0:
                # Target ~50% bitcoin / ~50% cash (+ gold untouched unless open).
                value = _mark_to_market(portfolio, effective)
                target_btc_value = value * 0.5
                current_btc_value = portfolio.bitcoin * bar.bitcoin
                delta = target_btc_value - current_btc_value
                if delta > 1.0 and portfolio.cash > 1.0:
                    frac = min(1.0, delta / max(portfolio.cash, 1e-9))
                    _buy_bitcoin(portfolio, bar.bitcoin, alpha_b, fraction=frac)
                    trades.append(
                        {
                            "day": bar.date,
                            "asset": "bitcoin",
                            "side": "buy",
                            "price": bar.bitcoin,
                            "rebalance": True,
                        }
                    )
                elif delta < -1.0 and portfolio.bitcoin > 0:
                    sell_value = min(-delta, current_btc_value)
                    frac = min(1.0, sell_value / max(current_btc_value, 1e-9))
                    _sell_bitcoin(portfolio, bar.bitcoin, alpha_b, fraction=frac)
                    trades.append(
                        {
                            "day": bar.date,
                            "asset": "bitcoin",
                            "side": "sell",
                            "price": bar.bitcoin,
                            "rebalance": True,
                        }
                    )
                if gold_open and portfolio.gold_oz == 0 and portfolio.cash > value * 0.05:
                    # Small optional gold sleeve once.
                    _buy_gold(portfolio, bar.gold or 0.0, alpha_g, fraction=0.1)
                    trades.append(
                        {
                            "day": bar.date,
                            "asset": "gold",
                            "side": "buy",
                            "price": bar.gold,
                            "rebalance": True,
                        }
                    )
        else:
            notes.append(f"Unknown strategy '{strategy}' — treated as cash_hold.")

        equity.append(round(_mark_to_market(portfolio, effective), 6))

    return portfolio, trades, equity, notes


def build_experiment_params(
    *,
    constraints: ProblemConstraintSnapshot,
    strategy_id: StrategyId,
    lookback_days: int = 3,
    rebalance_every_n_days: int = 5,
    allow_sandboxed_python: bool = False,
    price_fixture_id: str = PRICE_FIXTURE_ID,
) -> ExperimentParams:
    return ExperimentParams(
        initial_cash=constraints.initial_cash,
        alpha_gold=constraints.alpha_gold,
        alpha_bitcoin=constraints.alpha_bitcoin,
        assets=list(constraints.assets),
        past_data_only=constraints.past_data_only,
        strategy_id=strategy_id,
        lookback_days=lookback_days,
        rebalance_every_n_days=rebalance_every_n_days,
        price_fixture_id=price_fixture_id,
        allow_sandboxed_python=allow_sandboxed_python,
    )


def _metrics_from_portfolio(
    portfolio: Portfolio,
    *,
    initial_cash: float,
    equity: list[float],
) -> list[MetricResult]:
    terminal = equity[-1] if equity else float(portfolio.cash)
    total_return = (terminal - initial_cash) / initial_cash if initial_cash else 0.0
    peak = equity[0] if equity else terminal
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, (value - peak) / peak)
    return [
        MetricResult(
            metric_id="m_terminal_value",
            kind="terminal_value",
            label="Terminal portfolio value",
            value=round(terminal, 6),
            unit="USD",
        ),
        MetricResult(
            metric_id="m_total_return",
            kind="total_return",
            label="Total return",
            value=round(total_return, 8),
            unit="fraction",
        ),
        MetricResult(
            metric_id="m_n_trades",
            kind="n_trades",
            label="Number of trades",
            value=float(portfolio.n_trades),
            unit="count",
        ),
        MetricResult(
            metric_id="m_cost_paid",
            kind="transaction_cost_paid",
            label="Transaction costs paid",
            value=round(portfolio.cost_paid, 6),
            unit="USD",
        ),
        MetricResult(
            metric_id="m_max_drawdown",
            kind="max_drawdown",
            label="Max drawdown (fixture window)",
            value=round(max_dd, 8),
            unit="fraction",
        ),
        MetricResult(
            metric_id="m_cash_end",
            kind="cash_end",
            label="Ending cash",
            value=round(portfolio.cash, 6),
            unit="USD",
        ),
        MetricResult(
            metric_id="m_gold_oz_end",
            kind="gold_oz_end",
            label="Ending gold ounces",
            value=round(portfolio.gold_oz, 8),
            unit="oz",
        ),
        MetricResult(
            metric_id="m_bitcoin_end",
            kind="bitcoin_end",
            label="Ending bitcoin",
            value=round(portfolio.bitcoin, 8),
            unit="BTC",
        ),
    ]


def execute_experiment_run(
    *,
    proposal: ResearchProposal | dict[str, Any],
    selected_candidate_id: str,
    problem_specification: ProblemSpecification | dict[str, Any] | None,
    h1_decision_id: str | None = None,
    strategy_id: str | None = None,
    lookback_days: int = 3,
    rebalance_every_n_days: int = 5,
    allow_sandboxed_python: bool = False,
) -> ExperimentRun:
    """Build and execute one deterministic experiment run (no H1 check here).

    Callers must enforce ``assert_modeling_allowed`` before invoking.
    """
    proposal_model = (
        proposal
        if isinstance(proposal, ResearchProposal)
        else ResearchProposal.model_validate(proposal)
    )
    candidate = next(
        (c for c in proposal_model.candidates if c.candidate_id == selected_candidate_id),
        None,
    )
    if candidate is None:
        raise ValueError(
            f"selected_candidate_id '{selected_candidate_id}' not found in proposal "
            f"'{proposal_model.proposal_id}'."
        )

    constraints = extract_problem_constraints(problem_specification)
    resolved_strategy = resolve_strategy_id(
        method_family=candidate.method_family,
        explicit=strategy_id,
    )
    params = build_experiment_params(
        constraints=constraints,
        strategy_id=resolved_strategy,
        lookback_days=lookback_days,
        rebalance_every_n_days=rebalance_every_n_days,
        allow_sandboxed_python=allow_sandboxed_python,
    )

    started = _utc_now()
    sandbox_note = None
    sandbox_attempted = False
    if allow_sandboxed_python or params.allow_sandboxed_python:
        sandbox_attempted = True
        sandbox_note = SANDBOX_UNAVAILABLE_NOTE

    portfolio, trades, equity, notes = run_deterministic_backtest(
        params=params,
        constraints=constraints,
    )
    finished = _utc_now()
    metrics = _metrics_from_portfolio(
        portfolio,
        initial_cash=constraints.initial_cash,
        equity=equity,
    )

    meta = fixture_metadata(params.price_fixture_id)
    bars = load_price_fixture(params.price_fixture_id)
    equity_series = [
        {
            "day_index": bars[i].day_index if i < len(bars) else i,
            "date": bars[i].date if i < len(bars) else str(i),
            "equity": equity[i],
        }
        for i in range(len(equity))
    ]
    equity_payload = {
        "n_points": len(equity),
        "first": equity[0] if equity else None,
        "last": equity[-1] if equity else None,
        "min": min(equity) if equity else None,
        "max": max(equity) if equity else None,
        # Cap stored points for persistence safety.
        "sample_points": equity[:: max(1, len(equity) // 8)][:8],
        # Full short fixture series for UI charts (14 bars max in CI fixture).
        "series": equity_series[:64],
    }
    trade_payload = {
        "n_trades": len(trades),
        "trades": trades[:12],
    }
    constraint_payload = constraints.model_dump(mode="json")

    artifacts = [
        ModelArtifactRef(
            artifact_id=_stable_id("art", "equity", proposal_model.proposal_id, started),
            kind="equity_curve_summary",
            summary="Compact equity curve summary over synthetic fixture window.",
            payload=equity_payload,
            content_sha256=_payload_sha(equity_payload),
        ),
        ModelArtifactRef(
            artifact_id=_stable_id("art", "trades", proposal_model.proposal_id, started),
            kind="trade_log_summary",
            summary="Compact trade log (capped) from deterministic runner.",
            payload=trade_payload,
            content_sha256=_payload_sha(trade_payload),
        ),
        ModelArtifactRef(
            artifact_id=_stable_id("art", "constraints", proposal_model.proposal_id, started),
            kind="constraint_snapshot",
            summary="Problem constraints applied to this run.",
            payload=constraint_payload,
            content_sha256=_payload_sha(constraint_payload),
        ),
        ModelArtifactRef(
            artifact_id=_stable_id("art", "fixture", proposal_model.proposal_id, started),
            kind="price_fixture_ref",
            summary=PRICE_FIXTURE_NOTE,
            payload=dict(meta),
            content_sha256=_payload_sha(dict(meta)),
        ),
    ]

    code_refs = [
        ExperimentCodeRef(
            kind="module_path",
            value="modeling/runner.py",
            note="Deterministic Phase 6 fixture runner",
        ),
        ExperimentCodeRef(
            kind="function_name",
            value="run_deterministic_backtest",
        ),
        ExperimentCodeRef(
            kind="strategy_id",
            value=resolved_strategy,
            note=f"mapped from method_family={candidate.method_family}",
        ),
        ExperimentCodeRef(
            kind="fixture_id",
            value=params.price_fixture_id,
        ),
        ExperimentCodeRef(
            kind="prompt_version",
            value=PROMPT_VERSION,
        ),
    ]

    if sandbox_note:
        notes.append(sandbox_note)

    run_id = _stable_id(
        "erun",
        proposal_model.proposal_id,
        selected_candidate_id,
        resolved_strategy,
        started,
    )
    return ExperimentRun(
        run_id=run_id,
        status="completed",
        strategy="deterministic_fixture",
        proposal_id=proposal_model.proposal_id,
        selected_candidate_id=selected_candidate_id,
        candidate_title=candidate.title,
        method_family=candidate.method_family,
        h1_status="approved",
        h1_decision_id=h1_decision_id,
        params=params,
        code_refs=code_refs,
        metrics=metrics,
        artifacts=artifacts,
        constraints=constraints,
        started_at_utc=started,
        finished_at_utc=finished,
        analysis_notes=notes[:32],
        sandboxed_python_attempted=sandbox_attempted,
        sandboxed_python_note=sandbox_note,
        live_trading_api_used=False,
        invented_results=False,
        agent_prompt_version=PROMPT_VERSION,
    )
