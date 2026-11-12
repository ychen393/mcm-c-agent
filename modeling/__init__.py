"""Mathematical Modeling & Experiment package (Phase 6).

``gate`` enforces human H1 approval before any experiment run/persist.
``runner`` provides the CI-safe deterministic 2022 MCM C fixture path.
"""

from modeling.gate import (
    assert_modeling_allowed,
    modeling_allowed,
    modeling_gate_status,
    read_h1_status,
)

__all__ = [
    "assert_modeling_allowed",
    "modeling_allowed",
    "modeling_gate_status",
    "read_h1_status",
]
