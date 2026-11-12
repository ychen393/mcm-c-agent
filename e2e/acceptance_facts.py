"""Golden acceptance facts for 2022 MCM Problem C Trading Strategies.

These facts are derived from the official problem statement / Phase 2 extractor
and are asserted by the Phase 9 offline E2E harness.
"""

from __future__ import annotations

from typing import Any

# Canonical CSV deliverables named in the problem statement.
REQUIRED_CSV_NAMES: tuple[str, ...] = ("LBMA-GOLD.csv", "BCHAIN-MKPRU.csv")

# Compact catalogue used by docs / harness / golden checks.
ACCEPTANCE_FACTS_2022_C: dict[str, Any] = {
    "problem_id": "2022_mcm_c",
    "title": "Trading Strategies",
    "initial_cash_usd": 1000.0,
    "initial_state": [1000, 0, 0],
    "assets": ("gold", "bitcoin"),
    "alpha_gold": 0.01,
    "alpha_bitcoin": 0.02,
    "alpha_gold_display": "1%",
    "alpha_bitcoin_display": "2%",
    "past_data_only": True,
    "past_data_phrase": "only the past stream of daily prices",
    "csv_files": REQUIRED_CSV_NAMES,
    "gold_trade_weekdays_only": True,
    "bitcoin_trade_every_day": True,
    "gates_required": ("H1", "H2", "H3"),
    "never_auto_approve": ("H1", "H2", "H3"),
}

HARNESS_SIMULATED_HUMAN_NOTE = (
    "E2E harness simulated human approval (test-only double). "
    "Product UI remains human Approve / Request-revision only — "
    "H1/H2/H3 are never auto-approved in production."
)
