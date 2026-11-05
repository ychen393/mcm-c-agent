import json
from pathlib import Path

import pandas as pd

from schemas.chart_plan import ChartPlan, ChartSpec
from tools.chart_plan_evaluator import evaluate_chart_plan

ROOT = Path(__file__).resolve().parents[2]
CASES = {
    case["case_id"]: case
    for case in (
        json.loads(line)
        for line in (ROOT / "evaluation/chart_planning_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
}


def chart(chart_type, x, y=None, rank=1, role="trend"):
    return ChartSpec(
        chart_id=f"chart_{rank}",
        chart_type=chart_type,
        title="Evaluation chart",
        figure_label=f"fig:chart_{rank}",
        x=x,
        y=y,
        x_label=x,
        y_label=y or "Count",
        caption="A chart generated for an offline evaluation case.",
        analytical_question="What pattern in the supplied data is relevant?",
        rationale="The selected fields address the evaluation question.",
        analytical_role=role,
        rank=rank,
        relevance_score=0.8,
    )


def fixture_frame(case_id):
    fixture_ref = CASES[case_id]["fixture_refs"][0]
    fixture_path = fixture_ref.split("#sha256=", 1)[0]
    return pd.read_csv(ROOT / fixture_path)


def test_offline_evaluator_accepts_problem_relevant_time_series():
    case = CASES["EDA-VIS-001"]
    frame = fixture_frame(case["case_id"])
    plan = ChartPlan(
        strategy="agent",
        charts=[chart("time_series", "date", "rentals")],
    )

    result = evaluate_chart_plan(plan, case, frame)

    assert result["passed"]
    assert result["checks"]["required_columns_present"]
    assert result["checks"]["structural_valid"]


def test_offline_evaluator_accepts_abstention_for_insufficient_time_coverage():
    case = CASES["EDA-VIS-005"]
    frame = fixture_frame(case["case_id"])
    plan = ChartPlan(
        strategy="agent",
        charts=[],
        skipped_reasons=["Only two distinct dates are available; a time-series chart is unsuitable."],
    )

    result = evaluate_chart_plan(plan, case, frame)

    assert result["passed"]
    assert result["chart_count"] == 0
    assert result["checks"]["no_prohibited_chart_types"]


def test_offline_evaluator_rejects_prohibited_identifier_field():
    case = CASES["EDA-VIS-002"]
    frame = fixture_frame(case["case_id"])
    plan = ChartPlan(
        strategy="agent",
        charts=[chart("histogram", "record_id", role="distribution")],
    )

    result = evaluate_chart_plan(plan, case, frame)

    assert not result["passed"]
    assert result["prohibited_columns_used"] == ["record_id"]


def test_offline_evaluator_checks_fallback_reason():
    case = CASES["EDA-VIS-006"]
    frame = fixture_frame(case["case_id"])
    plan = ChartPlan(
        strategy="deterministic",
        charts=[],
        fallback_reason="No problem statement was supplied; used generic deterministic EDA.",
    )

    result = evaluate_chart_plan(plan, case, frame)

    assert result["passed"]
    assert result["checks"]["fallback_reason_match"]
    assert result["human_review_required"]
