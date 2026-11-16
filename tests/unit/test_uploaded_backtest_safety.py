"""Causal trading and calendar/fee invariants with offline uploaded bars."""
from __future__ import annotations

from modeling.runner import build_experiment_params, run_deterministic_backtest
from modeling.uploaded_prices import prepare_uploaded_2022_prices
from schemas.experiment import ProblemConstraintSnapshot

GOLD = b"Date,USD (PM)\n2022-01-07,1800\n2022-01-10,1810\n"
BTC = (
    b"Date,Value\n2022-01-07,40000\n2022-01-08,43000\n"
    b"2022-01-09,45000\n2022-01-10,47000\n"
)


def _run(strategy, bars, lookback=2):
    constraints = ProblemConstraintSnapshot(
        initial_cash=1000,
        alpha_gold=0.01,
        alpha_bitcoin=0.02,
        assets=["gold", "bitcoin"],
        past_data_only=True,
        gold_trade_weekdays_only=True,
    )
    params = build_experiment_params(
        constraints=constraints,
        strategy_id=strategy,
        lookback_days=lookback,
        price_fixture_id="uploaded_2022_mcm_c_csv_v1",
    )
    return run_deterministic_backtest(
        params=params, constraints=constraints, price_bars=bars
    )


def test_cash_hold_and_buy_hold_bitcoin_respect_commission():
    bars = list(prepare_uploaded_2022_prices(GOLD, BTC).bars)
    cash, trades, curve, notes = _run("cash_hold", bars)
    assert cash.cash == 1000
    assert not trades
    assert all(v == 1000 for v in curve)

    btc_portfolio, btc_trades, equity, notes = _run("buy_hold_bitcoin", bars)
    assert len(btc_trades) == 1
    assert btc_trades[0]["day"] == "2022-01-07"
    assert btc_portfolio.bitcoin > 0
    assert btc_portfolio.cost_paid > 0
    assert abs(equity[0] - 1000 / 1.02) < 1e-4


def test_gold_trades_only_on_available_quotes():
    bars = list(prepare_uploaded_2022_prices(GOLD, BTC).bars)
    gold, trades, curve, notes = _run("buy_hold_gold", bars)
    assert [t["day"] for t in trades] == ["2022-01-07"]
    assert gold.gold_oz > 0
    assert curve[1] == curve[0]
    assert curve[2] == curve[0]


def test_first_three_trend_decisions_do_not_depend_on_future_price():
    bars = list(prepare_uploaded_2022_prices(GOLD, BTC).bars)
    short = _run("trend_follow_bitcoin", bars[:3], lookback=2)
    full = _run("trend_follow_bitcoin", bars, lookback=2)
    assert short[1] == [trade for trade in full[1] if trade["day"] <= bars[2].date]
    assert short[2] == full[2][:3]
