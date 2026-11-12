"""Problem Analyst: problem text → validated ProblemSpecification.

Default path is deterministic (fixture-backed for 2022 MCM C). An optional LLM
path is available behind Settings.problem_analyst_use_llm / use_llm=True, with
one structured repair attempt on Pydantic validation failure.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from core.config import Settings, get_settings
from llm.base import BaseLLM
from llm.factory import LLMFactory
from schemas.problem_specification import ProblemSpecification
from tools.problem_spec_2022_c import build_2022_c_specification, detect_2022_mcm_c

PROMPT_VERSION = "problem_analyst_v1"
MAX_PROBLEM_CHARS = 40_000


def _prompt_text() -> str:
    prompt_path = Path(__file__).parent / "prompts" / "problem_analyst_v1.txt"
    return prompt_path.read_text(encoding="utf-8")


def _strip_code_fence(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    return cleaned.strip()


def parse_problem_specification(content: str) -> ProblemSpecification:
    cleaned = _strip_code_fence(content)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Model response is not valid JSON: {exc.msg} at character {exc.pos}."
        ) from exc
    try:
        return ProblemSpecification.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Model response does not match ProblemSpecification: {exc}") from exc


def _llm_enabled(settings: Settings | None, use_llm: bool | None) -> bool:
    if use_llm is not None:
        return bool(use_llm)
    if settings is not None:
        return bool(settings.problem_analyst_use_llm)
    env = os.getenv("PROBLEM_ANALYST_USE_LLM", "").strip().lower()
    return env in {"1", "true", "yes", "on"}


def _generic_unknown_spec(problem_text: str, *, reason: str) -> ProblemSpecification:
    """Minimal fail-soft specification when the problem is not a known fixture."""
    snippet = " ".join(problem_text.strip().split())[:240] or "No problem text supplied."
    return ProblemSpecification(
        problem_id="unknown_mcm_c",
        title="Unrecognized MCM Problem C statement",
        research_questions=[
            {
                "id": "rq_clarify_problem",
                "statement": (
                    "Clarify the official problem identity, research questions, and constraints "
                    "before modeling."
                ),
                "provenance": "unknown",
                "source_location": "Analyst fallback",
            }
        ],
        objectives=[
            {
                "id": "obj_await_official_text",
                "statement": "Obtain a complete official problem statement suitable for structured parsing.",
                "provenance": "unknown",
                "source_location": "Analyst fallback",
            }
        ],
        constraints=[],
        supplied_datasets=[],
        assumptions_to_validate=[],
        required_deliverables=[],
        unknowns_or_risks=[
            {
                "id": "u_problem_identity",
                "statement": f"Could not map the statement to a supported fixture. Detail: {reason}",
                "severity": "high",
                "mitigation_hint": "Paste the full official MCM C text or enable the LLM analyst path.",
            }
        ],
        subproblems=[
            {
                "id": "sp_intake_clarification",
                "title": "Problem intake clarification",
                "statement": snippet,
                "provenance": "unknown",
                "inputs": ["Full official problem PDF/text", "Any supplied data files"],
                "outputs": ["Validated ProblemSpecification"],
                "evidence_needed": ["Official wording for capital, assets, calendars, costs, data rules"],
                "candidate_methods": ["Deterministic fixture match", "Structured LLM extraction with repair"],
                "acceptance_criteria": [
                    "Pydantic ProblemSpecification validates",
                    "Official vs inferred vs unknown labels are explicit",
                ],
            }
        ],
        key_formulas=[],
        numeric_conditions=[],
        trading_rules=[],
        strategy="deterministic",
        analyst_prompt_version=PROMPT_VERSION,
        fallback_reason=reason[:1000],
        analysis_notes=[
            "Deterministic fixture match failed; returned an explicit unknown specification.",
            "This is not a silent success for modeling — treat unknowns as blockers.",
        ],
    )


def _analyze_deterministic(problem_text: str) -> ProblemSpecification:
    text = (problem_text or "").strip()
    if not text:
        return _generic_unknown_spec("", reason="Empty problem statement.")
    if detect_2022_mcm_c(text):
        return build_2022_c_specification(text)
    return _generic_unknown_spec(
        text,
        reason="No deterministic fixture matched; LLM path was not enabled.",
    )


def _build_messages(problem_text: str) -> list[dict[str, str]]:
    if len(problem_text) > MAX_PROBLEM_CHARS:
        raise ValueError(
            f"Problem statement exceeds {MAX_PROBLEM_CHARS:,} characters; shorten it before analysis."
        )
    user_payload: dict[str, Any] = {
        "problem_statement": problem_text,
        "required_output_schema": ProblemSpecification.model_json_schema(),
        "instructions": {
            "strategy": "agent",
            "analyst_prompt_version": PROMPT_VERSION,
            "prefer_official_excerpts": True,
        },
    }
    return [
        {"role": "system", "content": _prompt_text()},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def _analyze_with_llm(
    problem_text: str,
    *,
    llm: BaseLLM | None,
    settings: Settings | None,
) -> ProblemSpecification:
    messages = _build_messages(problem_text.strip())
    planner = llm or LLMFactory.create(settings or get_settings())
    response = planner.invoke(messages)
    try:
        spec = parse_problem_specification(response.content)
    except Exception as first_error:
        repair_messages = messages + [
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": (
                    "Your previous response failed ProblemSpecification validation. "
                    "Return one corrected JSON object only. Do not invent official facts. "
                    f"Validation error: {type(first_error).__name__}: {first_error}"
                ),
            },
        ]
        repaired = planner.invoke(repair_messages)
        try:
            spec = parse_problem_specification(repaired.content)
            response = repaired
        except Exception as repair_error:
            # Prefer deterministic fixture recovery when the text is 2022 C.
            if detect_2022_mcm_c(problem_text):
                recovered = build_2022_c_specification(problem_text)
                return recovered.model_copy(
                    update={
                        "fallback_reason": (
                            "LLM output remained invalid after one repair; "
                            f"used deterministic 2022 C extractor ({type(repair_error).__name__})."
                        )[:1000],
                        "analysis_notes": list(recovered.analysis_notes)
                        + ["Recovered via deterministic extractor after LLM repair failure."],
                    }
                )
            raise ValueError(
                "Problem Analyst LLM output remained invalid after one repair attempt: "
                f"{type(repair_error).__name__}: {repair_error}"
            ) from repair_error

    return spec.model_copy(
        update={
            "strategy": "agent",
            "analyst_provider": response.provider,
            "analyst_model": response.model,
            "analyst_prompt_version": PROMPT_VERSION,
            "fallback_reason": None,
        }
    )


def analyze_problem(
    problem_text: str | None,
    *,
    use_llm: bool | None = None,
    llm: BaseLLM | None = None,
    settings: Settings | None = None,
) -> ProblemSpecification:
    """Produce a validated ProblemSpecification from problem text.

    By default this is deterministic and CI-safe. Set use_llm=True or
    PROBLEM_ANALYST_USE_LLM / Settings.problem_analyst_use_llm to attempt the
    structured LLM path (still validated; one repair attempt).
    """
    text = (problem_text or "").strip()
    cfg = settings or get_settings()
    if not _llm_enabled(cfg, use_llm):
        return _analyze_deterministic(text)

    if not text:
        return _generic_unknown_spec("", reason="Empty problem statement (LLM path skipped).")

    try:
        return _analyze_with_llm(text, llm=llm, settings=cfg)
    except Exception as exc:
        # Fail closed to deterministic when possible; otherwise explicit unknown.
        if detect_2022_mcm_c(text):
            recovered = build_2022_c_specification(text)
            return recovered.model_copy(
                update={
                    "fallback_reason": (
                        f"LLM analyst failed ({type(exc).__name__}); used deterministic 2022 C extractor."
                    )[:1000],
                }
            )
        return _generic_unknown_spec(
            text,
            reason=f"LLM analyst failed ({type(exc).__name__}): {exc}",
        )
