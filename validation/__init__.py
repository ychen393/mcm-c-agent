"""Validation / Sensitivity package (Phase 7).

``gate`` enforces H1-approved + available experiment results before validation,
and blocks Paper / LaTeX until human H2 approval. ``runner`` provides the
CI-safe deterministic sensitivity path over Phase 6 fixture experiment outputs.
"""

from validation.gate import (
    assert_paper_allowed,
    assert_validation_allowed,
    paper_allowed,
    paper_gate_status,
    read_h2_status,
    validation_allowed,
    validation_gate_status,
)

__all__ = [
    "assert_paper_allowed",
    "assert_validation_allowed",
    "paper_allowed",
    "paper_gate_status",
    "read_h2_status",
    "validation_allowed",
    "validation_gate_status",
]
