"""CI-safe deterministic validation / sensitivity runner (Phase 7).

Reuses the Phase 6 synthetic price fixture and backtest stubs. Perturbs
transaction costs, lookback / rebalance windows, and related params for the
2022 MCM C trading slice. No live trading APIs. Optional LLM critique is a
non-executing stub when requested.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from modeling.constraints import extract_problem_constraints
from modeling.runner import (
    build_experiment_params,
    resolve_strategy_id,
    run_deterministic_backtest,
)
from schemas.experiment import ExperimentParams, ProblemConstraintSnapshot
from schemas.problem_specification import ProblemSpecification
from schemas.validation import (
    MetricDelta,
    MetricSnapshot,
    PerturbationSpec,
    RobustnessNote,
    SensitivityScenario,
    ValidationReport,
)

PROMPT_VERSION = "validation_sensitivity_v1"
LLM_UNAVAILABLE_NOTE = (
    "Optional LLM validation critique is not enabled for live calls in this "
    "Phase 7 slice. The deterministic sensitivity runner remains authoritative."
)

# Metrics used for robustness summaries (stable ids from Phase 6 runner).
_FOCUS_METRICS = (
    "m_terminal_value",
    "m_total_return",
    "m_max_drawdown",
    "m_cost_paid",
    "m_n_trades",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"[:64]


def _payload_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _metric_map_from_run(run: dict[str, Any]) -> dict[str, MetricSnapshot]:
    out: dict[str, MetricSnapshot] = {}
    for item in run.get("metrics") or []:
        if not isinstance(item, dict):
            continue
        mid = item.get("metric_id")
        if not mid:
            continue
        out[str(mid)] = MetricSnapshot(
            metric_id=str(mid),
            kind=str(item.get("kind") or "other"),
            label=str(item.get("label") or mid),
            value=float(item["value"]),
            unit=item.get("unit"),
        )
    return out


def _metrics_from_portfolio(
    portfolio: Any,
    *,
    initial_cash: float,
    equity: list[float],
) -> list[MetricSnapshot]:
    terminal = equity[-1] if equity else float(portfolio.cash)
    total_return = (terminal - initial_cash) / initial_cash if initial_cash else 0.0
    peak = equity[0] if equity else terminal
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, (value - peak) / peak)
    return [
        MetricSnapshot(
            metric_id="m_terminal_value",
            kind="terminal_value",
            label="Terminal portfolio value",
            value=round(terminal, 6),
            unit="USD",
        ),
        MetricSnapshot(
            metric_id="m_total_return",
            kind="total_return",
            label="Total return",
            value=round(total_return, 8),
            unit="fraction",
        ),
        MetricSnapshot(
            metric_id="m_n_trades",
            kind="n_trades",
            label="Number of trades",
            value=float(portfolio.n_trades),
            unit="count",
        ),
        MetricSnapshot(
            metric_id="m_cost_paid",
            kind="transaction_cost_paid",
            label="Transaction costs paid",
            value=round(portfolio.cost_paid, 6),
            unit="USD",
        ),
        MetricSnapshot(
            metric_id="m_max_drawdown",
            kind="max_drawdown",
            label="Max drawdown (fixture window)",
            value=round(max_dd, 8),
            unit="fraction",
        ),
        MetricSnapshot(
            metric_id="m_cash_end",
            kind="cash_end",
            label="Ending cash",
            value=round(portfolio.cash, 6),
            unit="USD",
        ),
        MetricSnapshot(
            metric_id="m_gold_oz_end",
            kind="gold_oz_end",
            label="Ending gold ounces",
            value=round(portfolio.gold_oz, 8),
            unit="oz",
        ),
        MetricSnapshot(
            metric_id="m_bitcoin_end",
            kind="bitcoin_end",
            label="Ending bitcoin",
            value=round(portfolio.bitcoin, 8),
            unit="BTC",
        ),
    ]


def _deltas(
    baseline: dict[str, MetricSnapshot],
    scenario: list[MetricSnapshot],
) -> list[MetricDelta]:
    deltas: list[MetricDelta] = []
    for metric in scenario:
        base = baseline.get(metric.metric_id)
        if base is None:
            continue
        abs_delta = metric.value - base.value
        rel = None
        if base.value != 0:
            rel = abs_delta / abs(base.value)
        deltas.append(
            MetricDelta(
                metric_id=metric.metric_id,
                label=metric.label,
                baseline_value=base.value,
                scenario_value=metric.value,
                absolute_delta=round(abs_delta, 8),
                relative_delta=round(rel, 8) if rel is not None else None,
                unit=metric.unit or base.unit,
            )
        )
    return deltas


def _resolve_baseline_run(experiment: dict[str, Any]) -> dict[str, Any]:
    runs = experiment.get("runs") or []
    latest_id = experiment.get("latest_run_id")
    if latest_id and isinstance(runs, list):
        for run in runs:
            if isinstance(run, dict) and run.get("run_id") == latest_id:
                return run
    if isinstance(runs, list) and runs:
        last = runs[-1]
        if isinstance(last, dict):
            return last
    # experiment_logs lean entry may itself be the "run"
    if experiment.get("run_id") and experiment.get("metrics"):
        return experiment
    raise ValueError("Baseline experiment run with metrics is required for validation.")


def _params_from_baseline(
    baseline_run: dict[str, Any],
    *,
    problem_specification: ProblemSpecification | dict[str, Any] | None,
) -> tuple[ExperimentParams, ProblemConstraintSnapshot]:
    """Rebuild runnable params/constraints from a persisted baseline run."""
    params_raw = baseline_run.get("params") or {}
    constraints_raw = baseline_run.get("constraints")
    if isinstance(constraints_raw, dict) and constraints_raw:
        constraints = ProblemConstraintSnapshot.model_validate(constraints_raw)
    else:
        constraints = extract_problem_constraints(problem_specification)

    strategy = None
    if isinstance(params_raw, dict):
        strategy = params_raw.get("strategy_id")
    if not strategy:
        strategy = resolve_strategy_id(
            method_family=baseline_run.get("method_family"),
            explicit=None,
        )

    lookback = 3
    rebalance = 5
    fixture_id = "fx_2022_mcm_c_prices_v1"
    if isinstance(params_raw, dict):
        lookback = int(params_raw.get("lookback_days") or lookback)
        rebalance = int(params_raw.get("rebalance_every_n_days") or rebalance)
        fixture_id = str(params_raw.get("price_fixture_id") or fixture_id)

    params = build_experiment_params(
        constraints=constraints,
        strategy_id=strategy,  # type: ignore[arg-type]
        lookback_days=lookback,
        rebalance_every_n_days=rebalance,
        allow_sandboxed_python=False,
        price_fixture_id=fixture_id,
    )
    # Prefer explicit alphas / cash from persisted params when present.
    if isinstance(params_raw, dict):
        updates: dict[str, Any] = {}
        for key in ("initial_cash", "alpha_gold", "alpha_bitcoin"):
            if key in params_raw and params_raw[key] is not None:
                updates[key] = params_raw[key]
        if updates:
            params = params.model_copy(update=updates)
            constraints = constraints.model_copy(
                update={
                    k: updates[k]
                    for k in ("initial_cash", "alpha_gold", "alpha_bitcoin")
                    if k in updates
                }
            )
    return params, constraints


def _run_scenario(
    *,
    scenario_id: str,
    kind: str,
    label: str,
    description: str,
    baseline_run_id: str,
    baseline_metrics: dict[str, MetricSnapshot],
    params: ExperimentParams,
    constraints: ProblemConstraintSnapshot,
    perturbations: list[PerturbationSpec],
) -> SensitivityScenario:
    portfolio, _trades, equity, notes = run_deterministic_backtest(
        params=params,
        constraints=constraints,
    )
    metrics = _metrics_from_portfolio(
        portfolio,
        initial_cash=float(constraints.initial_cash),
        equity=equity,
    )
    return SensitivityScenario(
        scenario_id=scenario_id,
        kind=kind,  # type: ignore[arg-type]
        label=label,
        description=description,
        baseline_run_id=baseline_run_id,
        perturbations=perturbations,
        metrics=metrics,
        deltas=_deltas(baseline_metrics, metrics),
        status="completed",
        notes=notes[:8],
        invented_results=False,
    )


def _clamp_alpha(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _clamp_days(value: int, *, lo: int = 1, hi: int = 60) -> int:
    return max(lo, min(hi, int(value)))


def build_default_scenarios(
    *,
    baseline_run: dict[str, Any],
    baseline_metrics: dict[str, MetricSnapshot],
    params: ExperimentParams,
    constraints: ProblemConstraintSnapshot,
) -> list[SensitivityScenario]:
    """Construct the CI-safe default sensitivity suite for 2022 MCM C."""
    baseline_run_id = str(baseline_run["run_id"])
    scenarios: list[SensitivityScenario] = []

    # 1) Cost: double gold commission
    alpha_g_hi = _clamp_alpha(params.alpha_gold * 2.0 if params.alpha_gold > 0 else 0.02)
    c1 = constraints.model_copy(update={"alpha_gold": alpha_g_hi})
    p1 = params.model_copy(update={"alpha_gold": alpha_g_hi})
    scenarios.append(
        _run_scenario(
            scenario_id="scn_cost_alpha_gold_x2",
            kind="cost",
            label="Gold commission ×2",
            description=(
                "Double αgold relative to the baseline run to test cost sensitivity "
                "on gold trades (2022 MCM C commission)."
            ),
            baseline_run_id=baseline_run_id,
            baseline_metrics=baseline_metrics,
            params=p1,
            constraints=c1,
            perturbations=[
                PerturbationSpec(
                    target="alpha_gold",
                    description="Double gold transaction cost fraction",
                    baseline_value=params.alpha_gold,
                    scenario_value=alpha_g_hi,
                    relative_change=(
                        (alpha_g_hi - params.alpha_gold) / params.alpha_gold
                        if params.alpha_gold
                        else None
                    ),
                )
            ],
        )
    )

    # 2) Cost: double bitcoin commission
    alpha_b_hi = _clamp_alpha(
        params.alpha_bitcoin * 2.0 if params.alpha_bitcoin > 0 else 0.04
    )
    c2 = constraints.model_copy(update={"alpha_bitcoin": alpha_b_hi})
    p2 = params.model_copy(update={"alpha_bitcoin": alpha_b_hi})
    scenarios.append(
        _run_scenario(
            scenario_id="scn_cost_alpha_btc_x2",
            kind="cost",
            label="Bitcoin commission ×2",
            description=(
                "Double αbitcoin relative to the baseline run to test cost "
                "sensitivity on bitcoin trades."
            ),
            baseline_run_id=baseline_run_id,
            baseline_metrics=baseline_metrics,
            params=p2,
            constraints=c2,
            perturbations=[
                PerturbationSpec(
                    target="alpha_bitcoin",
                    description="Double bitcoin transaction cost fraction",
                    baseline_value=params.alpha_bitcoin,
                    scenario_value=alpha_b_hi,
                    relative_change=(
                        (alpha_b_hi - params.alpha_bitcoin) / params.alpha_bitcoin
                        if params.alpha_bitcoin
                        else None
                    ),
                )
            ],
        )
    )

    # 3) Window: shorter lookback
    lookback_lo = _clamp_days(max(1, params.lookback_days - 2))
    p3 = params.model_copy(update={"lookback_days": lookback_lo})
    scenarios.append(
        _run_scenario(
            scenario_id="scn_window_lookback_short",
            kind="window",
            label="Shorter lookback window",
            description=(
                "Reduce trend lookback_days to probe window-length sensitivity "
                "for past-data-only signals."
            ),
            baseline_run_id=baseline_run_id,
            baseline_metrics=baseline_metrics,
            params=p3,
            constraints=constraints,
            perturbations=[
                PerturbationSpec(
                    target="lookback_days",
                    description="Shorter moving-average / lookback window",
                    baseline_value=params.lookback_days,
                    scenario_value=lookback_lo,
                )
            ],
        )
    )

    # 4) Window: longer lookback
    lookback_hi = _clamp_days(params.lookback_days + 2)
    p4 = params.model_copy(update={"lookback_days": lookback_hi})
    scenarios.append(
        _run_scenario(
            scenario_id="scn_window_lookback_long",
            kind="window",
            label="Longer lookback window",
            description=(
                "Increase trend lookback_days to probe slower signal windows."
            ),
            baseline_run_id=baseline_run_id,
            baseline_metrics=baseline_metrics,
            params=p4,
            constraints=constraints,
            perturbations=[
                PerturbationSpec(
                    target="lookback_days",
                    description="Longer moving-average / lookback window",
                    baseline_value=params.lookback_days,
                    scenario_value=lookback_hi,
                )
            ],
        )
    )

    # 5) Param: rebalance cadence
    rebalance_hi = _clamp_days(params.rebalance_every_n_days + 3)
    p5 = params.model_copy(update={"rebalance_every_n_days": rebalance_hi})
    scenarios.append(
        _run_scenario(
            scenario_id="scn_param_rebalance_slower",
            kind="param",
            label="Slower rebalance cadence",
            description=(
                "Increase rebalance_every_n_days to test parameter sensitivity of "
                "periodic rebalancing stubs."
            ),
            baseline_run_id=baseline_run_id,
            baseline_metrics=baseline_metrics,
            params=p5,
            constraints=constraints,
            perturbations=[
                PerturbationSpec(
                    target="rebalance_every_n_days",
                    description="Slower periodic rebalance cadence",
                    baseline_value=params.rebalance_every_n_days,
                    scenario_value=rebalance_hi,
                )
            ],
        )
    )

    # 6) Combined: higher both commissions
    alpha_g_c = _clamp_alpha(params.alpha_gold * 1.5 if params.alpha_gold > 0 else 0.015)
    alpha_b_c = _clamp_alpha(
        params.alpha_bitcoin * 1.5 if params.alpha_bitcoin > 0 else 0.03
    )
    c6 = constraints.model_copy(
        update={"alpha_gold": alpha_g_c, "alpha_bitcoin": alpha_b_c}
    )
    p6 = params.model_copy(update={"alpha_gold": alpha_g_c, "alpha_bitcoin": alpha_b_c})
    scenarios.append(
        _run_scenario(
            scenario_id="scn_combined_costs_x1_5",
            kind="combined",
            label="Both commissions ×1.5",
            description=(
                "Raise αgold and αbitcoin together (×1.5) as a combined cost stress."
            ),
            baseline_run_id=baseline_run_id,
            baseline_metrics=baseline_metrics,
            params=p6,
            constraints=c6,
            perturbations=[
                PerturbationSpec(
                    target="alpha_gold",
                    description="Gold commission ×1.5",
                    baseline_value=params.alpha_gold,
                    scenario_value=alpha_g_c,
                ),
                PerturbationSpec(
                    target="alpha_bitcoin",
                    description="Bitcoin commission ×1.5",
                    baseline_value=params.alpha_bitcoin,
                    scenario_value=alpha_b_c,
                ),
            ],
        )
    )

    return scenarios


def _robustness_notes(
    scenarios: list[SensitivityScenario],
) -> list[RobustnessNote]:
    notes: list[RobustnessNote] = []
    # Terminal-value relative swings.
    tv_swings: list[tuple[str, float]] = []
    for scn in scenarios:
        for delta in scn.deltas:
            if delta.metric_id == "m_total_return" and delta.relative_delta is not None:
                tv_swings.append((scn.scenario_id, abs(delta.relative_delta)))
    if tv_swings:
        worst_id, worst_rel = max(tv_swings, key=lambda item: item[1])
        severity = "info"
        if worst_rel >= 0.25:
            severity = "high"
        elif worst_rel >= 0.10:
            severity = "medium"
        elif worst_rel >= 0.05:
            severity = "low"
        notes.append(
            RobustnessNote(
                note_id="rn_return_sensitivity",
                severity=severity,  # type: ignore[arg-type]
                summary=(
                    f"Largest absolute relative change in total return across "
                    f"sensitivity scenarios is {worst_rel:.4f} "
                    f"(scenario `{worst_id}`)."
                ),
                related_scenario_ids=[worst_id],
                related_metric_ids=["m_total_return"],
            )
        )

    cost_scenarios = [s for s in scenarios if s.kind in {"cost", "combined"}]
    if cost_scenarios:
        notes.append(
            RobustnessNote(
                note_id="rn_cost_stress_covered",
                severity="info",
                summary=(
                    f"Cost-stress coverage: {len(cost_scenarios)} scenario(s) "
                    "perturb αgold and/or αbitcoin on the synthetic fixture."
                ),
                related_scenario_ids=[s.scenario_id for s in cost_scenarios],
                related_metric_ids=["m_cost_paid", "m_terminal_value"],
            )
        )

    window_scenarios = [s for s in scenarios if s.kind in {"window", "param"}]
    if window_scenarios:
        notes.append(
            RobustnessNote(
                note_id="rn_window_param_covered",
                severity="info",
                summary=(
                    f"Window/param coverage: {len(window_scenarios)} scenario(s) "
                    "perturb lookback_days and/or rebalance_every_n_days."
                ),
                related_scenario_ids=[s.scenario_id for s in window_scenarios],
                related_metric_ids=list(_FOCUS_METRICS[:3]),
            )
        )

    notes.append(
        RobustnessNote(
            note_id="rn_fixture_limitation",
            severity="info",
            summary=(
                "Sensitivity uses the Phase 6 synthetic 2022 MCM C price fixture, "
                "not live LBMA/BCHAIN series. Treat results as CI-safe robustness "
                "signals, not competition-grade validation."
            ),
            related_scenario_ids=[s.scenario_id for s in scenarios[:4]],
            related_metric_ids=[],
        )
    )
    return notes


def execute_validation_report(
    *,
    experiment: dict[str, Any],
    proposal_id: str,
    selected_candidate_id: str,
    problem_specification: ProblemSpecification | dict[str, Any] | None = None,
    problem_id: str | None = None,
    llm_enabled: bool = False,
) -> ValidationReport:
    """Build a deterministic ValidationReport from a Phase 6 experiment payload.

    Callers must enforce ``assert_validation_allowed`` before invoking.
    """
    baseline_run = _resolve_baseline_run(experiment)
    if not baseline_run.get("metrics"):
        raise ValueError("Baseline experiment run is missing metrics.")

    baseline_metrics = _metric_map_from_run(baseline_run)
    if not baseline_metrics:
        raise ValueError("Baseline experiment metrics could not be parsed.")

    params, constraints = _params_from_baseline(
        baseline_run,
        problem_specification=problem_specification,
    )
    scenarios = build_default_scenarios(
        baseline_run=baseline_run,
        baseline_metrics=baseline_metrics,
        params=params,
        constraints=constraints,
    )
    robustness = _robustness_notes(scenarios)

    llm_attempted = bool(llm_enabled)
    llm_note = LLM_UNAVAILABLE_NOTE if llm_attempted else None

    started = _utc_now()
    report_id = _stable_id(
        "vrep",
        proposal_id,
        selected_candidate_id,
        str(baseline_run["run_id"]),
        started,
    )
    notes = [
        "Phase 7 deterministic sensitivity runner completed.",
        f"baseline_run_id={baseline_run['run_id']}",
        f"n_scenarios={len(scenarios)}",
        "Paper / LaTeX (Phase 8) remains blocked until human H2 approval.",
        f"generated_at_utc={started}",
    ]
    if llm_note:
        notes.append(llm_note)

    # Touch payload hash for stable provenance without inventing results.
    _ = _payload_sha(
        {
            "baseline_run_id": baseline_run["run_id"],
            "scenario_ids": [s.scenario_id for s in scenarios],
        }
    )

    return ValidationReport(
        report_id=report_id,
        problem_id=problem_id or constraints.problem_id,
        proposal_id=proposal_id,
        selected_candidate_id=selected_candidate_id,
        baseline_run_id=str(baseline_run["run_id"]),
        baseline_experiment_report_id=experiment.get("report_id"),
        h1_approved=True,
        validation_allowed=True,
        strategy="deterministic_fixture",
        llm_enabled=False,
        llm_attempted=llm_attempted,
        llm_note=llm_note,
        baseline_metrics=list(baseline_metrics.values()),
        scenarios=scenarios,
        robustness_notes=robustness,
        invented_results=False,
        live_trading_api_used=False,
        agent_prompt_version=PROMPT_VERSION,
        analysis_notes=notes,
    )
