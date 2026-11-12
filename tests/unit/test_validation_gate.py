"""Phase 7 validation + paper gates."""

from __future__ import annotations

import pytest

from validation.gate import (
    assert_paper_allowed,
    assert_validation_allowed,
    paper_allowed,
    paper_gate_status,
    read_h2_status,
    validation_allowed,
    validation_gate_status,
)


def _approved_with_experiment() -> dict:
    return {
        "research_proposal": {"proposal_id": "prop_x"},
        "approval_status": {"h1": "approved"},
        "decision_report": {
            "h1": {"status": "approved", "auto_approved": False},
            "experiment": {
                "report_id": "erep_x",
                "latest_run_id": "erun_x",
                "runs": [
                    {
                        "run_id": "erun_x",
                        "status": "completed",
                        "metrics": [
                            {
                                "metric_id": "m_terminal_value",
                                "label": "Terminal",
                                "value": 1000.0,
                            }
                        ],
                    }
                ],
            },
        },
    }


def test_default_blocks_validation():
    assert validation_allowed(None) is False
    assert validation_allowed({}) is False
    gate = validation_gate_status({})
    assert gate.validation_allowed is False
    assert gate.reason in {"h1_absent", "h1_not_approved"}


def test_h1_pending_blocks_even_with_experiments():
    state = _approved_with_experiment()
    state["approval_status"]["h1"] = "pending"
    assert validation_allowed(state) is False
    assert validation_gate_status(state).reason == "h1_pending"


def test_h1_approved_without_experiments_blocks():
    state = {
        "research_proposal": {"proposal_id": "prop_x"},
        "approval_status": {"h1": "approved"},
        "decision_report": {"h1": {"status": "approved"}},
        "experiment_logs": [],
    }
    assert validation_allowed(state) is False
    assert validation_gate_status(state).reason == "no_experiment_results"


def test_h1_and_experiments_allow_validation():
    state = _approved_with_experiment()
    assert validation_allowed(state) is True
    gate = validation_gate_status(state)
    assert gate.reason == "validation_allowed"
    assert gate.baseline_run_id == "erun_x"
    assert_validation_allowed(state)


def test_assert_validation_raises_when_blocked():
    with pytest.raises(PermissionError):
        assert_validation_allowed({"approval_status": {"h1": "pending"}})


def test_paper_blocked_until_h2_approved():
    assert paper_allowed(None) is False
    pending = {
        "validation_report": {"report_id": "vrep_x"},
        "approval_status": {"h2": "pending"},
    }
    assert paper_allowed(pending) is False
    assert paper_gate_status(pending).reason == "h2_pending"

    approved = {
        "validation_report": {"report_id": "vrep_x"},
        "approval_status": {"h2": "approved"},
        "decision_report": {"h2": {"status": "approved"}},
    }
    assert read_h2_status(approved) == "approved"
    assert paper_allowed(approved) is True
    assert paper_gate_status(approved).reason == "h2_approved"
    assert_paper_allowed(approved)


def test_assert_paper_raises_when_blocked():
    with pytest.raises(PermissionError):
        assert_paper_allowed(
            {
                "validation_report": {"report_id": "vrep_x"},
                "approval_status": {"h2": "pending"},
            }
        )


def test_no_validation_report_blocks_paper():
    gate = paper_gate_status({"approval_status": {}})
    assert gate.paper_allowed is False
    assert gate.reason == "no_validation_report"
