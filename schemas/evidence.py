"""Versioned Literature & Evidence contracts (Phase 4 / VS-2).

Evidence cards carry source metadata, quotes/snippets, method notes, and
citation fields. Findings must ground to a ProblemSpecification (and optional
EDA plan/report) without inventing sources. Unverified or missing evidence is
marked explicitly — never silently verified.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SourceType = Literal[
    "fixture_stub",
    "official_problem",
    "open_access",
    "author_authorized",
    "user_provided",
    "institutional",
    "link_only",
    "other",
]
AcquisitionMethod = Literal[
    "fixture_bundle",
    "official_public",
    "author_authorized",
    "user_provided",
    "institutional_subscription",
    "web_link",
    "other",
]
AllowedOperation = Literal[
    "link_only",
    "metadata_index",
    "internal_fulltext",
    "summarize",
    "excerpt_quote",
    "redistribute",
]
ReviewStatus = Literal["approved", "pending", "rejected", "fixture"]
LocatorStatus = Literal[
    "fixture_local",
    "file_present",
    "url_unchecked",
    "url_unreachable",
    "missing",
    "insufficient",
]
VerificationStatus = Literal[
    "verified_fixture",
    "unverified",
    "insufficient_evidence",
    "unknown",
    "rejected",
]
GroundingKind = Literal[
    "research_question",
    "objective",
    "constraint",
    "assumption",
    "subproblem",
    "eda_finding",
    "eda_plan_item",
    "method_gap",
    "other",
]
RetrievalStrategy = Literal["deterministic_fixture", "live_retrieval", "hybrid"]
EvidenceSufficiency = Literal["sufficient", "partial", "insufficient", "unknown"]


class SourceMetadata(BaseModel):
    """Corpus registry row fields required by AC-04."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    title: str = Field(min_length=3, max_length=400)
    authors: list[str] = Field(default_factory=list, max_length=32)
    year: int | None = Field(default=None, ge=1800, le=2100)
    venue: str | None = Field(default=None, max_length=240)
    source_type: SourceType
    original_url: str | None = Field(default=None, max_length=1000)
    local_path: str | None = Field(default=None, max_length=500)
    publisher: str | None = Field(default=None, max_length=240)
    license_or_rights: str | None = Field(default=None, max_length=400)
    acquisition_method: AcquisitionMethod = "fixture_bundle"
    allowed_operations: list[AllowedOperation] = Field(
        default_factory=lambda: ["metadata_index", "summarize", "excerpt_quote"],
        max_length=12,
    )
    review_status: ReviewStatus = "fixture"
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("authors")
    @classmethod
    def _trim_authors(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        return cleaned


class EvidenceSnippet(BaseModel):
    """Quoted or paraphrased excerpt tied to a locator."""

    model_config = ConfigDict(extra="forbid")

    snippet_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    text: str = Field(min_length=3, max_length=2000)
    locator: str | None = Field(default=None, max_length=240)
    is_verbatim_quote: bool = False
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _span_order(self) -> EvidenceSnippet:
        if self.char_start is not None and self.char_end is not None:
            if self.char_end < self.char_start:
                raise ValueError(f"snippet '{self.snippet_id}' has inverted char span")
        return self


class MethodNote(BaseModel):
    """Method / modeling takeaway extracted from a source."""

    model_config = ConfigDict(extra="forbid")

    note_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    method_name: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=3, max_length=2000)
    applicability: str | None = Field(default=None, max_length=800)
    limitations: str | None = Field(default=None, max_length=800)


class CitationFields(BaseModel):
    """Citation-facing fields for later BibTeX / LaTeX mapping."""

    model_config = ConfigDict(extra="forbid")

    citation_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_:-]{1,79}$")
    citation_type: Literal[
        "article",
        "book",
        "inproceedings",
        "techreport",
        "misc",
        "online",
        "fixture",
    ] = "fixture"
    bibtex_fields: dict[str, str] = Field(default_factory=dict, max_length=32)

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


class GroundingLink(BaseModel):
    """Links an evidence card to a ProblemSpecification / EDA item."""

    model_config = ConfigDict(extra="forbid")

    kind: GroundingKind
    target_id: str = Field(min_length=1, max_length=80)
    target_statement: str | None = Field(default=None, max_length=800)
    relevance: str = Field(min_length=3, max_length=800)
    strength: Literal["strong", "moderate", "weak", "none"] = "moderate"


class EvidenceCard(BaseModel):
    """One grounded literature / evidence unit (AC-04)."""

    model_config = ConfigDict(extra="forbid")

    card_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    source: SourceMetadata
    snippets: list[EvidenceSnippet] = Field(default_factory=list, max_length=16)
    method_notes: list[MethodNote] = Field(default_factory=list, max_length=16)
    citation: CitationFields
    grounding: list[GroundingLink] = Field(default_factory=list, max_length=24)
    locator_status: LocatorStatus
    verification_status: VerificationStatus
    claim_summary: str = Field(min_length=3, max_length=2000)
    invented: bool = False
    tags: list[str] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def _no_fake_verified(self) -> EvidenceCard:
        if self.invented:
            raise ValueError(f"evidence card '{self.card_id}' must not be invented")
        if self.verification_status == "verified_fixture":
            if self.source.source_type != "fixture_stub":
                raise ValueError(
                    f"card '{self.card_id}': verified_fixture requires source_type=fixture_stub"
                )
            if self.locator_status not in {"fixture_local", "file_present"}:
                raise ValueError(
                    f"card '{self.card_id}': verified_fixture requires a local locator"
                )
        if self.verification_status == "verified_fixture" and self.locator_status == "missing":
            raise ValueError(f"card '{self.card_id}' cannot be verified with missing locator")
        return self


class EvidenceGap(BaseModel):
    """Explicit insufficient / unknown evidence for a grounded target."""

    model_config = ConfigDict(extra="forbid")

    gap_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    kind: GroundingKind
    target_id: str = Field(min_length=1, max_length=80)
    statement: str = Field(min_length=3, max_length=2000)
    sufficiency: EvidenceSufficiency = "insufficient"
    mitigation_hint: str | None = Field(default=None, max_length=800)


class LiteratureEvidenceReport(BaseModel):
    """Agent output: evidence cards + gaps grounded to the problem (and EDA)."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    problem_id: str | None = Field(default=None, max_length=64)
    strategy: RetrievalStrategy = "deterministic_fixture"
    retrieval_backend: str = Field(default="fixture_corpus", max_length=80)
    live_retrieval_enabled: bool = False
    live_retrieval_attempted: bool = False
    live_retrieval_note: str | None = Field(default=None, max_length=1000)
    cards: list[EvidenceCard] = Field(default_factory=list, max_length=64)
    gaps: list[EvidenceGap] = Field(default_factory=list, max_length=64)
    grounded_target_ids: list[str] = Field(default_factory=list, max_length=64)
    eda_context_present: bool = False
    problem_specification_present: bool = False
    invented_sources: bool = False
    analysis_notes: list[str] = Field(default_factory=list, max_length=32)
    agent_prompt_version: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _integrity(self) -> LiteratureEvidenceReport:
        if self.invented_sources:
            raise ValueError("LiteratureEvidenceReport must not invent sources")
        if any(card.invented for card in self.cards):
            raise ValueError("LiteratureEvidenceReport contains an invented card")
        # verified status is never allowed for non-fixture paths in this phase
        for card in self.cards:
            if card.verification_status not in {
                "verified_fixture",
                "unverified",
                "insufficient_evidence",
                "unknown",
                "rejected",
            }:
                raise ValueError(f"unsupported verification_status on {card.card_id}")
        return self
