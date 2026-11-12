"""Versioned Research Strategy / Debate / H1 contracts (Phase 5).

Candidates carry hypotheses, methods, data needs, and validation plans with
explicit provenance from ProblemSpecification, EDA, and Evidence when present.
H1 approval is human-only — never auto-approved. Modeling stays blocked until
``approval_status.h1 == approved``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProvenanceKind = Literal[
    "problem_specification",
    "eda_plan",
    "eda_report",
    "evidence_report",
    "evidence_gap",
    "rule_based",
    "llm",
    "human",
    "unknown",
]
SynthesisStrategy = Literal["deterministic_rules", "llm", "hybrid"]
CritiqueStrategy = Literal["deterministic_rules", "llm", "hybrid"]
CandidateStatus = Literal["proposed", "recommended", "rejected", "revised"]
CritiqueSeverity = Literal["info", "low", "medium", "high", "blocking"]
CritiqueKind = Literal[
    "contradiction",
    "weak_assumption",
    "evidence_gap",
    "data_gap",
    "validation_gap",
    "alternative",
    "other",
]
H1DecisionStatus = Literal["pending", "approved", "revision_requested", "rejected"]
ModelingGateReason = Literal[
    "h1_not_decided",
    "h1_pending",
    "h1_revision_requested",
    "h1_rejected",
    "h1_approved",
    "no_proposal",
]


class ProvenanceRef(BaseModel):
    """Traceable pointer back to an upstream research artifact."""

    model_config = ConfigDict(extra="forbid")

    kind: ProvenanceKind
    ref_id: str | None = Field(default=None, max_length=80)
    summary: str = Field(min_length=3, max_length=800)


class HypothesisItem(BaseModel):
    """Testable hypothesis tied to a research question or subproblem."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    statement: str = Field(min_length=3, max_length=2000)
    related_question_ids: list[str] = Field(default_factory=list, max_length=16)
    related_subproblem_ids: list[str] = Field(default_factory=list, max_length=16)
    provenance: list[ProvenanceRef] = Field(default_factory=list, max_length=16)
    confidence: Literal["low", "medium", "high"] = "medium"


class DataNeed(BaseModel):
    """Dataset / feature / evidence requirement for a candidate method."""

    model_config = ConfigDict(extra="forbid")

    need_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    description: str = Field(min_length=3, max_length=1000)
    required: bool = True
    satisfied: bool | None = None
    provenance: list[ProvenanceRef] = Field(default_factory=list, max_length=8)


class ValidationPlanItem(BaseModel):
    """How a candidate will be checked before trusting results."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    description: str = Field(min_length=3, max_length=1500)
    method: Literal[
        "backtest",
        "holdout",
        "cross_validation",
        "sensitivity",
        "scenario",
        "assumption_check",
        "ablation",
        "other",
    ] = "other"
    success_criteria: str | None = Field(default=None, max_length=800)
    provenance: list[ProvenanceRef] = Field(default_factory=list, max_length=8)


class CandidateMethod(BaseModel):
    """One candidate research / modeling route for H1 review."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=3, max_length=4000)
    method_family: str = Field(min_length=2, max_length=120)
    hypotheses: list[HypothesisItem] = Field(default_factory=list, max_length=16)
    data_needs: list[DataNeed] = Field(default_factory=list, max_length=24)
    validation_plan: list[ValidationPlanItem] = Field(default_factory=list, max_length=16)
    strengths: list[str] = Field(default_factory=list, max_length=12)
    weaknesses: list[str] = Field(default_factory=list, max_length=12)
    evidence_card_ids: list[str] = Field(default_factory=list, max_length=32)
    evidence_gap_ids: list[str] = Field(default_factory=list, max_length=32)
    subproblem_ids: list[str] = Field(default_factory=list, max_length=16)
    status: CandidateStatus = "proposed"
    provenance: list[ProvenanceRef] = Field(default_factory=list, max_length=24)
    invented_sources: bool = False

    @model_validator(mode="after")
    def _no_invented(self) -> CandidateMethod:
        if self.invented_sources:
            raise ValueError(f"candidate '{self.candidate_id}' must not invent sources")
        return self


class ResearchProposal(BaseModel):
    """Synthesized research proposal ready for Debate + H1."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    proposal_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    problem_id: str | None = Field(default=None, max_length=64)
    strategy: SynthesisStrategy = "deterministic_rules"
    llm_enabled: bool = False
    llm_attempted: bool = False
    llm_note: str | None = Field(default=None, max_length=1000)
    candidates: list[CandidateMethod] = Field(default_factory=list, max_length=12)
    recommended_candidate_id: str | None = Field(default=None, max_length=64)
    consensus_notes: list[str] = Field(default_factory=list, max_length=24)
    open_questions: list[str] = Field(default_factory=list, max_length=24)
    problem_specification_present: bool = False
    eda_context_present: bool = False
    evidence_present: bool = False
    invented_sources: bool = False
    agent_prompt_version: str | None = Field(default=None, max_length=80)
    analysis_notes: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _integrity(self) -> ResearchProposal:
        if self.invented_sources:
            raise ValueError("ResearchProposal must not invent sources")
        if any(c.invented_sources for c in self.candidates):
            raise ValueError("ResearchProposal contains a candidate with invented sources")
        if self.recommended_candidate_id:
            ids = {c.candidate_id for c in self.candidates}
            if self.recommended_candidate_id not in ids:
                raise ValueError(
                    f"recommended_candidate_id '{self.recommended_candidate_id}' "
                    "is not among candidates"
                )
        return self


class CritiqueFinding(BaseModel):
    """One Debate/Critic finding against a candidate or the proposal."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    kind: CritiqueKind
    severity: CritiqueSeverity = "medium"
    candidate_id: str | None = Field(default=None, max_length=64)
    statement: str = Field(min_length=3, max_length=2000)
    evidence_refs: list[ProvenanceRef] = Field(default_factory=list, max_length=12)
    suggested_action: str | None = Field(default=None, max_length=800)
    invented_source: bool = False

    @model_validator(mode="after")
    def _no_invented(self) -> CritiqueFinding:
        if self.invented_source:
            raise ValueError(f"critique finding '{self.finding_id}' must not invent sources")
        return self


class DebateCritique(BaseModel):
    """Independent critique of a ResearchProposal (no invented sources)."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    critique_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    proposal_id: str = Field(min_length=1, max_length=64)
    strategy: CritiqueStrategy = "deterministic_rules"
    llm_enabled: bool = False
    llm_attempted: bool = False
    llm_note: str | None = Field(default=None, max_length=1000)
    findings: list[CritiqueFinding] = Field(default_factory=list, max_length=64)
    blocking_count: int = Field(default=0, ge=0)
    invented_sources: bool = False
    agent_prompt_version: str | None = Field(default=None, max_length=80)
    analysis_notes: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _integrity(self) -> DebateCritique:
        if self.invented_sources:
            raise ValueError("DebateCritique must not invent sources")
        if any(f.invented_source for f in self.findings):
            raise ValueError("DebateCritique contains an invented-source finding")
        blocking = sum(1 for f in self.findings if f.severity == "blocking")
        object.__setattr__(self, "blocking_count", blocking)
        return self


class H1Decision(BaseModel):
    """Human-only H1 research-plan approval record."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    gate: Literal["H1"] = "H1"
    status: H1DecisionStatus
    proposal_id: str = Field(min_length=1, max_length=64)
    selected_candidate_id: str | None = Field(default=None, max_length=64)
    notes: str = Field(default="", max_length=4000)
    decided_by: Literal["human"] = "human"
    auto_approved: bool = False
    decided_at_utc: str | None = Field(default=None, max_length=64)
    proposal_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    critique_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _human_only(self) -> H1Decision:
        if self.auto_approved:
            raise ValueError("H1 must never be auto-approved")
        if self.decided_by != "human":
            raise ValueError("H1 decisions must be human")
        if self.status == "approved" and not self.selected_candidate_id:
            raise ValueError("H1 approval requires selected_candidate_id")
        if self.status in {"approved", "revision_requested", "rejected"} and not self.decided_at_utc:
            raise ValueError(f"H1 status '{self.status}' requires decided_at_utc")
        return self


class ModelingGateStatus(BaseModel):
    """Explicit gate: Modeling & Experiment stays blocked until H1 approved."""

    model_config = ConfigDict(extra="forbid")

    modeling_allowed: bool = False
    h1_status: H1DecisionStatus | Literal["absent"] = "absent"
    reason: ModelingGateReason = "h1_not_decided"
    message: str = Field(min_length=3, max_length=500)

    @field_validator("modeling_allowed")
    @classmethod
    def _default_blocked(cls, value: bool) -> bool:
        return bool(value)

    @model_validator(mode="after")
    def _consistent(self) -> ModelingGateStatus:
        if self.modeling_allowed and self.h1_status != "approved":
            raise ValueError("modeling_allowed requires h1_status=approved")
        if self.modeling_allowed and self.reason != "h1_approved":
            raise ValueError("modeling_allowed requires reason=h1_approved")
        if not self.modeling_allowed and self.reason == "h1_approved":
            raise ValueError("blocked gate cannot claim h1_approved")
        return self
