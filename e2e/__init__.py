"""Phase 9 offline historical E2E acceptance for 2022 MCM C.

Walks the product chain with fixtures. Human H1/H2/H3 approvals used here are
**harness test doubles** only — product UI gates remain human-only and are
never auto-approved.
"""

from e2e.acceptance_facts import ACCEPTANCE_FACTS_2022_C, REQUIRED_CSV_NAMES
from e2e.assertions import assert_acceptance_facts, collect_acceptance_fact_checks
from e2e.harness import E2EHarnessResult, run_2022_c_historical_e2e
from e2e.human_gates import (
    GATE_PRODUCT_VS_HARNESS,
    apply_harness_h1_approval,
    apply_harness_h2_approval,
    apply_harness_h3_approval,
)

__all__ = [
    "ACCEPTANCE_FACTS_2022_C",
    "E2EHarnessResult",
    "GATE_PRODUCT_VS_HARNESS",
    "REQUIRED_CSV_NAMES",
    "apply_harness_h1_approval",
    "apply_harness_h2_approval",
    "apply_harness_h3_approval",
    "assert_acceptance_facts",
    "collect_acceptance_fact_checks",
    "run_2022_c_historical_e2e",
]
