"""Versioned Validation / Sensitivity / H2 contracts (Phase 7).

Validation reports link to Phase 6 experiment results and record deterministic
sensitivity scenarios (param / cost / window perturbations). H2 approval is
human-only — never auto-approved. Paper / LaTeX (Phase 8) stays blocked until
``approval_status.h2 == approved``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ValidationStrategy = Literal["deterministic_fixture", "llm_critique", "hybrid"]
ScenarioKind = Literal["baseline", "param", "cost", "window", "combined", "other"]
PerturbationTarget = Literal[
    "alpha_gold",
    "alpha_bitcoin",
    "lookback_days",
    "rebalance_every_n_days",
    "initial_cash",
    "other",
]
RobustnessSeverity = Literal["info", "low", "medium", "high", "blocking"]
H2DecisionStatus = Literal["pending", "approved", "revision_requested", "rejected"]
ValidationGateReason = Literal[
    "h1_not_approved",
    "h1_pending",
    "h1_revision_requested",
    "h1_rejected",
    "h1_absent",
    "no_experiment_results",
    "experiment_incomplete",
    "validation_allowed",
]
PaperGateReason = Literal[
    "h2_not_decided",
    "h2_pending",
    "h2_revision_requested",
    "h2_rejected",
    "h2_approved",
    "no_validation_report",
]


class MetricSnapshot(BaseModel):
    """Compact metric value captured for baseline or a sensitivity scenario."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    kind: str = Field(default="other", max_length=64)
    label: str = Field(min_length=1, max_length=120)
    value: float
    unit: str | None = Field(default=None, max_length=40)


class MetricDelta(BaseModel):
    """Change in one metric relative to the baseline experiment run."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    label: str = Field(min_length=1, max_length=120)
    baseline_value: float
    scenario_value: float
    absolute_delta: float
    relative_delta: float | None = None
    unit: str | None = Field(default=None, max_length=40)


class PerturbationSpec(BaseModel):
    """One parameter / cost / window perturbation applied in a scenario."""

    model_config = ConfigDict(extra="forbid")

    target: PerturbationTarget
    description: str = Field(min_length=3, max_length=400)
    baseline_value: float | int | str | None = None
    scenario_value: float | int | str | None = None
    relative_change: float | None = None


class SensitivityScenario(BaseModel):
    """One deterministic sensitivity / scenario evaluation."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    kind: ScenarioKind = "other"
    label: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=1500)
    baseline_run_id: str = Field(min_length=1, max_length=64)
    perturbations: list[PerturbationSpec] = Field(default_factory=list, max_length=16)
    metrics: list[MetricSnapshot] = Field(default_factory=list, max_length=32)
    deltas: list[MetricDelta] = Field(default_factory=list, max_length=32)
    status: Literal["completed", "skipped", "failed"] = "completed"
    notes: list[str] = Field(default_factory=list, max_length=16)
    invented_results: bool = False

    @model_validator(mode="after")
    def _no_invented(self) -> SensitivityScenario:
        if self.invented_results:
            raise ValueError(
                f"scenario '{self.scenario_id}' must not invent results"
            )
        if self.status == "completed" and not self.metrics:
            raise ValueError(
                f"completed scenario '{self.scenario_id}' requires metrics"
            )
        return self


class RobustnessNote(BaseModel):
    """Human-readable robustness / sensitivity observation."""

    model_config = ConfigDict(extra="forbid")

    note_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    severity: RobustnessSeverity = "info"
    summary: str = Field(min_length=3, max_length=1000)
    related_scenario_ids: list[str] = Field(default_factory=list, max_length=16)
    related_metric_ids: list[str] = Field(default_factory=list, max_length=16)


class ValidationReport(BaseModel):
    """Panel / persistence envelope for Phase 7 validation & sensitivity."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    report_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    problem_id: str | None = Field(default=None, max_length=64)
    proposal_id: str = Field(min_length=1, max_length=64)
    selected_candidate_id: str = Field(min_length=1, max_length=64)
    baseline_run_id: str = Field(min_length=1, max_length=64)
    baseline_experiment_report_id: str | None = Field(default=None, max_length=64)
    h1_approved: bool = True
    validation_allowed: bool = True
    strategy: ValidationStrategy = "deterministic_fixture"
    llm_enabled: bool = False
    llm_attempted: bool = False
    llm_note: str | None = Field(default=None, max_length=1000)
    baseline_metrics: list[MetricSnapshot] = Field(default_factory=list, max_length=32)
    scenarios: list[SensitivityScenario] = Field(default_factory=list, max_length=24)
    robustness_notes: list[RobustnessNote] = Field(default_factory=list, max_length=32)
    invented_results: bool = False
    live_trading_api_used: bool = False
    agent_prompt_version: str | None = Field(default=None, max_length=80)
    analysis_notes: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _integrity(self) -> ValidationReport:
        if self.invented_results:
            raise ValueError("ValidationReport must not invent results")
        if self.live_trading_api_used:
            raise ValueError("ValidationReport must not use live trading APIs")
        if not self.h1_approved or not self.validation_allowed:
            raise ValueError(
                "ValidationReport requires H1-approved validation gate"
            )
        if any(s.invented_results for s in self.scenarios):
            raise ValueError("ValidationReport contains invented scenario results")
        if not self.baseline_metrics:
            raise ValueError("ValidationReport requires baseline_metrics")
        if not self.scenarios:
            raise ValueError("ValidationReport requires at least one scenario")
        return self


class H2Decision(BaseModel):
    """Human-only H2 validation / sensitivity approval record."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    gate: Literal["H2"] = "H2"
    status: H2DecisionStatus
    validation_report_id: str = Field(min_length=1, max_length=64)
    baseline_run_id: str | None = Field(default=None, max_length=64)
    proposal_id: str | None = Field(default=None, max_length=64)
    notes: str = Field(default="", max_length=4000)
    decided_by: Literal["human"] = "human"
    auto_approved: bool = False
    decided_at_utc: str | None = Field(default=None, max_length=64)
    validation_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _human_only(self) -> H2Decision:
        if self.auto_approved:
            raise ValueError("H2 must never be auto-approved")
        if self.decided_by != "human":
            raise ValueError("H2 decisions must be human")
        if self.status in {"approved", "revision_requested", "rejected"} and not self.decided_at_utc:
            raise ValueError(f"H2 status '{self.status}' requires decided_at_utc")
        return self


class ValidationGateStatus(BaseModel):
    """Explicit gate: Validation runs only with H1 approved + experiment results."""

    model_config = ConfigDict(extra="forbid")

    validation_allowed: bool = False
    h1_status: Literal[
        "pending", "approved", "revision_requested", "rejected", "absent"
    ] = "absent"
    has_experiment_results: bool = False
    baseline_run_id: str | None = Field(default=None, max_length=64)
    reason: ValidationGateReason = "h1_not_approved"
    message: str = Field(min_length=3, max_length=500)

    @field_validator("validation_allowed")
    @classmethod
    def _default_blocked(cls, value: bool) -> bool:
        return bool(value)

    @model_validator(mode="after")
    def _consistent(self) -> ValidationGateStatus:
        if self.validation_allowed and self.h1_status != "approved":
            raise ValueError("validation_allowed requires h1_status=approved")
        if self.validation_allowed and not self.has_experiment_results:
            raise ValueError("validation_allowed requires experiment results")
        if self.validation_allowed and self.reason != "validation_allowed":
            raise ValueError("validation_allowed requires reason=validation_allowed")
        if not self.validation_allowed and self.reason == "validation_allowed":
            raise ValueError("blocked gate cannot claim validation_allowed")
        return self


class PaperGateStatus(BaseModel):
    """Explicit gate: Paper Planner / LaTeX stays blocked until H2 approved."""

    model_config = ConfigDict(extra="forbid")

    paper_allowed: bool = False
    h2_status: H2DecisionStatus | Literal["absent"] = "absent"
    reason: PaperGateReason = "h2_not_decided"
    message: str = Field(min_length=3, max_length=500)

    @field_validator("paper_allowed")
    @classmethod
    def _default_blocked(cls, value: bool) -> bool:
        return bool(value)

    @model_validator(mode="after")
    def _consistent(self) -> PaperGateStatus:
        if self.paper_allowed and self.h2_status != "approved":
            raise ValueError("paper_allowed requires h2_status=approved")
        if self.paper_allowed and self.reason != "h2_approved":
            raise ValueError("paper_allowed requires reason=h2_approved")
        if not self.paper_allowed and self.reason == "h2_approved":
            raise ValueError("blocked paper gate cannot claim h2_approved")
        return self
