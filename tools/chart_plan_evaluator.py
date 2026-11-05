"""Offline checks for Visual EDA chart-planning evaluation cases.

This evaluator measures contract/selection coverage only. It does not replace the
human rubric for evidence quality, analytical usefulness or competition compliance.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from schemas.chart_plan import ChartPlan
from tools.chart_plan_validator import validate_chart_plan


def evaluate_chart_plan(plan: ChartPlan, case: dict[str, Any], frame: pd.DataFrame) -> dict[str, Any]:
    case_input = case.get("input", {})
    chart_types = [chart.chart_type for chart in plan.charts]
    used_columns = {
        column
        for chart in plan.charts
        for column in (chart.x, chart.y)
        if column is not None
    }

    expected_strategy = case_input.get("expected_strategy")
    strategy_match = expected_strategy is None or plan.strategy == expected_strategy

    required_types = set(case_input.get("required_chart_types", []))
    acceptable_types = set(case_input.get("acceptable_chart_types", []))
    if required_types:
        chart_type_match = required_types.issubset(set(chart_types))
    elif acceptable_types:
        chart_type_match = bool(acceptable_types.intersection(chart_types))
    else:
        chart_type_match = True

    required_columns = set(case_input.get("required_columns", []))
    prohibited_columns = set(case_input.get("prohibited_columns", []))
    prohibited_types = set(case_input.get("prohibited_chart_types", []))
    missing_columns = sorted(required_columns - used_columns)
    used_prohibited_columns = sorted(prohibited_columns.intersection(used_columns))
    used_prohibited_types = sorted(prohibited_types.intersection(chart_types))

    fallback_fragment = case_input.get("expected_fallback_reason_contains")
    fallback_reason_match = (
        fallback_fragment is None
        or (
            plan.fallback_reason is not None
            and fallback_fragment.casefold() in plan.fallback_reason.casefold()
        )
    )

    structural_error = None
    try:
        validate_chart_plan(plan, frame)
    except ValueError as exc:
        structural_error = str(exc)

    checks = {
        "strategy_match": strategy_match,
        "chart_type_match": chart_type_match,
        "required_columns_present": not missing_columns,
        "no_prohibited_columns": not used_prohibited_columns,
        "no_prohibited_chart_types": not used_prohibited_types,
        "fallback_reason_match": fallback_reason_match,
        "structural_valid": structural_error is None,
    }
    return {
        "case_id": case.get("case_id"),
        "passed": all(checks.values()),
        "checks": checks,
        "chart_count": len(plan.charts),
        "chart_types": chart_types,
        "used_columns": sorted(used_columns),
        "missing_required_columns": missing_columns,
        "prohibited_columns_used": used_prohibited_columns,
        "prohibited_chart_types_used": used_prohibited_types,
        "structural_error": structural_error,
        "human_review_required": True,
        "note": (
            "Automated contract/selection checks only; human rubric review is still required "
            "for analytical relevance, evidence quality and unsupported claims."
        ),
    }
