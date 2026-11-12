"""Phase 9 E2E contract — harness gate doubles never auto-approve."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from e2e.human_gates import refuse_auto_approved_payload
from schemas.e2e import E2EAcceptanceReport, HarnessGateRecord


def test_harness_gate_record_requires_simulated_human():
    record = HarnessGateRecord(
        gate="H1",
        status="approved",
        notes="E2E harness simulated human approval (test-only).",
        decision_id="h1d_x",
    )
    assert record.auto_approved is False
    assert record.harness_simulated_human is True
    assert record.decided_by == "human"


def test_e2e_report_rejects_auto_approve_flags():
    with pytest.raises(ValidationError):
        E2EAcceptanceReport(
            report_id="e2e_bad",
            overall_passed=False,
            e2e_allowed=False,
            h1_auto_approve=True,  # type: ignore[arg-type]
        )


def test_e2e_report_passed_requires_e2e_allowed():
    with pytest.raises(ValidationError):
        E2EAcceptanceReport(
            report_id="e2e_bad2",
            overall_passed=True,
            e2e_allowed=False,
        )


def test_refuse_auto_approved_payload():
    refuse_auto_approved_payload("H1", auto_approved=False)
    with pytest.raises(ValueError, match="auto_approved"):
        refuse_auto_approved_payload("H2", auto_approved=True)
