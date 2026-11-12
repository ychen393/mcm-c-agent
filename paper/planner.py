"""CI-safe deterministic Paper Planner for 2022 MCM C (Phase 8).

Builds a typed outline / section map and bibliography contracts grounded only
in prior artifacts (ProblemSpecification, evidence, experiments, validation).
Never invents citations. Optional LLM outline remains a non-executing stub.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from schemas.paper import (
    ArtifactRef,
    BibEntry,
    PaperOutline,
    PaperSection,
)
from schemas.problem_specification import ProblemSpecification

PROMPT_VERSION = "paper_planner_v1"
LLM_UNAVAILABLE_NOTE = (
    "Optional LLM paper outline is not enabled for live calls in this Phase 8 "
    "slice. The deterministic fixture outline remains authoritative."
)

_DEFAULT_TITLE = (
    "Trading Strategies for Gold and Bitcoin under Proportional Transaction Costs"
)

# Canonical MCM C section map (fixture outline).
_SECTION_SPECS: tuple[dict[str, Any], ...] = (
    {
        "section_id": "sec_abstract",
        "kind": "abstract",
        "title": "Abstract",
        "summary": (
            "Summarize the trading problem, cost-aware strategy, deterministic "
            "backtest results, and sensitivity findings for gold and bitcoin."
        ),
        "order": 0,
        "required": True,
        "topic_ids": ["trading_strategy", "transaction_costs"],
    },
    {
        "section_id": "sec_introduction",
        "kind": "introduction",
        "title": "Introduction",
        "summary": (
            "Motivate portfolio trading with proportional transaction costs and "
            "state the research questions from the problem specification."
        ),
        "order": 1,
        "required": True,
        "topic_ids": ["problem_framing", "research_questions"],
    },
    {
        "section_id": "sec_problem",
        "kind": "problem",
        "title": "Problem Restatement",
        "summary": (
            "Restate MCM 2022 Problem C objectives, constraints (past prices "
            "only), assets, and evaluation criteria without inventing data."
        ),
        "order": 2,
        "required": True,
        "topic_ids": ["problem_framing", "constraints"],
    },
    {
        "section_id": "sec_data",
        "kind": "data",
        "title": "Data and Assumptions",
        "summary": (
            "Describe uploaded LBMA gold / bitcoin price series provenance, "
            "calendar alignment, and modeling assumptions from EDA / research."
        ),
        "order": 3,
        "required": True,
        "topic_ids": ["data", "assumptions"],
    },
    {
        "section_id": "sec_methods",
        "kind": "methods",
        "title": "Methodology",
        "summary": (
            "Present the selected H1 candidate method, cost-aware rebalancing "
            "rules, and experiment parameters used in Phase 6."
        ),
        "order": 4,
        "required": True,
        "topic_ids": ["methods", "transaction_costs", "portfolio_allocation"],
    },
    {
        "section_id": "sec_results",
        "kind": "results",
        "title": "Results",
        "summary": (
            "Report baseline experiment metrics (terminal value, return, "
            "drawdown, costs, trade count) linked to the Phase 6 run."
        ),
        "order": 5,
        "required": True,
        "topic_ids": ["results", "backtest"],
    },
    {
        "section_id": "sec_validation",
        "kind": "validation",
        "title": "Validation and Sensitivity",
        "summary": (
            "Summarize Phase 7 sensitivity scenarios (α, lookback, rebalance) "
            "and robustness notes supporting H2."
        ),
        "order": 6,
        "required": True,
        "topic_ids": ["validation", "sensitivity", "robustness"],
    },
    {
        "section_id": "sec_conclusion",
        "kind": "conclusion",
        "title": "Conclusion",
        "summary": (
            "Conclude with strategy recommendations, limitations, and open "
            "risks; do not claim live trading performance."
        ),
        "order": 7,
        "required": True,
        "topic_ids": ["conclusion", "limitations"],
    },
    {
        "section_id": "sec_references",
        "kind": "references",
        "title": "References",
        "summary": (
            "List bibliography entries grounded only in attached evidence / "
            "fixture corpus citations — never invented sources."
        ),
        "order": 8,
        "required": True,
        "topic_ids": ["citations"],
    },
)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"[:64]


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def _problem_id(spec: Any, state: dict[str, Any] | None) -> str | None:
    if isinstance(spec, ProblemSpecification):
        return spec.problem_id
    if isinstance(spec, dict) and spec.get("problem_id"):
        return str(spec["problem_id"])
    if state:
        raw = state.get("problem_specification") or {}
        if isinstance(raw, dict) and raw.get("problem_id"):
            return str(raw["problem_id"])
    return None


def _topic_ids_from_spec(spec: Any) -> list[str]:
    payload = _as_dict(spec)
    topics: list[str] = []
    for rq in payload.get("research_questions") or []:
        if isinstance(rq, dict) and rq.get("question_id"):
            topics.append(str(rq["question_id"]))
        elif isinstance(rq, str) and rq.strip():
            topics.append(rq.strip()[:64])
    for obj in payload.get("objectives") or []:
        if isinstance(obj, dict) and obj.get("objective_id"):
            topics.append(str(obj["objective_id"]))
    # Stable thematic topics for 2022 C fixture coverage checks.
    for theme in (
        "trading_strategy",
        "transaction_costs",
        "portfolio_allocation",
        "validation",
        "sensitivity",
    ):
        if theme not in topics:
            topics.append(theme)
    # Deduplicate preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for item in topics:
        key = item[:64]
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out[:64]


def _collect_bib_entries(
    state: dict[str, Any] | None,
) -> tuple[list[BibEntry], list[str]]:
    """Ground bib entries from evidence cards / citations only. No invention."""
    entries: list[BibEntry] = []
    seen_keys: set[str] = set()
    gaps: list[str] = []

    def _add_from_card(card: dict[str, Any]) -> None:
        citation = card.get("citation") or {}
        source = card.get("source") or {}
        if not isinstance(citation, dict):
            return
        key = citation.get("citation_key")
        if not key or str(key) in seen_keys:
            return
        title = source.get("title") if isinstance(source, dict) else None
        if not title:
            title = citation.get("bibtex_fields", {}).get("title") if isinstance(
                citation.get("bibtex_fields"), dict
            ) else None
        if not title:
            gaps.append(str(key))
            return
        authors = []
        if isinstance(source, dict):
            authors = [str(a) for a in (source.get("authors") or []) if a][:32]
        fields = citation.get("bibtex_fields") or {}
        if not isinstance(fields, dict):
            fields = {}
        entry = BibEntry(
            citation_key=str(key),
            entry_type=str(citation.get("citation_type") or "fixture"),  # type: ignore[arg-type]
            source_id=str(source.get("source_id")) if isinstance(source, dict) and source.get("source_id") else None,
            title=str(title)[:400],
            authors=authors,
            year=source.get("year") if isinstance(source, dict) else None,
            venue=source.get("venue") if isinstance(source, dict) else None,
            bibtex_fields={str(k): str(v) for k, v in fields.items() if k and v},
            invented=False,
            grounded=True,
        )
        entries.append(entry)
        seen_keys.add(str(key))

    if not state:
        return entries, gaps

    evidence = state.get("evidence_report") or {}
    if isinstance(evidence, dict):
        for card in evidence.get("cards") or []:
            if isinstance(card, dict) and not card.get("invented"):
                _add_from_card(card)

    for item in state.get("citations") or []:
        if not isinstance(item, dict):
            continue
        # Compact citation rows may already look like BibEntry / CitationFields.
        key = item.get("citation_key")
        if not key or str(key) in seen_keys:
            continue
        if item.get("invented"):
            continue
        title = item.get("title")
        if not title:
            gaps.append(str(key))
            continue
        entries.append(
            BibEntry(
                citation_key=str(key),
                entry_type=str(item.get("entry_type") or item.get("citation_type") or "fixture"),  # type: ignore[arg-type]
                source_id=str(item["source_id"]) if item.get("source_id") else None,
                title=str(title)[:400],
                authors=[str(a) for a in (item.get("authors") or []) if a][:32],
                year=item.get("year"),
                venue=item.get("venue"),
                bibtex_fields={
                    str(k): str(v)
                    for k, v in (item.get("bibtex_fields") or {}).items()
                    if k and v
                }
                if isinstance(item.get("bibtex_fields"), dict)
                else {},
                invented=False,
                grounded=True,
            )
        )
        seen_keys.add(str(key))

    return entries, gaps


def _artifact_refs_for_section(
    kind: str,
    *,
    problem_id: str | None,
    proposal_id: str | None,
    experiment_id: str | None,
    validation_id: str | None,
    baseline_run_id: str | None,
) -> list[ArtifactRef]:
    refs: list[ArtifactRef] = []
    if kind in {"introduction", "problem", "abstract"} and problem_id:
        refs.append(
            ArtifactRef(
                kind="problem_specification",
                ref_id=problem_id,
                label="ProblemSpecification",
            )
        )
    if kind in {"methods", "introduction"} and proposal_id:
        refs.append(
            ArtifactRef(
                kind="research_proposal",
                ref_id=proposal_id,
                label="ResearchProposal",
            )
        )
    if kind in {"results", "methods"} and (experiment_id or baseline_run_id):
        refs.append(
            ArtifactRef(
                kind="experiment",
                ref_id=str(experiment_id or baseline_run_id),
                label="ExperimentReport",
            )
        )
    if kind == "validation" and validation_id:
        refs.append(
            ArtifactRef(
                kind="validation_report",
                ref_id=validation_id,
                label="ValidationReport",
            )
        )
    if kind == "references":
        refs.append(
            ArtifactRef(
                kind="evidence_report",
                ref_id="evidence_report",
                label="LiteratureEvidenceReport",
            )
        )
    return refs[:24]


def _assign_citations(
    sections: list[PaperSection],
    bib_keys: list[str],
) -> list[PaperSection]:
    """Attach available citation keys to methods / introduction / references."""
    if not bib_keys:
        return sections
    primary = bib_keys[:3]
    updated: list[PaperSection] = []
    for section in sections:
        keys: list[str] = []
        if section.kind in {"introduction", "methods", "discussion"}:
            keys = list(primary)
        elif section.kind == "references":
            keys = list(bib_keys)
        updated.append(section.model_copy(update={"citation_keys": keys[:32]}))
    return updated


def build_fixture_outline(
    *,
    state: dict[str, Any] | None,
    problem_specification: Any = None,
    llm_enabled: bool = False,
) -> PaperOutline:
    """Build the deterministic 2022 C paper outline from prior artifacts."""
    spec = problem_specification
    if spec is None and state:
        spec = state.get("problem_specification")

    problem_id = _problem_id(spec, state) or "2022_mcm_c"
    topics = _topic_ids_from_spec(spec)

    validation = {}
    proposal_id = None
    baseline_run_id = None
    validation_report_id = None
    experiment_id = None
    if state:
        validation = state.get("validation_report") or {}
        if not isinstance(validation, dict):
            validation = {}
        validation_report_id = validation.get("report_id")
        baseline_run_id = validation.get("baseline_run_id")
        proposal_id = validation.get("proposal_id")
        decision = state.get("decision_report") or {}
        if isinstance(decision, dict):
            experiment = decision.get("experiment") or {}
            if isinstance(experiment, dict):
                experiment_id = experiment.get("report_id")
                if not baseline_run_id:
                    baseline_run_id = experiment.get("latest_run_id")
                if not proposal_id:
                    proposal_id = experiment.get("proposal_id")
            h1 = decision.get("h1") or {}
            if isinstance(h1, dict) and not proposal_id:
                proposal_id = None
        proposal = state.get("research_proposal") or {}
        if isinstance(proposal, dict) and proposal.get("proposal_id") and not proposal_id:
            proposal_id = str(proposal["proposal_id"])

    bib_entries, citation_gaps = _collect_bib_entries(state)
    bib_keys = [e.citation_key for e in bib_entries]

    title = _DEFAULT_TITLE
    payload = _as_dict(spec)
    if payload.get("title"):
        title = str(payload["title"])[:300]
    elif payload.get("problem_title"):
        title = str(payload["problem_title"])[:300]

    sections: list[PaperSection] = []
    for spec_row in _SECTION_SPECS:
        kind = str(spec_row["kind"])
        summary = str(spec_row["summary"])
        # Enrich summaries with concrete artifact ids when present (still deterministic).
        if kind == "results" and baseline_run_id:
            summary = (
                f"{summary} Baseline run id: {baseline_run_id}."
            )[:2000]
        if kind == "validation" and validation_report_id:
            n_scn = len(validation.get("scenarios") or [])
            summary = (
                f"{summary} Validation report {validation_report_id} with "
                f"{n_scn} scenarios."
            )[:2000]
        sections.append(
            PaperSection(
                section_id=str(spec_row["section_id"]),
                kind=kind,  # type: ignore[arg-type]
                title=str(spec_row["title"]),
                summary=summary,
                order=int(spec_row["order"]),
                required=bool(spec_row["required"]),
                topic_ids=list(spec_row.get("topic_ids") or [])[:24],
                artifact_refs=_artifact_refs_for_section(
                    kind,
                    problem_id=problem_id,
                    proposal_id=str(proposal_id) if proposal_id else None,
                    experiment_id=str(experiment_id) if experiment_id else None,
                    validation_id=str(validation_report_id)
                    if validation_report_id
                    else None,
                    baseline_run_id=str(baseline_run_id) if baseline_run_id else None,
                ),
            )
        )

    sections = _assign_citations(sections, bib_keys)

    notes = [
        "strategy=deterministic_fixture",
        f"problem_id={problem_id}",
        f"bib_entries={len(bib_entries)}",
        f"citation_gaps={len(citation_gaps)}",
    ]
    if not bib_entries:
        notes.append(
            "No grounded citations attached; references section lists citation gaps only."
        )
        if "missing_grounded_citations" not in citation_gaps:
            citation_gaps.append("missing_grounded_citations")

    llm_note = None
    llm_attempted = False
    if llm_enabled:
        llm_attempted = True
        llm_note = LLM_UNAVAILABLE_NOTE
        notes.append("llm_outline_stub=unavailable")

    outline_seed = {
        "problem_id": problem_id,
        "proposal_id": proposal_id,
        "validation_report_id": validation_report_id,
        "baseline_run_id": baseline_run_id,
        "section_ids": [s.section_id for s in sections],
        "bib_keys": bib_keys,
    }
    outline_id = _stable_id(
        "pout",
        json.dumps(outline_seed, sort_keys=True, separators=(",", ":")),
    )

    return PaperOutline(
        outline_id=outline_id,
        problem_id=problem_id,
        proposal_id=str(proposal_id) if proposal_id else None,
        validation_report_id=str(validation_report_id) if validation_report_id else None,
        baseline_run_id=str(baseline_run_id) if baseline_run_id else None,
        h2_approved=True,
        paper_allowed=True,
        strategy="deterministic_fixture",
        llm_enabled=bool(llm_enabled),
        llm_attempted=llm_attempted,
        llm_note=llm_note,
        title=title,
        sections=sections,
        bib_entries=bib_entries,
        topic_ids=topics,
        citation_gaps=citation_gaps[:32],
        invented_citations=False,
        agent_prompt_version=PROMPT_VERSION,
        analysis_notes=notes[:32],
    )
