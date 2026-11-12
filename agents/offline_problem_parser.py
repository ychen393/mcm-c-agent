"""Deterministic problem reading for tests.

This is not an LLM call and must never be labeled as a completed model analysis.
It only copies sentences and metadata lines that are already present.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from core.ids import utc_now_iso
from schemas.problem_specification import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    ProblemSpecification,
    ProblemSpecificationBody,
    assert_grounded,
)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
_MONEY_RE = re.compile(r"\$\d{1,3}(?:,\d{3})+(?:\.\d+)?|\$\d+(?:\.\d+)?")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}")


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_RE.split(text.strip()) if part.strip()]


def _evidence(evidence_id: str, quote: str, source: str = "problem_text") -> dict[str, str]:
    return {"evidence_id": evidence_id, "source": source, "quote": quote}


def _constraint(
    constraint_id: str,
    subject: str,
    sentence: str,
    evidence_id: str,
    *,
    value: str | None = None,
) -> dict[str, Any]:
    return {
        "constraint_id": constraint_id,
        "subject": subject,
        "statement": sentence,
        "kind": "official",
        "evidence_ids": [evidence_id],
        "value": value,
    }


def _classify(sentence: str) -> tuple[str, str | None] | None:
    lowered = sentence.lower()
    percent = _PERCENT_RE.search(sentence)
    money = _MONEY_RE.search(sentence)
    if money and ("start" in lowered or "cash" in lowered or "dollar" in lowered):
        return "initial_cash", money.group(0)
    if "trading period" in lowered or ("from" in lowered and len(_DATE_RE.findall(sentence)) >= 2):
        dates = _DATE_RE.findall(sentence)
        return "trading_period", " to ".join(dates[:2]) if len(dates) >= 2 else None
    if "gold" in lowered and ("market is open" in lowered or "only on days" in lowered):
        return "gold_trading_days", None
    if "bitcoin" in lowered and "every day" in lowered:
        return "bitcoin_trading_days", None
    if "gold" in lowered and percent:
        return "gold_commission", percent.group(0)
    if "bitcoin" in lowered and percent:
        return "bitcoin_commission", percent.group(0)
    if any(
        phrase in lowered
        for phrase in ("no look-ahead", "cannot see the future", "only the past", "past stream")
    ):
        return "information_set", None
    if "portfolio value" in lowered or "final portfolio" in lowered:
        return "terminal_value", None
    if "sensitiv" in lowered:
        return "sensitivity", None
    if "memorandum" in lowered:
        return "memorandum", None
    return None


def dataset_metadata_bulletin(
    uploaded_files: list[dict[str, Any]] | None,
    dataset_metadata: dict[str, Any] | None = None,
) -> str:
    """Safe metadata lines. No raw rows, file bytes, or secret-shaped keys."""
    lines: list[str] = []
    metadata = dataset_metadata or {}
    count = metadata.get("dataset_count")
    if isinstance(count, int):
        lines.append(f"dataset_count: {count}")
    lines.append("joined: false")
    for item in uploaded_files or []:
        if not isinstance(item, dict):
            continue
        file_name = item.get("file_name")
        dataset_id = item.get("dataset_id")
        digest = item.get("sha256")
        if not (file_name and dataset_id and digest):
            continue
        lines.append(f"file_name: {file_name}")
        lines.append(f"dataset_id: {dataset_id}")
        lines.append(f"sha256: {digest}")
        if isinstance(item.get("row_count"), int):
            lines.append(f"row_count: {item['row_count']}")
        if isinstance(item.get("column_count"), int):
            lines.append(f"column_count: {item['column_count']}")
        columns = item.get("column_names") or []
        if isinstance(columns, list) and columns:
            lines.append("columns: " + ", ".join(str(column) for column in columns))
        for bound in ("period_start", "period_end"):
            if item.get(bound):
                lines.append(f"{bound}: {item[bound]}")
    return "\n".join(lines)


def interpret_problem_offline(
    *,
    problem_text: str,
    project_id: str,
    run_id: str,
    input_signature: str,
    uploaded_files: list[dict[str, Any]] | None = None,
    dataset_metadata: dict[str, Any] | None = None,
    revision_notes: str = "",
    version: int = 1,
    generated_at: str | None = None,
) -> ProblemSpecification:
    """Build a grounded specification without calling a model.

    The result is an offline fixture. ``llm_analysis_complete`` is false.
    """
    bulletin = dataset_metadata_bulletin(uploaded_files, dataset_metadata)
    sentences = _sentences(problem_text)
    if not sentences:
        raise ValueError("Problem text is empty.")
    evidence: list[dict[str, str]] = []
    constraints: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    uncertainties: list[dict[str, Any]] = []
    seen_subjects: dict[str, str | None] = {}
    subject_counts: dict[str, int] = {}
    conflicts: set[str] = set()

    for index, sentence in enumerate(sentences, start=1):
        evidence_id = f"ev_s{index}"
        evidence.append(_evidence(evidence_id, sentence))
        classified = _classify(sentence)
        if classified is None:
            if any(word in sentence.lower() for word in ("must", "determine", "report", "explain")):
                questions.append(
                    {
                        "question_id": f"q_s{index}",
                        "text": sentence,
                        "evidence_ids": [evidence_id],
                    }
                )
            continue
        subject, value = classified
        if subject in conflicts:
            continue
        previous = seen_subjects.get(subject)
        if subject in seen_subjects and value and previous and previous != value:
            conflicts.add(subject)
            continue
        if subject in seen_subjects and value and value == previous:
            continue
        seen_subjects[subject] = value
        subject_counts[subject] = subject_counts.get(subject, 0) + 1
        suffix = "" if subject_counts[subject] == 1 else f"_{subject_counts[subject]}"
        constraints.append(
            _constraint(f"con_{subject}{suffix}", subject, sentence, evidence_id, value=value)
        )
        tracked = subject in {"terminal_value", "memorandum", "sensitivity"}
        if tracked and subject_counts[subject] == 1:
            outputs.append(
                {
                    "output_id": f"out_{subject}",
                    "name": subject.replace("_", " "),
                    "description": sentence,
                    "evidence_ids": [evidence_id],
                }
            )
        if subject in {"terminal_value", "sensitivity"} and subject_counts[subject] == 1:
            questions.append(
                {
                    "question_id": f"q_{subject}",
                    "text": sentence,
                    "evidence_ids": [evidence_id],
                }
            )

    for subject in conflicts:
        constraints = [item for item in constraints if item["subject"] != subject]
        uncertainties.append(
            {
                "uncertainty_id": f"unc_{subject}",
                "statement": f"The problem text states conflicting values for {subject}.",
                "needs_user_clarification": True,
            }
        )
    if "gold_commission" not in seen_subjects and "bitcoin_commission" not in seen_subjects:
        uncertainties.append(
            {
                "uncertainty_id": "unc_fees",
                "statement": "No commission rate is stated in the problem text.",
                "needs_user_clarification": True,
            }
        )
    if "trading_period" not in seen_subjects:
        uncertainties.append(
            {
                "uncertainty_id": "unc_period",
                "statement": "No trading period is stated in the problem text.",
                "needs_user_clarification": True,
            }
        )
    if revision_notes.strip():
        uncertainties.append(
            {
                "uncertainty_id": "unc_revision",
                "statement": "User revision notes are recorded and are not official constraints.",
                "needs_user_clarification": True,
            }
        )

    if not questions:
        questions.append(
            {
                "question_id": "q_main",
                "text": sentences[0],
                "evidence_ids": ["ev_s1"],
            }
        )
    if not outputs:
        outputs.append(
            {
                "output_id": "out_main",
                "name": "requested work",
                "description": sentences[0],
                "evidence_ids": ["ev_s1"],
            }
        )

    datasets: list[dict[str, Any]] = []
    for index, item in enumerate(uploaded_files or []):
        if not isinstance(item, dict) or not item.get("file_name"):
            continue
        file_name = str(item["file_name"])
        quote = f"file_name: {file_name}"
        if quote not in bulletin:
            continue
        evidence_id = f"ev_file_{index}"
        evidence.append(_evidence(evidence_id, quote, "dataset_metadata"))
        datasets.append(
            {
                "dataset_id": str(item.get("dataset_id") or f"file_{index}"),
                "file_name": file_name,
                "role": file_name,
                "column_names": [str(column) for column in (item.get("column_names") or [])],
                "evidence_ids": [evidence_id],
            }
        )

    digest = hashlib.sha256(
        f"{project_id}|{run_id}|{problem_text}|{input_signature}".encode()
    ).hexdigest()
    body = ProblemSpecificationBody.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "task_intent": sentences[0],
            "research_questions": questions,
            "objectives": [
                {
                    "objective_id": "obj_main",
                    "text": sentences[0],
                    "evidence_ids": ["ev_s1"],
                }
            ],
            "required_outputs": outputs,
            "datasets": datasets,
            "constraints": constraints,
            "uncertainties": uncertainties,
            "proposed_modeling_directions": [
                {
                    "direction_id": "dir_later",
                    "summary": (
                        "Later research may compare candidate approaches. "
                        "This phase does not select or execute a strategy."
                    ),
                    "status": "proposed",
                    "confirmed_fact": False,
                }
            ],
            "evidence": evidence,
        }
    )
    assert_grounded(
        body,
        problem_text=problem_text,
        bulletin=bulletin,
        revision_notes=revision_notes,
    )
    return ProblemSpecification.model_validate(
        {
            **body.model_dump(mode="python"),
            "specification_id": f"psp_{digest[:12]}",
            "project_id": project_id,
            "run_id": run_id,
            "input_signature": input_signature,
            "version": version,
            "generation_mode": "offline_fixture",
            "llm_analysis_complete": False,
            "provider": "offline_fixture",
            "model": "deterministic-parser-v1",
            "prompt_version": PROMPT_VERSION,
            "generated_at": generated_at or utc_now_iso(),
            "downstream_modeling_performed": False,
            "trades_performed": False,
            "h1_approved": False,
        }
    )
