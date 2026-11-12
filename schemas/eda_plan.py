"""Problem-aware EDA plan contracts (Phase 3).

Plans guide independent profiling and relationship review. They never encode an
automatic merge, concatenation, resample, or unit conversion.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EDA_PLAN_VERSION = "1.0"
JoinStance = Literal["suggest_preview", "cannot_join", "abstain", "side_by_side_only"]
MatchStatus = Literal["matched", "missing_upload", "unexpected_upload", "unmatched"]


class DatasetMatchItem(BaseModel):
    """How one uploaded file relates to ProblemSpecification.supplied_datasets."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str | None = None
    upload_file_name: str | None = None
    expected_file_name: str | None = None
    status: MatchStatus
    notes: str = Field(default="", max_length=800)


class ConstraintReminder(BaseModel):
    """A ProblemSpecification constraint that must shape EDA / later modeling."""

    model_config = ConfigDict(extra="forbid")

    constraint_id: str
    statement: str = Field(min_length=3, max_length=2000)
    constraint_kind: str
    provenance: str
    eda_implication: str = Field(min_length=3, max_length=1000)


class SuggestedRelationship(BaseModel):
    """A relationship suggestion grounded in evidence — never an executed join."""

    model_config = ConfigDict(extra="forbid")

    left_dataset_id: str
    right_dataset_id: str
    left_display_name: str
    right_display_name: str
    left_column: str | None = None
    right_column: str | None = None
    stance: JoinStance
    evidence_summary: str = Field(min_length=3, max_length=2000)
    caveats: list[str] = Field(default_factory=list, max_length=16)
    auto_join_allowed: Literal[False] = False


class FocusColumn(BaseModel):
    """Per-dataset columns to emphasize during independent EDA."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    display_name: str
    file_name: str
    qualified_columns: list[str] = Field(default_factory=list, max_length=64)
    focus_notes: list[str] = Field(default_factory=list, max_length=16)


class ProblemAwareEDAPlan(BaseModel):
    """Deterministic EDA guidance conditioned on ProblemSpecification when present."""

    model_config = ConfigDict(extra="forbid")

    plan_version: Literal["1.0"] = EDA_PLAN_VERSION
    problem_id: str | None = None
    title: str | None = None
    strategy: Literal["deterministic"] = "deterministic"
    has_problem_specification: bool
    dataset_matches: list[DatasetMatchItem] = Field(default_factory=list, max_length=32)
    constraint_reminders: list[ConstraintReminder] = Field(default_factory=list, max_length=32)
    focus_by_dataset: list[FocusColumn] = Field(default_factory=list, max_length=8)
    suggested_relationships: list[SuggestedRelationship] = Field(
        default_factory=list, max_length=16
    )
    must_not: list[str] = Field(default_factory=list, max_length=24)
    analysis_notes: list[str] = Field(default_factory=list, max_length=32)
    joined: Literal[False] = False
    invented_joins: Literal[False] = False

    @model_validator(mode="after")
    def _no_auto_join(self) -> ProblemAwareEDAPlan:
        if any(item.auto_join_allowed for item in self.suggested_relationships):
            raise ValueError("Problem-aware EDA plans cannot allow automatic joins.")
        return self
