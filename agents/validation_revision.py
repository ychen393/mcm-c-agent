"""Human H2 revision: LLM designs bounded scenarios, deterministic engine computes.

NEVER trust LLM numerical performance claims. Historical runs require matching
source CSV checksums. An independent second provider call critiques actual
computed results; all database writes remain in UI after success.
"""
from __future__ import annotations
import json
from typing import Any

from agents.research_revision import _parse_json_object
from agents.validation_sensitivity import run_validation_sensitivity
from core.config import Settings
from llm.base import BaseLLM
from llm.factory import LLMFactory
from schemas.validation import ValidationReport


def revise_validation_with_feedback(
    *,
    state: dict[str, Any],
    feedback: str,
    report: ValidationReport | dict[str, Any],
    settings: Settings,
    price_bars: list[Any] | None = None,
    price_sha256: dict[str, str] | None = None,
    llm: BaseLLM | None = None,
    language: str = "zh",
) -> tuple[ValidationReport, dict[str, str]]:
    existing = report if isinstance(report, ValidationReport) else ValidationReport.model_validate({
        k:v for k,v in report.items() if k != "report_version"
    })
    feedback=feedback.strip()
    if not 12 <= len(feedback) <= 2400:
        raise ValueError("H2 feedback must contain 12–2400 characters")
    if ((state.get("approval_status") or {}).get("h2") != "revision_requested"
            or ((state.get("decision_report") or {}).get("h2") or {}).get("status") != "revision_requested"):
        raise PermissionError("H2 must first be explicitly returned for revision")
    experiment=((state.get("decision_report") or {}).get("experiment") or {})
    if existing.baseline_run_id != experiment.get("latest_run_id"):
        raise ValueError("H2 baseline has changed; rerun baseline validation first")
    if existing.strategy == "deterministic_uploaded_csv" and (not price_bars or not price_sha256):
        raise ValueError("Historical H2 re-run requires identical original CSVs")
    if existing.strategy != "deterministic_uploaded_csv" and price_bars is not None:
        raise ValueError("Do not mix synthetic experiment and uploaded datasets")
    source_stats=[{
        "metric":m.metric_id, "value":m.value, "unit":m.unit
    } for m in existing.baseline_metrics[:15]]
    old_cases=[{"name":s.label,"kind":s.kind,"changes":[{
        "target":p.target,"value":p.scenario_value
    } for p in s.perturbations]} for s in existing.scenarios[:12]]
    lang="Chinese" if language=="zh" else "English"
    provider=llm or LLMFactory.create(settings)
    plan=provider.invoke([
        {"role":"system","content":(
            "You are a validation experiment designer responding to H2 human feedback. "
            "Return ONLY JSON object with keys scenarios (array of 1–3 objects, "
            "each EXACTLY target, value, rationale) and changes_made (string). "
            "Allowed target: alpha_gold, alpha_bitcoin, lookback_days, "
            "rebalance_every_n_days. Fees are fractions from 0 to 0.10; "
            "day parameters are whole numbers from 1 to 60. "
            "Propose changes clearly connected to reviewer feedback and different "
            "from current baseline. Do NOT invent results. No new algorithms, "
            "out-of-sample tests, datasets or trading simulations can be claimed. "
            "If feedback demands unsupported evaluation, return a JSON error "
            "with key unsupported_experiment instead of pretending it was run. "
            f"Write all human text in {lang}."
        )},
        {"role":"user","content":json.dumps({
            "human_feedback":feedback,
            "baseline_run_id":existing.baseline_run_id,
            "previous_report_id":existing.report_id,
            "source_mode":existing.strategy,
            "measured_baseline_metrics":source_stats,
            "existing_test_scenarios":old_cases,
        },ensure_ascii=False)},
    ])
    proposal=_parse_json_object(str(plan.content))
    if proposal.get("unsupported_experiment"):
        raise ValueError(
            "Requested experiment not implemented: "+
            str(proposal["unsupported_experiment"])[:400]
        )
    cases=proposal.get("scenarios")
    if not isinstance(cases,list) or not 1 <= len(cases) <= 3:
        raise ValueError("Revised H2 test plan requires 1–3 executable scenarios")
    if not isinstance(proposal.get("changes_made"),str) or len(proposal["changes_made"].strip()) < 20:
        raise ValueError("Revised H2 must explain how user feedback was addressed")
    # All values/targets are rechecked in the deterministic runner. Unrecognized
    # operations and unsupported requests fail closed before any persistence.
    updated=run_validation_sensitivity(
        state=state,
        problem_specification=state.get("problem_specification"),
        proposal=state.get("research_proposal"),
        use_llm=False,
        settings=settings,
        price_bars=price_bars,
        price_sha256=price_sha256,
        extra_scenarios=cases,
    )
    if updated.baseline_run_id != existing.baseline_run_id:
        raise ValueError("Recomputed validation changed its underlying experiment")
    measured=[{
        "scenario_id":s.scenario_id,
        "parameter_changes":[{
            "target":p.target,"before":p.baseline_value,"after":p.scenario_value
        } for p in s.perturbations],
        "computed_metrics":[{
            "metric":m.metric_id,"value":m.value
        } for m in s.metrics if m.metric_id in {"m_terminal_value","m_total_return",
                                                   "m_max_drawdown","m_cost_paid"}]
    } for s in updated.scenarios if s.scenario_id.startswith("scn_feedback_")]
    critical=provider.invoke([
        {"role":"system","content":(
            "You are an INDEPENDENT validation critic. The supplied scenario "
            "metric values were recomputed by deterministic code, not by a model. "
            "Critique whether the requested feedback is sufficiently addressed, "
            "whether the stress test is meaningful for this trading strategy, "
            "and what remains unsupported (e.g. walk-forward validation). "
            "Do not claim a new experiment ran or approve H2. "
            f"Respond in {lang} with 3–6 concrete points."
        )},
        {"role":"user","content":json.dumps({
            "human_feedback":feedback,
            "changes_made":proposal["changes_made"],
            "old_scenario_count":len(existing.scenarios),
            "recomputed_stress_results":measured,
            "limitation":"This is in-sample sensitivity, NOT out-of-sample proof.",
        },ensure_ascii=False)},
    ])
    critique=str(critical.content).strip()[:2800]
    if len(critique) < 20:
        raise ValueError("Independent H2 critic returned insufficient review")
    audit={
        "feedback":feedback,
        "before":f"Report {existing.report_id}; {len(existing.scenarios)} computed scenarios",
        "after":f"Report {updated.report_id}; {len(updated.scenarios)} computed scenarios; "+json.dumps(measured,ensure_ascii=False)[:1450],
        "changes_made":proposal["changes_made"].strip()[:900],
        "critic_feedback":critique,
        "previous_report_id":existing.report_id,
        "new_report_id":updated.report_id,
        "baseline_run_id":updated.baseline_run_id,
        "mode":"two_llm_calls_plus_deterministic_recomputation",
        "model":str(plan.model)[:100],
        "provider":str(plan.provider)[:80],
    }
    return updated,audit
