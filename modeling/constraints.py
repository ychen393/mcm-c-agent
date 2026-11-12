"""Extract trading constraints from ProblemSpecification for Phase 6 runs.

When a validated ProblemSpecification is present, official numeric conditions
and constraints win. Otherwise fall back to documented 2022 MCM C defaults
(initial $1000, αgold=1%, αbitcoin=2%, gold+bitcoin, past-data-only).
"""

from __future__ import annotations

from typing import Any

from schemas.experiment import ProblemConstraintSnapshot
from schemas.problem_specification import ProblemSpecification

# Official 2022 MCM C defaults used when the spec is absent or incomplete.
DEFAULT_INITIAL_CASH = 1000.0
DEFAULT_ALPHA_GOLD = 0.01
DEFAULT_ALPHA_BITCOIN = 0.02
DEFAULT_ASSETS = ["cash", "gold", "bitcoin"]


def _as_problem_spec(
    problem_specification: ProblemSpecification | dict[str, Any] | None,
) -> ProblemSpecification | None:
    if problem_specification is None:
        return None
    if isinstance(problem_specification, ProblemSpecification):
        return problem_specification
    if isinstance(problem_specification, dict) and problem_specification:
        try:
            return ProblemSpecification.model_validate(problem_specification)
        except Exception:
            return None
    return None


def _parse_cash(raw: str) -> float | None:
    text = str(raw).strip().replace("$", "").replace(",", "")
    try:
        value = float(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _parse_rate_percent(raw: str) -> float | None:
    """Parse α values stored as percent ("1") or fraction ("0.01")."""
    text = str(raw).strip().lower().replace("%", "").replace(",", "")
    try:
        value = float(text)
    except ValueError:
        return None
    if value < 0:
        return None
    if value > 1.0:
        return value / 100.0
    # Ambiguous: 2022 C stores "1" / "2" as percent integers.
    # Values in (0, 1] may already be fractions; treat <=1 as fraction only when
    # the raw string contains a decimal point, else as percent.
    if "." in text:
        return value
    return value / 100.0


def _numeric_map(spec: ProblemSpecification) -> dict[str, str]:
    return {item.id: item.value for item in spec.numeric_conditions}


def extract_problem_constraints(
    problem_specification: ProblemSpecification | dict[str, Any] | None,
) -> ProblemConstraintSnapshot:
    """Build a constraint snapshot for the deterministic modeling runner."""
    spec = _as_problem_spec(problem_specification)
    if spec is None:
        return ProblemConstraintSnapshot(
            problem_id=None,
            initial_cash=DEFAULT_INITIAL_CASH,
            alpha_gold=DEFAULT_ALPHA_GOLD,
            alpha_bitcoin=DEFAULT_ALPHA_BITCOIN,
            assets=list(DEFAULT_ASSETS),
            past_data_only=True,
            gold_trade_weekdays_only=True,
            source="defaults_2022_mcm_c",
            notes=[
                "ProblemSpecification absent — using documented 2022 MCM C defaults.",
            ],
        )

    notes: list[str] = []
    numeric = _numeric_map(spec)

    initial_cash = DEFAULT_INITIAL_CASH
    if "n_initial_cash" in numeric:
        parsed = _parse_cash(numeric["n_initial_cash"])
        if parsed is not None:
            initial_cash = parsed
            notes.append("initial_cash from ProblemSpecification n_initial_cash.")
        else:
            notes.append("Could not parse n_initial_cash; kept default 1000.")
    else:
        notes.append("n_initial_cash missing — default initial_cash=1000.")

    alpha_gold = DEFAULT_ALPHA_GOLD
    if "n_alpha_gold" in numeric:
        parsed = _parse_rate_percent(numeric["n_alpha_gold"])
        if parsed is not None:
            alpha_gold = parsed
            notes.append("alpha_gold from ProblemSpecification n_alpha_gold.")
        else:
            notes.append("Could not parse n_alpha_gold; kept default 0.01.")
    else:
        notes.append("n_alpha_gold missing — default alpha_gold=0.01.")

    alpha_bitcoin = DEFAULT_ALPHA_BITCOIN
    if "n_alpha_bitcoin" in numeric:
        parsed = _parse_rate_percent(numeric["n_alpha_bitcoin"])
        if parsed is not None:
            alpha_bitcoin = parsed
            notes.append("alpha_bitcoin from ProblemSpecification n_alpha_bitcoin.")
        else:
            notes.append("Could not parse n_alpha_bitcoin; kept default 0.02.")
    else:
        notes.append("n_alpha_bitcoin missing — default alpha_bitcoin=0.02.")

    past_data_only = True
    gold_weekdays = True
    assets = list(DEFAULT_ASSETS)
    for item in spec.constraints:
        statement = item.statement.lower()
        if item.constraint_kind == "assets":
            found: list[str] = ["cash"]
            if "gold" in statement:
                found.append("gold")
            if "bitcoin" in statement or "btc" in statement:
                found.append("bitcoin")
            if len(found) > 1:
                assets = found
        if "past" in statement and "price" in statement:
            past_data_only = True
        if "gold" in statement and ("weekday" in statement or "market is open" in statement):
            gold_weekdays = True

    for rule in spec.trading_rules:
        text = rule.statement.lower()
        if "gold" in text and ("open" in text or "weekday" in text):
            gold_weekdays = True
        if "past" in text and "price" in text:
            past_data_only = True

    return ProblemConstraintSnapshot(
        problem_id=spec.problem_id,
        initial_cash=float(initial_cash),
        alpha_gold=float(alpha_gold),
        alpha_bitcoin=float(alpha_bitcoin),
        assets=assets,
        past_data_only=past_data_only,
        gold_trade_weekdays_only=gold_weekdays,
        source="problem_specification",
        notes=notes[:16],
    )
