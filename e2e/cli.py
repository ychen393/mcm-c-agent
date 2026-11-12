"""Optional CLI entry for Phase 9 offline E2E (pytest remains the CI path).

Usage:
    python -m e2e.cli [--projects-root PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from e2e.harness import run_2022_c_historical_e2e


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run offline 2022 MCM C historical E2E acceptance. "
            "H1/H2/H3 are harness simulated-human doubles only — never product auto-approve."
        )
    )
    parser.add_argument(
        "--projects-root",
        type=Path,
        default=None,
        help="Directory for LocalProjectStore (default: temp dir).",
    )
    args = parser.parse_args(argv)

    root = args.projects_root
    cleanup: tempfile.TemporaryDirectory[str] | None = None
    if root is None:
        cleanup = tempfile.TemporaryDirectory(prefix="mcm-c-e2e-")
        root = Path(cleanup.name)

    try:
        result = run_2022_c_historical_e2e(projects_root=root)
        payload = {
            "overall_passed": result.report.overall_passed,
            "report_id": result.report.report_id,
            "e2e_allowed": result.report.e2e_allowed,
            "n_fact_checks": len(result.report.fact_checks),
            "n_gate_records": len(result.report.gate_records),
            "h1_auto_approve": result.report.h1_auto_approve,
            "h2_auto_approve": result.report.h2_auto_approve,
            "h3_auto_approve": result.report.h3_auto_approve,
            "product_ui_gates_remain_human_only": (
                result.report.product_ui_gates_remain_human_only
            ),
            "workspace_e2e": (result.state.get("workspace_phases") or {}).get(
                "e2e_acceptance"
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if result.report.overall_passed else 1
    finally:
        if cleanup is not None:
            cleanup.cleanup()


if __name__ == "__main__":
    sys.exit(main())
