"""Debate / Critic Agent (Phase 5).

Independently critiques ResearchProposal candidates for contradictions, weak
assumptions, and evidence gaps. Default path is CI-safe deterministic rules.
Optional LLM remains off by default and never invents sources.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

from core.config import Settings, get_settings
from schemas.evidence import LiteratureEvidenceReport
from schemas.problem_specification import ProblemSpecification
from schemas.research import (
    CritiqueFinding,
    DebateCritique,
    ProvenanceRef,
    ResearchProposal,
)

PROMPT_VERSION = "debate_critic_v1"
LLM_UNAVAILABLE_NOTE = (
    "Optional LLM Debate/Critic path is not configured in this Phase 5 slice. "
    "Deterministic critique findings remain authoritative. Invented sources are forbidden."
)


def _llm_enabled(settings: Settings | None, use_llm: bool | None) -> bool:
    if use_llm is not None:
        return bool(use_llm)
    if settings is not None:
        return bool(settings.research_strategy_use_llm)
    env = os.getenv("RESEARCH_STRATEGY_USE_LLM", "").strip().lower()
    return env in {"1", "true", "yes", "on"}


def _as_proposal(
    proposal: ResearchProposal | dict[str, Any] | None,
) -> ResearchProposal | None:
    if proposal is None:
        return None
    if isinstance(proposal, ResearchProposal):
        return proposal
    if isinstance(proposal, dict) and proposal:
        return ResearchProposal.model_validate(proposal)
    return None


def _as_problem_spec(
    problem_specification: ProblemSpecification | dict[str, Any] | None,
) -> ProblemSpecification | None:
    if problem_specification is None:
        return None
    if isinstance(problem_specification, ProblemSpecification):
        return problem_specification
    if isinstance(problem_specification, dict) and problem_specification:
        return ProblemSpecification.model_validate(problem_specification)
    return None


def _as_evidence(
    evidence_report: LiteratureEvidenceReport | dict[str, Any] | None,
) -> LiteratureEvidenceReport | None:
    if evidence_report is None:
        return None
    if isinstance(evidence_report, LiteratureEvidenceReport):
        return evidence_report
    if isinstance(evidence_report, dict) and evidence_report:
        try:
            return LiteratureEvidenceReport.model_validate(evidence_report)
        except Exception:
            return None
    return None


def _fid(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"cf_{digest}"[:64]


def _critique_evidence_gaps(
    proposal: ResearchProposal,
    evidence: LiteratureEvidenceReport | None,
) -> list[CritiqueFinding]:
    findings: list[CritiqueFinding] = []
    if evidence is None:
        findings.append(
            CritiqueFinding(
                finding_id=_fid("no_evidence", proposal.proposal_id),
                kind="evidence_gap",
                severity="high",
                candidate_id=proposal.recommended_candidate_id,
                statement=(
                    "No LiteratureEvidenceReport is attached. Method selection lacks "
                    "corpus-backed grounding; do not treat candidates as literature-validated."
                ),
                evidence_refs=[
                    ProvenanceRef(
                        kind="unknown",
                        ref_id="evidence_absent",
                        summary="Evidence report missing at critique time.",
                    )
                ],
                suggested_action="Gather and attach evidence cards before H1 approval.",
                invented_source=False,
            )
        )
        return findings

    for gap in evidence.gaps:
        # Prefer linking to a candidate that already references the gap.
        linked = None
        for cand in proposal.candidates:
            if gap.gap_id in cand.evidence_gap_ids:
                linked = cand.candidate_id
                break
        if gap.sufficiency == "partial":
            severity = "medium"
        elif gap.sufficiency in {"insufficient", "unknown"}:
            severity = "blocking"
        else:
            severity = "medium"
        findings.append(
            CritiqueFinding(
                finding_id=_fid("gap", gap.gap_id, proposal.proposal_id),
                kind="evidence_gap",
                severity=severity,  # type: ignore[arg-type]
                candidate_id=linked or proposal.recommended_candidate_id,
                statement=f"Evidence gap `{gap.gap_id}` ({gap.sufficiency}): {gap.statement}",
                evidence_refs=[
                    ProvenanceRef(
                        kind="evidence_gap",
                        ref_id=gap.gap_id,
                        summary=gap.statement[:400],
                    )
                ],
                suggested_action=gap.mitigation_hint
                or "Close the gap or downgrade claims that depend on missing evidence.",
                invented_source=False,
            )
        )
    return findings


def _critique_weak_assumptions(
    proposal: ResearchProposal,
    spec: ProblemSpecification | None,
) -> list[CritiqueFinding]:
    findings: list[CritiqueFinding] = []
    if spec is None:
        return findings
    for assumption in spec.assumptions_to_validate:
        covered = False
        for cand in proposal.candidates:
            for plan in cand.validation_plan:
                if assumption.id in (plan.plan_id + " " + plan.description):
                    covered = True
                    break
                refs = {ref.ref_id for ref in plan.provenance if ref.ref_id}
                if assumption.id in refs:
                    covered = True
                    break
            if covered:
                break
        severity: str = "medium" if covered else "high"
        findings.append(
            CritiqueFinding(
                finding_id=_fid("assumption", assumption.id, proposal.proposal_id),
                kind="weak_assumption",
                severity=severity,  # type: ignore[arg-type]
                candidate_id=proposal.recommended_candidate_id,
                statement=(
                    f"Assumption `{assumption.id}` must be validated: {assumption.statement}"
                    + (
                        " Validation plan references it, but results are still pending."
                        if covered
                        else " No candidate validation plan clearly covers this assumption."
                    )
                ),
                evidence_refs=[
                    ProvenanceRef(
                        kind="problem_specification",
                        ref_id=assumption.id,
                        summary=assumption.statement[:400],
                    )
                ],
                suggested_action="Require an explicit assumption-check before modeling claims.",
                invented_source=False,
            )
        )
    return findings


def _critique_contradictions(
    proposal: ResearchProposal,
    spec: ProblemSpecification | None,
) -> list[CritiqueFinding]:
    findings: list[CritiqueFinding] = []
    if spec is None:
        return findings
    constraint_blobs = [
        (c.id, c.statement, c.constraint_kind) for c in spec.constraints
    ]
    for cand in proposal.candidates:
        hay = f"{cand.title} {cand.summary} {cand.method_family}".lower()
        for cid, statement, kind in constraint_blobs:
            # Heuristic: aggressive turnover / ignore costs vs transaction_cost constraint.
            if kind == "transaction_cost" and re.search(
                r"ignore (costs|fees)|zero[- ]cost|frictionless", hay
            ):
                findings.append(
                    CritiqueFinding(
                        finding_id=_fid("contra", cand.candidate_id, cid),
                        kind="contradiction",
                        severity="blocking",
                        candidate_id=cand.candidate_id,
                        statement=(
                            f"Candidate `{cand.candidate_id}` appears to ignore trading frictions "
                            f"while constraint `{cid}` requires cost awareness: {statement}"
                        ),
                        evidence_refs=[
                            ProvenanceRef(
                                kind="problem_specification",
                                ref_id=cid,
                                summary=statement[:400],
                            )
                        ],
                        suggested_action="Revise the candidate to include explicit cost modeling.",
                        invented_source=False,
                    )
                )
            if kind == "capital" and re.search(r"unlimited capital|no budget", hay):
                findings.append(
                    CritiqueFinding(
                        finding_id=_fid("contra_cap", cand.candidate_id, cid),
                        kind="contradiction",
                        severity="blocking",
                        candidate_id=cand.candidate_id,
                        statement=(
                            f"Candidate `{cand.candidate_id}` conflicts with capital constraint "
                            f"`{cid}`: {statement}"
                        ),
                        evidence_refs=[
                            ProvenanceRef(
                                kind="problem_specification",
                                ref_id=cid,
                                summary=statement[:400],
                            )
                        ],
                        suggested_action="Bound the strategy to the stated capital constraint.",
                        invented_source=False,
                    )
                )
            # Soft contradiction: candidate claims completeness while open data needs remain.
            unsatisfied = [n for n in cand.data_needs if n.satisfied is False]
            if unsatisfied and re.search(r"complete|sufficient evidence|fully grounded", hay):
                findings.append(
                    CritiqueFinding(
                        finding_id=_fid("contra_data", cand.candidate_id, unsatisfied[0].need_id),
                        kind="contradiction",
                        severity="high",
                        candidate_id=cand.candidate_id,
                        statement=(
                            f"Candidate `{cand.candidate_id}` claims strong readiness while "
                            f"{len(unsatisfied)} data/evidence need(s) remain unsatisfied."
                        ),
                        evidence_refs=[
                            ProvenanceRef(
                                kind="rule_based",
                                ref_id=unsatisfied[0].need_id,
                                summary=unsatisfied[0].description[:400],
                            )
                        ],
                        suggested_action="Downgrade certainty language until needs are closed.",
                        invented_source=False,
                    )
                )
    return findings


def _critique_validation_gaps(proposal: ResearchProposal) -> list[CritiqueFinding]:
    findings: list[CritiqueFinding] = []
    for cand in proposal.candidates:
        if not cand.validation_plan:
            findings.append(
                CritiqueFinding(
                    finding_id=_fid("valgap", cand.candidate_id),
                    kind="validation_gap",
                    severity="blocking",
                    candidate_id=cand.candidate_id,
                    statement=(
                        f"Candidate `{cand.candidate_id}` has an empty validation plan. "
                        "H1 should not approve modeling without a check plan."
                    ),
                    evidence_refs=[
                        ProvenanceRef(
                            kind="rule_based",
                            ref_id=cand.candidate_id,
                            summary="Missing validation_plan on candidate.",
                        )
                    ],
                    suggested_action="Add holdout / sensitivity / assumption checks before approval.",
                    invented_source=False,
                )
            )
        if not cand.hypotheses:
            findings.append(
                CritiqueFinding(
                    finding_id=_fid("hypgap", cand.candidate_id),
                    kind="other",
                    severity="low",
                    candidate_id=cand.candidate_id,
                    statement=f"Candidate `{cand.candidate_id}` lists no explicit hypotheses.",
                    evidence_refs=[
                        ProvenanceRef(
                            kind="rule_based",
                            ref_id=cand.candidate_id,
                            summary="Missing hypotheses list.",
                        )
                    ],
                    suggested_action="State at least one testable hypothesis for the route.",
                    invented_source=False,
                )
            )
        # Alternative note when a non-recommended candidate has more evidence cards.
        if (
            proposal.recommended_candidate_id
            and cand.candidate_id != proposal.recommended_candidate_id
        ):
            recommended = next(
                (c for c in proposal.candidates if c.candidate_id == proposal.recommended_candidate_id),
                None,
            )
            if recommended and len(cand.evidence_card_ids) > len(recommended.evidence_card_ids):
                findings.append(
                    CritiqueFinding(
                        finding_id=_fid("alt", cand.candidate_id, recommended.candidate_id),
                        kind="alternative",
                        severity="info",
                        candidate_id=cand.candidate_id,
                        statement=(
                            f"Alternative `{cand.candidate_id}` matches more evidence cards "
                            f"({len(cand.evidence_card_ids)}) than recommended "
                            f"`{recommended.candidate_id}` ({len(recommended.evidence_card_ids)})."
                        ),
                        evidence_refs=[
                            ProvenanceRef(
                                kind="evidence_report",
                                ref_id=cand.evidence_card_ids[0]
                                if cand.evidence_card_ids
                                else cand.candidate_id,
                                summary="Relative evidence-card coverage comparison.",
                            )
                        ],
                        suggested_action="Human H1 reviewer should compare both candidates explicitly.",
                        invented_source=False,
                    )
                )
    return findings


def critique_research_proposal(
    *,
    proposal: ResearchProposal | dict[str, Any],
    problem_specification: ProblemSpecification | dict[str, Any] | None = None,
    evidence_report: LiteratureEvidenceReport | dict[str, Any] | None = None,
    use_llm: bool | None = None,
    settings: Settings | None = None,
) -> DebateCritique:
    """Critique candidates without inventing sources. Deterministic by default."""
    settings = settings or get_settings()
    model = _as_proposal(proposal)
    if model is None:
        raise ValueError("critique_research_proposal requires a ResearchProposal")
    spec = _as_problem_spec(problem_specification)
    evidence = _as_evidence(evidence_report)
    llm_on = _llm_enabled(settings, use_llm)

    findings: list[CritiqueFinding] = []
    findings.extend(_critique_evidence_gaps(model, evidence))
    findings.extend(_critique_weak_assumptions(model, spec))
    findings.extend(_critique_contradictions(model, spec))
    findings.extend(_critique_validation_gaps(model))

    # Deduplicate by finding_id
    seen: set[str] = set()
    unique: list[CritiqueFinding] = []
    for finding in findings:
        if finding.finding_id in seen:
            continue
        seen.add(finding.finding_id)
        unique.append(finding)
    unique = unique[:64]

    notes = [
        "Phase 5 Debate/Critic used deterministic rules (CI-safe default).",
        "Findings cite ProblemSpecification / Evidence artifacts only — no invented sources.",
        "H1 remains a human gate; critique does not approve or reject the plan.",
    ]
    llm_attempted = False
    llm_note = None
    if llm_on:
        llm_attempted = True
        llm_note = LLM_UNAVAILABLE_NOTE
        notes.append(LLM_UNAVAILABLE_NOTE)

    critique_id = _fid("critique", model.proposal_id, str(len(unique)))
    # _fid returns cf_...; make a dedicated critique id.
    digest = hashlib.sha256(f"{model.proposal_id}|{len(unique)}".encode("utf-8")).hexdigest()[:10]
    critique_id = f"crit_{digest}"

    return DebateCritique(
        critique_id=critique_id,
        proposal_id=model.proposal_id,
        strategy="deterministic_rules" if not llm_on else "hybrid",
        llm_enabled=llm_on,
        llm_attempted=llm_attempted,
        llm_note=llm_note,
        findings=unique,
        invented_sources=False,
        agent_prompt_version=PROMPT_VERSION,
        analysis_notes=notes,
    )
