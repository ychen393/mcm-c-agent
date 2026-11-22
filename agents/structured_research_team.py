"""Structured optional research collaboration: two explicit provider calls.

The Strategist proposes a typed patch to the single official ResearchProposal;
the independent Critic reviews the ACTUAL patched proposal. Neither role
persists, approves H1, executes trades, or invents numerical outcomes.
Default/offline paths never instantiate a provider.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from agents.research_evidence import build_research_evidence_packet
from agents.research_revision import _parse_json_object
from core.config import Settings
from llm.base import BaseLLM
from llm.factory import LLMFactory
from schemas.research import (
    CritiqueFinding, DebateCritique, ProvenanceRef, ResearchProposal,
)
from schemas.research_plan_v2 import StructuredResearchEdit, StructuredResearchCritique
from tools.research_persistence import as_research_proposal


_KIND = {
    "lookahead": "contradiction",
    "calendar": "weak_assumption",
    "fees": "weak_assumption",
    "data": "data_gap",
    "implementation": "validation_gap",
    "validation": "validation_gap",
    "future_work": "alternative",
}
_PRIORITY = {"blocking": "blocking", "important": "high", "future_work": "info"}


def run_structured_research_team(
    *,
    specification: dict[str, Any],
    proposal: ResearchProposal | dict[str, Any],
    eda_report: dict[str, Any] | None,
    settings: Settings,
    llm: BaseLLM | None = None,
    language: str = "zh",
) -> tuple[ResearchProposal, DebateCritique, dict[str, str]]:
    """Use two *opt-in* LLM calls, returning schema-validated artifacts.

    Caller controls user consent and persistence. The source fingerprint and
    candidate/execution statuses are authoritative, never editable by the LLM.
    """
    old = as_research_proposal(proposal)
    if old.research_decision is None:
        raise ValueError("Structured collaboration requires a V2 research plan")
    packet = build_research_evidence_packet(eda_report)
    if old.research_decision.evidence_packet_sha256 != packet["packet_sha256"]:
        raise ValueError("EDA evidence changed; rebuild the research plan first")
    provider = llm if llm is not None else LLMFactory.create(settings)
    lang = "Chinese" if language == "zh" else "English"
    shortlist = [
        old.research_decision.primary_candidate_id,
        *old.research_decision.alternate_candidate_ids,
    ]
    candidates = {
        c.candidate_id: c for c in old.candidates if c.candidate_id in shortlist
    }
    request = {
        "problem": {
            "title": specification.get("title"),
            "constraints": [
                r.get("statement") for r in (specification.get("constraints") or [])[:15]
                if isinstance(r, dict)
            ],
        },
        "evidence": packet,
        "shortlist": [
            {"candidate_id": c.candidate_id, "method_family": c.method_family,
             "summary": c.summary,
             "execution_plan": c.execution_plan.model_dump(mode="json")}
            for c in candidates.values() if c.execution_plan is not None
        ],
        "instruction": "Propose one concrete field edit, not measured experiment results.",
    }
    first = provider.invoke([
        {"role": "system", "content": (
            "You are a mathematical-modeling STRATEGIST revising an EXISTING "
            "research candidate in the official proposal. Return only one JSON "
            "object containing: candidate_id, revised_summary, "
            "revised_execution_plan (FULL object with every execution-plan field), "
            "changes_made, evidence_refs. Use only an existing short-listed ID. "
            "Retain implementation_status='needs_implementation' and "
            "executable_strategy_id=null; never invent backtests, forecasts, "
            "new citations or numeric findings. Respect market closures, "
            "fees and information/transaction timing. Cite only evidence "
            f"in the provided packet. Write human text in {lang}."
        )},
        {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
    ])
    edit = StructuredResearchEdit.model_validate(
        _parse_json_object(str(first.content))
    )
    if edit.candidate_id not in candidates:
        raise ValueError("LLM revision refers to an unknown or non-shortlisted candidate")
    previous = candidates[edit.candidate_id]
    if previous.execution_plan is None:
        raise ValueError("The selected candidate has no executable research contract")
    if (edit.revised_execution_plan.implementation_status !=
            previous.execution_plan.implementation_status
            or edit.revised_execution_plan.executable_strategy_id !=
            previous.execution_plan.executable_strategy_id):
        raise ValueError("LLM cannot claim implementation or change strategy mapping")
    allowed_refs = set(previous.execution_plan.evidence_refs)
    allowed_refs.add("eda:" + packet["packet_sha256"][:20])
    if any(ref not in allowed_refs for ref in edit.evidence_refs):
        raise ValueError("LLM provided an unverified evidence reference")
    candidate_payloads = []
    for c in old.candidates:
        payload = c.model_dump(mode="python")
        if c.candidate_id == edit.candidate_id:
            payload["summary"] = edit.revised_summary
            payload["execution_plan"] = edit.revised_execution_plan.model_dump(mode="python")
            payload["strengths"] = (
                list(c.strengths) +
                ["Structured Strategist revision; factual evidence still needs human review."]
            )[:12]
        candidate_payloads.append(payload)
    payload = old.model_dump(mode="python")
    payload["candidates"] = candidate_payloads
    digest = hashlib.sha256(json.dumps(
        {"base": old.proposal_id, "edit": edit.model_dump(mode="json")},
        sort_keys=True, ensure_ascii=False,
    ).encode("utf-8")).hexdigest()[:14]
    payload["proposal_id"] = f"prop_{digest}"
    payload["strategy"] = "hybrid"
    payload["llm_enabled"] = True
    payload["llm_attempted"] = True
    payload["llm_note"] = (
        "Structured Strategist proposal was checked against evidence and "
        "reviewed independently; not yet attached or approved."
    )
    payload["analysis_notes"] = (
        [*old.analysis_notes, "Structured revision: " + edit.changes_made[:850]]
    )[-32:]
    updated = ResearchProposal.model_validate(payload)

    second = provider.invoke([
        {"role": "system", "content": (
            "You are an INDEPENDENT skeptical research CRITIC reviewing the "
            "actual structured amended proposal, not the strategist's prose. "
            "Return only JSON with 'notes' (array of 0-12 objects: kind, "
            "priority, candidate_id, target_field, problem, suggested_fix) and "
            "verdict ('changes_needed' or 'ready_for_human_review'). "
            "Priorities: blocking for concrete causality/timing/fees/data "
            "violations or missing critical plan fields; important for "
            "reproducibility improvements; future_work for optional global "
            "optimality, RL or hypothetical extensions. Do NOT approve H1 "
            "and do not invent data, sources, or test results. "
            f"Respond in {lang}."
        )},
        {"role": "user", "content": json.dumps({
            "problem": request["problem"],
            "evidence": packet,
            "revised_candidate": next(
                x for x in updated.candidates if x.candidate_id == edit.candidate_id
            ).model_dump(mode="json"),
            "changes_made": edit.changes_made,
        }, ensure_ascii=False)},
    ])
    review = StructuredResearchCritique.model_validate(
        _parse_json_object(str(second.content))
    )
    known = {c.candidate_id for c in updated.candidates}
    findings = []
    for i, note in enumerate(review.notes, start=1):
        if note.candidate_id not in known:
            raise ValueError("Critic refers to an unknown candidate")
        if note.target_field not in {
            "summary", "objective", "input_features", "signal_definition",
            "decision_timing", "execution_rule", "transaction_costs",
            "parameters", "risk_controls", "validation_design",
            "implementation_status", "evidence_refs",
        }:
            raise ValueError("Critic refers to an unrecognized plan field")
        findings.append(CritiqueFinding(
            finding_id=f"finding_{digest}_{i}",
            kind=_KIND[note.kind],
            severity=_PRIORITY[note.priority],
            candidate_id=note.candidate_id,
            statement=note.problem,
            suggested_action=note.suggested_fix,
            target_field=note.target_field,
            review_priority=note.priority,
            evidence_refs=[ProvenanceRef(
                kind="eda_report",
                ref_id="eda_" + packet["packet_sha256"][:20],
                summary="Source-fingerprinted observed EDA summary, not a live trading signal.",
            )],
        ))
    critic = DebateCritique(
        critique_id=f"crit_{digest}",
        proposal_id=updated.proposal_id,
        strategy="llm",
        llm_enabled=True,
        llm_attempted=True,
        llm_note="Independent structured review of the exact revised proposal; H1 is human-only.",
        findings=findings,
        analysis_notes=[f"Verdict: {review.verdict}"],
    )
    audit = {
        "previous_proposal_id": old.proposal_id,
        "new_proposal_id": updated.proposal_id,
        "candidate_id": edit.candidate_id,
        "changes_made": edit.changes_made,
        "critic_verdict": review.verdict,
        "provider": str(first.provider)[:80],
        "model": str(first.model)[:100],
        "evidence_packet_sha256": packet["packet_sha256"],
    }
    return updated, critic, audit
