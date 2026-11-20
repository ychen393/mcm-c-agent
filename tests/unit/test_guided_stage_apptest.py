"""Streamlit user's six-stage navigation must not expose unrelated panels."""
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"


def test_guided_stage_switch_changes_visible_research_panel_without_approvals():
    app = AppTest.from_file(str(APP_PATH), default_timeout=60).run()
    assert not app.exception
    guide = next(
        s for s in app.selectbox
        if "Explore a stage" in s.label or "查看阶段说明" in s.label
    )
    assert len(guide.options) == 6

    app = guide.select(guide.options[3]).run()
    assert not app.exception
    headings = [str(x.value) for x in app.subheader]
    assert not any("Problem Analyst" == h for h in headings)
    assert any("Model" in h or "建模" in h for h in headings)
    assert not any("Paper Planner" in h or "论文规划" in h for h in headings)


def test_next_button_browses_eda_without_setting_h1_or_running_model():
    app = AppTest.from_file(str(APP_PATH), default_timeout=60).run()
    assert not app.exception
    assert "last_run" not in app.session_state
    next_button = next(
        b for b in app.button if b.label in ("Next stage →", "下一阶段 →")
    )
    app = next_button.click().run()
    assert not app.exception
    assert app.session_state["guided_stage_preview"] == 1
    assert "last_run" not in app.session_state
    assert not any(b.label == "Run historical backtest" for b in app.button)
