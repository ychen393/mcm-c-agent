"""Mocked Problem Analyst: valid output, repairs, secrets, cache, and persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from agents.problem_analyst import (
    MAX_REPAIR_RETRIES,
    apply_h1_plan_request,
    build_analyst_messages,
    run_problem_analysis,
)
from core.config import Settings
from core.foundation import build_initialized_state, foundation_input_signature, selection_token
from core.graph import build_foundation_graph
from core.ids import new_run_id
from core.problem_analysis_graph import build_problem_analysis_graph
from core.project_store import LocalProjectStore
from llm.base import LLMResponse
from llm.providers.openai_compatible import OpenAICompatibleLLM
from tools.dataset_bundle import build_dataset_bundle

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "problem_c_2022_excerpt.txt"
EXCERPT = FIXTURE.read_text(encoding="utf-8")
GOLD = (
    b"Date,USD (PM)\n"
    b"9/12/2016,1324.60\n"
    b"9/13/2016,1321.75\n"
)
BITCOIN = b"Date,Value\n9/11/2016,621.65\n9/12/2016,609.67\n"
SECRET = "sk-analyst-test-secret"


class ScriptedLLM:
    def __init__(self, replies: list):
        self.replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    def invoke(self, messages):
        self.calls.append(messages)
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _settings() -> Settings:
    return Settings(
        llm_provider="deepseek",
        llm_model="deepseek-chat",
        llm_base_url="https://api.deepseek.com",
        deepseek_api_key=SecretStr(SECRET),
        project_store_backend="local",
    )


def _foundation(problem: str = EXCERPT, uploads=None):
    if uploads is None:
        uploads = [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)]
    bundle = build_dataset_bundle(uploads, project_id="mcm-2022-c")
    state = build_initialized_state(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        problem_text=problem,
        bundle=bundle,
        selection_status="ready",
        llm_config_revision=0,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    result = build_foundation_graph().invoke(state)
    result["run_id"] = new_run_id()
    signature = foundation_input_signature(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        problem_text=problem,
        selection_token_value=selection_token(
            uploads, fingerprint=bundle.fingerprint, rejected=False
        ),
        llm_config_revision=0,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
    )
    result["eda_report"] = {"keep": True}
    result["approval_status"] = {"chart_plan": "approved"}
    result["analysis_status"] = "not_started"
    return result, signature


def _model_payload(problem: str, files: list[dict] | None = None) -> str:
    from agents.offline_problem_parser import interpret_problem_offline

    spec = interpret_problem_offline(
        problem_text=problem,
        project_id="mcm-2022-c",
        run_id="run_0123456789ab",
        input_signature="a" * 64,
        uploaded_files=files,
        dataset_metadata={"dataset_count": len(files or [])},
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
    payload["trades_performed"] = True
    payload["h1_approved"] = True
    payload["downstream_modeling_performed"] = True
    return json.dumps(payload)


def _response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        provider="deepseek",
        model="deepseek-chat",
        usage={"input_tokens": 11, "output_tokens": 7},
    )


def test_prompt_does_not_send_raw_rows_or_secrets():
    state, signature = _foundation()
    state["uploaded_files"][0]["preview_rows"] = ["1324.60"]
    state["uploaded_files"][0]["api_key"] = SECRET
    state["dataset_metadata"]["deepseek_api_key"] = SECRET
    bulletin_files = state["uploaded_files"]
    from agents.offline_problem_parser import dataset_metadata_bulletin

    bulletin = dataset_metadata_bulletin(bulletin_files, state["dataset_metadata"])
    assert "1324.60" not in bulletin
    assert SECRET not in bulletin
    assert "api_key" not in bulletin
    messages = build_analyst_messages(
        problem_text=EXCERPT + " " + SECRET,
        bulletin=bulletin,
        revision_notes="",
        secrets=[SECRET],
    )
    blob = json.dumps(messages)
    assert SECRET not in blob
    assert "1324.60" not in blob
    assert "raw_bytes" not in blob
    prompt = Path("agents/prompts/problem_analyst_v1.txt").read_text(encoding="utf-8")
    assert "$1,000" not in prompt
    assert "2016-09-11" not in prompt
    llm = ScriptedLLM([_response(_model_payload(EXCERPT))])
    outcome = run_problem_analysis(
        state,
        settings=_settings(),
        revision_notes="",
        foundation_signature=signature,
        llm=llm,
    )
    sent = json.dumps(llm.calls)
    assert SECRET not in sent
    assert "1324.60" not in sent
    assert outcome.status == "ready"


def test_valid_model_output_is_llm_complete_and_does_not_trade(tmp_path):
    state, signature = _foundation()
    llm = ScriptedLLM([_response(_model_payload(EXCERPT))])
    outcome = run_problem_analysis(
        state,
        settings=_settings(),
        revision_notes="",
        foundation_signature=signature,
        llm=llm,
    )
    assert outcome.status == "ready"
    assert outcome.billed_calls == 1
    assert len(llm.calls) == 1
    wrapper = outcome.state["problem_specification"]
    spec = wrapper["specification"]
    official = " ".join(
        item["statement"] for item in spec["constraints"] if item["kind"] == "official"
    )
    assert "$1,000" in official and "1%" in official and "2%" in official
    assert spec["generation_mode"] == "llm"
    assert spec["llm_analysis_complete"] is True
    assert spec["trades_performed"] is False
    assert spec["h1_approved"] is False
    assert spec["downstream_modeling_performed"] is False
    assert outcome.state["analysis_status"] == "not_started"
    assert outcome.state["lifecycle"] == "problem_analysis_ready"
    assert outcome.state["eda_report"] == {"keep": True}
    assert outcome.state["approval_status"]["chart_plan"] == "approved"
    assert "problem_analysis_running" in wrapper["record"]["transitions"]
    store = LocalProjectStore(tmp_path / "projects")
    _project, run, saved = store.save_project_state(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        state=outcome.state,
        input_signature=signature,
    )
    loaded = store.load_run_state("mcm-2022-c", run.run_id)
    assert loaded is not None
    assert loaded["problem_specification"]["status"] == "ready"
    assert loaded["problem_specification"]["specification"]["input_signature"] == signature
    assert SECRET not in json.dumps(saved)
    again = run_problem_analysis(
        loaded,
        settings=_settings(),
        revision_notes="",
        foundation_signature=signature,
        llm=ScriptedLLM([_response("should-not-be-called")]),
    )
    assert again.cache_hit is True
    assert again.billed_calls == 0


def test_malformed_output_retries_twice_then_fails_closed():
    state, signature = _foundation()
    bad = _response("not json")
    llm = ScriptedLLM([bad, bad, bad])
    outcome = run_problem_analysis(
        state,
        settings=_settings(),
        revision_notes="",
        foundation_signature=signature,
        llm=llm,
    )
    assert len(llm.calls) == MAX_REPAIR_RETRIES + 1
    wrapper = outcome.state["problem_specification"]
    assert wrapper["status"] == "failed"
    assert wrapper["llm_analysis_complete"] is False
    assert "invalid_output" in wrapper["reason"]
    assert outcome.state["analysis_status"] == "not_started"
    assert outcome.state["uploaded_files"][0]["file_name"] == "LBMA-GOLD.csv"
    assert outcome.state["eda_report"] == {"keep": True}


def test_repair_accepts_the_third_response_and_stops():
    state, signature = _foundation()
    good = _response(_model_payload(EXCERPT))
    llm = ScriptedLLM([_response("{"), _response("still bad"), good])
    outcome = run_problem_analysis(
        state,
        settings=_settings(),
        revision_notes="",
        foundation_signature=signature,
        llm=llm,
    )
    assert outcome.status == "ready"
    assert outcome.billed_calls == 3
    assert llm.replies == []


def test_invented_fee_and_provider_error_do_not_complete():
    state, signature = _foundation()
    invented = json.loads(_model_payload(EXCERPT))
    invented["constraints"][0]["value"] = "9%"
    invented["constraints"][0]["statement"] = "The commission for gold is 9% of the amount traded."
    llm = ScriptedLLM([_response(json.dumps(invented)) for _ in range(3)])
    outcome = run_problem_analysis(
        state,
        settings=_settings(),
        revision_notes="",
        foundation_signature=signature,
        llm=llm,
    )
    assert outcome.status == "failed"
    assert outcome.state["problem_specification"]["llm_analysis_complete"] is False
    assert "9%" in outcome.state["problem_specification"]["reason"] or "invalid_output" in (
        outcome.state["problem_specification"]["reason"]
    )

    state, signature = _foundation()
    failed = run_problem_analysis(
        state,
        settings=_settings(),
        revision_notes="",
        foundation_signature=signature,
        llm=ScriptedLLM([RuntimeError("boom sk-should-not-leak")]),
    )
    assert failed.status == "failed"
    assert failed.billed_calls == 1
    assert "provider_error" in failed.state["problem_specification"]["reason"]
    assert "sk-" not in failed.state["problem_specification"]["reason"]
    assert failed.state["uploaded_files"]


def test_unconfigured_model_is_blocked_not_complete():
    state, signature = _foundation()
    settings = Settings(
        llm_provider="deepseek",
        llm_model="replace-with-model-id",
        project_store_backend="local",
    )
    outcome = run_problem_analysis(
        state,
        settings=settings,
        revision_notes="",
        foundation_signature=signature,
    )
    assert outcome.status == "blocked"
    assert outcome.billed_calls == 0
    assert outcome.state["problem_specification"]["llm_analysis_complete"] is False
    assert outcome.state["analysis_status"] != "complete"
    assert outcome.state["lifecycle"] == "problem_analysis_failed"


def test_graph_streams_running_before_ready():
    state, signature = _foundation()
    from agents.problem_analyst import ProblemAnalyst

    analyst = ProblemAnalyst(
        ScriptedLLM([_response(_model_payload(EXCERPT))]),
        provider="deepseek",
        model="deepseek-chat",
        configured=True,
    )
    prepared = dict(state)
    prepared["foundation_input_signature"] = signature
    prepared["problem_revision_notes"] = ""
    seen = []
    graph = build_problem_analysis_graph(analyst)
    assert graph.checkpointer is None
    for update in graph.stream(prepared):
        seen.append(update)
    assert seen[0]["mark_running"]["lifecycle"] == "problem_analysis_running"
    final = seen[-1]["analyze"]
    assert final["lifecycle"] == "problem_analysis_ready"
    assert final["eda_report"] == {"keep": True}
    assert final["analysis_status"] == "not_started"


def test_signature_change_hides_the_old_specification(tmp_path):
    state, signature = _foundation()
    outcome = run_problem_analysis(
        state,
        settings=_settings(),
        revision_notes="",
        foundation_signature=signature,
        llm=ScriptedLLM([_response(_model_payload(EXCERPT))]),
    )
    store = LocalProjectStore(tmp_path / "projects")
    _project, first_run, _saved = store.save_project_state(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        state=outcome.state,
        input_signature=signature,
    )
    replacement, new_signature = _foundation(problem=EXCERPT + "\nExtra note.")
    assert new_signature != signature
    _project, run, saved = store.save_project_state(
        project_id="mcm-2022-c",
        project_name="2022 MCM Problem C",
        state=replacement,
        input_signature=new_signature,
    )
    assert saved["problem_specification"] == {}
    assert run.run_id != first_run.run_id
    stale = store.continue_run("mcm-2022-c", first_run.run_id)
    assert stale is not None
    assert any(item.get("code") == "stale_run" for item in stale.get("errors") or [])
    requested = apply_h1_plan_request(outcome.state)
    assert requested["problem_specification"]["h1_plan_request"]["approved"] is False
    assert requested["approval_status"].get("H1") != "approved"
    with pytest.raises(ValueError):
        apply_h1_plan_request(replacement)


def test_adapter_still_refuses_a_missing_key():
    adapter = OpenAICompatibleLLM(
        provider="deepseek",
        model="deepseek-chat",
        api_key=None,
        base_url="https://api.deepseek.com",
    )
    with pytest.raises(RuntimeError, match="Missing API key"):
        adapter.invoke([{"role": "user", "content": "hello"}])
