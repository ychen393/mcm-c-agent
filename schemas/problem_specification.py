"""ProblemSpecification contract for the Problem Analyst.

Official constraints must cite verbatim problem-text evidence. Proposed
modeling directions are never confirmed facts. This phase does not record
trades, executed models, or an H1 approval.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "problem-specification-v1"
PROMPT_VERSION = "problem-analyst-v1"

_NUMBER_RE = re.compile(
    r"\$\d{1,3}(?:,\d{3})+(?:\.\d+)?|"
    r"\$\d+(?:\.\d+)?|"
    r"\d+(?:\.\d+)?\s*%|"
    r"\d{4}-\d{2}-\d{2}|"
    r"\d{1,2}/\d{1,2}/\d{4}"
)
_LEAK_RE = re.compile(
    r"(?<!no )(?<!not )look-?ahead is allowed|(?<!not )may use future|"
    r"future prices may be used|use prices after the decision|see the future prices",
    re.IGNORECASE,
)
_BAN_RE = re.compile(
    r"only the past|cannot see the future|no look-?ahead|past stream of daily prices",
    re.IGNORECASE,
)


def numeric_tokens(text: str) -> list[str]:
    return [match.group(0) for match in _NUMBER_RE.finditer(text or "")]


class EvidenceAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(pattern=r"^ev_[a-z0-9_]{1,40}$")
    source: Literal["problem_text", "dataset_metadata", "user_revision"]
    quote: str = Field(min_length=1, max_length=400)


class ResearchQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(pattern=r"^q_[a-z0-9_]{1,40}$")
    text: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1)


class ObjectiveItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective_id: str = Field(pattern=r"^obj_[a-z0-9_]{1,40}$")
    text: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1)


class RequiredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_id: str = Field(pattern=r"^out_[a-z0-9_]{1,40}$")
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1)


class DatasetRole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1, max_length=80)
    file_name: str = Field(min_length=1, max_length=180)
    role: str = Field(min_length=1, max_length=180)
    column_names: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)


class ConstraintItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    constraint_id: str = Field(pattern=r"^con_[a-z0-9_]{1,40}$")
    subject: str = Field(min_length=1, max_length=80)
    statement: str = Field(min_length=1, max_length=500)
    kind: Literal["official", "inferred"]
    evidence_ids: list[str] = Field(min_length=1)
    value: str | None = Field(default=None, max_length=80)


class UncertaintyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uncertainty_id: str = Field(pattern=r"^unc_[a-z0-9_]{1,40}$")
    statement: str = Field(min_length=1, max_length=500)
    needs_user_clarification: bool = True


class ModelingDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction_id: str = Field(pattern=r"^dir_[a-z0-9_]{1,40}$")
    summary: str = Field(min_length=1, max_length=400)
    status: Literal["proposed"] = "proposed"
    confirmed_fact: Literal[False] = False


class ProblemSpecificationBody(BaseModel):
    """Analytical content returned by a model or the offline fixture."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["problem-specification-v1"]
    task_intent: str = Field(min_length=1, max_length=500)
    research_questions: list[ResearchQuestion] = Field(min_length=1)
    objectives: list[ObjectiveItem] = Field(min_length=1)
    required_outputs: list[RequiredOutput] = Field(min_length=1)
    datasets: list[DatasetRole] = Field(default_factory=list)
    constraints: list[ConstraintItem] = Field(default_factory=list)
    uncertainties: list[UncertaintyItem] = Field(default_factory=list)
    proposed_modeling_directions: list[ModelingDirection] = Field(min_length=1)
    evidence: list[EvidenceAnchor] = Field(min_length=1)

    @model_validator(mode="after")
    def _internal_consistency(self) -> ProblemSpecificationBody:
        evidence = {item.evidence_id: item for item in self.evidence}
        if len(evidence) != len(self.evidence):
            raise ValueError("Duplicate evidence ids.")
        referenced: list[tuple[str, list[str]]] = []
        for question in self.research_questions:
            referenced.append((question.question_id, question.evidence_ids))
        for objective in self.objectives:
            referenced.append((objective.objective_id, objective.evidence_ids))
        for output in self.required_outputs:
            referenced.append((output.output_id, output.evidence_ids))
        for dataset in self.datasets:
            referenced.append((dataset.dataset_id, dataset.evidence_ids))
        for constraint in self.constraints:
            referenced.append((constraint.constraint_id, constraint.evidence_ids))
            if constraint.kind == "official":
                for evidence_id in constraint.evidence_ids:
                    anchor = evidence.get(evidence_id)
                    if anchor is None:
                        raise ValueError(
                            f"{constraint.constraint_id} cites missing evidence {evidence_id}."
                        )
                    if anchor.source != "problem_text":
                        raise ValueError(
                            "Official constraint "
                            f"{constraint.constraint_id} must cite problem text."
                        )
        for owner, evidence_ids in referenced:
            for evidence_id in evidence_ids:
                if evidence_id not in evidence:
                    raise ValueError(f"{owner} cites missing evidence {evidence_id}.")
        official_values: dict[str, str] = {}
        for constraint in self.constraints:
            if constraint.kind != "official" or not constraint.value:
                continue
            previous = official_values.get(constraint.subject)
            if previous is not None and previous != constraint.value:
                raise ValueError(
                    f"Contradictory official constraints for subject {constraint.subject}."
                )
            official_values[constraint.subject] = constraint.value
        for constraint in self.constraints:
            if constraint.kind != "inferred" or not constraint.value:
                continue
            official = official_values.get(constraint.subject)
            if official is not None and official != constraint.value:
                raise ValueError(
                    f"Inferred constraint contradicts official subject {constraint.subject}."
                )
        for direction in self.proposed_modeling_directions:
            if direction.confirmed_fact is not False or direction.status != "proposed":
                raise ValueError("Modeling directions must stay proposed, not confirmed.")
            if numeric_tokens(direction.summary):
                raise ValueError("Proposed modeling directions cannot carry numeric facts.")
        return self


class ProblemSpecification(ProblemSpecificationBody):
    """Versioned specification stored on a run. Server-owned fields are not model claims."""

    specification_id: str = Field(pattern=r"^psp_[0-9a-f]{12}$")
    project_id: str = Field(min_length=1, max_length=80)
    run_id: str = Field(pattern=r"^run_[0-9a-f]{12}$")
    input_signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    version: int = Field(ge=1)
    generation_mode: Literal["llm", "offline_fixture"]
    llm_analysis_complete: bool
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=128)
    prompt_version: Literal["problem-analyst-v1"]
    generated_at: str = Field(min_length=10, max_length=40)
    downstream_modeling_performed: Literal[False] = False
    trades_performed: Literal[False] = False
    h1_approved: Literal[False] = False

    @model_validator(mode="after")
    def _honest_generation_flag(self) -> ProblemSpecification:
        if self.generation_mode == "offline_fixture" and self.llm_analysis_complete:
            raise ValueError("An offline fixture cannot be marked as a completed LLM analysis.")
        if self.generation_mode == "llm" and not self.llm_analysis_complete:
            raise ValueError("An LLM specification must be marked llm_analysis_complete.")
        if self.downstream_modeling_performed or self.trades_performed or self.h1_approved:
            raise ValueError("This phase cannot record modeling, trades, or H1 approval.")
        return self


def assert_grounded(
    body: ProblemSpecificationBody,
    *,
    problem_text: str,
    bulletin: str,
    revision_notes: str = "",
) -> None:
    """Reject quotes and numbers that are not in the supplied sources."""
    corpora = {
        "problem_text": problem_text,
        "dataset_metadata": bulletin,
        "user_revision": revision_notes,
    }
    evidence = {item.evidence_id: item for item in body.evidence}
    for anchor in body.evidence:
        corpus = corpora[anchor.source]
        if anchor.quote not in corpus:
            raise ValueError(
                f"Evidence {anchor.evidence_id} is not a verbatim quote of its source."
            )

    if body.task_intent not in problem_text:
        raise ValueError("task_intent must be a verbatim excerpt of the problem text.")

    def _quotes(evidence_ids: list[str]) -> str:
        return "\n".join(evidence[evidence_id].quote for evidence_id in evidence_ids)

    def _require_numbers(label: str, text: str, blob: str, *, allow_bulletin: bool = False) -> None:
        for token in numeric_tokens(text):
            if token not in blob:
                raise ValueError(f"Numeric fact {token} in {label} is not in the cited quote.")
            if token not in problem_text and not (allow_bulletin and token in bulletin):
                raise ValueError(f"Numeric fact {token} in {label} is not in the problem text.")

    for question in body.research_questions:
        _require_numbers(question.question_id, question.text, _quotes(question.evidence_ids))
    for objective in body.objectives:
        _require_numbers(objective.objective_id, objective.text, _quotes(objective.evidence_ids))
    for output in body.required_outputs:
        _require_numbers(output.output_id, output.description, _quotes(output.evidence_ids))
        if numeric_tokens(output.name):
            raise ValueError(f"Output name {output.output_id} cannot carry numeric facts.")
    for dataset in body.datasets:
        blob = _quotes(dataset.evidence_ids)
        for evidence_id in dataset.evidence_ids:
            if evidence[evidence_id].source != "dataset_metadata":
                raise ValueError(f"Dataset {dataset.file_name} must cite dataset metadata.")
        if dataset.file_name not in bulletin and dataset.file_name not in problem_text:
            raise ValueError(f"Dataset file {dataset.file_name} is not in the recorded metadata.")
        if dataset.role not in bulletin and dataset.role not in problem_text:
            raise ValueError(f"Dataset role for {dataset.file_name} is not in the sources.")
        for column in dataset.column_names:
            if column not in bulletin and column not in problem_text:
                raise ValueError(f"Column {column} is not in the recorded metadata.")
        _require_numbers(dataset.file_name, dataset.role, blob, allow_bulletin=True)
    for constraint in body.constraints:
        blob = _quotes(constraint.evidence_ids)
        allow_bulletin = constraint.kind == "inferred"
        _require_numbers(
            constraint.constraint_id,
            constraint.statement,
            blob,
            allow_bulletin=allow_bulletin,
        )
        if constraint.value:
            _require_numbers(
                constraint.constraint_id,
                constraint.value,
                blob,
                allow_bulletin=allow_bulletin,
            )
        if constraint.kind == "official" and _LEAK_RE.search(constraint.statement):
            if not _LEAK_RE.search(blob):
                raise ValueError("Look-ahead claim is not in the cited quote.")
            if _BAN_RE.search(problem_text):
                raise ValueError("Future-data leakage contradicts the problem text.")
    for item in body.uncertainties:
        for token in numeric_tokens(item.statement):
            if token not in problem_text and token not in bulletin and token not in revision_notes:
                raise ValueError(
                    f"Uncertainty states a number that is not in the sources: {token}."
                )
