"""Offline 2022 MCM C CSV price-series preparation.

No interpolation of gold market closures, no future-data lookups, and no
implicit substitution of fixture data. The caller must supply both CSV files.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO

import pandas as pd

from modeling.fixture_data import PriceBar


@dataclass(frozen=True)
class PreparedPrices:
    bars: tuple[PriceBar, ...]
    gold_sha256: str
    bitcoin_sha256: str
    source: str = "uploaded_2022_mcm_c_csv"


def _parse_prices(payload: bytes, *, price_column: str, name: str) -> pd.DataFrame:
    if not payload:
        raise ValueError(f"{name}: empty CSV")
    frame = pd.read_csv(BytesIO(payload))
    if "Date" not in frame.columns or price_column not in frame.columns:
        raise ValueError(f"{name}: expected Date and {price_column} columns")
    frame = frame[["Date", price_column]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame[price_column] = pd.to_numeric(frame[price_column], errors="coerce")
    if frame["Date"].isna().any():
        raise ValueError(f"{name}: invalid date")
    if frame["Date"].duplicated().any():
        raise ValueError(f"{name}: duplicate date")
    valid = frame[price_column].dropna()
    if (valid <= 0).any():
        raise ValueError(f"{name}: nonpositive price")
    return frame.sort_values("Date").reset_index(drop=True)


def prepare_uploaded_2022_prices(gold_csv: bytes, bitcoin_csv: bytes) -> PreparedPrices:
    """Align on bitcoin calendar; gold None on closed/missing quote days.

    Missing bitcoin prices are rejected rather than filled. Gold positions are
    zero until an observed quote, avoiding any future price lookahead.
    """
    gold = _parse_prices(gold_csv, price_column="USD (PM)", name="LBMA-GOLD")
    btc = _parse_prices(bitcoin_csv, price_column="Value", name="BCHAIN-MKPRU")
    if btc.empty or gold.empty:
        raise ValueError("Both datasets must contain rows")
    if gold["USD (PM)"].notna().sum() == 0:
        raise ValueError("Gold has no observed price")
    if btc["Value"].isna().any():
        raise ValueError("Bitcoin prices must be present for each provided date")
    if len(btc) > 1 and not btc["Date"].diff().iloc[1:].eq(pd.Timedelta(days=1)).all():
        raise ValueError("Bitcoin daily dates have gaps; missing days must be resolved explicitly")
    if gold.loc[gold["USD (PM)"].notna(), "Date"].dt.dayofweek.ge(5).any():
        raise ValueError("Gold trading quotes on weekends are not permitted")
    # The official competition begins on a Sunday (before the first gold quote).
    # Initial zero gold holdings are valued at zero until the first observed quote.
    # Never fill with a future price.
    merged = btc.merge(gold, on="Date", how="left", validate="one_to_one")
    bars = tuple(
        PriceBar(
            day_index=i,
            date=row["Date"].strftime("%Y-%m-%d"),
            weekday=int(row["Date"].weekday()),
            gold=None if pd.isna(row["USD (PM)"]) else float(row["USD (PM)"]),
            bitcoin=float(row["Value"]),
        )
        for i, (_, row) in enumerate(merged.iterrows())
    )
    return PreparedPrices(
        bars=bars,
        gold_sha256=hashlib.sha256(gold_csv).hexdigest(),
        bitcoin_sha256=hashlib.sha256(bitcoin_csv).hexdigest(),
    )
