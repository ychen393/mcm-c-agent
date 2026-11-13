"""Streamlit AppTest: 2022 MCM C gold and bitcoin files enter foundation state.

No model is called. uploaded_files receives provenance only.
"""

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.foundation_panel import INIT_MESSAGE, UPDATE_MESSAGE
from core.foundation import NOT_IMPLEMENTED

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"

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
GOLD_REPLACEMENT = (
    b"Date,USD (PM)\n"
    b"9/12/2016,1325.10\n"
    b"9/13/2016,1322.00\n"
    b"9/15/2016,1309.00\n"
)
PROBLEM = (
    "2022 MCM Problem C Trading Strategies. "
    "Use LBMA gold and bitcoin prices. Do not treat this initialization as a model."
)
SECRET = "sk-foundation-test-secret"


@pytest.fixture(autouse=True)
def _forbid_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def _called(*_args, **_kwargs):
        raise AssertionError("Foundation setup must not call a model.")

    monkeypatch.setattr("agents.visual_eda_agent.plan_visual_eda", _called)
    monkeypatch.setattr("llm.factory.LLMFactory.create", _called)


def _app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=60).run()


def _messages(at: AppTest) -> str:
    parts: list[str] = []
    for group in (at.success, at.error, at.info, at.warning, at.caption, at.markdown, at.subheader):
        for widget in group:
            value = getattr(widget, "value", None)
            if value:
                parts.append(str(value))
    return "\n".join(parts)


def _input(at: AppTest, label: str):
    return next(box for box in at.text_input if box.label == label)


def _problem(at: AppTest):
    return next(area for area in at.text_area if area.label.startswith("MCM problem statement"))


def _button(at: AppTest, label: str):
    return next(button for button in at.button if button.label == label)


def _cells(raw: bytes) -> set[str]:
    rows = list(csv.reader(io.StringIO(raw.decode())))
    cells: set[str] = set()
    for row in rows[1:]:
        for cell in row:
            if cell:
                cells.add(cell)
    return cells


def _assert_configured_key_stays_out(state: dict) -> None:
    from core.config import get_settings

    key = get_settings().provider_api_key()
    if key is None:
        return
    secret = key.get_secret_value().strip()
    if len(secret) >= 12:
        assert secret not in json.dumps(state)


def _assert_safe_state(state: dict, *payloads: bytes) -> None:
    document = json.dumps(state)
    _assert_configured_key_stays_out(state)
    for raw in payloads:
        for cell in _cells(raw):
            assert cell not in document
    assert "raw_bytes" not in document
    assert "sample_values" not in document
    assert "api_key" not in document
    assert "demo-project" not in document
    assert "problem_analysis" not in document
    assert "ready_for_problem_analysis" not in document
    assert SECRET not in document
    assert state["analysis_status"] == "not_started"
    assert state["workspace_phases"]["joint_analysis"] == NOT_IMPLEMENTED
    assert state["workspace_phases"]["strategy_modeling"] == NOT_IMPLEMENTED
    assert state["eda_report"] == {}
    assert state["approval_status"] == {}
    assert state["research_proposal"] == {}
    assert state["dataset_metadata"]["joined"] is False
    assert state["dataset_metadata"]["raw_rows_included"] is False
    assert state["dataset_metadata"]["file_bytes_included"] is False


def _prepare(at: AppTest, *, project_id: str = "mcm-2022-c", problem: str = PROBLEM) -> AppTest:
    _input(at, "Project name").set_value("2022 MCM Problem C")
    _input(at, "Project ID for saved artifacts").set_value(project_id)
    _problem(at).set_value(problem)
    return at.run()


def _initialize(at: AppTest) -> AppTest:
    at = _button(at, "Initialize project").click().run()
    assert not at.exception
    assert INIT_MESSAGE in _messages(at)
    assert "Foundation workflow completed" not in _messages(at)
    assert UPDATE_MESSAGE not in _messages(at)
    return at


def _upload(at: AppTest, files: list[tuple[str, bytes]]) -> AppTest:
    payload = [(name, raw, "text/csv") for name, raw in files]
    at = at.file_uploader[0].set_value(payload).run()
    assert not at.exception
    return at


def test_two_files_are_recorded_only_after_initialize_and_stay_unjoined():
    at = _prepare(_app())
    at = _upload(at, [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)])
    assert "last_run" not in at.session_state
    assert "**Project initialized:** no" in _messages(at)
    text_before = _messages(at)
    assert "NOT IMPLEMENTED" in text_before
    assert "not in the project state yet" in text_before

    at = _initialize(at)
    state = at.session_state["last_run"]
    files = state["uploaded_files"]
    assert [item["file_name"] for item in files] == ["LBMA-GOLD.csv", "BCHAIN-MKPRU.csv"]
    assert files[0]["row_count"] == 4
    assert files[1]["row_count"] == 5
    assert files[0]["column_count"] == 2
    assert files[0]["sha256"] == hashlib.sha256(GOLD).hexdigest()
    assert files[1]["sha256"] == hashlib.sha256(BITCOIN).hexdigest()
    assert state["project_id"] == "mcm-2022-c"
    assert state["project_name"] == "2022 MCM Problem C"
    assert state["problem_text"] == PROBLEM
    assert state["dataset_metadata"]["problem_text_sha256"] == hashlib.sha256(
        PROBLEM.encode()
    ).hexdigest()
    assert state["dataset_metadata"]["bundle_project_id"] == "mcm-2022-c"
    gold_date = files[0]["qualified_column_names"][0]
    bitcoin_date = files[1]["qualified_column_names"][0]
    assert gold_date.endswith(".Date") and bitcoin_date.endswith(".Date")
    assert gold_date != bitcoin_date
    assert files[0]["column_names"] == ["Date", "USD (PM)"]
    assert files[1]["column_names"] == ["Date", "Value"]
    assert all(item["joined"] is False for item in files)
    assert state["current_stage"] == "datasets_loaded"
    assert state["workspace_phases"]["project_initialized"] == "yes"
    assert state["workspace_phases"]["datasets_loaded"] == "yes"
    assert state["workspace_phases"]["independent_eda"] == "ready"
    assert state["workspace_phases"]["relationship_preview"] == "ready"
    _assert_safe_state(state, GOLD, BITCOIN)
    rendered = _messages(at)
    assert "**Project initialized:** yes" in rendered
    assert "**Datasets loaded:** yes" in rendered
    assert "**Independent EDA:** ready" in rendered
    assert "**Relationship preview:** ready" in rendered
    assert "**Joint analysis:** NOT IMPLEMENTED" in rendered
    assert "**Strategy modeling:** NOT IMPLEMENTED" in rendered
    assert "Joint analysis / strategy modeling" not in rendered
    assert "does not auto-join" in rendered or "does not join" in rendered
    assert "Generate chart plan" not in [button.label for button in at.button]
    assert any(
        "Developer / foundation state" in str(getattr(exp, "label", "") or getattr(exp, "value", "") or "")
        for exp in getattr(at, "expander", [])
    ) or "Developer / foundation state (JSON)" in rendered
    shown = json.dumps(at.json[0].value)
    assert "LBMA-GOLD.csv" in shown and "BCHAIN-MKPRU.csv" in shown
    assert "1324.60" not in shown and "621.65" not in shown
    # UX-A: no hardcoded Phase 5 / Workflow nodes 2 chrome
    assert "Phase 5" not in rendered
    assert "Workflow nodes" not in rendered
    assert "Phase 6 not started" not in rendered

    at.session_state["last_run"]["approval_status"] = {"h1": "approved"}
    at.session_state["last_run"]["research_proposal"] = {"strategy": "momentum"}
    at = _button(at, "Preview join").click().run()
    assert not at.exception
    kept = at.session_state["last_run"]
    assert kept["approval_status"] == {"h1": "approved"}
    assert kept["research_proposal"] == {"strategy": "momentum"}
    assert [item["file_name"] for item in kept["uploaded_files"]] == [
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    ]
    _assert_safe_state(
        {**kept, "approval_status": {}, "research_proposal": {}},
        GOLD,
        BITCOIN,
    )
    assert "1324.60" not in json.dumps(kept["uploaded_files"])


def test_upload_before_init_and_init_before_upload_both_record_the_files():
    at = _upload(_prepare(_app()), [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)])
    assert "last_run" not in at.session_state
    at = _initialize(at)
    assert [item["file_name"] for item in at.session_state["last_run"]["uploaded_files"]] == [
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    ]

    at = _initialize(_prepare(_app()))
    assert at.session_state["last_run"]["uploaded_files"] == []
    assert at.session_state["last_run"]["current_stage"] == "project_initialized"
    assert at.session_state["last_run"]["workspace_phases"]["datasets_loaded"] == "no"
    at = _upload(at, [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)])
    assert UPDATE_MESSAGE in _messages(at)
    assert [item["file_name"] for item in at.session_state["last_run"]["uploaded_files"]] == [
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    ]
    _assert_safe_state(at.session_state["last_run"], GOLD, BITCOIN)


def test_one_file_then_empty_selection_updates_phases_and_keeps_chart_planning():
    at = _upload(_prepare(_app()), [("LBMA-GOLD.csv", GOLD)])
    at = _initialize(at)
    state = at.session_state["last_run"]
    assert len(state["uploaded_files"]) == 1
    assert state["uploaded_files"][0]["sha256"] == hashlib.sha256(GOLD).hexdigest()
    assert state["workspace_phases"]["independent_eda"] == "ready"
    assert state["workspace_phases"]["relationship_preview"] == "not ready"
    assert "Generate chart plan" in [button.label for button in at.button]
    assert "Preview join" not in [button.label for button in at.button]
    _assert_safe_state(state, GOLD)

    at.session_state["last_run"]["approval_status"] = {"chart": "approved"}
    at = _button(at, "Generate chart plan").click().run()
    assert not at.exception
    assert at.session_state["last_run"]["approval_status"] == {"chart": "approved"}
    assert "eda_pending_plan" in at.session_state

    at = at.file_uploader[0].set_value(None).run()
    assert not at.exception
    cleared = at.session_state["last_run"]
    assert cleared["uploaded_files"] == []
    assert cleared["dataset_metadata"]["selection_status"] == "empty"
    assert cleared["workspace_phases"]["datasets_loaded"] == "no"
    assert cleared["workspace_phases"]["independent_eda"] == "not ready"
    assert cleared["approval_status"] == {}
    assert cleared["current_stage"] == "project_initialized"
    assert UPDATE_MESSAGE in _messages(at)


def test_reorder_and_replace_change_recorded_provenance():
    at = _initialize(
        _upload(
            _prepare(_app()),
            [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)],
        )
    )
    original = at.session_state["last_run"]["uploaded_files"]
    assert [item["position"] for item in original] == [0, 1]
    gold_sha = original[0]["sha256"]

    at = _upload(at, [("BCHAIN-MKPRU.csv", BITCOIN), ("LBMA-GOLD.csv", GOLD)])
    reordered = at.session_state["last_run"]["uploaded_files"]
    assert [item["file_name"] for item in reordered] == ["BCHAIN-MKPRU.csv", "LBMA-GOLD.csv"]
    assert [item["position"] for item in reordered] == [0, 1]
    assert reordered[1]["sha256"] == gold_sha
    assert reordered[0]["qualified_column_names"][0] != reordered[1]["qualified_column_names"][0]

    at = _upload(at, [("LBMA-GOLD.csv", GOLD_REPLACEMENT), ("BCHAIN-MKPRU.csv", BITCOIN)])
    replaced = at.session_state["last_run"]["uploaded_files"]
    assert replaced[0]["file_name"] == "LBMA-GOLD.csv"
    assert replaced[0]["sha256"] == hashlib.sha256(GOLD_REPLACEMENT).hexdigest()
    assert replaced[0]["sha256"] != gold_sha
    assert replaced[0]["row_count"] == 3
    assert gold_sha not in {item["sha256"] for item in replaced}
    _assert_safe_state(at.session_state["last_run"], GOLD_REPLACEMENT, BITCOIN)
    assert "1324.60" not in json.dumps(at.session_state["last_run"])


def test_problem_text_and_project_id_edits_replace_stale_products():
    at = _initialize(
        _upload(_prepare(_app()), [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)])
    )
    at.session_state["last_run"]["eda_report"] = {"claim": "strategy complete"}
    at.session_state["last_run"]["approval_status"] = {"h1": "approved"}
    at.session_state["last_run"]["research_proposal"] = {"trade": "gold"}
    revised = PROBLEM + " Revised after review."
    at = _problem(at).set_value(revised).run()
    state = at.session_state["last_run"]
    assert state["problem_text"] == revised
    assert state["dataset_metadata"]["problem_text_sha256"] == hashlib.sha256(
        revised.encode()
    ).hexdigest()
    assert state["eda_report"] == {}
    assert state["approval_status"] == {}
    assert state["research_proposal"] == {}
    assert UPDATE_MESSAGE in _messages(at)
    _assert_safe_state(state, GOLD, BITCOIN)

    at.session_state["last_run"]["approval_status"] = {"h1": "approved"}
    at = _input(at, "Project ID for saved artifacts").set_value("mcm-2022-c-revised").run()
    revised_state = at.session_state["last_run"]
    assert revised_state["project_id"] == "mcm-2022-c-revised"
    assert revised_state["dataset_metadata"]["bundle_project_id"] == "mcm-2022-c-revised"
    assert revised_state["approval_status"] == {}
    assert "demo-project" not in json.dumps(revised_state)
    assert [item["file_name"] for item in revised_state["uploaded_files"]] == [
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    ]


def test_rejected_selection_removes_previously_recorded_files():
    at = _initialize(
        _upload(_prepare(_app()), [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)])
    )
    duplicate = b"id,value\n1,10\n"
    at = at.file_uploader[0].set_value(
        [("one.csv", duplicate, "text/csv"), ("two.csv", duplicate, "text/csv")]
    ).run()
    assert not at.exception
    state = at.session_state["last_run"]
    assert state["uploaded_files"] == []
    assert state["dataset_metadata"]["selection_status"] == "rejected"
    assert state["workspace_phases"]["datasets_loaded"] == "no"
    assert state["current_stage"] == "project_initialized"
    assert "Duplicate dataset content" in _messages(at)
    assert "The current file selection is not recorded." in _messages(at)
    assert duplicate.decode() not in json.dumps(state)
    assert "1324.60" not in json.dumps(state)
    _assert_safe_state(state)


def test_api_settings_refresh_clears_foundation_products_and_omits_the_key():
    at = _initialize(
        _upload(_prepare(_app()), [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)])
    )
    at.session_state["last_run"]["approval_status"] = {"h1": "approved"}
    at.session_state["last_run"]["eda_report"] = {"secret_row": SECRET}
    at.session_state["last_run"]["research_proposal"] = {"plan": "trade"}
    at = at.radio[0].set_value("API Settings").run()
    assert not at.exception
    next(box for box in at.text_input if box.label == "Model ID").set_value("deepseek-chat")
    next(box for box in at.text_input if box.label == "API Key").set_value(SECRET)
    at = at.form_submit_button[0].click().run()
    assert not at.exception
    assert "API configuration saved for this session." in _messages(at)
    at = at.radio[0].set_value("Research Lab").run()
    assert not at.exception
    state = at.session_state["last_run"]
    assert state["dataset_metadata"]["llm_config_revision"] == 1
    assert state["dataset_metadata"]["llm_provider"] == "deepseek"
    assert state["dataset_metadata"]["llm_model"] == "deepseek-chat"
    assert state["approval_status"] == {}
    assert state["eda_report"] == {}
    assert state["research_proposal"] == {}
    assert SECRET not in json.dumps(state)
    assert [item["file_name"] for item in state["uploaded_files"]] == [
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    ]
    _assert_safe_state(state, GOLD, BITCOIN)
