"""Streamlit AppTest coverage for multi-file intake. No model provider is called."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"

SALES = b"date,value\n2026-01-01,10\n2026-01-02,30\n2026-01-03,20\n"
WEATHER = b"date,value\n2026-01-01,100\n2026-01-02,80\n2026-01-03,90\n"
OUTCOMES = b"region,outcome\nNorth,1\nSouth,2\nEast,3\n"


def _app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=60).run()


def _button_labels(at: AppTest) -> list[str]:
    return [button.label for button in at.button]


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
    sales_profile = at.dataframe[2].value
    weather_profile = at.dataframe[4].value
    assert sales_profile.loc[sales_profile["Column"] == "value", "Mean"].iloc[0] == 20
    assert weather_profile.loc[weather_profile["Column"] == "value", "Mean"].iloc[0] == 90
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
