from __future__ import annotations

import pandas as pd
import pytest

from app.joint_eda_panel import calculate_joint_market_view


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
