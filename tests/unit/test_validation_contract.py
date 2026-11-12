"""Phase 7 validation / sensitivity / H2 contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.validation import (
    H2Decision,
    MetricSnapshot,
    PaperGateStatus,
    RobustnessNote,
    SensitivityScenario,
    ValidationGateStatus,
    ValidationReport,
)


def _baseline_metrics() -> list[MetricSnapshot]:
    return [
        MetricSnapshot(
            metric_id="m_terminal_value",
            kind="terminal_value",
            label="Terminal portfolio value",
            value=1100.0,
            unit="USD",
        ),
        MetricSnapshot(
            metric_id="m_total_return",
            kind="total_return",
            label="Total return",
            value=0.1,
            unit="fraction",
        ),
    ]


def _scenario() -> SensitivityScenario:
    return SensitivityScenario(
        scenario_id="scn_cost_alpha_btc_x2",
        kind="cost",
        label="Bitcoin commission ×2",
        description="Double αbitcoin relative to baseline.",
        baseline_run_id="erun_base",
        metrics=_baseline_metrics(),
        invented_results=False,
    )


def test_validation_report_requires_h1_and_scenarios():
    with pytest.raises(ValidationError):
        ValidationReport(
            report_id="vrep_x",
            proposal_id="prop_x",
            selected_candidate_id="cand_x",
            baseline_run_id="erun_base",
            h1_approved=False,
            validation_allowed=True,
            baseline_metrics=_baseline_metrics(),
            scenarios=[_scenario()],
        )
    with pytest.raises(ValidationError):
        ValidationReport(
            report_id="vrep_x",
            proposal_id="prop_x",
            selected_candidate_id="cand_x",
            baseline_run_id="erun_base",
            h1_approved=True,
            validation_allowed=True,
            baseline_metrics=_baseline_metrics(),
            scenarios=[],
        )


def test_validation_report_rejects_invented_and_live_trading():
    with pytest.raises(ValidationError):
        ValidationReport(
            report_id="vrep_x",
            proposal_id="prop_x",
            selected_candidate_id="cand_x",
            baseline_run_id="erun_base",
            baseline_metrics=_baseline_metrics(),
            scenarios=[_scenario()],
            invented_results=True,
        )
    with pytest.raises(ValidationError):
        ValidationReport(
            report_id="vrep_x",
            proposal_id="prop_x",
            selected_candidate_id="cand_x",
            baseline_run_id="erun_base",
            baseline_metrics=_baseline_metrics(),
            scenarios=[_scenario()],
            live_trading_api_used=True,
        )


def test_scenario_rejects_invented_and_requires_metrics_when_completed():
    with pytest.raises(ValidationError):
        SensitivityScenario(
            scenario_id="scn_bad",
            kind="cost",
            label="Bad",
            description="Invented",
            baseline_run_id="erun_base",
            metrics=_baseline_metrics(),
            invented_results=True,
        )
    with pytest.raises(ValidationError):
        SensitivityScenario(
            scenario_id="scn_empty",
            kind="cost",
            label="Empty",
            description="No metrics",
            baseline_run_id="erun_base",
            metrics=[],
            status="completed",
        )


def test_h2_rejects_auto_approve():
    with pytest.raises(ValidationError):
        H2Decision.model_validate(
            {
                "decision_id": "h2d_x",
                "status": "approved",
                "validation_report_id": "vrep_x",
                "notes": "nope",
                "decided_by": "human",
                "auto_approved": True,
                "decided_at_utc": "2026-11-12T00:00:00Z",
            }
        )


def test_h2_approve_requires_timestamp():
    with pytest.raises(ValidationError):
        H2Decision.model_validate(
            {
                "decision_id": "h2d_x",
                "status": "approved",
                "validation_report_id": "vrep_x",
                "decided_by": "human",
                "auto_approved": False,
            }
        )


def test_validation_gate_consistency():
    with pytest.raises(ValidationError):
        ValidationGateStatus(
            validation_allowed=True,
            h1_status="pending",
            has_experiment_results=True,
            reason="validation_allowed",
            message="bad",
        )
    ok = ValidationGateStatus(
        validation_allowed=True,
        h1_status="approved",
        has_experiment_results=True,
        baseline_run_id="erun_x",
        reason="validation_allowed",
        message="H1 approved and experiments available for validation.",
    )
    assert ok.validation_allowed is True


def test_paper_gate_consistency():
    with pytest.raises(ValidationError):
        PaperGateStatus(
            paper_allowed=True,
            h2_status="pending",
            reason="h2_approved",
            message="bad",
        )
    ok = PaperGateStatus(
        paper_allowed=True,
        h2_status="approved",
        reason="h2_approved",
        message="H2 approved by a human. Paper may advance.",
    )
    assert ok.paper_allowed is True


def test_valid_report_builds():
    report = ValidationReport(
        report_id="vrep_ok",
        proposal_id="prop_ok",
        selected_candidate_id="cand_ok",
        baseline_run_id="erun_ok",
        baseline_metrics=_baseline_metrics(),
        scenarios=[_scenario()],
        robustness_notes=[
            RobustnessNote(
                note_id="rn_info",
                severity="info",
                summary="Fixture-only sensitivity coverage note.",
            )
        ],
    )
    assert report.h1_approved is True
    assert len(report.scenarios) == 1
