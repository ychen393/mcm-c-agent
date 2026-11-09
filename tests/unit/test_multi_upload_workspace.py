"""Offline checks for multi-file intake and independent EDA views."""
import ast
import json
from pathlib import Path

import pytest

from app.dataset_workspace import (
    ANALYTICAL_SCOPE_INDEPENDENT,
    open_workspace,
    pending_plan_matches,
)
from schemas.eda import EDAReport
from tools.data_loader import load_dataset
from tools.eda_engine import build_eda_report


def _body(report: EDAReport) -> dict:
    payload = report.model_dump(mode="json")
    payload.pop("generated_at_utc")
    payload["dataset"].pop("loaded_at_utc")
    return payload


SALES = b"date,value\n2026-01-01,10\n2026-01-02,30\n"
WEATHER = b"date,value\n2026-01-01,100\n2026-01-02,80\n"
OUTCOMES = b"region,outcome\nNorth,1\nSouth,2\nEast,3\n"


def test_single_file_matches_direct_eda_and_keeps_chart_planning():
    direct = load_dataset(SALES, "sales.csv")
    preview = open_workspace([("sales.csv", SALES)], project_id="mcm-c-demo")
    dataset_id = preview.bundle.datasets[0].dataset_id
    workspace = open_workspace(
        [("sales.csv", SALES)],
        project_id="mcm-c-demo",
        data_source_by_dataset={dataset_id: "ledger"},
    )
    view = workspace.views[0]
    profile = workspace.profiles[dataset_id]
    assert workspace.chart_planning_allowed is True
    assert workspace.approval_identity == direct.sha256
    assert view["dataset_id"] == dataset_id
    assert view["joined"] is False
    assert view["analytical_scope"] == ANALYTICAL_SCOPE_INDEPENDENT
    assert _body(profile.report) == _body(
        build_eda_report(direct, "mcm-c-demo", data_source="ledger")
    )
    assert pending_plan_matches(direct.sha256, workspace.approval_identity)


def test_two_and_three_uploads_stay_independent_with_stable_ids():
    two = open_workspace(
        [("sales.csv", SALES), ("weather.csv", WEATHER)],
        project_id="bundle-demo",
    )
    three = open_workspace(
        [("sales.csv", SALES), ("weather.csv", WEATHER), ("outcomes.csv", OUTCOMES)],
        project_id="bundle-demo",
    )
    assert two.chart_planning_allowed is False
    assert two.approval_identity is None
    assert [view["file_name"] for view in two.views] == ["sales.csv", "weather.csv"]
    assert len({view["dataset_id"] for view in two.views}) == 2
    sales, weather = two.views
    assert sales["columns"][1]["qualified_name"].endswith(".value")
    assert weather["columns"][1]["qualified_name"].endswith(".value")
    assert sales["columns"][1]["qualified_name"] != weather["columns"][1]["qualified_name"]
    assert sales["columns"][1]["numeric_summary"]["mean"] == 20.0
    assert weather["columns"][1]["numeric_summary"]["mean"] == 90.0
    sales_dump = json.dumps(sales)
    assert weather["sha256"] not in sales_dump
    assert weather["dataset_id"] not in sales_dump
    assert "raw_bytes" not in sales_dump
    assert sales["joined"] is weather["joined"] is False
    assert two.bundle.manifest.joined is False

    assert [view["file_name"] for view in three.views] == [
        "sales.csv",
        "weather.csv",
        "outcomes.csv",
    ]
    assert len({view["dataset_id"] for view in three.views}) == 3
    by_hash = {view["sha256"]: view["dataset_id"] for view in two.views}
    for view in three.views:
        if view["sha256"] in by_hash:
            assert view["dataset_id"] == by_hash[view["sha256"]]
    assert three.chart_planning_allowed is False


def test_same_column_names_and_duplicate_file_names_stay_distinct():
    first = b"id,value\n1,10\n"
    second = b"id,value\n1,99\n"
    workspace = open_workspace(
        [("data.csv", first), ("data.csv", second)],
        project_id="names",
    )
    left, right = workspace.views
    assert left["file_name"] == right["file_name"] == "data.csv"
    assert left["display_name"] != right["display_name"]
    assert left["dataset_id"] != right["dataset_id"]
    assert left["columns"][1]["qualified_name"] != right["columns"][1]["qualified_name"]
    assert left["columns"][1]["numeric_summary"]["mean"] == 10.0
    assert right["columns"][1]["numeric_summary"]["mean"] == 99.0


def test_duplicate_content_invalid_file_and_too_many_uploads_are_rejected():
    raw = b"id,value\n1,10\n"
    with pytest.raises(ValueError, match="Duplicate dataset content"):
        open_workspace([("one.csv", raw), ("two.csv", raw)], project_id="dupes")
    with pytest.raises(ValueError, match="bad.csv"):
        open_workspace(
            [("ok.csv", raw), ("bad.csv", b"\xff")],
            project_id="invalid",
        )
    with pytest.raises(ValueError, match="notes.xlsx"):
        open_workspace(
            [("notes.xlsx", b"this is not a workbook")],
            project_id="invalid",
        )
    uploads = [(f"part-{index}.csv", f"id,value\n{index},{index}\n".encode()) for index in range(6)]
    with pytest.raises(ValueError, match="at most 5 files"):
        open_workspace(uploads, project_id="too-many")
    accepted = open_workspace(uploads[:5], project_id="five")
    assert len(accepted.views) == 5
    assert accepted.chart_planning_allowed is False


def test_file_change_invalidates_pending_approval_identity():
    original = open_workspace([("sales.csv", SALES)], project_id="demo")
    replaced = open_workspace([("weather.csv", WEATHER)], project_id="demo")
    multi = open_workspace(
        [("sales.csv", SALES), ("weather.csv", WEATHER)],
        project_id="demo",
    )
    stored = original.approval_identity
    assert pending_plan_matches(stored, original.approval_identity)
    assert not pending_plan_matches(stored, replaced.approval_identity)
    assert not pending_plan_matches(stored, multi.approval_identity)
    assert not pending_plan_matches(None, original.approval_identity)
    assert original.approval_identity != replaced.approval_identity


def test_streamlit_planner_is_limited_to_the_single_file_gate():
    source = Path("app/main.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    assert "accept_multiple_files=True" in source
    assert "build_dataset_bundle" in source

    planner_calls = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def generic_visit(self, node):
            self.stack.append(node)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "plan_visual_eda"
            ):
                planner_calls.append(list(self.stack))
            super().generic_visit(node)
            self.stack.pop()

    Visitor().visit(module)
    assert len(planner_calls) == 1
    ancestors = planner_calls[0][:-1]
    assert any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Call)
        and isinstance(node.test.func, ast.Name)
        and node.test.func.id == "chart_planning_allowed"
        for node in ancestors
    )
    assert "concat(" not in source
    assert ".merge(" not in source
