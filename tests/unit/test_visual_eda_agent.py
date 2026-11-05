import json

import pandas as pd
import pytest

from llm.base import LLMResponse
from schemas.chart_plan import ChartPlan, ChartSpec
from tools.chart_plan_validator import validate_chart_plan
from tools.data_loader import load_dataset
from tools.eda_engine import build_eda_report
from agents.visual_eda_agent import (
    PROMPT_VERSION,
    _build_messages,
    plan_visual_eda,
)


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return LLMResponse(
            content=result,
            provider="deepseek",
            model="test-model",
            usage=None,
        )


def sample():
    dataset = load_dataset(
        b"date,value,group\n"
        b"2026-01-01,10,A\n"
        b"2026-01-02,12,B\n"
        b"2026-01-03,11,A\n"
        b"2026-01-04,15,B\n",
        "sample.csv",
    )
    report = build_eda_report(
        dataset,
        "mcm-demo",
        data_source="Synthetic fixture",
        temporal_frequency="Daily",
        column_units={"value": "USD"},
    )
    return dataset, report


def valid_plan_json():
    spec = ChartSpec(
        chart_id="value_over_time",
        chart_type="time_series",
        title="Observed value over time",
        figure_label="fig:value_over_time",
        x="date",
        y="value",
        x_label="Date",
        y_label="Value",
        y_unit="USD",
        caption="Observed value across the four supplied dates.",
        analytical_question="How does the observed value change over time?",
        rationale="The problem asks for temporal movement and the dataset contains a date field.",
        priority="required",
        rank=1,
        relevance_score=0.93,
        analytical_role="trend",
        caveats=["This descriptive series does not establish causality."],
    )
    return ChartPlan(
        strategy="agent",
        planning_summary="Prioritize the time trend requested in the problem.",
        problem_alignment="The time-series chart directly addresses the temporal component.",
        charts=[spec],
        skipped_reasons=["No group comparison requested in the current research question."],
    ).model_dump_json()


def test_planner_returns_valid_ranked_agent_plan_and_provenance():
    dataset, report = sample()
    llm = FakeLLM([valid_plan_json()])

    plan = plan_visual_eda(
        "Analyze the temporal movement of the observed value.",
        report,
        dataset.frame,
        llm=llm,
    )

    assert plan.strategy == "agent"
    assert plan.planner_provider == "deepseek"
    assert plan.planner_model == "test-model"
    assert plan.planner_prompt_version == PROMPT_VERSION
    assert plan.fallback_reason is None
    assert plan.charts[0].rank == 1
    assert plan.charts[0].relevance_score == pytest.approx(0.93)
    assert len(llm.calls) == 1


def test_planner_context_contains_profile_not_full_dataframe_rows():
    dataset, report = sample()
    messages = _build_messages("Analyze the time trend.", report)
    serialized = messages[1]["content"]

    assert "date" in serialized
    assert "value" in serialized
    assert "numeric_correlations" in serialized
    assert "2026-01-01,10,A" not in serialized
    assert "Synthetic fixture" in serialized


def test_missing_problem_statement_uses_generic_fallback_without_calling_llm():
    dataset, report = sample()
    llm = FakeLLM([])

    plan = plan_visual_eda("  ", report, dataset.frame, llm=llm)

    assert plan.strategy == "deterministic"
    assert "No problem statement" in plan.fallback_reason
    assert plan.planner_prompt_version == PROMPT_VERSION
    assert llm.calls == []


def test_malformed_first_response_gets_one_bounded_repair_attempt():
    dataset, report = sample()
    llm = FakeLLM(["not json", valid_plan_json()])

    plan = plan_visual_eda(
        "Analyze the temporal movement of value.",
        report,
        dataset.frame,
        llm=llm,
    )

    assert plan.strategy == "agent"
    assert len(llm.calls) == 2
    assert "Validation error" in llm.calls[1][-1]["content"]


def test_invalid_column_after_repair_falls_back_to_deterministic_plan():
    dataset, report = sample()
    invalid = json.loads(valid_plan_json())
    invalid["charts"][0]["x"] = "invented_date"
    llm = FakeLLM([json.dumps(invalid), json.dumps(invalid)])

    plan = plan_visual_eda(
        "Analyze temporal movement.",
        report,
        dataset.frame,
        llm=llm,
    )

    assert plan.strategy == "deterministic"
    assert "one repair attempt" in plan.fallback_reason
    assert plan.charts
    assert len(llm.calls) == 2


def test_provider_failure_uses_deterministic_fallback():
    dataset, report = sample()
    llm = FakeLLM([RuntimeError("provider timeout")])

    plan = plan_visual_eda(
        "Analyze temporal movement.",
        report,
        dataset.frame,
        llm=llm,
    )

    assert plan.strategy == "deterministic"
    assert "provider invocation failed" in plan.fallback_reason
    assert "provider timeout" in plan.fallback_reason
    assert len(llm.calls) == 1


def test_validator_rejects_unverified_units_and_numeric_bar_categories():
    dataset, report = sample()
    wrong_unit = ChartSpec(
        chart_id="bad_unit",
        chart_type="time_series",
        title="Value over time",
        figure_label="fig:bad_unit",
        x="date",
        y="value",
        x_label="Date",
        y_label="Value",
        y_unit="EUR",
        rank=1,
        relevance_score=0.5,
        analytical_role="trend",
        caption="Observed values over the supplied dates.",
        analytical_question="How does value change over time?",
        rationale="Inspect temporal movement in the measured value.",
    )
    with pytest.raises(ValueError, match="only explicitly declared unit"):
        validate_chart_plan(ChartPlan(charts=[wrong_unit]), dataset.frame, report)

    numeric_bar = ChartSpec(
        chart_id="numeric_bar",
        chart_type="bar",
        title="Numeric categories",
        figure_label="fig:numeric_bar",
        x="value",
        x_label="Value",
        y_label="Count",
        rank=1,
        relevance_score=0.5,
        analytical_role="comparison",
        caption="Counts for values treated as categories.",
        analytical_question="How often does each numeric value occur?",
        rationale="Inspect the frequency of each numeric value.",
    )
    with pytest.raises(ValueError, match="categorical x column"):
        validate_chart_plan(ChartPlan(charts=[numeric_bar]), dataset.frame, report)


def test_validator_rejects_duplicate_analytical_intent():
    dataset, report = sample()
    first = ChartSpec(
        chart_id="value_distribution",
        chart_type="histogram",
        title="Value distribution",
        figure_label="fig:value_distribution",
        x="value",
        x_label="Value",
        y_label="Frequency",
        caption="Distribution of observed values in the dataset.",
        analytical_question="How are the observed values distributed?",
        rationale="Inspect the spread of observed values.",
        analytical_role="distribution",
        rank=1,
        relevance_score=0.5,
    )
    second = first.model_copy(
        update={
            "chart_id": "value_distribution_again",
            "figure_label": "fig:value_distribution_again",
            "title": "Another value distribution",
            "rank": 2,
        }
    )
    with pytest.raises(ValueError, match="Duplicate analytical intent"):
        validate_chart_plan(
            ChartPlan(charts=[first, second]),
            dataset.frame,
            report,
        )


def test_missing_api_key_uses_deterministic_fallback_without_network(test_settings):
    dataset, report = sample()
    test_settings.deepseek_api_key = None
    test_settings.llm_api_key = None

    plan = plan_visual_eda(
        "Analyze the temporal movement of rentals.",
        report,
        dataset.frame,
        settings=test_settings,
    )

    assert plan.strategy == "deterministic"
    assert "Missing API key" in plan.fallback_reason


def test_empty_agent_plan_is_preserved_when_planner_abstains():
    dataset, report = sample()
    empty = ChartPlan(
        strategy="agent",
        planning_summary="The available fields do not support a useful chart for this question.",
        problem_alignment="The requested analysis cannot be answered by the available dataset.",
        charts=[],
        skipped_reasons=["No chart meets the required evidence and sample-size constraints."],
    ).model_dump_json()
    llm = FakeLLM([empty])

    plan = plan_visual_eda(
        "Analyze an outcome that is not present in this dataset.",
        report,
        dataset.frame,
        llm=llm,
    )

    assert plan.strategy == "agent"
    assert plan.charts == []
    assert plan.skipped_reasons
    assert len(llm.calls) == 1


def test_planner_accepts_json_code_fence_from_provider():
    dataset, report = sample()
    llm = FakeLLM([f"```json\\n{valid_plan_json()}\\n```"])

    plan = plan_visual_eda(
        "Analyze the temporal movement in rentals.",
        report,
        dataset.frame,
        llm=llm,
    )

    assert plan.strategy == "agent"
    assert len(llm.calls) == 1
