"""Evidence for cross-dataset keys and an explicit, non-persistent join preview.

These models carry column statistics and a bounded preview. They never carry a
source frame or the original file bytes.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RELATIONSHIP_VERSION = "1.0"
MAX_PREVIEW_ROWS = 100
MAX_JOIN_ROWS = 5_000
MAX_JOIN_COLUMNS = 60

CARDINALITY = (
    "ONE_TO_ONE",
    "ONE_TO_MANY",
    "MANY_TO_ONE",
    "MANY_TO_MANY",
    "NO_OVERLAP",
    "UNKNOWN",
)
PAIR_VERDICT = (*CARDINALITY, "UNRELATED")
SAFE_CARDINALITY = ("ONE_TO_ONE", "ONE_TO_MANY", "MANY_TO_ONE")
JOIN_TYPES = ("inner", "left", "right", "outer")
BLOCK_REASONS = (
    "many_to_many",
    "oversized_result",
    "untrusted_key",
    "invalid_join_strategy",
    "unknown_dataset",
    "incompatible_dtype",
    "unit_mismatch",
    "frequency_mismatch",
    "cannot_safely_join",
    "same_dataset",
)

RELATIONSHIP_LIMITATIONS: tuple[str, ...] = (
    (
        "Candidates come from exact column names or exact ISO date columns. "
        "Similar names are not matched."
    ),
    (
        "Statistics are computed without joining. An ambiguous pair stays UNKNOWN "
        "until a person chooses keys."
    ),
    "A preview runs only after an explicit request. It is not saved and is not a new dataset.",
    (
        "Many-to-many keys, mismatched date frequencies, mismatched key units, "
        "incompatible types, unknown keys, and oversized results are refused."
    ),
    "The preview does not aggregate, impute, resample, convert time zones, or convert units.",
    (
        f"A result above {MAX_JOIN_ROWS:,} rows or {MAX_JOIN_COLUMNS} columns is refused. "
        f"At most {MAX_PREVIEW_ROWS} rows are shown."
    ),
)


class KeyEvidence(BaseModel):
    """One candidate key, measured on each side without matching the row frames."""

    model_config = ConfigDict(extra="forbid")

    left_dataset_id: str
    right_dataset_id: str
    left_column: str
    right_column: str
    left_qualified_column: str
    right_qualified_column: str
    left_dtype: str
    right_dtype: str
    left_null_count: int = Field(ge=0)
    right_null_count: int = Field(ge=0)
    left_null_rate: float = Field(ge=0, le=1)
    right_null_rate: float = Field(ge=0, le=1)
    left_unique_count: int = Field(ge=0)
    right_unique_count: int = Field(ge=0)
    left_duplicate_key_count: int = Field(ge=0)
    right_duplicate_key_count: int = Field(ge=0)
    left_rows_in_duplicate_keys: int = Field(ge=0)
    right_rows_in_duplicate_keys: int = Field(ge=0)
    overlap_key_count: int = Field(ge=0)
    left_unmatched_key_count: int = Field(ge=0)
    right_unmatched_key_count: int = Field(ge=0)
    left_unmatched_row_count: int = Field(ge=0)
    right_unmatched_row_count: int = Field(ge=0)
    left_overlap_rate: float | None = Field(default=None, ge=0, le=1)
    right_overlap_rate: float | None = Field(default=None, ge=0, le=1)
    cardinality: Literal[
        "ONE_TO_ONE",
        "ONE_TO_MANY",
        "MANY_TO_ONE",
        "MANY_TO_MANY",
        "NO_OVERLAP",
        "UNKNOWN",
    ]
    estimated_inner_rows: int = Field(ge=0)
    estimated_left_rows: int = Field(ge=0)
    estimated_right_rows: int = Field(ge=0)
    estimated_outer_rows: int = Field(ge=0)
    left_frequency: str | None = None
    right_frequency: str | None = None
    mixed_frequency: bool
    dtype_compatible: bool
    unit_conflict: bool
    caveats: list[str]
    safe_to_preview: bool

    @model_validator(mode="after")
    def _safe_candidate_is_defensible(self) -> KeyEvidence:
        if self.safe_to_preview:
            if self.mixed_frequency or self.unit_conflict or not self.dtype_compatible:
                raise ValueError(
                    "A safe candidate cannot have a type, unit, or frequency conflict."
                )
            if self.cardinality not in SAFE_CARDINALITY or self.overlap_key_count < 1:
                raise ValueError("A safe candidate needs overlap and a one-sided key cardinality.")
        return self


class PairRelationship(BaseModel):
    """Every candidate between two datasets, plus the pair-level verdict."""

    model_config = ConfigDict(extra="forbid")

    left_dataset_id: str
    right_dataset_id: str
    left_display_name: str
    right_display_name: str
    left_sha256: str
    right_sha256: str
    verdict: Literal[
        "ONE_TO_ONE",
        "ONE_TO_MANY",
        "MANY_TO_ONE",
        "MANY_TO_MANY",
        "NO_OVERLAP",
        "UNKNOWN",
        "UNRELATED",
    ]
    can_safely_join: bool
    state: Literal["candidate", "cannot safely join", "ambiguous"]
    caveats: list[str]
    candidates: list[KeyEvidence]

    @model_validator(mode="after")
    def _state_matches_evidence(self) -> PairRelationship:
        if self.state == "cannot safely join" and self.can_safely_join:
            raise ValueError("A pair that cannot safely join cannot be marked safe.")
        if self.verdict == "UNRELATED" and self.candidates:
            raise ValueError("An unrelated pair cannot list candidate keys.")
        if self.verdict == "UNKNOWN" and self.can_safely_join:
            raise ValueError("An UNKNOWN pair is not a single safe relationship.")
        return self


class RelationshipReport(BaseModel):
    """Bounded pair report. `joined` stays false because nothing was merged."""

    model_config = ConfigDict(extra="forbid")

    relationship_version: Literal["1.0"] = RELATIONSHIP_VERSION
    project_id: str
    dataset_ids: list[str] = Field(min_length=2, max_length=5)
    pairs: list[PairRelationship]
    limitations: list[str]
    joined: Literal[False] = False
    persisted: Literal[False] = False

    @model_validator(mode="after")
    def _limitations_stay_visible(self) -> RelationshipReport:
        if self.limitations != list(RELATIONSHIP_LIMITATIONS):
            raise ValueError("Relationship limitations are fixed for this slice.")
        return self


class JoinLineage(BaseModel):
    """Provenance for one explicit preview. All mutation flags stay false."""

    model_config = ConfigDict(extra="forbid")

    left_dataset_id: str
    right_dataset_id: str
    left_file_name: str
    right_file_name: str
    left_sha256: str
    right_sha256: str
    left_column: str
    right_column: str
    left_qualified_key: str
    right_qualified_key: str
    join_type: str
    persisted: Literal[False] = False
    aggregated: Literal[False] = False
    imputed: Literal[False] = False
    resampled: Literal[False] = False
    timezone_converted: Literal[False] = False
    units_coerced: Literal[False] = False
    source_mutated: Literal[False] = False


class JoinPreviewResult(BaseModel):
    """A refused join or a bounded preview. Source datasets stay unchanged."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["preview", "blocked"]
    reason: str | None = None
    message: str
    warnings: list[str]
    caveats: list[str]
    lineage: JoinLineage | None = None
    preview_rows: list[dict[str, Any]]
    preview_columns: list[str]
    preview_row_count: int = Field(ge=0)
    output_row_count: int | None = Field(default=None, ge=0)
    output_column_count: int | None = Field(default=None, ge=0)
    truncated: bool
    unmatched_left_rows: int | None = Field(default=None, ge=0)
    unmatched_right_rows: int | None = Field(default=None, ge=0)
    overlap_key_count: int | None = Field(default=None, ge=0)
    cardinality: str | None = None
    persisted: Literal[False] = False
    source_mutated: Literal[False] = False

    @model_validator(mode="after")
    def _blocked_preview_is_empty(self) -> JoinPreviewResult:
        if self.status == "blocked":
            if self.preview_rows or self.truncated or self.output_row_count:
                raise ValueError("A blocked join cannot return preview rows.")
            if self.reason not in BLOCK_REASONS:
                raise ValueError("A blocked join needs a known reason.")
        if self.status == "preview" and self.reason is not None:
            raise ValueError("A successful preview does not carry a block reason.")
        return self
