"""Streamlit AppTest coverage for multi-file intake. No model provider is called."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"

SALES = b"date,value\n2026-01-01,10\n2026-01-02,30\n2026-01-03,20\n"
WEATHER = b"date,value\n2026-01-01,100\n2026-01-02,80\n2026-01-03,90\n"
OUTCOMES = b"region,outcome\nNorth,1\nSouth,2\nEast,3\n"


def _app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=60).run()


def _button_labels(at: AppTest) -> list[str]:
    return [button.label for button in at.button]


def _subheaders(at: AppTest) -> list[str]:
    return [header.value for header in at.subheader]


def _forbid_planner(monkeypatch: pytest.MonkeyPatch) -> None:
    def _called(*_args, **_kwargs):
        raise AssertionError("Visual EDA planner must not be called in this test.")

    monkeypatch.setattr("agents.visual_eda_agent.plan_visual_eda", _called)


def _load_sales(at: AppTest) -> AppTest:
    return at.file_uploader[0].set_value([("sales.csv", SALES, "text/csv")]).run()


def _generate_plan(at: AppTest) -> AppTest:
    generate = next(button for button in at.button if button.label == "Generate chart plan")
    return generate.click().run()


def _approve_plan(at: AppTest) -> AppTest:
    approved = next(
        button for button in at.button if button.label == "Approve plan & generate charts"
    ).click().run()
    assert "EDA Summary" in _subheaders(approved)
    assert "eda_report" in approved.session_state
    assert approved.session_state["eda_report_dataset_sha"]
    return approved


def _assert_saved_report_hidden(at: AppTest) -> None:
    assert "EDA Summary" not in _subheaders(at)
    assert "eda_report" not in at.session_state
    assert "eda_artifacts" not in at.session_state
    assert "eda_report_dataset_sha" not in at.session_state
    assert "eda_pending_plan" not in at.session_state
    assert not list(at.image)


def _messages(at: AppTest) -> str:
    parts: list[str] = []
    for group in (at.success, at.error, at.info, at.warning, at.caption, at.markdown):
        for widget in group:
            value = getattr(widget, "value", None)
            if value:
                parts.append(str(value))
    return "\n".join(parts)


def test_two_and_three_uploads_render_independent_profiles():
    at = _app()
    assert at.file_uploader[0].accept_multiple_files is True
    at.file_uploader[0].set_value(
        [
            ("sales.csv", SALES, "text/csv"),
            ("weather.csv", WEATHER, "text/csv"),
        ]
    ).run()
    assert not at.exception
    registry = at.dataframe[0].value
    qualified = " ".join(registry["Qualified columns"].astype(str))
    assert "ds_sales_" in qualified and "ds_weather_" in qualified
    assert "ds_sales_" in qualified and ".value" in qualified
    assert qualified.index("ds_sales_") != qualified.index("ds_weather_")

    def _profile_mean(frames, column: str, expected_mean: float) -> bool:
        for frame in frames:
            if "Column" not in frame.columns or "Mean" not in frame.columns:
                continue
            matched = frame.loc[frame["Column"] == column, "Mean"]
            if not matched.empty and matched.iloc[0] == expected_mean:
                return True
        return False

    frames = [item.value for item in at.dataframe]
    assert _profile_mean(frames, "value", 20)
    assert _profile_mean(frames, "value", 90)
    assert "Generate chart plan" not in _button_labels(at)
    assert "Use AI Visual EDA Planner" not in [box.label for box in at.checkbox]
    text = _messages(at)
    assert "does not join files" in text
    assert "not joined" in text
    assert "eda_pending_plan" not in at.session_state

    at.file_uploader[0].set_value(
        [
            ("sales.csv", SALES, "text/csv"),
            ("weather.csv", WEATHER, "text/csv"),
            ("outcomes.csv", OUTCOMES, "text/csv"),
        ]
    ).run()
    names = set(at.dataframe[0].value["File"])
    assert names == {"sales.csv", "weather.csv", "outcomes.csv"}
    assert len(set(at.dataframe[0].value["Dataset ID"])) == 3


def test_single_file_plan_is_cleared_when_the_upload_changes():
    at = _app()
    at.file_uploader[0].set_value([("sales.csv", SALES, "text/csv")]).run()
    assert "Generate chart plan" in _button_labels(at)
    assert "Use AI Visual EDA Planner" in [box.label for box in at.checkbox]
    captions = [caption.value for caption in at.caption]
    assert any("Dataset ID: ds_sales_" in text for text in captions)
    next(button for button in at.button if button.label == "Generate chart plan").click().run()
    assert "eda_pending_plan" in at.session_state
    assert "Approve plan & generate charts" in _button_labels(at)
    assert not at.error

    at.file_uploader[0].set_value([("weather.csv", WEATHER, "text/csv")]).run()
    assert "previous unapproved chart plan was cleared" in _messages(at)
    assert "eda_pending_plan" not in at.session_state
    assert "Approve plan & generate charts" not in _button_labels(at)
    assert "Generate chart plan" in _button_labels(at)


def test_invalid_duplicate_and_oversized_selections_are_rejected_in_the_ui():
    at = _app()
    raw = b"id,value\n1,10\n"
    at.file_uploader[0].set_value(
        [
            ("one.csv", raw, "text/csv"),
            ("two.csv", raw, "text/csv"),
        ]
    ).run()
    assert "Duplicate dataset content" in _messages(at)
    assert "Generate chart plan" not in _button_labels(at)

    at.file_uploader[0].set_value([("bad.csv", b"\xff", "text/csv")]).run()
    assert "bad.csv" in _messages(at)

    at.file_uploader[0].set_value(
        [
            ("data.csv", b"id,value\n1,10\n", "text/csv"),
            ("data.csv", b"id,value\n1,99\n", "text/csv"),
        ]
    ).run()
    display_names = list(at.dataframe[0].value["Display name"])
    assert len(display_names) == 2
    assert display_names[0] != display_names[1]
    assert all(name.startswith("data.csv#") for name in display_names)

    too_many = [
        (f"part-{index}.csv", f"id,value\n{index},{index}\n".encode(), "text/csv")
        for index in range(6)
    ]
    at.file_uploader[0].set_value(too_many).run()
    assert "at most 5 files" in _messages(at)


def test_clearing_the_uploader_drops_a_pending_plan(monkeypatch):
    _forbid_planner(monkeypatch)
    at = _generate_plan(_load_sales(_app()))
    assert "eda_pending_plan" in at.session_state
    next(box for box in at.text_input if box.label == "Data source").set_value("LBMA gold").run()
    next(box for box in at.selectbox if box.label == "Data frequency").set_value("Daily").run()
    units = next(area for area in at.text_area if area.label.startswith("Column units"))
    units.set_value("value = USD").run()

    at.file_uploader[0].set_value(None).run()
    assert "previous unapproved chart plan was cleared" in _messages(at)
    assert "Approve plan & generate charts" not in _button_labels(at)
    assert "eda_pending_plan" not in at.session_state
    assert "EDA Summary" not in _subheaders(at)
    assert at.session_state["kept_eda_data_source"] == "LBMA gold"
    assert at.session_state["kept_eda_frequency"] == "Daily"
    assert at.session_state["kept_eda_column_units"] == "value = USD"

    at.file_uploader[0].set_value([("sales.csv", SALES, "text/csv")]).run()
    source = next(box.value for box in at.text_input if box.label == "Data source")
    frequency = next(box.value for box in at.selectbox if box.label == "Data frequency")
    units = next(area for area in at.text_area if area.label.startswith("Column units"))
    assert source == "LBMA gold"
    assert frequency == "Daily"
    assert units.value == "value = USD"


def test_rejected_selection_hides_an_approved_report(monkeypatch):
    _forbid_planner(monkeypatch)
    duplicate = b"id,value\n1,10\n"
    too_many = [
        (f"part-{index}.csv", f"id,value\n{index},{index}\n".encode(), "text/csv")
        for index in range(6)
    ]
    rejected_selections = [
        None,
        [("one.csv", duplicate, "text/csv"), ("two.csv", duplicate, "text/csv")],
        too_many,
    ]
    for selection in rejected_selections:
        at = _approve_plan(_generate_plan(_load_sales(_app())))
        at.file_uploader[0].set_value(selection).run()
        _assert_saved_report_hidden(at)
        assert "previous saved report was cleared" in _messages(at)


def test_single_to_multi_and_back_keeps_single_file_provenance(monkeypatch):
    _forbid_planner(monkeypatch)
    at = _approve_plan(_generate_plan(_load_sales(_app())))
    sales_sha = at.session_state["eda_report_dataset_sha"]

    at.file_uploader[0].set_value(
        [
            ("sales.csv", SALES, "text/csv"),
            ("weather.csv", WEATHER, "text/csv"),
        ]
    ).run()
    _assert_saved_report_hidden(at)
    text = _messages(at)
    assert "does not join files" in text
    assert "Generate chart plan" not in _button_labels(at)
    assert "Use AI Visual EDA Planner" not in [box.label for box in at.checkbox]
    assert "ds_sales_" in text and "ds_weather_" in text

    at.file_uploader[0].set_value([("sales.csv", SALES, "text/csv")]).run()
    assert "Generate chart plan" in _button_labels(at)
    assert "EDA Summary" not in _subheaders(at)
    assert "eda_report" not in at.session_state
    captions = [caption.value for caption in at.caption]
    assert any("Dataset ID: ds_sales_" in item for item in captions)
    assert not any("ds_weather_" in item for item in captions)
    preview = next(
        frame.value for frame in at.dataframe if list(frame.value.columns) == ["date", "value"]
    )
    assert int(preview["value"].max()) == 30
    assert sales_sha not in " ".join(_subheaders(at))


def _project_box(at: AppTest):
    return next(box for box in at.text_input if box.label == "Project ID for saved artifacts")


def test_project_id_change_does_not_present_the_old_approved_report(monkeypatch):
    _forbid_planner(monkeypatch)
    at = _load_sales(_app())
    at = _project_box(at).set_value("mcm-a").run()
    at = _approve_plan(_generate_plan(at))
    assert at.session_state["eda_report_project_id"] == "mcm-a"
    assert at.session_state["eda_report"]["project_id"] == "mcm-a"
    assert "Artifacts saved under" in _messages(at)
    assert "mcm-a" in _messages(at)

    at = _project_box(at).set_value("mcm-a").run()
    assert "EDA Summary" in _subheaders(at)
    assert at.session_state["eda_report_project_id"] == "mcm-a"

    at = _project_box(at).set_value("mcm-b").run()
    text = _messages(at)
    assert "EDA Summary" not in _subheaders(at)
    assert not list(at.image)
    assert not list(at.download_button)
    assert "Chart-plan approval" not in text
    assert "Artifacts saved under" not in text
    assert "approved for project mcm-a" in text
    assert "not shown as output for the current project ID" in text
    assert at.session_state["eda_report"]["project_id"] == "mcm-a"
    assert at.session_state["eda_report_project_id"] == "mcm-a"

    at = _project_box(at).set_value("mcm-a").run()
    assert "EDA Summary" in _subheaders(at)
    assert "mcm-a" in _messages(at)
    assert "mcm-b" not in _messages(at)

    at.file_uploader[0].set_value([("weather.csv", WEATHER, "text/csv")]).run()
    _assert_saved_report_hidden(at)
    assert "previous saved report was cleared" in _messages(at)
