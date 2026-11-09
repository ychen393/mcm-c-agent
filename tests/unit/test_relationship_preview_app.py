"""Streamlit AppTest for choosing keys and previewing a join. No model call."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"

SALES = b"date,value\n2026-01-01,10\n2026-01-02,30\n2026-01-03,20\n"
WEATHER = b"date,value\n2026-01-01,100\n2026-01-02,80\n2026-01-03,90\n"
OUTCOMES = b"region,outcome\nNorth,1\nSouth,2\nEast,3\n"
STATIONS = b"station_id,rainfall_mm\nA,1\nB,2\nC,3\nD,4\n"


def _app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=60).run()


def _forbid_planner(monkeypatch: pytest.MonkeyPatch) -> None:
    def _called(*_args, **_kwargs):
        raise AssertionError("Visual EDA planner must not be called in this test.")

    monkeypatch.setattr("agents.visual_eda_agent.plan_visual_eda", _called)


def _messages(at: AppTest) -> str:
    parts: list[str] = []
    for group in (at.success, at.error, at.info, at.warning, at.caption, at.markdown, at.subheader):
        for widget in group:
            value = getattr(widget, "value", None)
            if value:
                parts.append(str(value))
    return "\n".join(parts)


def _select(at: AppTest, label: str):
    return next(widget for widget in at.selectbox if widget.label == label)


def _join_frames(at: AppTest):
    frames = []
    for item in at.dataframe:
        columns = [str(column) for column in item.value.columns]
        if any(column.startswith("ds_") and "." in column for column in columns):
            frames.append(item.value)
    return frames


def test_single_file_path_has_no_join_preview(monkeypatch: pytest.MonkeyPatch):
    _forbid_planner(monkeypatch)
    at = _app()
    at = at.file_uploader[0].set_value([("sales.csv", SALES, "text/csv")]).run()
    assert not at.exception
    assert "Preview join" not in [button.label for button in at.button]
    assert "Relationship evidence" not in [header.value for header in at.subheader]
    assert "Generate chart plan" in [button.label for button in at.button]


def test_user_selects_keys_and_previews_a_safe_join(monkeypatch: pytest.MonkeyPatch):
    _forbid_planner(monkeypatch)
    at = _app()
    at = (
        at.file_uploader[0]
        .set_value(
            [
                ("sales.csv", SALES, "text/csv"),
                ("weather.csv", WEATHER, "text/csv"),
            ]
        )
        .run()
    )
    assert not at.exception
    assert "Generate chart plan" not in [button.label for button in at.button]
    text = _messages(at)
    assert "does not join files" in text
    assert "not joined" in text
    assert "Relationship evidence" in text
    at = _select(at, "Left dataset").set_value("sales.csv").run()
    at = _select(at, "Right dataset").set_value("weather.csv").run()
    at = _select(at, "Left key").set_value("date").run()
    at = _select(at, "Right key").set_value("date").run()
    at = _select(at, "Join type").set_value("Inner").run()
    preview = next(button for button in at.button if button.label == "Preview join")
    at = preview.click().run()
    assert not at.exception
    frames = _join_frames(at)
    assert len(frames) == 1
    columns = [str(column) for column in frames[0].columns]
    value_columns = [column for column in columns if column.endswith(".value")]
    assert len(value_columns) == 2
    assert value_columns[0] != value_columns[1]
    assert "value" not in columns
    assert set(frames[0][value_columns[0]]) == {10, 30, 20}
    assert set(frames[0][value_columns[1]]) == {100, 80, 90}
    assert "not saved" in _messages(at).lower()
    assert "eda_pending_plan" not in at.session_state


def test_unrelated_datasets_show_cannot_safely_join(monkeypatch: pytest.MonkeyPatch):
    _forbid_planner(monkeypatch)
    at = _app()
    at = (
        at.file_uploader[0]
        .set_value(
            [
                ("stations.csv", STATIONS, "text/csv"),
                ("outcomes.csv", OUTCOMES, "text/csv"),
            ]
        )
        .run()
    )
    assert not at.exception
    assert "cannot safely join" in _messages(at)
    at = _select(at, "Left dataset").set_value("stations.csv").run()
    at = _select(at, "Right dataset").set_value("outcomes.csv").run()
    at = _select(at, "Left key").set_value("station_id").run()
    at = _select(at, "Right key").set_value("region").run()
    at = _select(at, "Join type").set_value("Outer").run()
    at = next(button for button in at.button if button.label == "Preview join").click().run()
    assert not at.exception
    assert _join_frames(at) == []
    assert "cannot safely join" in _messages(at)
    assert "Generate chart plan" not in [button.label for button in at.button]
