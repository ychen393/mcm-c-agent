"""Phase 1 persistence contracts.

These models carry project, run, dataset, artifact, and approval identity.
They never include raw file bytes, API keys, or LLM secrets. Sanitization is
fail-closed: forbidden keys or raw payloads raise before any write.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tools.data_loader import safe_project_id

ProjectLifecycle = Literal[
    "created",
    "project_initialized",
    "datasets_recorded",
    "problem_analysis_running",
    "problem_analysis_ready",
    "problem_analysis_failed",
    "data_analysis_done",
    "research_task_complete",
]
RunStatus = Literal["active", "stale", "completed", "archived"]
ApprovalGate = Literal["H1", "H2", "H3", "chart_plan", "other"]
ApprovalStatus = Literal["pending", "approved", "rejected", "invalidated"]
BackendKind = Literal["postgres", "local"]
DataResumeMode = Literal["reupload_required"]

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
        "top_values",
        "numeric_summary",
        "numeric_correlations",
    }
)

# Provenance-only keys permitted inside uploaded_files records.
ALLOWED_UPLOAD_FILE_KEYS = frozenset(
    {
        "dataset_id",
        "position",
        "file_name",
        "display_name",
        "file_extension",
        "file_size_bytes",
        "sha256",
        "row_count",
        "column_count",
        "duplicate_row_count",
        "column_names",
        "qualified_column_names",
        "warnings",
        "period_start",
        "period_end",
        "joined",
    }
)

REUPLOAD_REQUIRED_MESSAGE = (
    "Reopen restores project provenance and run history only. "
    "Uploaded file bytes and DataFrames are not stored — re-upload the same files "
    "(matching SHA-256) before continuing EDA or chart planning."
)


def is_forbidden_key(key: Any) -> bool:
    text = str(key)
    lowered = text.lower()
    if text in FORBIDDEN_STATE_KEYS:
        return True
    if "api_key" in lowered or "apikey" in lowered:
        return True
    if lowered in {"password", "secret", "token", "authorization", "private_key"}:
        return True
    if lowered.endswith("_secret") or lowered.endswith("_token"):
        return True
    return False


def assert_safe_for_persistence(value: Any, path: str = "state") -> None:
    """Fail closed: raise if secret-shaped keys or raw payloads are present."""
    if isinstance(value, (bytes, bytearray)):
        raise ValueError(f"Refusing to persist raw bytes at {path}.")
    if isinstance(value, dict):
        for key, item in value.items():
            if is_forbidden_key(key):
                # Do not interpolate the secret value into the error.
                raise ValueError(f"Refusing to persist forbidden key '{key}' at {path}.")
            assert_safe_for_persistence(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_safe_for_persistence(item, f"{path}[{index}]")
    elif isinstance(value, (str, int, float, bool)) or value is None:
        return
    else:
        # Reject unexpected object types rather than pickle-like surprises.
        raise ValueError(f"Refusing to persist unsupported type {type(value).__name__} at {path}.")


def sanitize_uploaded_file_record(item: Any, *, path: str) -> dict[str, Any]:
    """Keep only allowlisted provenance fields; fail closed on secrets/bytes."""
    if not isinstance(item, dict):
        raise ValueError(f"uploaded_files entries must be objects at {path}.")
    assert_safe_for_persistence(item, path)
    cleaned: dict[str, Any] = {}
    for key, value in item.items():
        if key not in ALLOWED_UPLOAD_FILE_KEYS:
            # Unknown nested extras are not stored.
            continue
        cleaned[key] = value
    if not (cleaned.get("dataset_id") and cleaned.get("file_name") and cleaned.get("sha256")):
        raise ValueError(f"uploaded_files entry at {path} is missing required provenance fields.")
    cleaned["joined"] = False
    return cleaned


def sanitize_state_for_persistence(data: Any) -> dict[str, Any]:
    """Validate and return a persistence-safe ResearchState mapping."""
    if not isinstance(data, dict):
        raise ValueError("ResearchState must be a mapping.")
    assert_safe_for_persistence(data, "state")
    cleaned = dict(data)
    uploads = cleaned.get("uploaded_files") or []
    if not isinstance(uploads, list):
        raise ValueError("uploaded_files must be a list.")
    cleaned["uploaded_files"] = [
        sanitize_uploaded_file_record(item, path=f"state.uploaded_files[{index}]")
        for index, item in enumerate(uploads)
    ]
    metadata = cleaned.get("dataset_metadata") or {}
    if metadata and not isinstance(metadata, dict):
        raise ValueError("dataset_metadata must be an object.")
    if isinstance(metadata, dict):
        assert_safe_for_persistence(metadata, "state.dataset_metadata")
        metadata = dict(metadata)
        metadata["raw_rows_included"] = False
        metadata["file_bytes_included"] = False
        metadata["joined"] = False
        metadata["data_resume"] = "reupload_required"
        cleaned["dataset_metadata"] = metadata
    cleaned["data_resume"] = "reupload_required"
    # Snapshot validation (known fields + remaining extras still secret-scanned).
    snapshot = ResearchStateSnapshot.model_validate(cleaned)
    dumped = snapshot.model_dump(mode="python")
    assert_safe_for_persistence(dumped, "state")
    return dumped


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
        assert_safe_for_persistence(self.metadata, "artifact.metadata")
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
    """Validated ResearchState payload for disk/DB.

    Extra top-level research fields are allowed only after recursive secret
    scanning. File bytes and API keys are never accepted.
    """

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
    problem_specification: dict[str, Any] = Field(default_factory=dict)
    data_resume: DataResumeMode = "reupload_required"

    @model_validator(mode="before")
    @classmethod
    def _reject_forbidden(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        assert_safe_for_persistence(data, "state")
        return data

    @model_validator(mode="after")
    def _uploads_are_provenance(self) -> ResearchStateSnapshot:
        cleaned_uploads = [
            sanitize_uploaded_file_record(item, path=f"state.uploaded_files[{index}]")
            for index, item in enumerate(self.uploaded_files)
        ]
        object.__setattr__(self, "uploaded_files", cleaned_uploads)
        object.__setattr__(self, "data_resume", "reupload_required")
        return self


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
    backend_changed: bool = False
    previous_backend: str | None = None
    backend_mismatch_message: str | None = None
