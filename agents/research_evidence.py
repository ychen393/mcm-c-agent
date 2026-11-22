"""Compact, source-checked descriptive evidence shared by Strategist and Critic.

Never includes uploaded price rows. Joint statistics describe a full observed
window and must not be presented as trading-day information.
"""
from __future__ import annotations
import hashlib
import json
import math
from typing import Any

_SINGLE_FIELDS = (
    "name", "dataset_id", "sha256", "valid_prices", "date_start", "date_end",
    "volatility_pct", "max_drawdown_pct", "duplicate_dates", "invalid_dates",
    "missing_by_column",
)
_JOINT_FIELDS = (
    "analysis_type", "common_quote_days", "paired_return_intervals",
    "bitcoin_only_days", "gold_only_days", "both_negative_intervals",
    "both_negative_pct", "paired_return_correlation", "rolling_corr_latest",
    "rolling_corr_min", "rolling_corr_max", "gold_price_drawdown_pct",
    "bitcoin_price_drawdown_pct", "overlap_start", "overlap_end",
    "gold_sha256", "bitcoin_sha256", "bundle_fingerprint",
)


def _safe_value(v: Any) -> Any:
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, dict):
        return {str(k)[:80]: _safe_value(x) for k, x in list(v.items())[:30]}
    return v


def build_research_evidence_packet(eda_report: dict[str, Any] | None) -> dict[str, Any]:
    """Return deterministic limited input; fail closed for conflicting source ids."""
    findings = (eda_report or {}).get("interpreted_findings") or {}
    if not isinstance(findings, dict):
        raise ValueError("EDA findings must be structured")
    fingerprint = str(findings.get("bundle_fingerprint") or "")
    raw = findings.get("datasets") or []
    if not isinstance(raw, list):
        raise ValueError("EDA datasets must be a list")
    datasets = [
        {k: _safe_value(row.get(k)) for k in _SINGLE_FIELDS}
        for row in raw[:8] if isinstance(row, dict)
    ]
    if len(datasets) != len(raw):
        raise ValueError("Too many or invalid EDA datasets")
    joint_source = findings.get("joint_market")
    joint = None
    if joint_source is not None:
        if not isinstance(joint_source, dict):
            raise ValueError("Joint EDA must be a structured object")
        if not fingerprint or joint_source.get("bundle_fingerprint") != fingerprint:
            raise ValueError("Joint EDA bundle fingerprint does not match individual EDA")
        for token, expected in (("gold_sha256", "usd (pm)"), ("bitcoin_sha256", "value")):
            match = [d for d in datasets
                     if expected in str(d.get("name") or "").lower()
                     or ("gold" in str(d.get("name") or "").lower() if token == "gold_sha256"
                         else any(x in str(d.get("name") or "").lower() for x in ("bitcoin", "bchain", "btc")))]
            if len(match) == 1 and match[0].get("sha256") != joint_source.get(token):
                raise ValueError(f"Joint EDA {token} does not match the original upload")
        joint = {k: _safe_value(joint_source.get(k)) for k in _JOINT_FIELDS}
    result = {
        "version": "research_evidence_v2",
        "bundle_fingerprint": fingerprint or None,
        "datasets": datasets,
        "joint_market": joint,
        "facts_are": "descriptive_history_not_model_performance",
        "trading_information_warning": (
            "Full-window price statistics and correlations cannot be used as "
            "signals at earlier trading dates; use trailing past-only observations."
        ),
    }
    data = json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    result["packet_sha256"] = hashlib.sha256(data.encode("utf-8")).hexdigest()
    return result
