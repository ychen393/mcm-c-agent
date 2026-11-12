"""Deterministic 2022 MCM C → ProblemSpecification extractor.

Validates that required official facts appear in the supplied problem text, then
emits a typed specification with official / inferred / unknown provenance.
Does not call an LLM.
"""
from __future__ import annotations

import re
from pathlib import Path

from schemas.problem_specification import (
    AssumptionToValidate,
    ConstraintItem,
    DatasetItem,
    DeliverableItem,
    FormulaItem,
    NumericCondition,
    ObjectiveItem,
    ProblemSpecification,
    ResearchQuestion,
    SubproblemSpec,
    TradingRule,
    UnknownOrRisk,
)

FIXTURE_RELATIVE = Path("data/problem_fixtures/2022_mcm_c_trading_strategies.txt")
PROBLEM_ID = "2022_mcm_c"
TITLE = "Trading Strategies"

# Facts that must be literally present (case-insensitive where noted) for acceptance.
REQUIRED_SNIPPETS: dict[str, str] = {
    "initial_cash": "$1000",
    "initial_state": "[1000, 0, 0]",
    "assets_gold": "gold",
    "assets_bitcoin": "bitcoin",
    "alpha_gold": "αgold = 1%",
    "alpha_bitcoin": "αbitcoin = 2%",
    "past_data": "only the past stream of daily prices",
    "gold_schedule": "gold is only traded on days the market is open",
    "bitcoin_schedule": "bitcoin can be traded every day",
    "gold_file": "LBMA-GOLD.csv",
    "bitcoin_file": "BCHAIN-MKPRU.csv",
}


def fixture_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / FIXTURE_RELATIVE


def load_2022_c_fixture(repo_root: Path | None = None) -> str:
    path = fixture_path(repo_root)
    return path.read_text(encoding="utf-8")


def _require_snippet(text: str, key: str, snippet: str) -> str:
    if snippet.lower() not in text.lower() and snippet not in text:
        # Alpha character variants: allow ascii "alpha" forms in some copies.
        alt = {
            "αgold = 1%": ("agold = 1%", "alpha_gold = 1%", "α_gold = 1%"),
            "αbitcoin = 2%": ("abitcoin = 2%", "alpha_bitcoin = 2%", "α_bitcoin = 2%"),
        }.get(snippet, ())
        if not any(candidate.lower() in text.lower() or candidate in text for candidate in alt):
            raise ValueError(
                f"2022 MCM C acceptance fact '{key}' not found in problem text "
                f"(expected excerpt containing {snippet!r})."
            )
    # Prefer the exact official excerpt when present; else return the canonical snippet.
    idx = text.find(snippet)
    if idx >= 0:
        start = max(0, idx - 20)
        end = min(len(text), idx + len(snippet) + 40)
        return text[start:end].strip()
    return snippet


def _excerpt_around(text: str, needle: str, *, radius: int = 60) -> str:
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return needle
    start = max(0, idx - radius)
    end = min(len(text), idx + len(needle) + radius)
    return " ".join(text[start:end].split())


def detect_2022_mcm_c(problem_text: str) -> bool:
    lowered = problem_text.lower()
    has_title = "trading strategies" in lowered and ("2022" in lowered or "mcm problem c" in lowered)
    has_assets = "gold" in lowered and "bitcoin" in lowered
    has_cash = "$1000" in problem_text or "[1000, 0, 0]" in problem_text
    has_files = "lbma-gold.csv" in lowered and "bchain-mkpru.csv" in lowered
    return bool(has_title and has_assets and has_cash and has_files)


def build_2022_c_specification(problem_text: str) -> ProblemSpecification:
    """Build a validated ProblemSpecification for 2022 MCM C from problem text."""
    text = problem_text.strip()
    if not text:
        raise ValueError("problem text is empty")
    if not detect_2022_mcm_c(text):
        raise ValueError(
            "Problem text does not match the 2022 MCM C Trading Strategies signature "
            "(title/year, gold+bitcoin, $1000 / [1000,0,0], LBMA-GOLD + BCHAIN-MKPRU)."
        )

    excerpts = {key: _require_snippet(text, key, snippet) for key, snippet in REQUIRED_SNIPPETS.items()}

    research_questions = [
        ResearchQuestion(
            id="rq_best_strategy_value",
            statement=(
                "Develop a daily buy/hold/sell strategy using only past prices and report "
                "the terminal value of the initial $1000 on 9/10/2021."
            ),
            provenance="official",
            source_excerpt=_excerpt_around(text, "How much is the initial $1000 investment worth"),
            source_location="Requirement bullet 1",
        ),
        ResearchQuestion(
            id="rq_best_strategy_evidence",
            statement="Present evidence that the model provides the best strategy.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "Present evidence that your model provides the best strategy"),
            source_location="Requirement bullet 2",
        ),
        ResearchQuestion(
            id="rq_transaction_sensitivity",
            statement=(
                "Determine how sensitive the strategy is to transaction costs and how "
                "costs affect strategy and results."
            ),
            provenance="official",
            source_excerpt=_excerpt_around(text, "sensitive the strategy is to transaction costs"),
            source_location="Requirement bullet 3",
        ),
        ResearchQuestion(
            id="rq_trader_memorandum",
            statement="Communicate strategy, model, and results in a memorandum of at most two pages.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "memorandum of at most two pages"),
            source_location="Requirement bullet 4",
        ),
    ]

    objectives = [
        ObjectiveItem(
            id="obj_maximize_return",
            statement="Maximize total return of a portfolio trading gold and bitcoin.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "maximize their total return"),
            source_location="Background",
        ),
        ObjectiveItem(
            id="obj_daily_decisions",
            statement="Each day decide whether to buy, hold, or sell assets in the portfolio.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "buy, hold, or sell"),
            source_location="Requirement",
        ),
    ]

    constraints = [
        ConstraintItem(
            id="c_initial_capital",
            statement="Start with $1000 cash on 9/11/2016; initial portfolio state is [1000, 0, 0].",
            provenance="official",
            source_excerpt=excerpts["initial_state"],
            source_location="Requirement",
            constraint_kind="capital",
        ),
        ConstraintItem(
            id="c_assets_only",
            statement="Tradable assets are gold and bitcoin (plus cash holdings).",
            provenance="official",
            source_excerpt=_excerpt_around(text, "cash, gold, and bitcoin"),
            source_location="Requirement",
            constraint_kind="assets",
        ),
        ConstraintItem(
            id="c_trading_period",
            statement="Use the five-year trading period from 9/11/2016 to 9/10/2021.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "from 9/11/2016 to 9/10/2021"),
            source_location="Requirement",
            constraint_kind="trading_calendar",
        ),
        ConstraintItem(
            id="c_gold_trading_days",
            statement="Gold may be traded only on days the market is open (as in LBMA-GOLD.csv).",
            provenance="official",
            source_excerpt=excerpts["gold_schedule"],
            source_location="Trading schedule note",
            constraint_kind="trading_calendar",
        ),
        ConstraintItem(
            id="c_bitcoin_trading_days",
            statement="Bitcoin may be traded every day.",
            provenance="official",
            source_excerpt=excerpts["bitcoin_schedule"],
            source_location="Trading schedule note",
            constraint_kind="trading_calendar",
        ),
        ConstraintItem(
            id="c_transaction_costs",
            statement="Commission is α% of amount traded: αgold = 1%, αbitcoin = 2%; no hold cost.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "αgold = 1%"),
            source_location="Requirement",
            constraint_kind="transaction_cost",
        ),
        ConstraintItem(
            id="c_past_data_only",
            statement="Decisions may use only the past stream of daily prices to date (no future leakage).",
            provenance="official",
            source_excerpt=excerpts["past_data"],
            source_location="Requirement",
            constraint_kind="information",
        ),
        ConstraintItem(
            id="c_only_supplied_data",
            statement="Only LBMA-GOLD.csv and BCHAIN-MKPRU.csv may be used as data.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "only use the data in the two spreadsheets"),
            source_location="Data restriction",
            constraint_kind="data_use",
        ),
        ConstraintItem(
            id="c_page_limit",
            statement="PDF solution is limited to 25 total pages including all listed components.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "25 total pages"),
            source_location="Submission requirements",
            constraint_kind="deliverable",
        ),
    ]

    supplied_datasets = [
        DatasetItem(
            id="ds_lbma_gold",
            statement="LBMA gold PM closing prices by date.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "USD (PM)"),
            source_location="Data Descriptions",
            file_name="LBMA-GOLD.csv",
            columns=["Date", "USD (PM)"],
            notes="Date format mm-dd-yyyy; USD per troy ounce.",
        ),
        DatasetItem(
            id="ds_bchain_mkpru",
            statement="Bitcoin daily market price in USD.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "Value: The price in U.S. dollars of a single bitcoin"),
            source_location="Data Descriptions",
            file_name="BCHAIN-MKPRU.csv",
            columns=["Date", "Value"],
            notes="Date format mm-dd-yyyy; USD per bitcoin.",
        ),
    ]

    assumptions = [
        AssumptionToValidate(
            id="a_commission_each_side",
            statement=(
                "Each purchase and each sale incurs the stated commission on the traded amount "
                "(not a round-trip single fee)."
            ),
            provenance="inferred",
            source_excerpt=_excerpt_around(text, "commission for each transaction (purchase or sale)"),
            source_location="Requirement",
        ),
        AssumptionToValidate(
            id="a_price_executes_at_close",
            statement="Trades on a day execute at that day's reported closing/price series value.",
            provenance="inferred",
            source_location="Inferred from daily price files; not stated as an execution model",
        ),
        AssumptionToValidate(
            id="a_fractional_holdings",
            statement="Whether fractional troy ounces / bitcoin units are allowed is not specified.",
            provenance="unknown",
            source_location="Not stated in problem text",
        ),
    ]

    deliverables = [
        DeliverableItem(
            id="d_summary_sheet",
            statement="One-page Summary Sheet.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "One-page Summary Sheet"),
            source_location="PDF solution checklist",
        ),
        DeliverableItem(
            id="d_toc",
            statement="Table of Contents.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "Table of Contents"),
            source_location="PDF solution checklist",
        ),
        DeliverableItem(
            id="d_complete_solution",
            statement="Complete solution within the page limit.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "Your complete solution"),
            source_location="PDF solution checklist",
        ),
        DeliverableItem(
            id="d_memorandum",
            statement="One- to two-page memorandum to the trader.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "One- to two-page Memorandum"),
            source_location="PDF solution checklist",
        ),
        DeliverableItem(
            id="d_references",
            statement="Reference List with citations for ideas, images, and materials used.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "Reference List"),
            source_location="PDF solution checklist",
        ),
    ]

    unknowns = [
        UnknownOrRisk(
            id="u_best_strategy_definition",
            statement=(
                "What constitutes a uniquely 'best' strategy is under-specified "
                "(terminal wealth vs risk-adjusted vs robustness)."
            ),
            severity="high",
            mitigation_hint="Define optimality criteria explicitly and compare baselines.",
        ),
        UnknownOrRisk(
            id="u_slippage_liquidity",
            statement="Market impact, bid-ask spread, and liquidity are not modeled in the problem statement.",
            severity="medium",
            mitigation_hint="State as limitation; do not invent liquidity costs without labeling as assumption.",
        ),
        UnknownOrRisk(
            id="u_risk_free_cash",
            statement="Whether cash earns interest is not stated.",
            severity="low",
            mitigation_hint="Default to zero interest and mark as assumption to validate.",
        ),
    ]

    subproblems = [
        SubproblemSpec(
            id="sp_strategy_model",
            title="Daily trading strategy and terminal value",
            statement=(
                "Build a model that, each day, chooses buy/hold/sell using only prices observed "
                "up to that day, and report portfolio value on 9/10/2021 starting from $1000."
            ),
            provenance="official",
            source_excerpt=_excerpt_around(text, "best daily trading strategy based only on price data"),
            source_location="Requirement bullet 1",
            inputs=[
                "LBMA-GOLD.csv daily gold prices",
                "BCHAIN-MKPRU.csv daily bitcoin prices",
                "Initial portfolio [1000, 0, 0]",
                "Commission rates αgold=1%, αbitcoin=2%",
            ],
            outputs=[
                "Daily action policy for cash/gold/bitcoin",
                "Terminal portfolio value on 9/10/2021",
                "Equity / holdings trajectory",
            ],
            evidence_needed=[
                "Causal-safe features using only past prices",
                "Respect gold vs bitcoin trading calendars",
                "Account for commissions on each trade",
            ],
            candidate_methods=[
                "Rule-based technical indicators with walk-forward evaluation",
                "Trend/mean-reversion baselines",
                "Dynamic allocation / heuristic optimization with no lookahead",
            ],
            acceptance_criteria=[
                "No future price leakage in decisions",
                "Gold trades only on LBMA market days",
                "Reported terminal value reproducible from logged trades",
            ],
        ),
        SubproblemSpec(
            id="sp_strategy_evidence",
            title="Evidence of strategy quality",
            statement="Present evidence that the model provides the best strategy.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "Present evidence that your model provides the best strategy"),
            source_location="Requirement bullet 2",
            inputs=["Candidate strategies", "Price history within trading window"],
            outputs=["Comparative performance table", "Baseline benchmarks", "Robustness checks"],
            evidence_needed=["Out-of-sample or walk-forward metrics", "Baseline buy-and-hold comparisons"],
            candidate_methods=["Benchmark comparison", "Ablation of signals", "Bootstrap/resampling of returns"],
            acceptance_criteria=[
                "At least one transparent baseline",
                "Claims tied to computed metrics, not narrative alone",
            ],
        ),
        SubproblemSpec(
            id="sp_cost_sensitivity",
            title="Transaction-cost sensitivity",
            statement="Analyze how transaction costs affect strategy and results.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "sensitive the strategy is to transaction costs"),
            source_location="Requirement bullet 3",
            inputs=["Base strategy", "αgold / αbitcoin (and perturbations)"],
            outputs=["Sensitivity curves or tables", "Narrative of cost impact on trading frequency"],
            evidence_needed=["Re-runs under varied α", "Turnover statistics"],
            candidate_methods=["One-at-a-time sensitivity", "Grid over commission rates"],
            acceptance_criteria=[
                "Vary costs around official 1% / 2%",
                "Report effect on terminal value and trade frequency",
            ],
        ),
        SubproblemSpec(
            id="sp_memorandum",
            title="Trader memorandum",
            statement="Communicate strategy, model, and results in ≤2 pages.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "memorandum of at most two pages"),
            source_location="Requirement bullet 4",
            inputs=["Approved strategy summary", "Key results and limitations"],
            outputs=["1–2 page memorandum"],
            evidence_needed=["Clear decision rules", "Main numerical results", "Risks/limitations"],
            candidate_methods=["Executive memo structure"],
            acceptance_criteria=["Length ≤ 2 pages", "Actionable for a trader audience"],
        ),
    ]

    key_formulas = [
        FormulaItem(
            id="f_commission",
            name="Transaction commission",
            expression="commission = (α/100) * amount_traded; α_gold=1, α_bitcoin=2",
            provenance="official",
            source_excerpt=_excerpt_around(text, "costs α% of the amount traded"),
            source_location="Requirement",
            notes="Hold cost is zero.",
        ),
        FormulaItem(
            id="f_portfolio_state",
            name="Portfolio state vector",
            expression="[C, G, B] with units USD, troy ounces, bitcoins; initial [1000, 0, 0]",
            provenance="official",
            source_excerpt=_excerpt_around(text, "The initial state is [1000, 0, 0]"),
            source_location="Requirement",
        ),
    ]

    numeric_conditions = [
        NumericCondition(
            id="n_initial_cash",
            name="Initial cash",
            value="1000",
            unit="USD",
            provenance="official",
            source_excerpt=excerpts["initial_cash"],
            source_location="Requirement",
        ),
        NumericCondition(
            id="n_alpha_gold",
            name="Gold commission rate",
            value="1",
            unit="percent",
            provenance="official",
            source_excerpt=excerpts["alpha_gold"],
            source_location="Requirement",
        ),
        NumericCondition(
            id="n_alpha_bitcoin",
            name="Bitcoin commission rate",
            value="2",
            unit="percent",
            provenance="official",
            source_excerpt=excerpts["alpha_bitcoin"],
            source_location="Requirement",
        ),
        NumericCondition(
            id="n_period_start",
            name="Trading period start",
            value="2016-09-11",
            unit="date",
            provenance="official",
            source_excerpt=_excerpt_around(text, "9/11/2016"),
            source_location="Requirement",
        ),
        NumericCondition(
            id="n_period_end",
            name="Trading period end",
            value="2021-09-10",
            unit="date",
            provenance="official",
            source_excerpt=_excerpt_around(text, "9/10/2021"),
            source_location="Requirement",
        ),
        NumericCondition(
            id="n_page_limit",
            name="PDF page limit",
            value="25",
            unit="pages",
            provenance="official",
            source_excerpt=_excerpt_around(text, "25 total pages"),
            source_location="Submission requirements",
        ),
    ]

    trading_rules = [
        TradingRule(
            id="tr_actions",
            statement="Each trading day the decision is buy, hold, or sell assets in the portfolio.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "buy, hold, or sell their assets"),
            source_location="Requirement",
            applies_to=["cash", "gold", "bitcoin"],
        ),
        TradingRule(
            id="tr_past_prices_only",
            statement="Use only past daily prices available up to the decision day.",
            provenance="official",
            source_excerpt=excerpts["past_data"],
            source_location="Requirement",
            applies_to=["model_inputs"],
        ),
        TradingRule(
            id="tr_gold_calendar",
            statement="Gold trades only on market-open days reflected in LBMA-GOLD.csv.",
            provenance="official",
            source_excerpt=excerpts["gold_schedule"],
            source_location="Trading schedule note",
            applies_to=["gold"],
        ),
        TradingRule(
            id="tr_bitcoin_calendar",
            statement="Bitcoin can be traded every day.",
            provenance="official",
            source_excerpt=excerpts["bitcoin_schedule"],
            source_location="Trading schedule note",
            applies_to=["bitcoin"],
        ),
        TradingRule(
            id="tr_no_hold_cost",
            statement="There is no cost to hold an asset.",
            provenance="official",
            source_excerpt=_excerpt_around(text, "There is no cost to hold an asset"),
            source_location="Requirement",
            applies_to=["gold", "bitcoin", "cash"],
        ),
    ]

    return ProblemSpecification(
        problem_id=PROBLEM_ID,
        title=TITLE,
        research_questions=research_questions,
        objectives=objectives,
        constraints=constraints,
        supplied_datasets=supplied_datasets,
        assumptions_to_validate=assumptions,
        required_deliverables=deliverables,
        unknowns_or_risks=unknowns,
        subproblems=subproblems,
        key_formulas=key_formulas,
        numeric_conditions=numeric_conditions,
        trading_rules=trading_rules,
        strategy="deterministic",
        analyst_prompt_version="problem_analyst_v1",
        analysis_notes=[
            "Deterministic extractor for 2022 MCM Problem C.",
            "Official items require source excerpts from the supplied problem text.",
            "Inferred/unknown items must not be treated as contest constraints without labeling.",
        ],
    )


def acceptance_checklist_2022_c(spec: ProblemSpecification) -> dict[str, bool]:
    """Deterministic acceptance checks for Phase 2 / 2022 C."""
    dataset_names = " ".join(d.file_name for d in spec.supplied_datasets).lower()
    statements = " ".join(
        [
            *[c.statement for c in spec.constraints],
            *[t.statement for t in spec.trading_rules],
            *[o.statement for o in spec.objectives],
            *[q.statement for q in spec.research_questions],
        ]
    ).lower()
    numeric = {n.id: n for n in spec.numeric_conditions}
    return {
        "initial_1000": (
            numeric.get("n_initial_cash") is not None and numeric["n_initial_cash"].value == "1000"
        ),
        "assets_gold_bitcoin": "gold" in statements and "bitcoin" in statements,
        "trading_day_limits": ("market is open" in statements or "market-open" in statements),
        "bitcoin_every_day": "every day" in statements,
        "transaction_costs": (
            numeric.get("n_alpha_gold") is not None
            and numeric["n_alpha_gold"].value == "1"
            and numeric.get("n_alpha_bitcoin") is not None
            and numeric["n_alpha_bitcoin"].value == "2"
        ),
        "past_data_only": "past" in statements and ("price" in statements or "prices" in statements),
        "datasets_present": "lbma-gold.csv" in dataset_names and "bchain-mkpru.csv" in dataset_names,
        "problem_id": spec.problem_id == PROBLEM_ID,
        "title": re.search(r"trading strategies", spec.title, re.I) is not None,
    }
