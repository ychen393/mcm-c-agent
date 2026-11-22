"""Optional Research Plan V2 types. Legacy ResearchProposal remains readable."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutableResearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: str = Field(min_length=8, max_length=1000)
    input_features: list[str] = Field(min_length=1, max_length=12)
    signal_definition: str = Field(min_length=12, max_length=1800)
    decision_timing: str = Field(min_length=12, max_length=950)
    execution_rule: str = Field(min_length=12, max_length=1500)
    transaction_costs: str = Field(min_length=8, max_length=850)
    parameters: list[str] = Field(min_length=1, max_length=15)
    risk_controls: list[str] = Field(min_length=1, max_length=12)
    baseline_ids: list[str] = Field(min_length=1, max_length=8)
    validation_design: list[str] = Field(min_length=1, max_length=12)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    implementation_status: Literal["implemented", "partial", "needs_implementation"] = "needs_implementation"
    executable_strategy_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _truthful_status(self):
        if self.implementation_status == "implemented" and not self.executable_strategy_id:
            raise ValueError("Implemented plan requires explicit executable strategy id")
        if self.implementation_status != "implemented" and self.executable_strategy_id:
            raise ValueError("Unimplemented plans cannot advertise an executable strategy")
        return self


class ResearchDecisionV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["2.0"] = "2.0"
    primary_candidate_id: str = Field(min_length=1, max_length=64)
    alternate_candidate_ids: list[str] = Field(default_factory=list, max_length=2)
    prerequisite_tasks: list[str] = Field(default_factory=list, max_length=12)
    baseline_strategy_ids: list[str] = Field(default_factory=list, max_length=8)
    validation_tasks: list[str] = Field(default_factory=list, max_length=12)
    evidence_packet_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    evidence_bundle_fingerprint: str | None = Field(default=None, max_length=128)
    status: Literal["draft", "ready_for_h1"] = "draft"

    @model_validator(mode="after")
    def _distinct(self):
        if self.primary_candidate_id in self.alternate_candidate_ids:
            raise ValueError("Primary candidate cannot also be alternate")
        if len(set(self.alternate_candidate_ids)) != len(self.alternate_candidate_ids):
            raise ValueError("Alternate ids must be distinct")
        return self


class StructuredResearchEdit(BaseModel):
    """Exact patch to an EXISTING candidate. Model does not invent new IDs."""
    model_config = ConfigDict(extra="forbid")
    candidate_id: str = Field(min_length=1, max_length=64)
    revised_summary: str = Field(min_length=40, max_length=3000)
    revised_execution_plan: ExecutableResearchPlan
    changes_made: str = Field(min_length=15, max_length=1000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)


class StructuredCriticNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["lookahead", "calendar", "fees", "data", "implementation", "validation", "future_work"]
    priority: Literal["blocking", "important", "future_work"]
    candidate_id: str = Field(min_length=1, max_length=64)
    target_field: str = Field(min_length=1, max_length=64)
    problem: str = Field(min_length=12, max_length=1200)
    suggested_fix: str = Field(min_length=12, max_length=800)


class StructuredResearchCritique(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notes: list[StructuredCriticNote] = Field(default_factory=list, max_length=12)
    verdict: Literal["changes_needed", "ready_for_human_review"]
