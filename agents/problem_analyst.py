"""Problem Analyst.

Calls the configured LLM provider, validates the JSON, and retries malformed
output at most twice. A missing provider is blocked. It is not marked complete.
The offline parser is not a fallback for this path.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import SecretStr, ValidationError

from agents.offline_problem_parser import dataset_metadata_bulletin
from core.config import Settings
from core.ids import new_run_id, utc_now_iso, validate_run_id
from llm.base import BaseLLM, LLMResponse
from llm.factory import LLMFactory
from schemas.persistence import assert_safe_for_persistence
from schemas.problem_specification import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    ProblemSpecification,
    ProblemSpecificationBody,
    assert_grounded,
)

MAX_REPAIR_RETRIES = 2
MAX_PROBLEM_CHARS = 12_000
MAX_REVISION_CHARS = 2_000
_PLACEHOLDER_MODEL = "replace-with-model-id"
_PROMPT_PATH = Path(__file__).parent / "prompts" / "problem_analyst_v1.txt"
_SERVER_KEYS = (
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
)
_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "prompt_tokens",
    "completion_tokens",
)


@dataclass
class AnalysisRun:
    state: dict[str, Any]
    cache_hit: bool
    billed_calls: int
    status: str


def provider_is_configured(settings: Settings) -> bool:
    model = (settings.llm_model or "").strip()
    if not model or model == _PLACEHOLDER_MODEL:
        return False
    key = settings.provider_api_key()
    return bool(key and key.get_secret_value().strip())


def analysis_input_signature(
    foundation_signature: str,
    revision_notes: str,
    *,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    payload = {
        "foundation_signature": foundation_signature,
        "revision_notes": revision_notes,
        "prompt_version": prompt_version,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _prompt_text() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _redact(text: str, secrets: list[str]) -> str:
    cleaned = text
    for secret in secrets:
        if secret and len(secret) >= 8:
            cleaned = cleaned.replace(secret, "[redacted]")
    cleaned = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "[redacted]", cleaned)
    return cleaned[:500]


def _known_secrets(settings: Settings | None) -> list[str]:
    if settings is None:
        return []
    secrets: list[str] = []
    for value in (
        settings.llm_api_key,
        settings.openai_api_key,
        settings.deepseek_api_key,
        settings.anthropic_api_key,
    ):
        if isinstance(value, SecretStr) and value.get_secret_value().strip():
            secrets.append(value.get_secret_value().strip())
    return secrets


def build_analyst_messages(
    *,
    problem_text: str,
    bulletin: str,
    revision_notes: str,
    secrets: list[str] | None = None,
    repair_error: str | None = None,
    previous_content: str | None = None,
) -> list[dict[str, str]]:
    """Prompt payload. Callers must pass the bulletin, never file bytes."""
    safe_problem = _redact(problem_text, secrets or [])
    safe_bulletin = _redact(bulletin, secrets or [])
    safe_revision = _redact(revision_notes, secrets or [])
    user = (
        f"{_prompt_text().strip()}\n\n"
        "Problem text:\n"
        f"{safe_problem}\n\n"
        "Dataset metadata bulletin:\n"
        f"{safe_bulletin}\n"
    )
    if safe_revision.strip():
        user += (
            "\nUser revision notes (not official problem text):\n"
            f"{safe_revision}\n"
        )
    messages = [
        {
            "role": "system",
            "content": (
                "Return only a JSON ProblemSpecification body. "
                "Do not include API keys, file bytes, or row values."
            ),
        },
        {"role": "user", "content": user},
    ]
    if repair_error is not None:
        messages.append({"role": "assistant", "content": previous_content or ""})
        messages.append(
            {
                "role": "user",
                "content": (
                    "The previous JSON failed validation. Return one corrected JSON object. "
                    f"Do not invent facts. Validation error: {repair_error}"
                ),
            }
        )
    return messages


def _extract_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Model output did not contain a JSON object.")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model output JSON must be an object.")
    return parsed


def _usage(usage: Any) -> dict[str, int] | None:
    if usage is None:
        return None
    if not isinstance(usage, dict):
        mapping = getattr(usage, "items", None)
        usage = dict(mapping()) if callable(mapping) else None
    if not isinstance(usage, dict):
        return None
    cleaned: dict[str, int] = {}
    for key in _USAGE_KEYS:
        item = usage.get(key)
        if isinstance(item, int):
            cleaned[key] = item
    return cleaned or None


def _cache_hit(state: dict[str, Any], signature: str) -> dict[str, Any] | None:
    wrapper = state.get("problem_specification") or {}
    if not isinstance(wrapper, dict) or wrapper.get("status") != "ready":
        return None
    record = wrapper.get("record") or {}
    if record.get("analysis_input_signature") != signature:
        return None
    if not wrapper.get("specification"):
        return None
    return wrapper


def _specification_id(project_id: str, run_id: str, signature: str, version: int) -> str:
    digest = hashlib.sha256(f"{project_id}|{run_id}|{signature}|{version}".encode()).hexdigest()
    return f"psp_{digest[:12]}"


def _next_version(state: dict[str, Any]) -> int:
    wrapper = state.get("problem_specification") or {}
    record = wrapper.get("record") if isinstance(wrapper, dict) else None
    current = int(record.get("version") or 0) if isinstance(record, dict) else 0
    return current + 1


def _empty_wrapper(
    *,
    status: str,
    reason: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "llm_analysis_complete": False,
        "generation_mode": "none",
        "specification": None,
        "record": record,
        "h1_plan_request": None,
        "reason": reason,
    }


def _record(
    *,
    status: str,
    reason: str,
    provider: str,
    model: str,
    attempts: int,
    billed_calls: int,
    usage: dict[str, int] | None,
    started_at: str,
    finished_at: str,
    foundation_signature: str,
    analysis_signature: str,
    revision_notes: str,
    transitions: list[str],
    version: int,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "failure_reason": None if status == "ready" else reason,
        "provider": provider,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "attempts": attempts,
        "billed_calls": billed_calls,
        "usage": usage,
        "started_at": started_at,
        "finished_at": finished_at,
        "foundation_signature": foundation_signature,
        "analysis_input_signature": analysis_signature,
        "revision_notes": revision_notes,
        "transitions": transitions,
        "cache_hit": False,
        "version": version,
        "llm_analysis_complete": False,
    }


def _finish(
    state: dict[str, Any],
    *,
    lifecycle: str,
    current_stage: str,
    wrapper: dict[str, Any],
    entry: str,
) -> dict[str, Any]:
    updated = dict(state)
    updated["lifecycle"] = lifecycle
    updated["current_stage"] = current_stage
    updated["problem_specification"] = wrapper
    updated["analyst_entry_lifecycle"] = entry
    errors = [
        item
        for item in (state.get("errors") or [])
        if not (isinstance(item, dict) and item.get("source") == "problem_analyst")
    ]
    if wrapper["status"] != "ready":
        errors.append(
            {
                "source": "problem_analyst",
                "code": wrapper["status"],
                "message": wrapper.get("reason") or wrapper["status"],
            }
        )
    updated["errors"] = errors
    return updated


def parse_model_specification(
    content: str,
    *,
    problem_text: str,
    bulletin: str,
    revision_notes: str,
    project_id: str,
    run_id: str,
    input_signature: str,
    version: int,
    provider: str,
    model: str,
    generated_at: str,
) -> ProblemSpecification:
    payload = _extract_json(content)
    assert_safe_for_persistence(payload, "model_output")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version must be problem-specification-v1.")
    for key in _SERVER_KEYS:
        payload.pop(key, None)
    body = ProblemSpecificationBody.model_validate(payload)
    assert_grounded(
        body,
        problem_text=problem_text,
        bulletin=bulletin,
        revision_notes=revision_notes,
    )
    validate_run_id(run_id)
    return ProblemSpecification.model_validate(
        {
            **body.model_dump(mode="python"),
            "specification_id": _specification_id(project_id, run_id, input_signature, version),
            "project_id": project_id,
            "run_id": run_id,
            "input_signature": input_signature,
            "version": version,
            "generation_mode": "llm",
            "llm_analysis_complete": True,
            "provider": provider,
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "generated_at": generated_at,
            "downstream_modeling_performed": False,
            "trades_performed": False,
            "h1_approved": False,
        }
    )


class ProblemAnalyst:
    def __init__(
        self,
        llm: BaseLLM | None,
        *,
        provider: str,
        model: str,
        configured: bool,
        settings: Settings | None = None,
    ):
        self.llm = llm
        self.provider = provider
        self.model = model
        self.configured = configured
        self.settings = settings

    def analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        started = utc_now_iso()
        problem_text = str(state.get("problem_text") or "")
        revision = str(state.get("problem_revision_notes") or "")
        foundation_signature = str(state.get("foundation_input_signature") or "")
        entry = str(
            state.get("analyst_entry_lifecycle")
            or state.get("lifecycle")
            or "datasets_recorded"
        )
        if entry == "problem_analysis_running":
            entry = "datasets_recorded"
        transitions = [entry, "problem_analysis_running"]
        files = list(state.get("uploaded_files") or [])
        bulletin = dataset_metadata_bulletin(files, state.get("dataset_metadata") or {})
        version = _next_version(state)
        run_id = str(state.get("run_id") or "")
        project_id = str(state.get("project_id") or "")

        def failed(
            reason: str,
            *,
            attempts: int,
            billed: int,
            usage: dict[str, int] | None = None,
        ) -> dict[str, Any]:
            finished = utc_now_iso()
            record = _record(
                status="failed",
                reason=reason,
                provider=self.provider,
                model=self.model,
                attempts=attempts,
                billed_calls=billed,
                usage=usage,
                started_at=started,
                finished_at=finished,
                foundation_signature=foundation_signature,
                analysis_signature="",
                revision_notes=revision,
                transitions=transitions + ["problem_analysis_failed"],
                version=version,
            )
            wrapper = _empty_wrapper(status="failed", reason=reason, record=record)
            return _finish(
                state,
                lifecycle="problem_analysis_failed",
                current_stage="problem_analysis_failed",
                wrapper=wrapper,
                entry=entry,
            )

        if not problem_text.strip() or not files:
            return failed("Problem text and recorded datasets are required.", attempts=0, billed=0)
        if len(problem_text) > MAX_PROBLEM_CHARS or len(revision) > MAX_REVISION_CHARS:
            return failed(
                "Problem text or revision notes exceed the analyst limit.",
                attempts=0,
                billed=0,
            )
        if not foundation_signature or len(foundation_signature) != 64:
            return failed(
                "A foundation input signature is required before analysis.",
                attempts=0,
                billed=0,
            )
        try:
            validate_run_id(run_id)
        except ValueError:
            run_id = new_run_id()
            state = dict(state)
            state["run_id"] = run_id

        signature = analysis_input_signature(foundation_signature, revision)
        cached = _cache_hit(state, signature)
        if cached is not None:
            updated = dict(state)
            record = dict(cached.get("record") or {})
            record["cache_hit"] = True
            wrapper = dict(cached)
            wrapper["record"] = record
            updated["problem_specification"] = wrapper
            updated["lifecycle"] = "problem_analysis_ready"
            updated["current_stage"] = "problem_analysis_ready"
            return updated

        if not self.configured or self.llm is None:
            finished = utc_now_iso()
            record = _record(
                status="blocked",
                reason="provider_unconfigured",
                provider=self.provider,
                model=self.model,
                attempts=0,
                billed_calls=0,
                usage=None,
                started_at=started,
                finished_at=finished,
                foundation_signature=foundation_signature,
                analysis_signature=signature,
                revision_notes=revision,
                transitions=transitions + ["problem_analysis_failed"],
                version=version,
            )
            wrapper = _empty_wrapper(
                status="blocked",
                reason="No configured model. Problem analysis did not run.",
                record=record,
            )
            return _finish(
                state,
                lifecycle="problem_analysis_failed",
                current_stage="problem_analysis_failed",
                wrapper=wrapper,
                entry=entry,
            )

        secrets = _known_secrets(self.settings)
        messages = build_analyst_messages(
            problem_text=problem_text,
            bulletin=bulletin,
            revision_notes=revision,
            secrets=secrets,
        )
        attempts = 0
        billed = 0
        usage: dict[str, int] | None = None
        previous = ""
        last_error = "invalid_output"
        while attempts <= MAX_REPAIR_RETRIES:
            attempts += 1
            billed += 1
            try:
                response: LLMResponse = self.llm.invoke(messages)
            except Exception as exc:
                return failed(
                    f"provider_error: {type(exc).__name__}",
                    attempts=attempts,
                    billed=billed,
                    usage=usage,
                )
            previous = response.content or ""
            usage = _usage(response.usage) or usage
            try:
                spec = parse_model_specification(
                    previous,
                    problem_text=problem_text,
                    bulletin=bulletin,
                    revision_notes=revision,
                    project_id=project_id,
                    run_id=run_id,
                    input_signature=foundation_signature,
                    version=version,
                    provider=response.provider or self.provider,
                    model=response.model or self.model,
                    generated_at=utc_now_iso(),
                )
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = _redact(f"{type(exc).__name__}: {exc}", secrets)
                if attempts > MAX_REPAIR_RETRIES:
                    break
                messages = build_analyst_messages(
                    problem_text=problem_text,
                    bulletin=bulletin,
                    revision_notes=revision,
                    secrets=secrets,
                    repair_error=last_error,
                    previous_content=_redact(previous, secrets)[:4000],
                )
                continue
            finished = utc_now_iso()
            record = _record(
                status="ready",
                reason="",
                provider=spec.provider,
                model=spec.model,
                attempts=attempts,
                billed_calls=billed,
                usage=usage,
                started_at=started,
                finished_at=finished,
                foundation_signature=foundation_signature,
                analysis_signature=signature,
                revision_notes=revision,
                transitions=transitions + ["problem_analysis_ready"],
                version=spec.version,
            )
            record["llm_analysis_complete"] = True
            wrapper = {
                "status": "ready",
                "llm_analysis_complete": True,
                "generation_mode": "llm",
                "specification": spec.model_dump(mode="python"),
                "record": record,
                "h1_plan_request": None,
                "reason": "",
            }
            assert_safe_for_persistence(wrapper, "problem_specification")
            return _finish(
                state,
                lifecycle="problem_analysis_ready",
                current_stage="problem_analysis_ready",
                wrapper=wrapper,
                entry=entry,
            )
        return failed(
            f"invalid_output: {last_error}",
            attempts=attempts,
            billed=billed,
            usage=usage,
        )


def run_problem_analysis(
    state: dict[str, Any],
    *,
    settings: Settings,
    revision_notes: str,
    foundation_signature: str,
    llm: BaseLLM | None = None,
) -> AnalysisRun:
    """Run the typed graph. A cache hit does not call the provider again."""
    from core.problem_analysis_graph import build_problem_analysis_graph

    prepared = dict(state)
    prepared["problem_revision_notes"] = revision_notes
    prepared["foundation_input_signature"] = foundation_signature
    signature = analysis_input_signature(foundation_signature, revision_notes)
    if _cache_hit(prepared, signature) is not None:
        analyst = ProblemAnalyst(
            None,
            provider=settings.llm_provider,
            model=settings.llm_model,
            configured=False,
            settings=settings,
        )
        updated = analyst.analyze(prepared)
        return AnalysisRun(state=updated, cache_hit=True, billed_calls=0, status="ready")

    configured = llm is not None or provider_is_configured(settings)
    if llm is None and configured:
        llm = LLMFactory.create(settings)
    analyst = ProblemAnalyst(
        llm if configured else None,
        provider=settings.llm_provider,
        model=settings.llm_model,
        configured=configured,
        settings=settings,
    )
    result = build_problem_analysis_graph(analyst).invoke(prepared)
    wrapper = result.get("problem_specification") or {}
    record = wrapper.get("record") or {}
    return AnalysisRun(
        state=result,
        cache_hit=False,
        billed_calls=int(record.get("billed_calls") or 0),
        status=str(wrapper.get("status") or "failed"),
    )


def apply_h1_plan_request(state: dict[str, Any]) -> dict[str, Any]:
    """Record that a later phase may draft an H1 plan. Does not approve H1."""
    wrapper = dict(state.get("problem_specification") or {})
    if wrapper.get("status") != "ready" or not wrapper.get("specification"):
        raise ValueError("A current problem specification is required before preparing an H1 plan.")
    spec = wrapper["specification"]
    questions = [item["text"] for item in spec.get("research_questions") or []]
    unknowns = [item["statement"] for item in spec.get("uncertainties") or []]
    updated = dict(state)
    wrapper["h1_plan_request"] = {
        "status": "prepared_for_later_phase",
        "approved": False,
        "strategy_included": False,
        "specification_id": spec.get("specification_id"),
        "research_questions": questions,
        "unknowns": unknowns,
        "note": (
            "H1 research plan inputs were packaged for a later phase. "
            "No H1 approval was recorded. No strategy was selected or traded."
        ),
    }
    updated["problem_specification"] = wrapper
    updated["approval_status"] = dict(state.get("approval_status") or {})
    return updated
