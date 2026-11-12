"""Literature & Evidence Agent (Phase 4).

Default path is CI-safe offline retrieval over the fixture corpus. Live
retrieval is gated behind Settings.literature_live_retrieval / use_live=True
and remains a non-inventing stub (explicit unavailable note).
"""

from __future__ import annotations

import os
from typing import Any

from core.config import Settings, get_settings
from schemas.eda_plan import ProblemAwareEDAPlan
from schemas.evidence import (
    CitationFields,
    EvidenceCard,
    EvidenceGap,
    EvidenceSnippet,
    GroundingLink,
    LiteratureEvidenceReport,
    MethodNote,
    SourceMetadata,
)
from schemas.problem_specification import ProblemSpecification
from tools.literature_corpus import (
    DEFAULT_CORPUS_PATH,
    load_fixture_corpus,
    read_snippet_text,
    search_fixture_sources,
)

PROMPT_VERSION = "literature_evidence_v1"
LIVE_UNAVAILABLE_NOTE = (
    "Live literature retrieval is not configured in this Phase 4 slice. "
    "No remote sources were fetched; fixture corpus results (if any) remain authoritative. "
    "Invented citations are forbidden."
)


def _live_enabled(settings: Settings | None, use_live: bool | None) -> bool:
    if use_live is not None:
        return bool(use_live)
    if settings is not None:
        return bool(settings.literature_live_retrieval)
    env = os.getenv("LITERATURE_LIVE_RETRIEVAL", "").strip().lower()
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


def _query_from_context(
    spec: ProblemSpecification | None,
    eda_plan: ProblemAwareEDAPlan | None,
    eda_report: dict[str, Any] | None,
) -> tuple[str, list[str], list[tuple[str, str, str]]]:
    """Return (query_text, rq_ids, grounding_targets as kind/id/statement)."""
    parts: list[str] = []
    rq_ids: list[str] = []
    targets: list[tuple[str, str, str]] = []
    if spec is not None:
        parts.append(spec.title)
        parts.append(spec.problem_id)
        for item in spec.research_questions:
            rq_ids.append(item.id)
            targets.append(("research_question", item.id, item.statement))
            parts.append(item.statement)
        for item in spec.objectives:
            targets.append(("objective", item.id, item.statement))
            parts.append(item.statement)
        for item in spec.constraints:
            targets.append(("constraint", item.id, item.statement))
            parts.append(item.statement)
            parts.append(item.constraint_kind)
        for item in spec.assumptions_to_validate:
            targets.append(("assumption", item.id, item.statement))
            parts.append(item.statement)
        for item in spec.subproblems:
            targets.append(("subproblem", item.id, item.statement))
            parts.append(item.title)
            parts.extend(item.candidate_methods)
            parts.extend(item.evidence_needed)
        for dataset in spec.supplied_datasets:
            parts.append(dataset.file_name)
            parts.extend(dataset.columns)
    if eda_plan is not None:
        parts.append(eda_plan.problem_id or "")
        for index, note in enumerate(eda_plan.analysis_notes or []):
            parts.append(note)
            targets.append(("eda_plan_item", f"eda_note_{index}", note))
        for index, item in enumerate(eda_plan.suggested_relationships or []):
            summary = item.evidence_summary
            targets.append(("eda_plan_item", f"eda_rel_{index}", summary))
            parts.append(summary)
            parts.append(item.stance)
        for item in eda_plan.dataset_matches or []:
            parts.append(item.upload_file_name or "")
            parts.append(item.expected_file_name or "")
            parts.append(item.status)
        for reminder in eda_plan.constraint_reminders or []:
            parts.append(reminder.statement)
            parts.append(reminder.eda_implication)
    if isinstance(eda_report, dict) and eda_report:
        parts.append(str(eda_report.get("mode") or ""))
        for warning in _collect_eda_warnings(eda_report):
            targets.append(("eda_finding", f"eda_warn_{len(targets)}", warning))
            parts.append(warning)
    query = " ".join(part for part in parts if part)
    return query, rq_ids, targets


def _collect_eda_warnings(eda_report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for dataset in eda_report.get("datasets") or []:
        if isinstance(dataset, dict):
            for warning in dataset.get("warnings") or []:
                if isinstance(warning, str) and warning.strip():
                    warnings.append(warning.strip())
    rel = eda_report.get("relationships")
    if isinstance(rel, dict):
        for limitation in rel.get("limitations") or []:
            if isinstance(limitation, str) and limitation.strip():
                warnings.append(limitation.strip())
    return warnings[:12]


def _source_metadata(raw: dict[str, Any]) -> SourceMetadata:
    return SourceMetadata(
        source_id=raw["source_id"],
        title=raw["title"],
        authors=list(raw.get("authors") or []),
        year=raw.get("year"),
        venue=raw.get("venue"),
        source_type=raw.get("source_type") or "fixture_stub",
        original_url=raw.get("original_url"),
        local_path=raw.get("local_path") or raw.get("snippet_file"),
        publisher=raw.get("publisher"),
        license_or_rights=raw.get("license_or_rights"),
        acquisition_method=raw.get("acquisition_method") or "fixture_bundle",
        allowed_operations=list(
            raw.get("allowed_operations")
            or ["metadata_index", "summarize", "excerpt_quote"]
        ),
        review_status=raw.get("review_status") or "fixture",
        notes=raw.get("notes"),
    )


def _build_card(
    raw: dict[str, Any],
    *,
    targets: list[tuple[str, str, str]],
    rq_ids: list[str],
) -> EvidenceCard:
    source = _source_metadata(raw)
    snippet_path = raw.get("snippet_file") or raw.get("local_path")
    snippet_text = read_snippet_text(snippet_path)
    locator_status = "fixture_local" if snippet_text else "missing"
    snippets: list[EvidenceSnippet] = []
    if snippet_text:
        # Prefer body after the fixture banner line.
        body = snippet_text
        lines = snippet_text.splitlines()
        if lines and "FIXTURE" in lines[0].upper():
            body = "\n".join(lines[1:]).strip() or snippet_text
        snippets.append(
            EvidenceSnippet(
                snippet_id=f"sn_{source.source_id}"[:64],
                text=body[:2000],
                locator=str(snippet_path),
                is_verbatim_quote=True,
            )
        )
    method_notes = [
        MethodNote.model_validate(item) for item in (raw.get("method_notes") or [])
    ]
    citation_raw = raw.get("citation") or {}
    citation = CitationFields(
        citation_key=citation_raw.get("citation_key") or f"Fixture_{source.source_id}",
        citation_type=citation_raw.get("citation_type") or "fixture",
        bibtex_fields=dict(citation_raw.get("bibtex_fields") or {}),
    )
    grounding = _select_grounding(raw, targets, rq_ids)
    verification: str
    if locator_status == "fixture_local" and source.source_type == "fixture_stub":
        verification = "verified_fixture"
    elif locator_status == "missing":
        verification = "insufficient_evidence"
    else:
        verification = "unverified"
    return EvidenceCard(
        card_id=f"ec_{source.source_id}"[:64],
        source=source,
        snippets=snippets,
        method_notes=method_notes,
        citation=citation,
        grounding=grounding,
        locator_status=locator_status,  # type: ignore[arg-type]
        verification_status=verification,  # type: ignore[arg-type]
        claim_summary=str(raw.get("claim_summary") or source.title)[:2000],
        invented=False,
        tags=list(raw.get("themes") or raw.get("keywords") or [])[:24],
    )


def _select_grounding(
    raw: dict[str, Any],
    targets: list[tuple[str, str, str]],
    rq_ids: list[str],
) -> list[GroundingLink]:
    links: list[GroundingLink] = []
    hints = {str(item) for item in (raw.get("rq_hints") or [])}
    themes = " ".join(
        str(item) for item in (raw.get("themes") or []) + (raw.get("keywords") or [])
    ).lower()
    for kind, target_id, statement in targets:
        strength: str = "none"
        if target_id in hints or (kind == "research_question" and target_id in rq_ids and hints):
            strength = "strong" if target_id in hints else "moderate"
        else:
            stmt = statement.lower()
            overlap = any(
                token in stmt
                for token in (
                    "transaction",
                    "cost",
                    "gold",
                    "bitcoin",
                    "past",
                    "price",
                    "calendar",
                    "trade",
                    "portfolio",
                    "strategy",
                    "commission",
                    "sensitivity",
                )
                if token in themes or token in (raw.get("claim_summary") or "").lower()
            )
            if overlap:
                strength = "moderate"
        if strength == "none":
            continue
        links.append(
            GroundingLink(
                kind=kind,  # type: ignore[arg-type]
                target_id=target_id,
                target_statement=statement[:800],
                relevance=(
                    f"Fixture source '{raw.get('source_id')}' relates to {kind} '{target_id}'."
                ),
                strength=strength,  # type: ignore[arg-type]
            )
        )
        if len(links) >= 8:
            break
    if not links and targets:
        kind, target_id, statement = targets[0]
        links.append(
            GroundingLink(
                kind=kind,  # type: ignore[arg-type]
                target_id=target_id,
                target_statement=statement[:800],
                relevance="Weak default grounding to the primary problem target; review manually.",
                strength="weak",
            )
        )
    return links


def _build_gaps(
    targets: list[tuple[str, str, str]],
    cards: list[EvidenceCard],
) -> list[EvidenceGap]:
    covered: set[str] = set()
    for card in cards:
        for link in card.grounding:
            if link.strength in {"strong", "moderate"}:
                covered.add(link.target_id)
    gaps: list[EvidenceGap] = []
    for kind, target_id, statement in targets:
        if target_id in covered:
            continue
        # Only gap research questions / evidence-heavy subproblems by default.
        if kind not in {"research_question", "subproblem", "assumption", "method_gap"}:
            continue
        gaps.append(
            EvidenceGap(
                gap_id=f"gap_{target_id}"[:64],
                kind=kind,  # type: ignore[arg-type]
                target_id=target_id,
                statement=(
                    f"No fixture-corpus evidence with moderate+ grounding for {kind} "
                    f"'{target_id}': {statement}"
                )[:2000],
                sufficiency="insufficient",
                mitigation_hint=(
                    "Add an approved corpus entry or keep this claim marked unverified; "
                    "do not invent a citation."
                ),
            )
        )
        if len(gaps) >= 16:
            break
    if not targets:
        gaps.append(
            EvidenceGap(
                gap_id="gap_no_problem_spec",
                kind="other",
                target_id="problem_specification",
                statement=(
                    "No ProblemSpecification was supplied; evidence cannot be grounded "
                    "to official research questions."
                ),
                sufficiency="unknown",
                mitigation_hint="Run Problem Analyst before trusting literature grounding.",
            )
        )
    return gaps


def attempt_live_retrieval(*, enabled: bool) -> tuple[bool, str | None, list[EvidenceCard]]:
    """Optional live path — Phase 4 stub never invents remote sources."""
    if not enabled:
        return False, None, []
    return True, LIVE_UNAVAILABLE_NOTE, []


def gather_literature_evidence(
    *,
    problem_specification: ProblemSpecification | dict[str, Any] | None = None,
    eda_plan: ProblemAwareEDAPlan | dict[str, Any] | None = None,
    eda_report: dict[str, Any] | None = None,
    use_live: bool | None = None,
    settings: Settings | None = None,
    corpus_path: str | None = None,
    limit: int = 8,
) -> LiteratureEvidenceReport:
    """Build a typed evidence report grounded to the problem (and EDA when present)."""
    runtime = settings or get_settings()
    live = _live_enabled(runtime, use_live)
    spec = _as_problem_spec(problem_specification)
    plan = _as_eda_plan(eda_plan)
    query, rq_ids, targets = _query_from_context(spec, plan, eda_report)

    from pathlib import Path

    corpus_file = Path(corpus_path) if corpus_path else DEFAULT_CORPUS_PATH
    corpus = load_fixture_corpus(corpus_file)
    path = str(corpus_file)

    matches = search_fixture_sources(
        query_text=query,
        research_question_ids=rq_ids,
        problem_id=spec.problem_id if spec else None,
        limit=limit,
        corpus=corpus,
    )
    cards = [
        _build_card(raw, targets=targets, rq_ids=rq_ids)
        for raw in matches
        if isinstance(raw.get("source_id"), str)
    ]

    live_attempted, live_note, live_cards = attempt_live_retrieval(enabled=live)
    # Live stub returns no cards; never merge invented remote hits.
    if live_cards:
        cards.extend(live_cards)

    gaps = _build_gaps(targets, cards)
    notes = [
        f"Fixture corpus: {corpus.get('corpus_id', 'unknown')} @ {path}",
        "All cards are corpus-backed fixture stubs; not peer-reviewed publications.",
    ]
    if not spec:
        notes.append("ProblemSpecification missing — grounding is incomplete.")
    if plan is not None or eda_report:
        notes.append("EDA context was considered for grounding themes.")
    if live_attempted:
        notes.append(live_note or LIVE_UNAVAILABLE_NOTE)

    report = LiteratureEvidenceReport(
        problem_id=spec.problem_id if spec else None,
        strategy="hybrid" if live_attempted else "deterministic_fixture",
        retrieval_backend="fixture_corpus",
        live_retrieval_enabled=live,
        live_retrieval_attempted=live_attempted,
        live_retrieval_note=live_note,
        cards=cards,
        gaps=gaps,
        grounded_target_ids=sorted(
            {link.target_id for card in cards for link in card.grounding}
        ),
        eda_context_present=bool(plan is not None or eda_report),
        problem_specification_present=spec is not None,
        invented_sources=False,
        analysis_notes=notes,
        agent_prompt_version=PROMPT_VERSION,
    )
    return LiteratureEvidenceReport.model_validate(report.model_dump(mode="python"))
