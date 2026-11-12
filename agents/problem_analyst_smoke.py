"""Manual DeepSeek smoke for the Problem Analyst.

Pytest and CI do not import or run this module. It makes one provider call
only when PROBLEM_ANALYST_SMOKE=1 and a DeepSeek key are both set.

Example:
  PROBLEM_ANALYST_SMOKE=1 DEEPSEEK_API_KEY=... LLM_MODEL=deepseek-chat \\
    python -m agents.problem_analyst_smoke \\
    --problem tests/fixtures/problem_c_2022_excerpt.txt

Check the current DeepSeek price card before running. One short structured
call is the entire smoke. Do not loop it, and do not set the flag in CI.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pydantic import SecretStr

from agents.problem_analyst import run_problem_analysis
from core.config import get_settings
from core.ids import new_run_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One DeepSeek Problem Analyst smoke call.")
    parser.add_argument("--problem", type=Path, required=True)
    args = parser.parse_args(argv)
    if os.environ.get("PROBLEM_ANALYST_SMOKE") != "1":
        print(
            "Refusing to call a provider. Set PROBLEM_ANALYST_SMOKE=1 to allow one call.",
            file=sys.stderr,
        )
        return 2
    settings = get_settings()
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        print("DEEPSEEK_API_KEY is missing. No call was made.", file=sys.stderr)
        return 2
    settings = settings.model_copy(
        update={
            "llm_provider": "deepseek",
            "llm_model": os.environ.get("LLM_MODEL", "deepseek-chat"),
            "llm_base_url": os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
            "deepseek_api_key": SecretStr(key),
            "llm_api_key": SecretStr(key),
        }
    )
    problem_text = args.problem.read_text(encoding="utf-8")
    state = {
        "project_id": "smoke-2022-c",
        "project_name": "DeepSeek smoke",
        "problem_text": problem_text,
        "run_id": new_run_id(),
        "lifecycle": "datasets_recorded",
        "analysis_status": "not_started",
        "uploaded_files": [
            {
                "dataset_id": "ds_lbma_gold_smoke1",
                "file_name": "LBMA-GOLD.csv",
                "sha256": "a" * 64,
                "row_count": 1,
                "column_count": 2,
                "column_names": ["Date", "USD (PM)"],
            }
        ],
        "dataset_metadata": {"dataset_count": 1, "joined": False},
        "foundation_input_signature": "b" * 64,
        "eda_report": {},
        "approval_status": {},
    }
    outcome = run_problem_analysis(
        state,
        settings=settings,
        revision_notes="",
        foundation_signature="b" * 64,
    )
    wrapper = outcome.state.get("problem_specification") or {}
    print(f"status={wrapper.get('status')} billed_calls={outcome.billed_calls}")
    print(f"llm_analysis_complete={wrapper.get('llm_analysis_complete')}")
    if wrapper.get("status") != "ready":
        print(wrapper.get("reason") or "", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
