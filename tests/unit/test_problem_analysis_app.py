"""Streamlit AppTest: Analyze Problem on the 2022 gold and bitcoin fixture."""

from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from llm.base import LLMResponse

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"
EXCERPT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "problem_c_2022_excerpt.txt"
).read_text(encoding="utf-8")
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


class CountingLLM:
    def __init__(self, content: str):
        self.content = content
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        blob = json.dumps(messages)
        assert "1324.60" not in blob
        assert "621.65" not in blob
        return LLMResponse(
            content=self.content,
            provider="deepseek",
            model="deepseek-chat",
            usage={"input_tokens": 5, "output_tokens": 6},
        )


def _payload() -> str:
    from agents.offline_problem_parser import interpret_problem_offline

    spec = interpret_problem_offline(
        problem_text=EXCERPT,
        project_id="mcm-2022-c",
        run_id="run_0123456789ab",
        input_signature="a" * 64,
    )
    payload = spec.model_dump(mode="python")
    for key in (
        "specification_id",
        "project_id",
        "run_id",
        "input_signature",
        "version",
        "generation_mode",
        "llm_analysis_complete",
        "provider",
        "model",
        "prompt_version",
        "generated_at",
        "downstream_modeling_performed",
        "trades_performed",
        "h1_approved",
    ):
        payload.pop(key, None)
    return json.dumps(payload)


def _messages(at: AppTest) -> str:
    parts: list[str] = []
    for group in (at.success, at.error, at.info, at.warning, at.caption, at.markdown, at.subheader):
        for widget in group:
            value = getattr(widget, "value", None)
            if value:
                parts.append(str(value))
    return "\n".join(parts)


def _button(at: AppTest, label: str):
    return next(button for button in at.button if button.label == label)


def _prepare(at: AppTest) -> AppTest:
    name = next(box for box in at.text_input if box.label == "Project name")
    name.set_value("2022 MCM Problem C")
    next(box for box in at.text_input if box.label == "Project ID for saved artifacts").set_value(
        "mcm-2022-c"
    )
    next(area for area in at.text_area if area.label.startswith("MCM problem statement")).set_value(
        EXCERPT
    )
    at = at.run()
    at = (
        at.file_uploader[0]
        .set_value(
            [
                ("LBMA-GOLD.csv", GOLD, "text/csv"),
                ("BCHAIN-MKPRU.csv", BITCOIN, "text/csv"),
            ]
        )
        .run()
    )
    at = _button(at, "Initialize project").click().run()
    assert not at.exception
    return at


def test_analyze_problem_shows_grounded_facts_and_does_not_rebill(monkeypatch):
    llm = CountingLLM(_payload())
    monkeypatch.setattr("agents.problem_analyst.provider_is_configured", lambda _settings: True)
    monkeypatch.setattr("llm.factory.LLMFactory.create", lambda _settings: llm)
    at = _prepare(AppTest.from_file(APP_PATH, default_timeout=60).run())
    at = _button(at, "Analyze Problem").click().run()
    assert not at.exception
    text = _messages(at)
    assert "$1,000" in text
    assert "1%" in text and "2%" in text
    assert "2016-09-11" in text and "2021-09-10" in text
    assert "memorandum" in text.lower()
    assert "Proposed only" in text
    assert "not a trading strategy" in text or "No strategy was executed" in text
    state = at.session_state["last_run"]
    assert state["lifecycle"] == "problem_analysis_ready"
    assert state["analysis_status"] != "complete"
    assert state["problem_specification"]["llm_analysis_complete"] is True
    assert [item["file_name"] for item in state["uploaded_files"]] == [
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    ]
    assert llm.calls == 1
    at = _button(at, "Analyze Problem").click().run()
    assert not at.exception
    assert llm.calls == 1
    at = _button(at, "Prepare H1 research plan").click().run()
    assert not at.exception
    h1 = at.session_state["last_run"]["problem_specification"]["h1_plan_request"]
    assert h1["approved"] is False
    assert h1["strategy_included"] is False
    assert "No H1 approval" in _messages(at)


def test_provider_failure_is_visible_and_keeps_datasets(monkeypatch):
    class Boom:
        def invoke(self, _messages):
            raise RuntimeError("provider down")

    monkeypatch.setattr("agents.problem_analyst.provider_is_configured", lambda _settings: True)
    monkeypatch.setattr("llm.factory.LLMFactory.create", lambda _settings: Boom())
    at = _prepare(AppTest.from_file(APP_PATH, default_timeout=60).run())
    at = _button(at, "Analyze Problem").click().run()
    assert not at.exception
    assert "Problem analysis failed" in _messages(at)
    state = at.session_state["last_run"]
    assert state["problem_specification"]["status"] == "failed"
    assert state["problem_specification"]["llm_analysis_complete"] is False
    assert state["analysis_status"] != "complete"
    assert [item["file_name"] for item in state["uploaded_files"]] == [
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    ]


def test_missing_model_is_blocked_and_does_not_call_a_provider(monkeypatch):
    def _explode(_settings):
        raise AssertionError("unconfigured analysis must not create a provider")

    monkeypatch.setattr("agents.problem_analyst.provider_is_configured", lambda _settings: False)
    monkeypatch.setattr("llm.factory.LLMFactory.create", _explode)
    at = _prepare(AppTest.from_file(APP_PATH, default_timeout=60).run())
    at = _button(at, "Analyze Problem").click().run()
    assert not at.exception
    text = _messages(at)
    assert "No configured model" in text
    assert "not complete" in text
    state = at.session_state["last_run"]
    assert state["problem_specification"]["status"] == "blocked"
    assert state["analysis_status"] != "complete"
    assert state["uploaded_files"]
