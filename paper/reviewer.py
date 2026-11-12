"""Light CI-safe paper reviewer checklist (Phase 8).

Checks structure (required sections), citation presence (keys used vs bib /
gaps), and topic coverage against outline topic_ids. Never invents citations
and never calls a live LLM.
"""

from __future__ import annotations

import hashlib
from typing import Any

from paper.latex import latex_looks_structured
from schemas.paper import (
    LatexBundle,
    PaperOutline,
    PaperReviewReport,
    ReviewFinding,
    ReviewStatus,
)

_REQUIRED_KINDS = {
    "abstract",
    "introduction",
    "problem",
    "methods",
    "results",
    "validation",
    "conclusion",
    "references",
}


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"[:64]


def _dim_ok(findings: list[ReviewFinding], category: str) -> bool:
    return all(f.status != "fail" for f in findings if f.category == category)


def _overall_status(findings: list[ReviewFinding]) -> ReviewStatus:
    if any(f.status == "fail" for f in findings):
        return "fail"
    if any(f.status == "warn" for f in findings):
        return "warn"
    return "pass"


def review_paper_outline(
    outline: PaperOutline,
    *,
    latex: LatexBundle | None = None,
) -> PaperReviewReport:
    """Run the deterministic checklist over an outline (+ optional latex)."""
    findings: list[ReviewFinding] = []
    kinds = {s.kind for s in outline.sections}
    missing = sorted(_REQUIRED_KINDS - kinds)
    if missing:
        findings.append(
            ReviewFinding(
                finding_id="fnd_structure_missing",
                category="structure",
                severity="blocking",
                status="fail",
                summary=f"Missing required section kinds: {', '.join(missing)}",
                related_section_ids=[],
            )
        )
    else:
        findings.append(
            ReviewFinding(
                finding_id="fnd_structure_ok",
                category="structure",
                severity="info",
                status="pass",
                summary="All required MCM section kinds are present in the outline.",
                related_section_ids=[s.section_id for s in outline.sections],
            )
        )

    if outline.invented_citations or any(e.invented for e in outline.bib_entries):
        findings.append(
            ReviewFinding(
                finding_id="fnd_citations_invented",
                category="citations",
                severity="blocking",
                status="fail",
                summary="Invented citations are forbidden.",
                related_citation_keys=[
                    e.citation_key for e in outline.bib_entries if e.invented
                ],
            )
        )

    bib_keys = {e.citation_key for e in outline.bib_entries}
    used: set[str] = set()
    for section in outline.sections:
        used.update(section.citation_keys)
    orphan_used = sorted(used - bib_keys - set(outline.citation_gaps))
    if orphan_used:
        findings.append(
            ReviewFinding(
                finding_id="fnd_citations_orphan",
                category="citations",
                severity="high",
                status="fail",
                summary=(
                    "Section citation keys missing from bib_entries and "
                    f"citation_gaps: {', '.join(orphan_used)}"
                ),
                related_citation_keys=orphan_used,
            )
        )
    elif not bib_keys:
        findings.append(
            ReviewFinding(
                finding_id="fnd_citations_empty",
                category="citations",
                severity="medium",
                status="warn",
                summary=(
                    "No grounded bibliography entries; citation gaps recorded. "
                    "Do not invent sources."
                ),
                related_citation_keys=list(outline.citation_gaps)[:16],
            )
        )
    else:
        findings.append(
            ReviewFinding(
                finding_id="fnd_citations_ok",
                category="citations",
                severity="info",
                status="pass",
                summary=(
                    f"Bibliography has {len(bib_keys)} grounded entries; "
                    "section keys resolve."
                ),
                related_citation_keys=sorted(bib_keys)[:16],
            )
        )

    covered: set[str] = set()
    for section in outline.sections:
        covered.update(section.topic_ids)
    expected = set(outline.topic_ids)
    must = {"trading_strategy", "transaction_costs", "validation"} & expected
    missing_topics = sorted(must - covered)
    if missing_topics:
        findings.append(
            ReviewFinding(
                finding_id="fnd_topics_missing",
                category="topic_coverage",
                severity="high",
                status="fail",
                summary=f"Missing topic coverage in sections: {', '.join(missing_topics)}",
            )
        )
    else:
        findings.append(
            ReviewFinding(
                finding_id="fnd_topics_ok",
                category="topic_coverage",
                severity="info",
                status="pass",
                summary=(
                    "Core topics covered across sections "
                    f"({len(covered & expected)}/{max(len(expected), 1)} outline topics touched)."
                ),
            )
        )

    if latex is not None:
        if not latex_looks_structured(latex.tex_source):
            findings.append(
                ReviewFinding(
                    finding_id="fnd_latex_structure",
                    category="structure",
                    severity="high",
                    status="fail",
                    summary="LaTeX draft missing document/section structure.",
                )
            )
        else:
            findings.append(
                ReviewFinding(
                    finding_id="fnd_latex_ok",
                    category="structure",
                    severity="info",
                    status="pass",
                    summary=(
                        "LaTeX draft has document begin/end and section/abstract markers."
                    ),
                )
            )
        if latex.compile_attempted and latex.compile_ok is False:
            findings.append(
                ReviewFinding(
                    finding_id="fnd_latex_compile_soft",
                    category="other",
                    severity="low",
                    status="warn",
                    summary=(
                        latex.compile_note
                        or "PDF compile attempted and soft-failed; not required for CI."
                    ),
                )
            )

    overall = _overall_status(findings)
    structure_ok = _dim_ok(findings, "structure")
    citations_ok = _dim_ok(findings, "citations")
    topic_ok = _dim_ok(findings, "topic_coverage")
    # Schema: overall=pass requires all dims ok (warn is allowed with dims ok).
    if overall == "pass" and not (structure_ok and citations_ok and topic_ok):
        overall = "fail"

    notes = [
        f"findings={len(findings)}",
        f"overall={overall}",
        f"bib_entries={len(outline.bib_entries)}",
    ]

    return PaperReviewReport(
        review_id=_stable_id("prev", outline.outline_id, overall),
        outline_id=outline.outline_id,
        overall_status=overall,
        findings=findings[:64],
        structure_ok=structure_ok,
        citations_ok=citations_ok,
        topic_coverage_ok=topic_ok,
        invented_citations=False,
        analysis_notes=notes[:32],
    )


def review_status_summary(report: PaperReviewReport | dict[str, Any]) -> str:
    if isinstance(report, PaperReviewReport):
        return f"{report.overall_status} ({len(report.findings)} findings)"
    return f"{report.get('overall_status')} ({len(report.get('findings') or [])} findings)"
