"""Deterministic synthetic price fixture for 2022 MCM C modeling CI (Phase 6).

This is **not** LBMA / Blockchain.com historical data. It is a tiny fixed series
so pytest and the Streamlit deterministic path stay offline and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PRICE_FIXTURE_ID = "fx_2022_mcm_c_prices_v1"
PRICE_FIXTURE_NOTE = (
    "Synthetic CI price fixture for Phase 6 deterministic modeling. "
    "Not real LBMA-GOLD or BCHAIN-MKPRU market data."
)

AssetName = Literal["gold", "bitcoin"]


@dataclass(frozen=True)
class PriceBar:
    day_index: int
    date: str
    weekday: int  # Monday=0 .. Sunday=6
    gold: float | None  # None on weekends (gold market closed)
    bitcoin: float


# Fixed 14-day synthetic window (covers weekdays + weekend gold gaps).
_SYNTHETIC_BARS: tuple[PriceBar, ...] = (
    PriceBar(0, "2016-09-12", 0, 1324.60, 621.65),
    PriceBar(1, "2016-09-13", 1, 1321.75, 609.67),
    PriceBar(2, "2016-09-14", 2, 1325.10, 610.20),
    PriceBar(3, "2016-09-15", 3, 1328.40, 615.55),
    PriceBar(4, "2016-09-16", 4, 1330.00, 620.10),
    PriceBar(5, "2016-09-17", 5, None, 618.40),  # Saturday — gold closed
    PriceBar(6, "2016-09-18", 6, None, 622.00),  # Sunday — gold closed
    PriceBar(7, "2016-09-19", 0, 1332.25, 630.50),
    PriceBar(8, "2016-09-20", 1, 1335.80, 640.20),
    PriceBar(9, "2016-09-21", 2, 1331.10, 635.00),
    PriceBar(10, "2016-09-22", 3, 1329.40, 628.75),
    PriceBar(11, "2016-09-23", 4, 1334.00, 645.30),
    PriceBar(12, "2016-09-24", 5, None, 650.00),
    PriceBar(13, "2016-09-25", 6, None, 648.20),
)


def load_price_fixture(fixture_id: str = PRICE_FIXTURE_ID) -> list[PriceBar]:
    """Return the synthetic price bars. Raises if an unknown fixture is requested."""
    if fixture_id != PRICE_FIXTURE_ID:
        raise ValueError(
            f"Unknown price fixture '{fixture_id}'. "
            f"Phase 6 CI path supports only '{PRICE_FIXTURE_ID}'."
        )
    return list(_SYNTHETIC_BARS)


def fixture_metadata(fixture_id: str = PRICE_FIXTURE_ID) -> dict[str, object]:
    bars = load_price_fixture(fixture_id)
    return {
        "fixture_id": fixture_id,
        "note": PRICE_FIXTURE_NOTE,
        "n_bars": len(bars),
        "start_date": bars[0].date,
        "end_date": bars[-1].date,
        "assets": ["gold", "bitcoin"],
        "is_synthetic": True,
        "live_market_data": False,
    }
