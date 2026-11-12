"""Versioned Paper Planner / LaTeX / H3 contracts (Phase 8).

Outlines and bibliography entries must ground to prior artifacts
(ProblemSpecification, evidence, experiments, validation). Citations are never
invented. H3 approval is human-only — never auto-approved. Phase 9 E2E stays
blocked until ``approval_status.h3 == approved``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PaperStrategy = Literal["deterministic_fixture", "llm_outline", "hybrid"]
SectionKind = Literal[
    "abstract",
    "introduction",
    "problem",
    "data",
    "methods",
    "results",
    "validation",
    "discussion",
    "conclusion",
    "references",
    "appendix",
    "other",
]
ArtifactKind = Literal[
    "problem_specification",
    "evidence_report",
    "research_proposal",
    "experiment",
    "validation_report",
    "citation",
    "other",
]
ReviewSeverity = Literal["info", "low", "medium", "high", "blocking"]
ReviewStatus = Literal["pass", "warn", "fail"]
H3DecisionStatus = Literal["pending", "approved", "revision_requested", "rejected"]
PaperGenGateReason = Literal[
    "h2_not_decided",
    "h2_pending",
    "h2_revision_requested",
    "h2_rejected",
    "h2_approved",
    "no_validation_report",
]
E2EGateReason = Literal[
    "h3_not_decided",
    "h3_pending",
    "h3_revision_requested",
    "h3_rejected",
    "h3_approved",
    "no_paper_outline",
]


class ArtifactRef(BaseModel):
    """Pointer to a prior-phase artifact that grounds a section or claim."""

    model_config = ConfigDict(extra="forbid")

    kind: ArtifactKind
    ref_id: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=200)


class PaperSection(BaseModel):
    """One outline / section-map entry for the MCM paper."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    kind: SectionKind = "other"
    title: str = Field(min_length=2, max_length=200)
    summary: str = Field(min_length=3, max_length=2000)
    order: int = Field(ge=0, le=64)
    required: bool = True
    citation_keys: list[str] = Field(default_factory=list, max_length=32)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list, max_length=24)
    topic_ids: list[str] = Field(default_factory=list, max_length=24)
    notes: list[str] = Field(default_factory=list, max_length=16)


class BibEntry(BaseModel):
    """Bibliography entry grounded in evidence / fixture corpus — never invented."""

    model_config = ConfigDict(extra="forbid")

    citation_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_:-]{1,79}$")
    entry_type: Literal[
        "article",
        "book",
        "inproceedings",
        "techreport",
        "misc",
        "online",
        "fixture",
    ] = "fixture"
    source_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=3, max_length=400)
    authors: list[str] = Field(default_factory=list, max_length=32)
    year: int | None = Field(default=None, ge=1800, le=2100)
    venue: str | None = Field(default=None, max_length=240)
    bibtex_fields: dict[str, str] = Field(default_factory=dict, max_length=32)
    invented: bool = False
    grounded: bool = True

    @field_validator("bibtex_fields")
    @classmethod
    def _bounded_bibtex(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned: dict[str, str] = {}
        for key, item in value.items():
            k = str(key).strip()[:64]
            v = str(item).strip()[:800]
            if k and v:
                cleaned[k] = v
        return cleaned

    @model_validator(mode="after")
    def _no_invented(self) -> BibEntry:
        if self.invented:
            raise ValueError(
                f"bib entry '{self.citation_key}' must not invent citations"
            )
        if not self.grounded:
            raise ValueError(
                f"bib entry '{self.citation_key}' must be grounded in prior evidence"
            )
        return self


class PaperOutline(BaseModel):
    """Deterministic paper plan / section map for Phase 8."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    outline_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    problem_id: str | None = Field(default=None, max_length=64)
    proposal_id: str | None = Field(default=None, max_length=64)
    validation_report_id: str | None = Field(default=None, max_length=64)
    baseline_run_id: str | None = Field(default=None, max_length=64)
    h2_approved: bool = True
    paper_allowed: bool = True
    strategy: PaperStrategy = "deterministic_fixture"
    llm_enabled: bool = False
    llm_attempted: bool = False
    llm_note: str | None = Field(default=None, max_length=1000)
    title: str = Field(min_length=3, max_length=300)
    sections: list[PaperSection] = Field(default_factory=list, max_length=32)
    bib_entries: list[BibEntry] = Field(default_factory=list, max_length=64)
    topic_ids: list[str] = Field(default_factory=list, max_length=64)
    citation_gaps: list[str] = Field(default_factory=list, max_length=32)
    invented_citations: bool = False
    agent_prompt_version: str | None = Field(default=None, max_length=80)
    analysis_notes: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _integrity(self) -> PaperOutline:
        if self.invented_citations:
            raise ValueError("PaperOutline must not invent citations")
        if not self.h2_approved or not self.paper_allowed:
            raise ValueError("PaperOutline requires H2-approved paper gate")
        if any(entry.invented for entry in self.bib_entries):
            raise ValueError("PaperOutline contains invented bibliography entries")
        if not self.sections:
            raise ValueError("PaperOutline requires at least one section")
        # Every citation_key used in sections must appear in bib_entries (or be listed as gap).
        known = {e.citation_key for e in self.bib_entries}
        gaps = set(self.citation_gaps)
        for section in self.sections:
            for key in section.citation_keys:
                if key not in known and key not in gaps:
                    raise ValueError(
                        f"section '{section.section_id}' cites unknown key '{key}' "
                        "without a citation_gaps entry"
                    )
        return self


class LatexBundle(BaseModel):
    """Offline LaTeX / BibTeX emission. PDF compile is optional / best-effort."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    outline_id: str = Field(min_length=1, max_length=64)
    tex_source: str = Field(min_length=1, max_length=200_000)
    bib_source: str = Field(default="", max_length=100_000)
    tex_filename: str = Field(default="main.tex", max_length=120)
    bib_filename: str = Field(default="refs.bib", max_length=120)
    compile_attempted: bool = False
    compile_ok: bool | None = None
    compile_note: str | None = Field(default=None, max_length=1000)
    pdf_path: str | None = Field(default=None, max_length=500)


class ReviewFinding(BaseModel):
    """One light paper-reviewer checklist finding."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    category: Literal[
        "structure",
        "citations",
        "topic_coverage",
        "grounding",
        "other",
    ]
    severity: ReviewSeverity = "info"
    status: ReviewStatus = "pass"
    summary: str = Field(min_length=3, max_length=1000)
    related_section_ids: list[str] = Field(default_factory=list, max_length=16)
    related_citation_keys: list[str] = Field(default_factory=list, max_length=16)


class PaperReviewReport(BaseModel):
    """CI-safe light reviewer over outline + bib (+ optional latex)."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    review_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    outline_id: str = Field(min_length=1, max_length=64)
    overall_status: ReviewStatus = "pass"
    findings: list[ReviewFinding] = Field(default_factory=list, max_length=64)
    structure_ok: bool = True
    citations_ok: bool = True
    topic_coverage_ok: bool = True
    invented_citations: bool = False
    analysis_notes: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _integrity(self) -> PaperReviewReport:
        if self.invented_citations:
            raise ValueError("PaperReviewReport must not invent citations")
        if self.overall_status == "pass" and not (
            self.structure_ok and self.citations_ok and self.topic_coverage_ok
        ):
            raise ValueError("overall_status=pass requires all checklist dims ok")
        return self


class PaperPackage(BaseModel):
    """Panel / persistence envelope: outline + latex + review."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    package_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    outline: PaperOutline
    latex: LatexBundle | None = None
    review: PaperReviewReport | None = None
    h2_approved: bool = True
    paper_allowed: bool = True
    invented_citations: bool = False

    @model_validator(mode="after")
    def _integrity(self) -> PaperPackage:
        if self.invented_citations or self.outline.invented_citations:
            raise ValueError("PaperPackage must not invent citations")
        if not self.h2_approved or not self.paper_allowed:
            raise ValueError("PaperPackage requires H2-approved paper gate")
        if self.latex and self.latex.outline_id != self.outline.outline_id:
            raise ValueError("LatexBundle.outline_id must match PaperOutline")
        if self.review and self.review.outline_id != self.outline.outline_id:
            raise ValueError("PaperReviewReport.outline_id must match PaperOutline")
        return self


class H3Decision(BaseModel):
    """Human-only H3 paper / LaTeX approval record."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    gate: Literal["H3"] = "H3"
    status: H3DecisionStatus
    package_id: str = Field(min_length=1, max_length=64)
    outline_id: str | None = Field(default=None, max_length=64)
    notes: str = Field(default="", max_length=4000)
    decided_by: Literal["human"] = "human"
    auto_approved: bool = False
    decided_at_utc: str | None = Field(default=None, max_length=64)
    package_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _human_only(self) -> H3Decision:
        if self.auto_approved:
            raise ValueError("H3 must never be auto-approved")
        if self.decided_by != "human":
            raise ValueError("H3 decisions must be human")
        if self.status in {"approved", "revision_requested", "rejected"} and not self.decided_at_utc:
            raise ValueError(f"H3 status '{self.status}' requires decided_at_utc")
        return self


class PaperGenerationGateStatus(BaseModel):
    """Explicit gate: Paper Planner / LaTeX runs only with H2 approved."""

    model_config = ConfigDict(extra="forbid")

    paper_allowed: bool = False
    h2_status: Literal[
        "pending", "approved", "revision_requested", "rejected", "absent"
    ] = "absent"
    reason: PaperGenGateReason = "h2_not_decided"
    message: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def _consistent(self) -> PaperGenerationGateStatus:
        if self.paper_allowed and self.h2_status != "approved":
            raise ValueError("paper_allowed requires h2_status=approved")
        if self.paper_allowed and self.reason != "h2_approved":
            raise ValueError("paper_allowed requires reason=h2_approved")
        if not self.paper_allowed and self.reason == "h2_approved":
            raise ValueError("blocked paper gate cannot claim h2_approved")
        return self


class E2EGateStatus(BaseModel):
    """Explicit gate: Phase 9 E2E stays blocked until H3 approved."""

    model_config = ConfigDict(extra="forbid")

    e2e_allowed: bool = False
    h3_status: H3DecisionStatus | Literal["absent"] = "absent"
    reason: E2EGateReason = "h3_not_decided"
    message: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def _consistent(self) -> E2EGateStatus:
        if self.e2e_allowed and self.h3_status != "approved":
            raise ValueError("e2e_allowed requires h3_status=approved")
        if self.e2e_allowed and self.reason != "h3_approved":
            raise ValueError("e2e_allowed requires reason=h3_approved")
        if not self.e2e_allowed and self.reason == "h3_approved":
            raise ValueError("blocked e2e gate cannot claim h3_approved")
        return self
