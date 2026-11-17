"""Human-feedback revision of a research proposal with two *real* model calls.

The first LLM changes one already-known candidate (no invented executable model);
a separate skeptical reviewer challenges that revision. Invalid JSON, unknown IDs,
API errors or unverified data claims do not silently approve H1 or overwrite state.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from core.config import Settings
from llm.base import BaseLLM
from llm.factory import LLMFactory
from schemas.research import ResearchProposal


def _parse_json_object(content: str) -> dict[str, Any]:
    value = content.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Research revision must return one JSON object")
    return parsed


def _brief_for_model(
    original: ResearchProposal, spec: dict[str, Any], eda: dict[str, Any] | None,
) -> dict[str, Any]:
    metrics = ((eda or {}).get("interpreted_findings") or {}).get("datasets") or []
    return {
        "problem_title": str(spec.get("title") or "")[:180],
        "constraints": [
            str(item.get("statement") or "")[:200]
            for item in (spec.get("constraints") or [])[:12] if isinstance(item, dict)
        ],
        "observed_eda": [{
            k: m.get(k) for k in ("name", "rows", "valid_prices",
                                  "max_drawdown_pct", "volatility_pct", "missing_by_column")
        } for m in metrics[:5] if isinstance(m, dict)],
        "candidates": [{
            "id": c.candidate_id,
            "title": c.title,
            "method_family": c.method_family,
            "summary": c.summary[:650],
        } for c in original.candidates[:10]],
        "recommended_candidate_id": original.recommended_candidate_id,
    }


def revise_with_feedback(
    *,
    proposal: ResearchProposal | dict[str, Any],
    feedback: str,
    problem_specification: dict[str, Any],
    eda_report: dict[str, Any] | None,
    settings: Settings,
    llm: BaseLLM | None = None,
    language: str = "zh",
) -> tuple[ResearchProposal, dict[str, str]]:
    """Return a distinct revised proposal and independent critique metadata.

    Called only after explicit UI confirmation of potential paid model calls.
    This function does not persist, approve, run experiments or retry requests.
    """
    prev = (
        proposal if isinstance(proposal, ResearchProposal)
        else ResearchProposal.model_validate(proposal)
    )
    feedback = feedback.strip()
    if len(feedback) < 12 or len(feedback) > 2400:
        raise ValueError("Please describe the requested change in 12–2400 characters")
    if not prev.candidates:
        raise ValueError("There is no candidate proposal to revise")
    provider = llm or LLMFactory.create(settings)
    context = _brief_for_model(prev, problem_specification, eda_report)
    context["reviewer_feedback"] = feedback
    lang = "Chinese" if language == "zh" else "English"
    response = provider.invoke([
        {"role":"system","content":(
            "You are a mathematical modeling REVISER. A human has rejected the "
            "research plan and supplied explicit feedback. Use the given uploaded "
            "EDA measurements as observations and all other candidate model claims "
            "as hypotheses. Return exactly one JSON object with these keys: "
            "candidate_id (EXISTING candidate to revise), revised_summary "
            "(concrete revised process with data, signals, fees and validation, "
            "max 2600 chars), changes_made (a short explanation of HOW the human "
            "feedback was incorporated, max 900 chars), next_tests (array of up "
            "to 4 test instructions), and remaining_risks (array of up to 4 items). "
            "Do not invent dataset numbers, paper citations, completed tests, "
            "implementation status or a new candidate ID. "
            f"All user-visible text must be {lang}. "
            "Only cite numerical values that explicitly appear in the context."
        )},
        {"role":"user","content":json.dumps(context,ensure_ascii=False)},
    ])
    patch = _parse_json_object(str(response.content))
    cid = str(patch.get("candidate_id") or "")
    matched = next((c for c in prev.candidates if c.candidate_id == cid), None)
    if matched is None:
        raise ValueError("Reviser returned an unknown candidate; saved plan is unchanged")
    summary = str(patch.get("revised_summary") or "").strip()
    explanation = str(patch.get("changes_made") or "").strip()
    if len(summary) < 60 or len(summary) > 2600:
        raise ValueError("Revised research plan is missing concrete detail or too long")
    if len(explanation) < 20 or len(explanation) > 900:
        raise ValueError("Revision must explain which feedback it followed")
    tests = patch.get("next_tests") or []
    risks = patch.get("remaining_risks") or []
    if not isinstance(tests,list) or not isinstance(risks,list):
        raise ValueError("Revision checks and risks must be lists")
    tests = [str(x).strip()[:350] for x in tests[:4] if isinstance(x,str) and x.strip()]
    risks = [str(x).strip()[:350] for x in risks[:4] if isinstance(x,str) and x.strip()]
    if not tests:
        raise ValueError("Revision requires at least one next test")

    # A separate real model call critiques the actual revision, not a generic plan.
    skeptical = provider.invoke([
        {"role":"system","content":(
            "You are an INDEPENDENT research critic. Review a human-requested "
            "revision to a gold/Bitcoin strategy. In 3–6 numbered points, inspect "
            "trade-timing and lookahead, trading fees, market closures, model/EDA "
            "fit, whether feedback was really addressed, and validation gaps. "
            "Do not approve H1. Do not fabricate measurements. "
            f"Respond in {lang}."
        )},
        {"role":"user","content":json.dumps({
            "feedback":feedback,
            "original_summary":matched.summary[:650],
            "proposed_revision":patch,
            "observed_eda":context["observed_eda"],
            "constraints":context["constraints"],
        },ensure_ascii=False)},
    ])
    criticism = str(skeptical.content).strip()[:2800]
    if len(criticism) < 20:
        raise ValueError("Independent critic returned insufficient feedback; previous plan unchanged")

    new_candidates = []
    for candidate in prev.candidates:
        data = candidate.model_dump(mode="python")
        data["status"] = "recommended" if candidate.candidate_id == cid else "proposed"
        if candidate.candidate_id == cid:
            data["summary"] = summary
            data["weaknesses"] = (data["weaknesses"] + risks)[:12]
            data["strengths"] = (
                data["strengths"] +
                ["Revised in response to explicit human reviewer feedback; validation pending."]
            )[:12]
        new_candidates.append(data)

    digest = hashlib.sha256(json.dumps({
        "old_id":prev.proposal_id,"feedback":feedback,"patch":patch,
    },sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()[:14]
    updated = prev.model_dump(mode="python")
    updated.update({
        "proposal_id":f"prop_{digest}",
        "candidates":new_candidates,
        "recommended_candidate_id":cid,
        "strategy":"hybrid",
        "llm_enabled":True,
        "llm_attempted":True,
        "llm_note":"One live LLM revised the plan; an independent live LLM review raised concerns. H1 remains pending.",
        "analysis_notes":(list(prev.analysis_notes) + [
            f"Human reviewer explicitly requested revision: {feedback[:600]}",
            f"Reviser change explanation: {explanation[:650]}",
            f"Independent critique (unverified advisory): {criticism[:800]}",
        ])[-32:],
        "open_questions":(list(prev.open_questions) + risks)[:24],
    })
    new_proposal = ResearchProposal.model_validate(updated)
    record = {
        "previous_proposal_id":prev.proposal_id,
        "new_proposal_id":new_proposal.proposal_id,
        "changed_candidate_id":cid,
        "feedback":feedback,
        "before":matched.summary[:1400],
        "after":summary,
        "changes_made":explanation,
        "critic_feedback":criticism,
        "next_tests":"\n".join(tests),
        "provider":str(response.provider),
        "model":str(response.model),
        "mode":"two_live_llm_calls",
    }
    return new_proposal, record
