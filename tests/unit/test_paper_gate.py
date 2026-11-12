"""Phase 8 paper generation + E2E gates."""

from __future__ import annotations

import pytest

from paper.gate import (
    assert_e2e_allowed,
    assert_paper_allowed,
    e2e_allowed,
    e2e_gate_status,
    paper_allowed,
    paper_generation_gate_status,
    read_h3_status,
)


def test_paper_blocked_until_h2_approved():
    assert paper_allowed(None) is False
    pending = {
        "validation_report": {"report_id": "vrep_x"},
        "approval_status": {"h2": "pending"},
    }
    assert paper_allowed(pending) is False
    assert paper_generation_gate_status(pending).reason == "h2_pending"

    approved = {
        "validation_report": {"report_id": "vrep_x"},
        "approval_status": {"h2": "approved"},
    }
    assert paper_allowed(approved) is True
    assert paper_generation_gate_status(approved).reason == "h2_approved"
    assert_paper_allowed(approved)


def test_assert_paper_raises_when_blocked():
    with pytest.raises(PermissionError):
        assert_paper_allowed({"approval_status": {"h2": "pending"}})


def test_e2e_blocked_until_h3_approved():
    assert e2e_allowed(None) is False
    pending = {
        "paper_outline": {"outline_id": "pout_x"},
        "approval_status": {"h3": "pending"},
    }
    assert e2e_allowed(pending) is False
    assert e2e_gate_status(pending).reason == "h3_pending"

    approved = {
        "paper_outline": {"outline_id": "pout_x"},
        "approval_status": {"h3": "approved"},
        "decision_report": {"h3": {"status": "approved"}},
    }
    assert read_h3_status(approved) == "approved"
    assert e2e_allowed(approved) is True
    assert e2e_gate_status(approved).reason == "h3_approved"
    assert_e2e_allowed(approved)


def test_assert_e2e_raises_when_blocked():
    with pytest.raises(PermissionError):
        assert_e2e_allowed({"paper_outline": {"outline_id": "pout_x"}})


def test_no_outline_reason():
    gate = e2e_gate_status({"approval_status": {}})
    assert gate.e2e_allowed is False
    assert gate.reason == "no_paper_outline"
