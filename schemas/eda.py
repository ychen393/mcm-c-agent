from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class ColumnProfile(BaseModel):
    name: str
    dtype: str
    missing_count: int
    missing_rate: float = Field(ge=0, le=1)
    unique_count: int
    sample_values: list[Any] = Field(default_factory=list)
    numeric_summary: dict[str, float | None] | None = None
    outlier_count_iqr: int | None = None
    top_values: list[dict[str, Any]] | None = None
    datetime_min: str | None = None
    datetime_max: str | None = None

class DatasetMetadata(BaseModel):
    file_name: str
    file_extension: str
    file_size_bytes: int
    sha256: str
    loaded_at_utc: datetime
    row_count: int
    column_count: int
    duplicate_row_count: int
    columns: list[ColumnProfile]

class EDAReport(BaseModel):
    report_version: str = "1.0"
    project_id: str
    dataset: DatasetMetadata
    numeric_correlations: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    generated_at_utc: datetime
    chart_paths: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
