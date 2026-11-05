"""Versioned chart specification. No executable expressions."""
from typing import Literal
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, model_validator

ChartType = Literal["histogram", "time_series", "bar", "scatter", "box_plot"]

class ChartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chart_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    chart_type: ChartType
    title: str = Field(min_length=3, max_length=180)
    figure_label: str = Field(pattern=r"^fig:[a-z][a-z0-9_-]{0,63}$")
    x: str
    y: str | None = None
    x_label: str = Field(min_length=1)
    y_label: str = Field(min_length=1)
    x_unit: str | None = None
    y_unit: str | None = None
    legend: list[str] = Field(default_factory=list)
    caption: str = Field(min_length=8)
    analytical_question: str = Field(min_length=8)
    rationale: str = Field(min_length=8)
    priority: Literal["required", "recommended", "optional"] = "recommended"
    rank: int = Field(default=1, ge=1, le=12)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    analytical_role: Literal["distribution", "trend", "comparison", "relationship", "composition", "data_quality", "domain_specific"] = "distribution"
    caveats: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shape(self):
        if self.chart_type in ("time_series", "scatter") and not self.y:
            raise ValueError(f"{self.chart_type} requires y")
        return self

class ChartPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = "1.0"
    strategy: Literal["deterministic", "agent"] = "deterministic"
    charts: list[ChartSpec] = Field(default_factory=list, max_length=12)
    planning_summary: str | None = None
    problem_alignment: str | None = None
    planner_provider: str | None = None
    planner_model: str | None = None
    planner_prompt_version: str | None = None
    fallback_reason: str | None = None
    skipped_reasons: list[str] = Field(default_factory=list)

class ChartResult(BaseModel):
    chart_id: str
    figure_label: str
    path: str
    source_sha256: str
    spec: ChartSpec
    plotted_rows: int = Field(ge=0)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
    source_columns: list[str] = Field(default_factory=list)
    generated_at_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    chart_spec_version: str = "1.0"
