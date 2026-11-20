from __future__ import annotations

import pandas as pd
import pytest

from app.joint_eda_panel import (
    calculate_joint_market_insights,
    calculate_joint_market_view,
    joint_chart_explanations,
)


def test_joint_view_only_uses_observed_overlap_and_normalizes_first_price():
    gold = pd.DataFrame({
        "Date": ["2022-01-07", "2022-01-10"],
        "USD (PM)": [1800.0, 1818.0],
    })
    btc = pd.DataFrame({
        "Date": ["2022-01-07", "2022-01-08", "2022-01-09", "2022-01-10"],
        "Value": [40000.0, 50000.0, 60000.0, 44000.0],
    })
    joined = calculate_joint_market_view(gold, btc)
    assert len(joined) == 2
    assert joined["gold_index"].to_list() == [100.0, 101.0]
    assert joined["bitcoin_index"].to_list() == [100.0, 110.0]
    assert "2022-01-08" not in joined.index.strftime("%Y-%m-%d").to_list()


def test_join_rejects_ambiguous_duplicate_dates():
    gold = pd.DataFrame({
        "Date": ["2022-01-07", "2022-01-07"], "USD (PM)": [1800, 1810],
    })
    btc = pd.DataFrame({"Date": ["2022-01-07"], "Value": [40000]})
    with pytest.raises(ValueError, match="Duplicate dates"):
        calculate_joint_market_view(gold, btc)



def test_joint_insights_pair_exact_observed_dates_and_identify_btc_only_days():
    gold = pd.DataFrame({
        "Date": ["2022-01-07", "2022-01-10", "2022-01-11", "2022-01-12"],
        "USD (PM)": [100.0, 102.0, 99.0, 100.0],
    })
    btc = pd.DataFrame({
        "Date": [
            "2022-01-07", "2022-01-08", "2022-01-09",
            "2022-01-10", "2022-01-11", "2022-01-12",
        ],
        "Value": [1000.0, 1040.0, 1050.0, 1100.0, 1050.0, 990.0],
    })
    a, s = calculate_joint_market_insights(gold, btc)
    assert a.index.strftime("%Y-%m-%d").tolist() == [
        "2022-01-07", "2022-01-10", "2022-01-11", "2022-01-12"
    ]
    assert s["common_quote_days"] == 4
    assert s["bitcoin_observed_days"] == 6
    assert s["gold_observed_days"] == 4
    assert s["bitcoin_only_days"] == 2
    assert s["gold_only_days"] == 0
    assert s["paired_return_intervals"] == 3
    assert s["both_negative_intervals"] == 1
    assert -1 <= s["paired_return_correlation"] <= 1
    assert s["rolling_corr_latest"] is None
    assert s["joined"] is False
    assert set(s).isdisjoint({"preview_rows", "gold_price", "bitcoin_price", "raw_bytes"})
    stories = joint_chart_explanations(s, "zh")
    assert len(stories) == 6
    assert "2" in stories[5]["finding"]
    assert all(all(story[key] for key in ("read", "finding", "idea", "next"))
               for story in stories)
    assert any("相关" in story["finding"] for story in stories)
    assert len(joint_chart_explanations(s, "en")) == 6


def test_joint_rolling_correlation_uses_trailing_paired_returns_only():
    dates = pd.date_range("2021-01-01", periods=45, freq="D")
    # Alternate positive/negative returns and trends to avoid constant returns.
    gold_prices = [100.0]
    btc_prices = [1000.0]
    for i in range(1, 45):
        gold_prices.append(gold_prices[-1] * (1 + (0.01 if i % 2 else -0.015)))
        btc_prices.append(btc_prices[-1] * (1 + (0.025 if i % 3 else -0.010)))
    gold = pd.DataFrame({"Date": dates.astype(str), "USD (PM)": gold_prices})
    btc = pd.DataFrame({"Date": dates.astype(str), "Value": btc_prices})
    _, insight = calculate_joint_market_insights(gold, btc)
    assert insight["paired_return_intervals"] == 44
    assert insight["rolling_window_pairs"] == 20
    assert insight["rolling_corr_latest"] is not None
    assert -1 <= insight["rolling_corr_min"] <= insight["rolling_corr_max"] <= 1


def test_joint_requires_at_least_two_valid_overlapping_observations():
    gold = pd.DataFrame({"Date": ["2022-01-07", "2022-01-10"], "USD (PM)": [1800, None]})
    btc = pd.DataFrame({"Date": ["2022-01-07", "2022-01-10"], "Value": [40000, 41000]})
    with pytest.raises(ValueError, match="At least two"):
        calculate_joint_market_insights(gold, btc)
