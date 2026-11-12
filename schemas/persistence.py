"""Phase 1 persistence contracts.

These models carry project, run, dataset, artifact, and approval identity.
They never include raw file bytes, API keys, or LLM secrets.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tools.data_loader import safe_project_id

ProjectLifecycle = Literal[
    "created",
    "project_initialized",
    "datasets_recorded",
    "data_analysis_done",
    "research_task_complete",
]
RunStatus = Literal["active", "stale", "completed", "archived"]
ApprovalGate = Literal["H1", "H2", "H3", "chart_plan", "other"]
ApprovalStatus = Literal["pending", "approved", "rejected", "invalidated"]
BackendKind = Literal["postgres", "local"]

FORBIDDEN_STATE_KEYS = frozenset(
    {
        "api_key",
        "anthropic_api_key",
        "content",
        "deepseek_api_key",
        "frame",
        "llm_api_key",
        "openai_api_key",
        "preview_rows",
        "raw_bytes",
        "sample_values",
    }
)


class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=80)
    project_name: str = Field(min_length=3, max_length=120)
    description: str = ""
    lifecycle: ProjectLifecycle = "created"
    active_run_id: str | None = None
    created_at: str
    updated_at: str
    input_signature: str | None = None

    @field_validator("project_id")
    @classmethod
    def _project_id(cls, value: str) -> str:
        return safe_project_id(value)


class ResearchRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(pattern=r"^run_[0-9a-f]{12}$")
    project_id: str = Field(min_length=1, max_length=80)
    version: int = Field(ge=1)
    status: RunStatus = "active"
    lifecycle: ProjectLifecycle = "project_initialized"
    input_signature: str
    created_at: str
    updated_at: str
    parent_run_id: str | None = None
    note: str = ""

    @field_validator("project_id")
    @classmethod
    def _project_id(cls, value: str) -> str:
        return safe_project_id(value)


class DatasetRefRecord(BaseModel):
    """Persisted dataset provenance. No rows, no file bytes."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    project_id: str
    run_id: str
    file_name: str
    display_name: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_extension: str
    file_size_bytes: int = Field(ge=1)
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    column_names: list[str] = Field(default_factory=list)
    qualified_column_names: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    position: int = Field(ge=0, default=0)


class ArtifactRefRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(pattern=r"^art_[0-9a-f]{12}$")
    project_id: str
    run_id: str
    kind: str
    uri: str
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    label: str = ""
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _no_secrets(self) -> ArtifactRefRecord:
        for key in self.metadata:
            if key in FORBIDDEN_STATE_KEYS or "api_key" in key.lower():
                raise ValueError(f"Artifact metadata cannot contain {key}.")
        return self


class ApprovalDecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str = Field(pattern=r"^apr_[0-9a-f]{12}$")
    project_id: str
    run_id: str
    gate: ApprovalGate
    status: ApprovalStatus
    version: int = Field(ge=1, default=1)
    decided_at: str | None = None
    notes: str = ""
    subject_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ResearchStateSnapshot(BaseModel):
    """Validated ResearchState payload for disk/DB. Rejects secret-shaped keys."""

    model_config = ConfigDict(extra="allow")

    project_id: str
    project_name: str
    project_status: str = "initialized"
    current_stage: str = "project_initialized"
    analysis_status: str = "not_started"
    lifecycle: ProjectLifecycle = "project_initialized"
    run_id: str | None = None
    problem_text: str = ""
    uploaded_files: list[dict[str, Any]] = Field(default_factory=list)
    dataset_metadata: dict[str, Any] = Field(default_factory=dict)
    workspace_phases: dict[str, str] = Field(default_factory=dict)
    approval_status: dict[str, str] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _strip_forbidden(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        cleaned = dict(data)
        for key in list(cleaned):
            if key in FORBIDDEN_STATE_KEYS or "api_key" in str(key).lower():
                cleaned.pop(key)
        return cleaned


class ProjectHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    version: int
    status: RunStatus
    lifecycle: ProjectLifecycle
    input_signature: str
    created_at: str
    updated_at: str
    note: str = ""
    dataset_count: int = 0


class StoreInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: BackendKind
    detail: str
    root: str | None = None
