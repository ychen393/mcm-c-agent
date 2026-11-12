"""Phase 5 modeling gate — blocked until human H1 approval."""

from __future__ import annotations

import pytest

from modeling.gate import (
    assert_modeling_allowed,
    modeling_allowed,
    modeling_gate_status,
    read_h1_status,
)


def test_default_state_blocks_modeling():
    assert modeling_allowed(None) is False
    assert modeling_allowed({}) is False
    gate = modeling_gate_status({})
    assert gate.modeling_allowed is False
    assert gate.reason == "no_proposal"


def test_pending_and_revision_block():
    pending = {
        "research_proposal": {"proposal_id": "prop_x"},
        "approval_status": {"h1": "pending"},
    }
    assert modeling_allowed(pending) is False
    assert modeling_gate_status(pending).reason == "h1_pending"

    revise = {
        "research_proposal": {"proposal_id": "prop_x"},
        "approval_status": {"h1": "revision_requested"},
    }
    assert modeling_allowed(revise) is False
    assert modeling_gate_status(revise).reason == "h1_revision_requested"


def test_approved_allows_gate_flag():
    approved = {
        "research_proposal": {"proposal_id": "prop_x"},
        "approval_status": {"h1": "approved"},
    }
    assert read_h1_status(approved) == "approved"
    assert modeling_allowed(approved) is True
    gate = modeling_gate_status(approved)
    assert gate.modeling_allowed is True
    assert gate.reason == "h1_approved"
    assert_modeling_allowed(approved)


def test_assert_modeling_allowed_raises_when_blocked():
    with pytest.raises(PermissionError):
        assert_modeling_allowed({"approval_status": {"h1": "pending"}})
