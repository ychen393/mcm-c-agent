"""Optional live LLM research team, with two real independent calls.

Opt-in only. These are advisory observations, not verified empirical
findings or human H1 decisions. No raw uploaded dataset rows are transmitted.
"""
from __future__ import annotations

import json
from typing import Any

from core.config import Settings
from llm.base import BaseLLM
from llm.factory import LLMFactory


def _items(raw: dict[str, Any], key: str, limit: int = 8) -> list[str]:
    return [
        str(item.get("statement") or item.get("title") or "")[:350]
        for item in (raw.get(key) or [])[:limit] if isinstance(item, dict)
    ]


def _compact_context(
    specification: dict[str, Any],
    proposal: dict[str, Any],
    eda_report: dict[str, Any] | None,
) -> dict[str, Any]:
    insight = (
        eda_report.get("interpreted_findings") if isinstance(eda_report, dict)
        else None
    ) or {}
    return {
        "problem": {
            "title": str(specification.get("title") or "")[:250],
            "research_questions": _items(specification, "research_questions"),
            "constraints": _items(specification, "constraints", 15),
            "unknowns": _items(specification, "unknowns_or_risks"),
        },
        "observed_eda_statistics": [
            {
                key: row.get(key) for key in (
                    "name", "rows", "valid_prices", "date_start", "date_end",
                    "volatility_pct", "max_drawdown_pct", "missing_by_column",
                )
            }
            for row in insight.get("datasets", [])[:5] if isinstance(row, dict)
        ],
        "research_candidates": [
            {
                "candidate_id": str(c.get("candidate_id") or "")[:64],
                "method_family": str(c.get("method_family") or "")[:80],
                "summary": str(c.get("summary") or "")[:500],
            }
            for c in proposal.get("candidates", [])[:12] if isinstance(c, dict)
        ],
        "instruction": "Never invent numerical results or studies. Only the listed EDA metrics are observed.",
    }


def run_live_research_team(
    *,
    specification: dict[str, Any],
    proposal: dict[str, Any],
    eda_report: dict[str, Any] | None,
    settings: Settings,
    llm: BaseLLM | None = None,
    language: str = "zh",
) -> dict[str, str]:
    """Two calls: strategy reviewer then independent skeptical critic.

    Must be invoked only after a human explicitly enables live LLM and clicks
    the team-run button. Results are displayed separately and never persisted
    as experiment measurements or approvals.
    """
    provider = llm if llm is not None else LLMFactory.create(settings)
    context = json.dumps(_compact_context(specification, proposal, eda_report),
                         ensure_ascii=False, separators=(",", ":"))
    response_language = "Chinese with English technical terms" if language == "zh" else "English"
    strategist = provider.invoke([
        {"role": "system", "content": (
            "You are a mathematical modeling research strategist. Using ONLY "
            "the provided problem and measured EDA statistics, compare "
            "candidates, give a concrete modeling workflow, limitations and "
            "what must be tested. Never fabricate backtest results, papers or "
            "citations. Clearly distinguish observation from hypothesis. "
            f"Reply in {response_language}."
        )},
        {"role": "user", "content": context},
    ])
    advisor_text = str(strategist.content)[:8000]
    critic = provider.invoke([
        {"role": "system", "content": (
            "You are an INDEPENDENT skeptical reviewer, not the strategist. "
            "Interrogate the proposed modeling reasoning for lookahead bias, "
            "trading calendar mistakes, commission handling, data sufficiency, "
            "overfitting and unimplemented methods. Supply testable counterexamples. "
            "Use only source facts; do not invent results or citations. "
            f"Reply in {response_language}. Do not approve H1."
        )},
        {"role": "user", "content": context + "\nStrategist proposal for independent review:\n"
         + advisor_text},
    ])
    return {
        "mode": "real_llm_two_call_advisory",
        "provider": str(strategist.provider)[:80],
        "model": str(strategist.model)[:100],
        "strategist": advisor_text,
        "critic": str(critic.content)[:8000],
        "note": "Advisory output only. No model results or gate approvals were changed.",
    }
