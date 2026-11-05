from pydantic import ValidationError
import pandas as pd
import pytest

from schemas.chart_plan import ChartPlan, ChartSpec
from tools.chart_plan_validator import validate_chart_plan


def chart(rank: int, chart_id: str) -> ChartSpec:
    return ChartSpec(
        chart_id=chart_id,
        chart_type="histogram",
        title=f"Distribution of {chart_id}",
        figure_label=f"fig:{chart_id}",
        x="value",
        x_label="Value",
        y_label="Frequency (count)",
        caption=f"Distribution of observed values for {chart_id}.",
        analytical_question=f"How are the values of {chart_id} distributed?",
        rationale=f"Inspect the distribution of {chart_id} before modeling.",
        analytical_role="distribution",
        rank=rank,
        relevance_score=0.82,
    )


def test_chart_spec_accepts_rank_and_relevance_score():
    spec = chart(1, "value_distribution")
    assert spec.rank == 1
    assert spec.relevance_score == pytest.approx(0.82)
    assert spec.analytical_role == "distribution"


def test_chart_spec_rejects_out_of_range_rank_and_score():
    with pytest.raises(ValidationError):
        chart(13, "too_low_priority")
    with pytest.raises(ValidationError):
        ChartSpec(
            **{
                **chart(1, "invalid_score").model_dump(),
                "relevance_score": 1.1,
            }
        )


def test_chart_plan_records_agent_and_fallback_provenance():
    plan = ChartPlan(
        strategy="agent",
        planning_summary="Prioritize temporal movement relevant to the prompt.",
        problem_alignment="The time-series chart addresses the requested trend analysis.",
        planner_provider="deepseek",
        planner_model="test-model",
        charts=[chart(1, "value_distribution")],
        skipped_reasons=["No grouping field is available for a comparison chart."],
    )
    assert plan.strategy == "agent"
    assert plan.planner_provider == "deepseek"
    assert plan.planner_model == "test-model"
    assert plan.fallback_reason is None


def test_validator_rejects_duplicate_or_unsorted_chart_ranks():
    frame = pd.DataFrame({"value": [1, 2, 3, 4]})
    with pytest.raises(ValueError, match="Duplicate chart rank"):
        validate_chart_plan(
            ChartPlan(charts=[chart(1, "first"), chart(1, "second")]),
            frame,
        )
    with pytest.raises(ValueError, match="ascending rank"):
        validate_chart_plan(
            ChartPlan(charts=[chart(2, "second"), chart(1, "first")]),
            frame,
        )


def test_chart_plan_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ChartPlan.model_validate({"strategy": "agent", "untrusted_code": "print('hello')"})
