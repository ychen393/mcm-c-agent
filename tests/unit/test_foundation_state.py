"""Provenance copied into foundation state never includes file bytes or raw rows."""

import hashlib
import json

import pytest

from core.foundation import (
    NOT_IMPLEMENTED,
    build_initialized_state,
    dataset_provenance,
    foundation_input_signature,
    selection_token,
)
from core.graph import build_foundation_graph
from tools.dataset_bundle import build_dataset_bundle

GOLD = (
    b"Date,USD (PM)\n"
    b"9/12/2016,1324.60\n"
    b"9/13/2016,1321.75\n"
    b"9/14/2016,\n"
    b"9/15/2016,1308.35\n"
)
BITCOIN = (
    b"Date,Value\n"
    b"9/11/2016,621.65\n"
    b"9/12/2016,609.67\n"
    b"9/13/2016,610.92\n"
    b"9/14/2016,608.82\n"
    b"9/15/2016,610.12\n"
)
PROBLEM = "2022 MCM Problem C Trading Strategies"


def _cells(raw: bytes) -> set[str]:
    cells: set[str] = set()
    for line in raw.decode().splitlines()[1:]:
        for cell in line.split(","):
            if cell:
                cells.add(cell)
    return cells


def _assert_no_cells(document: str, *payloads: bytes) -> None:
    for raw in payloads:
        for cell in _cells(raw):
            assert cell not in document


def test_gold_and_bitcoin_provenance_is_safe_and_qualified():
    bundle = build_dataset_bundle(
        [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)],
        project_id="mcm-2022-c",
    )
    state = build_initialized_state(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        problem_text=PROBLEM,
        bundle=bundle,
        selection_status="ready",
        llm_config_revision=0,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    result = build_foundation_graph().invoke(state)
    files = result["uploaded_files"]
    assert [item["file_name"] for item in files] == ["LBMA-GOLD.csv", "BCHAIN-MKPRU.csv"]
    assert files[0]["row_count"] == 4
    assert files[1]["row_count"] == 5
    assert files[0]["sha256"] == hashlib.sha256(GOLD).hexdigest()
    assert files[1]["sha256"] == hashlib.sha256(BITCOIN).hexdigest()
    assert files[0]["column_names"] == ["Date", "USD (PM)"]
    assert files[1]["column_names"] == ["Date", "Value"]
    assert files[0]["qualified_column_names"][0].endswith(".Date")
    assert files[1]["qualified_column_names"][0].endswith(".Date")
    assert files[0]["qualified_column_names"][0] != files[1]["qualified_column_names"][0]
    assert "USD (PM)" not in files[1]["column_names"]
    assert "Value" not in files[0]["column_names"]
    assert all(item["joined"] is False for item in files)
    assert any("missing" in warning for warning in files[0]["warnings"])
    assert result["dataset_metadata"]["joined"] is False
    assert result["dataset_metadata"]["dataset_count"] == 2
    assert result["dataset_metadata"]["problem_text_sha256"] == hashlib.sha256(
        PROBLEM.encode()
    ).hexdigest()
    assert result["workspace_phases"]["relationship_preview"] == "ready"
    assert result["workspace_phases"]["joint_analysis"] == NOT_IMPLEMENTED
    assert result["analysis_status"] == "not_started"
    assert result["current_stage"] == "datasets_loaded"
    document = json.dumps(result)
    _assert_no_cells(document, GOLD, BITCOIN)
    assert "raw_bytes" not in document
    assert "sample_values" not in document
    assert "demo-project" not in document
    assert "problem_analysis" not in document


def test_same_name_value_columns_stay_on_their_own_dataset():
    sales = b"date,value\n2026-01-01,10\n2026-01-02,30\n"
    weather = b"date,value\n2026-01-01,100\n2026-01-02,80\n"
    bundle = build_dataset_bundle(
        [("sales.csv", sales), ("weather.csv", weather)],
        project_id="qualified-values",
    )
    records = dataset_provenance(bundle)
    sales_value = records[0]["qualified_column_names"][1]
    weather_value = records[1]["qualified_column_names"][1]
    assert sales_value.endswith(".value")
    assert weather_value.endswith(".value")
    assert sales_value != weather_value
    assert records[0]["row_count"] == 2
    assert records[1]["row_count"] == 2


def test_empty_and_rejected_selections_record_no_files():
    empty = build_initialized_state(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        problem_text=PROBLEM,
        bundle=None,
        selection_status="empty",
        llm_config_revision=0,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    assert empty["uploaded_files"] == []
    assert empty["dataset_metadata"]["selection_status"] == "empty"
    assert empty["errors"] == []
    assert empty["workspace_phases"]["datasets_loaded"] == "no"

    rejected = build_foundation_graph().invoke(
        build_initialized_state(
            project_id="mcm-2022-c",
            project_name="2022 MCM Problem C",
            problem_text=PROBLEM,
            bundle=None,
            selection_status="rejected",
            llm_config_revision=3,
            llm_provider="deepseek",
            llm_model="deepseek-chat",
        )
    )
    assert rejected["uploaded_files"] == []
    assert rejected["errors"] == [
        {
            "code": "dataset_bundle_rejected",
            "message": "The current file selection is not a valid dataset bundle.",
        }
    ]
    assert rejected["dataset_metadata"]["llm_config_revision"] == 3
    assert "sk-" not in json.dumps(rejected)


def test_input_signature_tracks_files_problem_project_and_api_revision():
    ready = selection_token(
        [("LBMA-GOLD.csv", GOLD)],
        fingerprint="a" * 64,
        rejected=False,
    )
    swapped = selection_token(
        [("BCHAIN-MKPRU.csv", BITCOIN), ("LBMA-GOLD.csv", GOLD)],
        fingerprint="b" * 64,
        rejected=False,
    )
    base = dict(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        problem_text=PROBLEM,
        selection_token_value=ready,
        llm_config_revision=0,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    original = foundation_input_signature(**base)
    assert foundation_input_signature(**base) == original
    assert foundation_input_signature(**{**base, "problem_text": PROBLEM + " Revised."}) != original
    assert foundation_input_signature(**{**base, "project_id": "mcm-2022-c-b"}) != original
    assert foundation_input_signature(**{**base, "selection_token_value": swapped}) != original
    assert foundation_input_signature(**{**base, "llm_config_revision": 1}) != original
    assert foundation_input_signature(**{**base, "llm_model": "deepseek-reasoner"}) != original
    assert "1324.60" not in original
    assert "sk-" not in original


def test_rejected_token_does_not_keep_the_file_bytes():
    token = selection_token([("LBMA-GOLD.csv", GOLD)], fingerprint=None, rejected=True)
    assert token.startswith("rejected:")
    assert "1324.60" not in token
    assert GOLD not in token.encode()


def test_ready_selection_requires_a_bundle():
    with pytest.raises(ValueError, match="requires a dataset bundle"):
        build_initialized_state(
            project_id="mcm-2022-c",
            project_name="2022 MCM Problem C",
            problem_text=PROBLEM,
            bundle=None,
            selection_status="ready",
            llm_config_revision=0,
            llm_provider="deepseek",
            llm_model="deepseek-chat",
        )
