"""Research Strategy Agent (Phase 5).

Default path is CI-safe deterministic rule synthesis over ProblemSpecification,
optional EDA context, and optional LiteratureEvidenceReport. Optional LLM path
is gated behind Settings.research_strategy_use_llm / use_llm=True and remains a
non-inventing stub (explicit unavailable note).
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

from core.config import Settings, get_settings
from schemas.eda_plan import ProblemAwareEDAPlan
from schemas.evidence import LiteratureEvidenceReport
from schemas.problem_specification import ProblemSpecification
from schemas.research import (
    CandidateMethod,
    DataNeed,
    HypothesisItem,
    ProvenanceRef,
    ResearchProposal,
    ValidationPlanItem,
)

PROMPT_VERSION = "research_strategy_v1"
LLM_UNAVAILABLE_NOTE = (
    "Optional LLM research-strategy synthesis is not configured in this Phase 5 slice. "
    "Deterministic rule-based candidates remain authoritative. Invented sources are forbidden."
)

METHOD_FAMILY_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"portfolio|markowitz|allocation|weight", re.I), "portfolio_optimization"),
    (re.compile(r"momentum|trend|moving.?average|signal", re.I), "trend_following"),
    (re.compile(r"mean.?reversion|pair|cointegrat", re.I), "mean_reversion"),
    (re.compile(r"transaction.?cost|rebalanc|turnover", re.I), "cost_aware_trading"),
    (re.compile(r"forecast|predict|regress|time.?series", re.I), "forecasting"),
    (re.compile(r"risk|var|drawdown|volatil", re.I), "risk_management"),
    (re.compile(r"backtest|simulation|monte.?carlo", re.I), "simulation_backtest"),
]


def _llm_enabled(settings: Settings | None, use_llm: bool | None) -> bool:
    if use_llm is not None:
        return bool(use_llm)
    if settings is not None:
        return bool(settings.research_strategy_use_llm)
    env = os.getenv("RESEARCH_STRATEGY_USE_LLM", "").strip().lower()
    return env in {"1", "true", "yes", "on"}


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


def _as_eda_plan(
    eda_plan: ProblemAwareEDAPlan | dict[str, Any] | None,
) -> ProblemAwareEDAPlan | None:
    if eda_plan is None:
        return None
    if isinstance(eda_plan, ProblemAwareEDAPlan):
        return eda_plan
    if isinstance(eda_plan, dict) and eda_plan:
        try:
            return ProblemAwareEDAPlan.model_validate(eda_plan)
        except Exception:
            return None
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


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    raw = f"{prefix}_{digest}"
    return raw[:64]


def _infer_method_family(text: str) -> str:
    for pattern, family in METHOD_FAMILY_RULES:
        if pattern.search(text):
            return family
    return "general_quantitative"


def _evidence_links_for_text(
    evidence: LiteratureEvidenceReport | None,
    text: str,
) -> tuple[list[str], list[str]]:
    """Return (card_ids, gap_ids) whose content overlaps keywords from text."""
    if evidence is None:
        return [], []
    tokens = {t for t in re.findall(r"[a-zA-Z]{4,}", text.lower())}
    card_ids: list[str] = []
    for card in evidence.cards:
        hay = " ".join(
            [
                card.claim_summary,
                " ".join(card.tags),
                " ".join(n.method_name for n in card.method_notes),
                " ".join(n.summary for n in card.method_notes),
            ]
        ).lower()
        if tokens & set(re.findall(r"[a-zA-Z]{4,}", hay)):
            card_ids.append(card.card_id)
    gap_ids: list[str] = []
    for gap in evidence.gaps:
        hay = f"{gap.statement} {gap.target_id}".lower()
        if tokens & set(re.findall(r"[a-zA-Z]{4,}", hay)):
            gap_ids.append(gap.gap_id)
    return card_ids[:16], gap_ids[:16]


def _hypothesis_from_question(
    question_id: str,
    statement: str,
    *,
    subproblem_id: str | None = None,
) -> HypothesisItem:
    return HypothesisItem(
        hypothesis_id=_stable_id("hyp", question_id, statement[:80]),
        statement=f"A tractable method can address: {statement[:900]}",
        related_question_ids=[question_id],
        related_subproblem_ids=[subproblem_id] if subproblem_id else [],
        provenance=[
            ProvenanceRef(
                kind="problem_specification",
                ref_id=question_id,
                summary=statement[:400],
            )
        ],
        confidence="medium",
    )


def _data_needs_from_context(
    spec: ProblemSpecification | None,
    evidence: LiteratureEvidenceReport | None,
    subproblem_id: str | None,
) -> list[DataNeed]:
    needs: list[DataNeed] = []
    if spec is not None:
        for dataset in spec.supplied_datasets:
            needs.append(
                DataNeed(
                    need_id=_stable_id("dn", dataset.id, dataset.file_name),
                    description=(
                        f"Use supplied dataset '{dataset.file_name}' "
                        f"({', '.join(dataset.columns[:6]) or 'columns TBD'})."
                    ),
                    required=True,
                    satisfied=True,
                    provenance=[
                        ProvenanceRef(
                            kind="problem_specification",
                            ref_id=dataset.id,
                            summary=dataset.statement[:400],
                        )
                    ],
                )
            )
        if subproblem_id:
            for sub in spec.subproblems:
                if sub.id != subproblem_id:
                    continue
                for index, item in enumerate(sub.evidence_needed):
                    needs.append(
                        DataNeed(
                            need_id=_stable_id("dn", sub.id, f"ev{index}", item[:40]),
                            description=item,
                            required=True,
                            satisfied=None,
                            provenance=[
                                ProvenanceRef(
                                    kind="problem_specification",
                                    ref_id=sub.id,
                                    summary=f"Subproblem evidence need: {item[:200]}",
                                )
                            ],
                        )
                    )
    if evidence is not None:
        for gap in evidence.gaps[:8]:
            needs.append(
                DataNeed(
                    need_id=_stable_id("dn", "gap", gap.gap_id),
                    description=f"Close evidence gap: {gap.statement[:400]}",
                    required=gap.sufficiency in {"insufficient", "unknown"},
                    satisfied=False,
                    provenance=[
                        ProvenanceRef(
                            kind="evidence_gap",
                            ref_id=gap.gap_id,
                            summary=gap.statement[:400],
                        )
                    ],
                )
            )
    # Deduplicate by need_id while preserving order.
    seen: set[str] = set()
    unique: list[DataNeed] = []
    for need in needs:
        if need.need_id in seen:
            continue
        seen.add(need.need_id)
        unique.append(need)
    return unique[:24]


def _validation_plan_from_context(
    spec: ProblemSpecification | None,
    subproblem_id: str | None,
) -> list[ValidationPlanItem]:
    plans: list[ValidationPlanItem] = []
    if spec is None:
        plans.append(
            ValidationPlanItem(
                plan_id="vp_holdout_default",
                description=(
                    "Hold out a recent period for out-of-sample checks before trusting "
                    "any trading or forecasting claim."
                ),
                method="holdout",
                success_criteria="Out-of-sample metrics remain directionally consistent.",
                provenance=[
                    ProvenanceRef(
                        kind="rule_based",
                        ref_id="default_holdout",
                        summary="Default validation plan when ProblemSpecification is absent.",
                    )
                ],
            )
        )
        return plans

    for assumption in spec.assumptions_to_validate[:6]:
        plans.append(
            ValidationPlanItem(
                plan_id=_stable_id("vp", assumption.id),
                description=f"Validate assumption: {assumption.statement}",
                method="assumption_check",
                success_criteria="Assumption is supported, revised, or explicitly rejected.",
                provenance=[
                    ProvenanceRef(
                        kind="problem_specification",
                        ref_id=assumption.id,
                        summary=assumption.statement[:400],
                    )
                ],
            )
        )

    if subproblem_id:
        for sub in spec.subproblems:
            if sub.id != subproblem_id:
                continue
            for index, criterion in enumerate(sub.acceptance_criteria[:4]):
                plans.append(
                    ValidationPlanItem(
                        plan_id=_stable_id("vp", sub.id, f"ac{index}"),
                        description=criterion,
                        method="other",
                        success_criteria=criterion[:400],
                        provenance=[
                            ProvenanceRef(
                                kind="problem_specification",
                                ref_id=sub.id,
                                summary=f"Acceptance criterion: {criterion[:200]}",
                            )
                        ],
                    )
                )

    # Always include a sensitivity / backtest style check for trading-like problems.
    plans.append(
        ValidationPlanItem(
            plan_id="vp_sensitivity_costs",
            description=(
                "Run sensitivity on transaction costs / rebalancing thresholds before "
                "claiming strategy superiority."
            ),
            method="sensitivity",
            success_criteria="Rankings remain stable under plausible cost shocks.",
            provenance=[
                ProvenanceRef(
                    kind="rule_based",
                    ref_id="cost_sensitivity",
                    summary="Default cost-sensitivity check for MCM C style problems.",
                )
            ],
        )
    )
    # Deduplicate
    seen: set[str] = set()
    unique: list[ValidationPlanItem] = []
    for plan in plans:
        if plan.plan_id in seen:
            continue
        seen.add(plan.plan_id)
        unique.append(plan)
    return unique[:16]


def _candidate_from_method_text(
    *,
    method_text: str,
    index: int,
    spec: ProblemSpecification | None,
    evidence: LiteratureEvidenceReport | None,
    subproblem_id: str | None,
    subproblem_title: str | None,
    question_ids: list[str],
) -> CandidateMethod:
    family = _infer_method_family(method_text)
    candidate_id = _stable_id("cand", family, method_text[:80], str(index), subproblem_id or "none")
    title = method_text.strip()[:200] or f"Candidate method {index + 1}"
    summary_parts = [
        f"Candidate route using {family.replace('_', ' ')}.",
        f"Method seed: {method_text.strip()[:500]}",
    ]
    if subproblem_title:
        summary_parts.append(f"Primary subproblem: {subproblem_title}")
    card_ids, gap_ids = _evidence_links_for_text(evidence, method_text + " " + (subproblem_title or ""))
    hypotheses: list[HypothesisItem] = []
    if question_ids and spec is not None:
        by_id = {q.id: q for q in spec.research_questions}
        for qid in question_ids[:3]:
            q = by_id.get(qid)
            if q is not None:
                hypotheses.append(
                    _hypothesis_from_question(q.id, q.statement, subproblem_id=subproblem_id)
                )
    if not hypotheses and spec is not None and spec.research_questions:
        q = spec.research_questions[0]
        hypotheses.append(_hypothesis_from_question(q.id, q.statement, subproblem_id=subproblem_id))

    strengths = [
        f"Grounded in ProblemSpecification method seed '{method_text[:120]}'.",
    ]
    weaknesses = []
    if gap_ids:
        weaknesses.append(f"Linked evidence gaps remain open: {', '.join(gap_ids[:4])}.")
    else:
        weaknesses.append("Evidence coverage may be incomplete; Debate/Critic must review gaps.")
    if not card_ids:
        weaknesses.append("No overlapping evidence cards were matched for this method seed.")

    provenance = [
        ProvenanceRef(
            kind="rule_based",
            ref_id=candidate_id,
            summary="Deterministic Research Strategy synthesis (Phase 5).",
        )
    ]
    if subproblem_id:
        provenance.append(
            ProvenanceRef(
                kind="problem_specification",
                ref_id=subproblem_id,
                summary=subproblem_title or subproblem_id,
            )
        )
    if card_ids:
        provenance.append(
            ProvenanceRef(
                kind="evidence_report",
                ref_id=card_ids[0],
                summary=f"Matched {len(card_ids)} evidence card(s).",
            )
        )

    return CandidateMethod(
        candidate_id=candidate_id,
        title=title if len(title) >= 3 else f"Method candidate {index + 1}",
        summary=" ".join(summary_parts)[:4000],
        method_family=family,
        hypotheses=hypotheses[:16],
        data_needs=_data_needs_from_context(spec, evidence, subproblem_id),
        validation_plan=_validation_plan_from_context(spec, subproblem_id),
        strengths=strengths[:12],
        weaknesses=weaknesses[:12],
        evidence_card_ids=card_ids,
        evidence_gap_ids=gap_ids,
        subproblem_ids=[subproblem_id] if subproblem_id else [],
        status="proposed",
        provenance=provenance,
        invented_sources=False,
    )


def _build_candidates(
    spec: ProblemSpecification | None,
    evidence: LiteratureEvidenceReport | None,
) -> list[CandidateMethod]:
    candidates: list[CandidateMethod] = []
    question_ids = [q.id for q in spec.research_questions] if spec else []

    if spec is not None:
        for sub in spec.subproblems:
            seeds = list(sub.candidate_methods) or [
                f"Structured quantitative approach for {sub.title}"
            ]
            for index, seed in enumerate(seeds[:3]):
                candidates.append(
                    _candidate_from_method_text(
                        method_text=seed,
                        index=index,
                        spec=spec,
                        evidence=evidence,
                        subproblem_id=sub.id,
                        subproblem_title=sub.title,
                        question_ids=question_ids,
                    )
                )
        # If no subproblems, seed from research questions / objectives.
        if not candidates:
            seeds: list[str] = []
            for obj in spec.objectives[:3]:
                seeds.append(obj.statement)
            for q in spec.research_questions[:3]:
                seeds.append(q.statement)
            if not seeds:
                seeds = ["Baseline quantitative research plan"]
            for index, seed in enumerate(seeds[:4]):
                candidates.append(
                    _candidate_from_method_text(
                        method_text=seed,
                        index=index,
                        spec=spec,
                        evidence=evidence,
                        subproblem_id=None,
                        subproblem_title=None,
                        question_ids=question_ids,
                    )
                )
    else:
        candidates.append(
            _candidate_from_method_text(
                method_text="Baseline exploratory quantitative plan (ProblemSpecification missing)",
                index=0,
                spec=None,
                evidence=evidence,
                subproblem_id=None,
                subproblem_title=None,
                question_ids=[],
            )
        )

    # Deduplicate by candidate_id
    seen: set[str] = set()
    unique: list[CandidateMethod] = []
    for cand in candidates:
        if cand.candidate_id in seen:
            continue
        seen.add(cand.candidate_id)
        unique.append(cand)
    return unique[:12]


def _recommend(candidates: list[CandidateMethod]) -> str | None:
    if not candidates:
        return None
    scored: list[tuple[int, CandidateMethod]] = []
    for cand in candidates:
        score = len(cand.evidence_card_ids) * 3 - len(cand.evidence_gap_ids)
        score += sum(1 for n in cand.data_needs if n.satisfied is True)
        scored.append((score, cand))
    scored.sort(key=lambda item: (-item[0], item[1].candidate_id))
    best = scored[0][1]
    # Mark recommended status on a copy handled by caller.
    return best.candidate_id


def synthesize_research_proposal(
    *,
    problem_specification: ProblemSpecification | dict[str, Any] | None = None,
    eda_plan: ProblemAwareEDAPlan | dict[str, Any] | None = None,
    eda_report: dict[str, Any] | None = None,
    evidence_report: LiteratureEvidenceReport | dict[str, Any] | None = None,
    use_llm: bool | None = None,
    settings: Settings | None = None,
) -> ResearchProposal:
    """Synthesize candidate methods for H1. Deterministic by default."""
    settings = settings or get_settings()
    spec = _as_problem_spec(problem_specification)
    plan = _as_eda_plan(eda_plan)
    evidence = _as_evidence(evidence_report)
    llm_on = _llm_enabled(settings, use_llm)

    candidates = _build_candidates(spec, evidence)
    recommended_id = _recommend(candidates)
    marked: list[CandidateMethod] = []
    for cand in candidates:
        payload = cand.model_dump(mode="python")
        if recommended_id and cand.candidate_id == recommended_id:
            payload["status"] = "recommended"
        marked.append(CandidateMethod.model_validate(payload))

    notes: list[str] = [
        "Phase 5 Research Strategy used deterministic rules (CI-safe default).",
        "Candidates are proposals only — H1 requires explicit human Approve / Request-revision.",
    ]
    open_questions: list[str] = []
    if spec is None:
        notes.append("ProblemSpecification absent; only a baseline candidate was emitted.")
        open_questions.append("Provide or attach a ProblemSpecification before H1 approval.")
    if evidence is None:
        notes.append("Evidence report absent; candidates lack literature grounding.")
        open_questions.append("Attach Literature & Evidence cards to strengthen method selection.")
    else:
        if evidence.gaps:
            open_questions.append(
                f"{len(evidence.gaps)} evidence gap(s) remain — Debate/Critic should surface them."
            )
    if plan is not None or (isinstance(eda_report, dict) and eda_report):
        notes.append("EDA context was present and recorded as provenance context.")
    else:
        notes.append("EDA context absent; data-readiness claims remain provisional.")

    consensus: list[str] = []
    if recommended_id:
        consensus.append(f"Rule-based recommendation: {recommended_id} (highest evidence/data score).")
    consensus.append("Modeling & Experiment remain blocked until human H1 approval.")

    llm_attempted = False
    llm_note = None
    if llm_on:
        llm_attempted = True
        llm_note = LLM_UNAVAILABLE_NOTE
        notes.append(LLM_UNAVAILABLE_NOTE)

    proposal_id = _stable_id(
        "prop",
        spec.problem_id if spec else "unknown",
        recommended_id or "none",
        str(len(marked)),
    )

    return ResearchProposal(
        proposal_id=proposal_id,
        problem_id=spec.problem_id if spec else None,
        strategy="deterministic_rules" if not llm_on else "hybrid",
        llm_enabled=llm_on,
        llm_attempted=llm_attempted,
        llm_note=llm_note,
        candidates=marked,
        recommended_candidate_id=recommended_id,
        consensus_notes=consensus,
        open_questions=open_questions,
        problem_specification_present=spec is not None,
        eda_context_present=bool(plan is not None or (isinstance(eda_report, dict) and eda_report)),
        evidence_present=evidence is not None,
        invented_sources=False,
        agent_prompt_version=PROMPT_VERSION,
        analysis_notes=notes,
    )


def research_strategy_status() -> dict[str, Any]:
    """Advertise Phase 5 Research Strategy / H1 availability (human gate only)."""
    return {
        "implemented": True,
        "phase": 5,
        "message": (
            "Research Strategy synthesizes candidate methods (deterministic default). "
            "Debate/Critic critiques them. H1 requires explicit human Approve / "
            "Request-revision — never auto-approved. Modeling stays blocked until H1 approved."
        ),
        "h1_available": True,
        "h1_auto_approve": False,
        "modeling_requires_h1": True,
        "llm_default": False,
    }
