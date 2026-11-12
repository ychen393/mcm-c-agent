"""Versioned ProblemSpecification contract for the Problem Analyst Agent.

Distinguishes official (stated in the problem text), inferred (reasonable reading),
and unknown (not evidenced) conditions. Key formulas, numeric conditions, and
trading rules carry explicit source marks.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Provenance = Literal["official", "inferred", "unknown"]
AnalystStrategy = Literal["deterministic", "agent"]


class SourcedItem(BaseModel):
    """A statement with provenance and an optional excerpt from the problem text."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    statement: str = Field(min_length=3, max_length=2000)
    provenance: Provenance
    source_excerpt: str | None = Field(default=None, max_length=800)
    source_location: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def official_requires_excerpt(self) -> SourcedItem:
        if self.provenance == "official" and not (self.source_excerpt and self.source_excerpt.strip()):
            raise ValueError(f"official item '{self.id}' requires a non-empty source_excerpt")
        return self


class ResearchQuestion(SourcedItem):
    """Top-level research question extracted from the problem."""


class ObjectiveItem(SourcedItem):
    """Modeling or research objective."""


class ConstraintItem(SourcedItem):
    """Hard or soft constraint stated or inferred from the problem."""

    constraint_kind: Literal[
        "capital",
        "assets",
        "trading_calendar",
        "transaction_cost",
        "information",
        "data_use",
        "deliverable",
        "other",
    ] = "other"


class DatasetItem(SourcedItem):
    """Supplied dataset referenced by the problem."""

    file_name: str = Field(min_length=1, max_length=260)
    columns: list[str] = Field(default_factory=list, max_length=32)
    notes: str | None = Field(default=None, max_length=800)


class AssumptionToValidate(SourcedItem):
    """Assumption that later stages must validate or justify."""


class DeliverableItem(SourcedItem):
    """Required contest or product deliverable."""


class UnknownOrRisk(BaseModel):
    """Gap, ambiguity, or risk that should not be silently filled."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    statement: str = Field(min_length=3, max_length=2000)
    provenance: Provenance = "unknown"
    severity: Literal["low", "medium", "high"] = "medium"
    mitigation_hint: str | None = Field(default=None, max_length=800)


class FormulaItem(BaseModel):
    """Key formula or symbolic condition with source marking."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    expression: str = Field(min_length=1, max_length=500)
    provenance: Provenance
    source_excerpt: str | None = Field(default=None, max_length=800)
    source_location: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=800)

    @model_validator(mode="after")
    def official_requires_excerpt(self) -> FormulaItem:
        if self.provenance == "official" and not (self.source_excerpt and self.source_excerpt.strip()):
            raise ValueError(f"official formula '{self.id}' requires a non-empty source_excerpt")
        return self


class NumericCondition(BaseModel):
    """Numeric condition (capital, rates, dates) with source marking."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=200)
    unit: str | None = Field(default=None, max_length=80)
    provenance: Provenance
    source_excerpt: str | None = Field(default=None, max_length=800)
    source_location: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def official_requires_excerpt(self) -> NumericCondition:
        if self.provenance == "official" and not (self.source_excerpt and self.source_excerpt.strip()):
            raise ValueError(f"official numeric condition '{self.id}' requires a non-empty source_excerpt")
        return self


class TradingRule(BaseModel):
    """Trading or portfolio rule with source marking."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    statement: str = Field(min_length=3, max_length=2000)
    provenance: Provenance
    source_excerpt: str | None = Field(default=None, max_length=800)
    source_location: str | None = Field(default=None, max_length=200)
    applies_to: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def official_requires_excerpt(self) -> TradingRule:
        if self.provenance == "official" and not (self.source_excerpt and self.source_excerpt.strip()):
            raise ValueError(f"official trading rule '{self.id}' requires a non-empty source_excerpt")
        return self


class SubproblemSpec(BaseModel):
    """Per-subproblem contract: I/O, evidence, methods, acceptance."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    title: str = Field(min_length=3, max_length=200)
    statement: str = Field(min_length=3, max_length=4000)
    provenance: Provenance
    source_excerpt: str | None = Field(default=None, max_length=1200)
    source_location: str | None = Field(default=None, max_length=200)
    inputs: list[str] = Field(default_factory=list, max_length=32)
    outputs: list[str] = Field(default_factory=list, max_length=32)
    evidence_needed: list[str] = Field(default_factory=list, max_length=32)
    candidate_methods: list[str] = Field(default_factory=list, max_length=24)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def official_requires_excerpt(self) -> SubproblemSpec:
        if self.provenance == "official" and not (self.source_excerpt and self.source_excerpt.strip()):
            raise ValueError(f"official subproblem '{self.id}' requires a non-empty source_excerpt")
        return self


class ProblemSpecification(BaseModel):
    """Machine-executable problem understanding for downstream research agents."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    problem_id: str = Field(min_length=3, max_length=64)
    title: str = Field(min_length=3, max_length=200)
    research_questions: list[ResearchQuestion] = Field(default_factory=list, max_length=32)
    objectives: list[ObjectiveItem] = Field(default_factory=list, max_length=32)
    constraints: list[ConstraintItem] = Field(default_factory=list, max_length=64)
    supplied_datasets: list[DatasetItem] = Field(default_factory=list, max_length=16)
    assumptions_to_validate: list[AssumptionToValidate] = Field(default_factory=list, max_length=32)
    required_deliverables: list[DeliverableItem] = Field(default_factory=list, max_length=32)
    unknowns_or_risks: list[UnknownOrRisk] = Field(default_factory=list, max_length=32)
    subproblems: list[SubproblemSpec] = Field(default_factory=list, max_length=16)
    key_formulas: list[FormulaItem] = Field(default_factory=list, max_length=24)
    numeric_conditions: list[NumericCondition] = Field(default_factory=list, max_length=32)
    trading_rules: list[TradingRule] = Field(default_factory=list, max_length=32)
    strategy: AnalystStrategy = "deterministic"
    analyst_provider: str | None = None
    analyst_model: str | None = None
    analyst_prompt_version: str | None = None
    fallback_reason: str | None = Field(default=None, max_length=1000)
    analysis_notes: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("problem_id")
    @classmethod
    def normalize_problem_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("problem_id cannot be empty")
        return cleaned

    @model_validator(mode="after")
    def require_core_sections(self) -> ProblemSpecification:
        if not self.research_questions and not self.subproblems:
            raise ValueError("ProblemSpecification needs research_questions or subproblems")
        return self
