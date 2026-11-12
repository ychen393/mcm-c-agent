"""Phase 6 experiment / model-run contract validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.experiment import (
    ExperimentParams,
    ExperimentReport,
    ExperimentRun,
    MetricResult,
    ModelArtifactRef,
    ProblemConstraintSnapshot,
)


def _constraints() -> ProblemConstraintSnapshot:
    return ProblemConstraintSnapshot(
        problem_id="2022_mcm_c",
        initial_cash=1000.0,
        alpha_gold=0.01,
        alpha_bitcoin=0.02,
        assets=["cash", "gold", "bitcoin"],
        past_data_only=True,
        source="defaults_2022_mcm_c",
    )


def _params() -> ExperimentParams:
    return ExperimentParams(
        initial_cash=1000.0,
        alpha_gold=0.01,
        alpha_bitcoin=0.02,
        assets=["cash", "gold", "bitcoin"],
        strategy_id="cash_hold",
    )


def test_completed_run_requires_metrics():
    with pytest.raises(ValidationError):
        ExperimentRun(
            run_id="erun_test0001",
            status="completed",
            proposal_id="prop_x",
            selected_candidate_id="cand_x",
            params=_params(),
            metrics=[],
            constraints=_constraints(),
        )


def test_run_rejects_invented_and_live_api():
    with pytest.raises(ValidationError):
        ExperimentRun(
            run_id="erun_test0002",
            status="planned",
            proposal_id="prop_x",
            selected_candidate_id="cand_x",
            params=_params(),
            constraints=_constraints(),
            invented_results=True,
        )
    with pytest.raises(ValidationError):
        ExperimentRun(
            run_id="erun_test0003",
            status="planned",
            proposal_id="prop_x",
            selected_candidate_id="cand_x",
            params=_params(),
            constraints=_constraints(),
            live_trading_api_used=True,
        )


def test_report_requires_h1_approved_gate():
    run = ExperimentRun(
        run_id="erun_test0004",
        status="completed",
        proposal_id="prop_x",
        selected_candidate_id="cand_x",
        params=_params(),
        metrics=[
            MetricResult(
                metric_id="m_terminal_value",
                kind="terminal_value",
                label="Terminal",
                value=1000.0,
                unit="USD",
            )
        ],
        constraints=_constraints(),
        artifacts=[
            ModelArtifactRef(
                artifact_id="art_cfg0001",
                kind="run_config",
                summary="config snapshot for contract test",
                payload={"ok": True},
            )
        ],
    )
    with pytest.raises(ValidationError):
        ExperimentReport(
            report_id="erep_test0001",
            proposal_id="prop_x",
            selected_candidate_id="cand_x",
            h1_approved=False,
            modeling_allowed=True,
            runs=[run],
            latest_run_id=run.run_id,
        )
    report = ExperimentReport(
        report_id="erep_test0002",
        proposal_id="prop_x",
        selected_candidate_id="cand_x",
        h1_approved=True,
        modeling_allowed=True,
        runs=[run],
        latest_run_id=run.run_id,
    )
    assert report.latest_run_id == run.run_id
