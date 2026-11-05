"""Problem-aware Visual EDA chart planning with deterministic fallback.

The LLM proposes a typed chart plan only. It never receives the full DataFrame and
never executes code. Python validates every proposed source column and chart shape.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

from core.config import Settings, get_settings
from llm.base import BaseLLM
from llm.factory import LLMFactory
from schemas.chart_plan import ChartPlan
from schemas.eda import EDAReport
from tools.chart_catalog import fallback_chart_plan
from tools.chart_plan_validator import validate_chart_plan

PROMPT_VERSION = "visual_eda_planner_v1"
MAX_PROBLEM_CHARS = 12_000
MAX_PROFILE_CHARS = 40_000


def _prompt_text() -> str:
    prompt_path = Path(__file__).parent / "prompts" / "visual_eda_planner_v1.txt"
    return prompt_path.read_text(encoding="utf-8")


def _dataset_context(report: EDAReport) -> dict[str, Any]:
    """Build a compact profile; never serialize or transmit raw dataset rows."""
    dataset = report.dataset
    columns = []
    for profile in dataset.columns:
        numeric = profile.numeric_summary or {}
        columns.append(
            {
                "name": profile.name,
                "dtype": profile.dtype,
                "missing_count": profile.missing_count,
                "missing_rate": profile.missing_rate,
                "unique_count": profile.unique_count,
                "numeric_summary": {
                    key: numeric.get(key)
                    for key in ("mean", "median", "std", "min", "max")
                    if key in numeric
                }
                or None,
                "top_value_counts": [item["count"] for item in (profile.top_values or [])[:5]] or None,
                "datetime_min": profile.datetime_min,
                "datetime_max": profile.datetime_max,
                "unit": profile.unit,
            }
        )
    return {
        "file_name": dataset.file_name,
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
        "duplicate_row_count": dataset.duplicate_row_count,
        "sha256": dataset.sha256,
        "data_source": dataset.data_source,
        "declared_frequency": dataset.temporal_frequency,
        "estimated_frequency": dataset.inferred_frequency,
        "period_start": dataset.period_start,
        "period_end": dataset.period_end,
        "column_units": dataset.column_units,
        "columns": columns,
        "summary": report.summary,
        "numeric_correlations": report.numeric_correlations,
        "quality_warnings": report.warnings,
    }


def _build_messages(problem_statement: str, report: EDAReport) -> list[dict[str, str]]:
    context = _dataset_context(report)
    context_json = json.dumps(context, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(context_json) > MAX_PROFILE_CHARS:
        raise ValueError(
            f"Dataset profile is too large for safe planning ({len(context_json):,} characters; "
            f"limit {MAX_PROFILE_CHARS:,}). Use a narrower dataset or select columns first."
        )
    if len(problem_statement) > MAX_PROBLEM_CHARS:
        raise ValueError(
            f"Problem statement exceeds {MAX_PROBLEM_CHARS:,} characters; shorten it before planning."
        )
    user_payload = {
        "problem_statement": problem_statement,
        "dataset_profile": context,
        "required_output_schema": ChartPlan.model_json_schema(),
    }
    return [
        {"role": "system", "content": _prompt_text()},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False, default=str),
        },
    ]


def _parse_plan(content: str) -> ChartPlan:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model response is not valid JSON: {exc.msg} at character {exc.pos}.") from exc
    try:
        return ChartPlan.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Model response does not match ChartPlan: {exc}") from exc


def _fallback(report: EDAReport, frame: pd.DataFrame, reason: str) -> ChartPlan:
    plan = fallback_chart_plan(report).model_copy(
        update={
            "strategy": "deterministic",
            "fallback_reason": reason[:1000],
            "planner_prompt_version": PROMPT_VERSION,
        }
    )
    validate_chart_plan(plan, frame, report)
    return plan


def plan_visual_eda(
    problem_statement: str | None,
    report: EDAReport,
    frame: pd.DataFrame,
    *,
    llm: BaseLLM | None = None,
    settings: Settings | None = None,
) -> ChartPlan:
    """Generate and validate an AI chart plan; return deterministic fallback on failure.

    One repair call is allowed for malformed or invalid model output. Provider invocation
    failures fall back immediately. The function only plans: it never renders charts.
    """
    if not problem_statement or not problem_statement.strip():
        return _fallback(
            report, frame, "No problem statement was supplied; used generic deterministic EDA."
        )

    try:
        messages = _build_messages(problem_statement.strip(), report)
    except Exception as exc:
        return _fallback(report, frame, f"Could not prepare planner context: {exc}")

    try:
        planner = llm or LLMFactory.create(settings or get_settings())
    except Exception as exc:
        return _fallback(report, frame, f"Could not initialize LLM provider ({type(exc).__name__}). Check API settings.")

    try:
        response = planner.invoke(messages)
    except Exception as exc:
        return _fallback(report, frame, f"LLM provider invocation failed ({type(exc).__name__}). Check API settings, network, and account access.")

    first_content = response.content
    try:
        plan = _parse_plan(first_content)
        validate_chart_plan(plan, frame, report)
    except Exception as first_error:
        repair_messages = messages + [
            {"role": "assistant", "content": first_content},
            {
                "role": "user",
                "content": (
                    "Your previous response failed parsing or deterministic validation. "
                    "Return one corrected JSON ChartPlan only. Do not change the task or invent "
                    "columns. Validation error: "
                    f"{type(first_error).__name__}: {first_error}"
                ),
            },
        ]
        try:
            repaired = planner.invoke(repair_messages)
            plan = _parse_plan(repaired.content)
            validate_chart_plan(plan, frame, report)
            response = repaired
        except Exception as repair_error:
            return _fallback(
                report,
                frame,
                "Planner output remained invalid after one repair attempt: "
                f"{type(repair_error).__name__}. Check model output or provider settings.",
            )

    return plan.model_copy(
        update={
            "strategy": "agent",
            "planner_provider": response.provider,
            "planner_model": response.model,
            "planner_prompt_version": PROMPT_VERSION,
            "fallback_reason": None,
        }
    )
