"""Build a foundation state from validated dataset provenance.

The foundation graph only records the project and the current files. It does
not join datasets, call a model, or read or write research checkpoint
documents. Provenance is dataset identity and profile counts, never file bytes
or raw rows.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.lifecycle import (
    LIFECYCLE_DATASETS_RECORDED,
    LIFECYCLE_PROJECT_INITIALIZED,
)
from core.state import ResearchState, new_research_state
from schemas.persistence import (
    FORBIDDEN_STATE_KEYS,
    assert_safe_for_persistence,
    is_forbidden_key,
    sanitize_uploaded_file_record,
)
from tools.dataset_bundle import DatasetBundle, build_bundle_profiles

ANALYSIS_NOT_STARTED = "not_started"
STAGE_PROJECT_INITIALIZED = "project_initialized"
STAGE_DATASETS_LOADED = "datasets_loaded"
PROJECT_STATUS_INITIALIZED = "initialized"
NOT_IMPLEMENTED = "NOT IMPLEMENTED"

# Kept as an alias of the persistence denylist for older call sites / tests.
FORBIDDEN_PROVENANCE_KEYS = FORBIDDEN_STATE_KEYS

_SELECTION_STATUSES = frozenset({"empty", "ready", "rejected"})


def workspace_phases(dataset_count: int) -> dict[str, str]:
    """Honest phases for an initialized project. Joint modeling is never ready."""
    if dataset_count < 0:
        raise ValueError("dataset_count cannot be negative.")
    loaded = dataset_count > 0
    return {
        "project_initialized": "yes",
        "datasets_loaded": "yes" if loaded else "no",
        "independent_eda": "ready" if loaded else "not ready",
        "relationship_preview": "ready" if dataset_count >= 2 else "not ready",
        "joint_analysis": NOT_IMPLEMENTED,
        "strategy_modeling": NOT_IMPLEMENTED,
    }


def cleared_derived_products() -> dict[str, Any]:
    """Drop reports, approvals, plans, and Phase 4/5/6/7 attach products.

    Experiment / AI usage logs stay. Literature ``citations`` are cleared with
    ``evidence_report`` because they are Phase 4 attach products, not durable logs.
    Phase 5 ``research_proposal`` / ``decision_report`` / ``disagreement_log`` /
    ``approval_status`` clear so a foundation rebuild cannot keep a stale H1.
    Phase 6 ``model_artifacts`` clear with other derived products; ``experiment_logs``
    remain as durable run logs (Phase 1 semantics).
    Phase 7 ``validation_report`` clears with approvals so a stale H2 cannot survive.
    """
    return {
        "problem_specification": {},
        "eda_report": {},
        "evidence_report": {},
        "citations": [],
        "research_proposal": {},
        "disagreement_log": [],
        "decision_report": {},
        "approval_status": {},
        "validation_report": {},
        "paper_outline": {},
        "latex_source": "",
        "review_report": {},
        "model_artifacts": [],
    }


def selection_token(
    uploads: list[tuple[str, bytes]],
    *,
    fingerprint: str | None,
    rejected: bool,
) -> str:
    """Identity of the current file selection. Hashes bytes and does not keep them."""
    if rejected:
        digest = hashlib.sha256()
        for name, raw in uploads:
            if not isinstance(raw, (bytes, bytearray)):
                raise TypeError("Upload payloads must be bytes.")
            digest.update(str(name).encode("utf-8", errors="replace"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(bytes(raw)).digest())
            digest.update(b"\0")
        return "rejected:" + digest.hexdigest()
    if not uploads:
        return "empty"
    if not fingerprint:
        raise ValueError("A ready dataset selection requires a bundle fingerprint.")
    return "ready:" + fingerprint


def foundation_input_signature(
    *,
    project_id: str,
    project_name: str,
    problem_text: str,
    selection_token_value: str,
    llm_config_revision: int,
    llm_provider: str,
    llm_model: str,
) -> str:
    """Hash the inputs that should refresh foundation state. Never includes a key."""
    payload = {
        "project_id": project_id,
        "project_name": project_name.strip(),
        "problem_text": problem_text,
        "selection_token": selection_token_value,
        "llm_config_revision": int(llm_config_revision),
        "llm_provider": llm_provider,
        "llm_model": llm_model,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def dataset_provenance(bundle: DatasetBundle) -> list[dict[str, Any]]:
    """Copy safe profile facts off an already validated bundle.

    Row values, sample cells, correlations, and the original file bytes stay
    on the in-memory bundle and are not copied.
    """
    profiles = build_bundle_profiles(bundle)
    records: list[dict[str, Any]] = []
    for ref in bundle.datasets:
        report = profiles[ref.dataset_id].report
        dataset = report.dataset
        records.append(
            {
                "dataset_id": ref.dataset_id,
                "position": ref.position,
                "file_name": ref.file_name,
                "display_name": ref.display_name,
                "file_extension": ref.file_extension,
                "file_size_bytes": ref.file_size_bytes,
                "sha256": ref.sha256,
                "row_count": dataset.row_count,
                "column_count": dataset.column_count,
                "duplicate_row_count": dataset.duplicate_row_count,
                "column_names": list(ref.column_names),
                "qualified_column_names": list(ref.qualified_column_names),
                "warnings": list(report.warnings),
                "period_start": dataset.period_start,
                "period_end": dataset.period_end,
                "joined": False,
            }
        )
    return records


def sanitize_uploaded_files(files: Any) -> list[dict[str, Any]]:
    """Keep allowlisted provenance only; fail closed on secret-shaped keys/bytes.

    Aligned with ``schemas.persistence`` so Issue #26 secrets cannot sit in
    in-memory ResearchState even before a store write.
    """
    if not files:
        return []
    if not isinstance(files, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            continue
        # Reject secrets/bytes before allowlisting; do not silently keep them.
        assert_safe_for_persistence(item, f"uploaded_files[{index}]")
        cleaned.append(
            sanitize_uploaded_file_record(item, path=f"uploaded_files[{index}]")
        )
    return cleaned


def sanitize_metadata(metadata: Any) -> dict[str, Any]:
    """Fail closed on secret-shaped or raw-payload keys in bundle metadata."""
    if not isinstance(metadata, dict):
        return {}
    assert_safe_for_persistence(metadata, "dataset_metadata")
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if is_forbidden_key(key) or isinstance(value, (bytes, bytearray)):
            raise ValueError(f"Foundation state cannot contain forbidden key '{key}'.")
        cleaned[key] = value
    cleaned["raw_rows_included"] = False
    cleaned["file_bytes_included"] = False
    cleaned["joined"] = False
    return cleaned


def _reject_unsafe_values(value: Any, path: str = "state") -> None:
    """Fail closed using the same heuristics as persistence sanitization."""
    try:
        assert_safe_for_persistence(value, path)
    except ValueError as exc:
        raise TypeError(str(exc).replace("Refusing to persist", "Foundation state cannot contain")) from exc


def build_initialized_state(
    *,
    project_id: str,
    project_name: str,
    problem_text: str,
    bundle: DatasetBundle | None,
    selection_status: str,
    llm_config_revision: int,
    llm_provider: str,
    llm_model: str,
) -> ResearchState:
    """Create a new foundation state for the current inputs.

    Callers pass an already validated bundle. This function does not read
    checkpoint storage and does not accept an API key.
    """
    if selection_status not in _SELECTION_STATUSES:
        raise ValueError("Unknown dataset selection status.")
    if selection_status == "ready":
        if bundle is None:
            raise ValueError("A ready selection requires a dataset bundle.")
        provenance = dataset_provenance(bundle)
    else:
        if bundle is not None:
            raise ValueError("Empty or rejected selections cannot carry a dataset bundle.")
        provenance = []

    state = new_research_state(project_id, project_name.strip())
    state["problem_text"] = problem_text
    state["analysis_status"] = ANALYSIS_NOT_STARTED
    state["lifecycle"] = (
        LIFECYCLE_DATASETS_RECORDED if provenance else LIFECYCLE_PROJECT_INITIALIZED
    )
    state["uploaded_files"] = sanitize_uploaded_files(provenance)
    limitations: list[str]
    if bundle is not None:
        limitations = list(bundle.manifest.limitations)
    else:
        limitations = [
            "No validated dataset bundle is recorded.",
            "Joint analysis and strategy modeling are not implemented.",
        ]
    state["dataset_metadata"] = sanitize_metadata(
        {
            "record": "validated_dataset_bundle" if bundle is not None else "no_dataset_bundle",
            "selection_status": selection_status,
            "bundle_version": bundle.manifest.bundle_version if bundle is not None else None,
            "bundle_fingerprint": bundle.fingerprint if bundle is not None else None,
            "bundle_project_id": bundle.project_id if bundle is not None else project_id,
            "dataset_count": len(state["uploaded_files"]),
            "dataset_ids": [item["dataset_id"] for item in state["uploaded_files"]],
            "limitations": limitations,
            "problem_text_sha256": hashlib.sha256(problem_text.encode("utf-8")).hexdigest(),
            "llm_config_revision": int(llm_config_revision),
            "llm_provider": llm_provider,
            "llm_model": llm_model,
        }
    )
    state["workspace_phases"] = workspace_phases(len(state["uploaded_files"]))
    state.update(cleared_derived_products())
    if selection_status == "rejected":
        state["errors"] = [
            {
                "code": "dataset_bundle_rejected",
                "message": "The current file selection is not a valid dataset bundle.",
            }
        ]
    else:
        state["errors"] = []
    _reject_unsafe_values(state)
    return state
