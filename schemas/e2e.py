"""Versioned Phase 9 E2E acceptance contracts (2022 MCM C).

The offline historical acceptance harness walks ProblemSpec → … → Paper/H3
using fixtures. Human H1/H2/H3 approvals in the harness are explicit **test
doubles** (simulated humans) — never production auto-approve. Product UI
gates remain human-only.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

E2EStepName = Literal[
    "problem_spec",
    "eda",
    "evidence",
    "research_h1",
    "modeling",
    "validation_h2",
    "paper_h3",
    "acceptance",
]
E2EStepStatus = Literal["passed", "failed", "skipped", "blocked"]
HumanGateName = Literal["H1", "H2", "H3"]
GateRepresentation = Literal["product_ui_human", "harness_test_double"]


class AcceptanceFactCheck(BaseModel):
    """One golden / regression acceptance assertion result."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    label: str = Field(min_length=3, max_length=200)
    expected: str = Field(min_length=1, max_length=500)
    observed: str = Field(min_length=1, max_length=1000)
    passed: bool
    notes: str | None = Field(default=None, max_length=500)


class HarnessGateRecord(BaseModel):
    """Provenance for a harness-applied human gate (test double only)."""

    model_config = ConfigDict(extra="forbid")

    gate: HumanGateName
    representation: GateRepresentation = "harness_test_double"
    status: Literal["approved", "revision_requested", "rejected"]
    decided_by: Literal["human"] = "human"
    auto_approved: Literal[False] = False
    harness_simulated_human: Literal[True] = True
    notes: str = Field(min_length=3, max_length=500)
    decision_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _never_auto(self) -> HarnessGateRecord:
        if self.auto_approved is not False:
            raise ValueError("Harness gate records must never set auto_approved=True")
        if self.representation != "harness_test_double":
            raise ValueError("HarnessGateRecord is only for harness test doubles")
        if not self.harness_simulated_human:
            raise ValueError("Harness gate must mark harness_simulated_human=True")
        return self


class E2EStepResult(BaseModel):
    """One step in the offline product-chain walk."""

    model_config = ConfigDict(extra="forbid")

    step: E2EStepName
    status: E2EStepStatus
    summary: str = Field(min_length=3, max_length=1000)
    artifact_ids: list[str] = Field(default_factory=list, max_length=32)
    details: dict[str, Any] = Field(default_factory=dict, max_length=32)


class E2EAcceptanceReport(BaseModel):
    """Typed Phase 9 historical E2E acceptance report (CI-safe)."""

    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    problem_id: Literal["2022_mcm_c"] = "2022_mcm_c"
    title: str = "2022 MCM C Trading Strategies — historical E2E acceptance"
    overall_passed: bool = False
    e2e_allowed: bool = False
    h3_required: Literal[True] = True
    h1_auto_approve: Literal[False] = False
    h2_auto_approve: Literal[False] = False
    h3_auto_approve: Literal[False] = False
    live_llm_used: Literal[False] = False
    live_retrieval_used: Literal[False] = False
    live_trading_api_used: Literal[False] = False
    steps: list[E2EStepResult] = Field(default_factory=list, max_length=32)
    gate_records: list[HarnessGateRecord] = Field(default_factory=list, max_length=8)
    fact_checks: list[AcceptanceFactCheck] = Field(default_factory=list, max_length=64)
    citation_invented: bool = False
    notes: list[str] = Field(default_factory=list, max_length=32)
    product_ui_gates_remain_human_only: Literal[True] = True

    @model_validator(mode="after")
    def _consistent(self) -> E2EAcceptanceReport:
        if self.overall_passed and not self.e2e_allowed:
            raise ValueError("overall_passed requires e2e_allowed (human H3)")
        if self.overall_passed and self.citation_invented:
            raise ValueError("overall_passed forbids invented citations")
        if any(g.auto_approved for g in self.gate_records):
            raise ValueError("E2E report must never record auto-approved gates")
        if self.h1_auto_approve or self.h2_auto_approve or self.h3_auto_approve:
            raise ValueError("E2E report must advertise H1/H2/H3 never auto-approve")
        return self
