"""Versioned Mathematical Modeling & Experiment contracts (Phase 6).

Experiment runs link to an approved research proposal / H1 selection and carry
params, code refs, metrics, and compact artifacts. Runs require human H1
approval in ResearchState — never auto-approve and never invent live market
results.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ExperimentStrategy = Literal["deterministic_fixture", "sandboxed_python", "hybrid"]
ExperimentStatus = Literal["planned", "running", "completed", "blocked", "failed"]
CodeRefKind = Literal[
    "module_path",
    "function_name",
    "strategy_id",
    "fixture_id",
    "prompt_version",
]
MetricKind = Literal[
    "terminal_value",
    "total_return",
    "n_trades",
    "transaction_cost_paid",
    "max_drawdown",
    "cash_end",
    "gold_oz_end",
    "bitcoin_end",
    "other",
]
ArtifactKind = Literal[
    "equity_curve_summary",
    "trade_log_summary",
    "constraint_snapshot",
    "price_fixture_ref",
    "run_config",
    "other",
]


class ExperimentCodeRef(BaseModel):
    """Pointer to deterministic code / strategy identity used for a run."""

    model_config = ConfigDict(extra="forbid")

    kind: CodeRefKind
    value: str = Field(min_length=1, max_length=240)
    note: str | None = Field(default=None, max_length=500)


class ExperimentParams(BaseModel):
    """Runnable parameters for a modeling experiment."""

    model_config = ConfigDict(extra="forbid")

    initial_cash: float = Field(gt=0, le=1_000_000)
    alpha_gold: float = Field(ge=0, le=1, description="Commission fraction on gold trades")
    alpha_bitcoin: float = Field(ge=0, le=1, description="Commission fraction on bitcoin trades")
    assets: list[str] = Field(default_factory=list, max_length=8)
    past_data_only: bool = True
    strategy_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    lookback_days: int = Field(default=3, ge=1, le=60)
    rebalance_every_n_days: int = Field(default=5, ge=1, le=60)
    price_fixture_id: str = Field(default="fx_2022_mcm_c_prices_v1", max_length=80)
    allow_sandboxed_python: bool = False
    extra: dict[str, Any] = Field(default_factory=dict, max_length=16)

    @field_validator("assets")
    @classmethod
    def _normalize_assets(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip().lower() for item in value if str(item).strip()]
        return cleaned[:8]


class MetricResult(BaseModel):
    """One reported experiment metric (compact, persistence-safe)."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    kind: MetricKind = "other"
    label: str = Field(min_length=1, max_length=120)
    value: float
    unit: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=400)


class ModelArtifactRef(BaseModel):
    """Compact artifact descriptor (no raw bytes / dense frames)."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    kind: ArtifactKind = "other"
    summary: str = Field(min_length=3, max_length=2000)
    payload: dict[str, Any] = Field(default_factory=dict, max_length=32)
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ProblemConstraintSnapshot(BaseModel):
    """Constraints respected (or defaulted) for the run."""

    model_config = ConfigDict(extra="forbid")

    problem_id: str | None = Field(default=None, max_length=64)
    initial_cash: float
    alpha_gold: float
    alpha_bitcoin: float
    assets: list[str] = Field(default_factory=list, max_length=8)
    past_data_only: bool = True
    gold_trade_weekdays_only: bool = True
    source: Literal["problem_specification", "defaults_2022_mcm_c", "explicit_params"] = (
        "defaults_2022_mcm_c"
    )
    notes: list[str] = Field(default_factory=list, max_length=16)


class ExperimentRun(BaseModel):
    """One modeling experiment attempt linked to an approved proposal."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    run_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    status: ExperimentStatus = "planned"
    strategy: ExperimentStrategy = "deterministic_fixture"
    proposal_id: str = Field(min_length=1, max_length=64)
    selected_candidate_id: str = Field(min_length=1, max_length=64)
    candidate_title: str | None = Field(default=None, max_length=200)
    method_family: str | None = Field(default=None, max_length=120)
    h1_status: Literal["approved"] = "approved"
    h1_decision_id: str | None = Field(default=None, max_length=64)
    params: ExperimentParams
    code_refs: list[ExperimentCodeRef] = Field(default_factory=list, max_length=16)
    metrics: list[MetricResult] = Field(default_factory=list, max_length=32)
    artifacts: list[ModelArtifactRef] = Field(default_factory=list, max_length=24)
    constraints: ProblemConstraintSnapshot
    started_at_utc: str | None = Field(default=None, max_length=64)
    finished_at_utc: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=2000)
    analysis_notes: list[str] = Field(default_factory=list, max_length=32)
    sandboxed_python_attempted: bool = False
    sandboxed_python_note: str | None = Field(default=None, max_length=1000)
    live_trading_api_used: bool = False
    invented_results: bool = False
    agent_prompt_version: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _integrity(self) -> ExperimentRun:
        if self.invented_results:
            raise ValueError("ExperimentRun must not invent results")
        if self.live_trading_api_used:
            raise ValueError("ExperimentRun must not call live trading APIs")
        if self.h1_status != "approved":
            raise ValueError("ExperimentRun requires h1_status=approved")
        if self.status == "completed" and not self.metrics:
            raise ValueError("completed ExperimentRun requires metrics")
        return self


class ExperimentReport(BaseModel):
    """Panel / persistence envelope for the latest Phase 6 experiment slice."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    report_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    problem_id: str | None = Field(default=None, max_length=64)
    proposal_id: str = Field(min_length=1, max_length=64)
    selected_candidate_id: str = Field(min_length=1, max_length=64)
    h1_approved: bool = True
    modeling_allowed: bool = True
    runs: list[ExperimentRun] = Field(default_factory=list, max_length=8)
    latest_run_id: str | None = Field(default=None, max_length=64)
    strategy: ExperimentStrategy = "deterministic_fixture"
    invented_results: bool = False
    live_trading_api_used: bool = False
    agent_prompt_version: str | None = Field(default=None, max_length=80)
    analysis_notes: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _integrity(self) -> ExperimentReport:
        if self.invented_results:
            raise ValueError("ExperimentReport must not invent results")
        if self.live_trading_api_used:
            raise ValueError("ExperimentReport must not use live trading APIs")
        if not self.h1_approved or not self.modeling_allowed:
            raise ValueError("ExperimentReport requires H1-approved modeling gate")
        if self.latest_run_id:
            ids = {run.run_id for run in self.runs}
            if self.latest_run_id not in ids:
                raise ValueError(
                    f"latest_run_id '{self.latest_run_id}' is not among runs"
                )
        if any(run.invented_results for run in self.runs):
            raise ValueError("ExperimentReport contains invented run results")
        return self
