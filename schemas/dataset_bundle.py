"""Provenance contract for an offline multi-dataset registry.

The manifest records dataset identity and column scope only. It never carries
a data frame or the original file bytes.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.eda import EDAReport

BUNDLE_VERSION = "1.0"
BUNDLE_LIMITATIONS: tuple[str, ...] = (
    "Files are profiled independently and are not joined, concatenated, or aligned.",
    "Date alignment, resampling, and cross-dataset charts are not supported in this slice.",
    "No joint LLM call is made; each profile is a local EDA report and omits the data frame.",
    "An XLSX file is one dataset (the first worksheet only).",
)


class DatasetRef(BaseModel):
    """One uploaded file inside a bundle, without its rows."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(pattern=r"^ds_[a-z0-9-]+_[0-9a-f]{12}(?:_[0-9]+)?$")
    position: int = Field(ge=0, le=4)
    file_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    file_extension: str
    file_size_bytes: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    column_names: list[str] = Field(min_length=1)
    qualified_column_names: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _columns_align(self) -> DatasetRef:
        if len(self.column_names) != len(self.qualified_column_names):
            raise ValueError("Qualified column names must align with column names.")
        expected = [f"{self.dataset_id}.{name}" for name in self.column_names]
        if self.qualified_column_names != expected:
            raise ValueError("Qualified column names must be dataset_id.column_name.")
        return self


class DatasetBundleManifest(BaseModel):
    """Serializable, ordered registry of 1–5 datasets."""

    model_config = ConfigDict(extra="forbid")

    bundle_version: Literal["1.0"] = BUNDLE_VERSION
    project_id: str = Field(min_length=1)
    datasets: list[DatasetRef] = Field(min_length=1, max_length=5)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    joined: Literal[False] = False
    limitations: list[str] = Field(default_factory=lambda: list(BUNDLE_LIMITATIONS))

    @model_validator(mode="after")
    def _bundle_invariants(self) -> DatasetBundleManifest:
        if self.limitations != list(BUNDLE_LIMITATIONS):
            raise ValueError("Bundle limitations are fixed for this slice and cannot be removed.")
        ids = [item.dataset_id for item in self.datasets]
        if len(ids) != len(set(ids)):
            raise ValueError("Dataset IDs must be unique within a bundle.")
        if [item.position for item in self.datasets] != list(range(len(self.datasets))):
            raise ValueError("Dataset positions must be a contiguous order starting at 0.")
        hashes = [item.sha256 for item in self.datasets]
        if len(hashes) != len(set(hashes)):
            raise ValueError("Dataset bundle cannot contain duplicate content hashes.")
        display_names = [item.display_name for item in self.datasets]
        if len(display_names) != len(set(display_names)):
            raise ValueError("Display names must be unique within a bundle.")
        qualified = [name for item in self.datasets for name in item.qualified_column_names]
        if len(qualified) != len(set(qualified)):
            raise ValueError("Qualified column names must be unique across the bundle.")
        return self


class DatasetProfileContract(BaseModel):
    """One dataset ID mapped to its own EDA report.

    `report` is the existing single-dataset profile. It does not include the
    frame. Callers that need rows keep using the in-memory bundle locally.
    """

    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    project_id: str
    display_name: str
    file_name: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    report: EDAReport

    @model_validator(mode="after")
    def _matches_report(self) -> DatasetProfileContract:
        if self.project_id != self.report.project_id:
            raise ValueError("Profile project_id must match the EDA report.")
        if self.sha256 != self.report.dataset.sha256:
            raise ValueError("Profile sha256 must match the EDA report.")
        if self.file_name != self.report.dataset.file_name:
            raise ValueError("Profile file_name must match the EDA report.")
        return self

    def model_context(self) -> dict[str, Any]:
        """Compact profile for a future planner. Omits raw rows and file bytes."""
        dataset = self.report.dataset
        return {
            "dataset_id": self.dataset_id,
            "project_id": self.project_id,
            "display_name": self.display_name,
            "file_name": self.file_name,
            "sha256": self.sha256,
            "row_count": dataset.row_count,
            "column_count": dataset.column_count,
            "qualified_columns": [
                f"{self.dataset_id}.{column.name}" for column in dataset.columns
            ],
            "columns": [
                {
                    "name": column.name,
                    "qualified_name": f"{self.dataset_id}.{column.name}",
                    "dtype": column.dtype,
                    "missing_count": column.missing_count,
                    "unique_count": column.unique_count,
                }
                for column in dataset.columns
            ],
            "summary": self.report.summary,
            "warnings": self.report.warnings,
        }
