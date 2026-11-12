"""ProblemSpecification rejects missing evidence, contradictions, and invented facts."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.offline_problem_parser import interpret_problem_offline
from schemas.problem_specification import (
    ProblemSpecification,
    ProblemSpecificationBody,
    assert_grounded,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "problem_c_2022_excerpt.txt"
EXCERPT = FIXTURE.read_text(encoding="utf-8")
SIGNATURE = "a" * 64
RUN = "run_0123456789ab"


def _direction() -> dict:
    return {
        "direction_id": "dir_later",
        "summary": "Later research may compare candidate approaches.",
        "status": "proposed",
        "confirmed_fact": False,
    }


def _body(**overrides) -> dict:
    payload = {
        "schema_version": "problem-specification-v1",
        "task_intent": "A trader starts with $1,000 on 2016-09-11.",
        "research_questions": [
            {
                "question_id": "q_main",
                "text": "What final portfolio value is reported on 2021-09-10?",
                "evidence_ids": ["ev_window"],
            }
        ],
        "objectives": [
            {
                "objective_id": "obj_main",
                "text": "A trader starts with $1,000 on 2016-09-11.",
                "evidence_ids": ["ev_cash"],
            }
        ],
        "required_outputs": [
            {
                "output_id": "out_memo",
                "name": "memorandum",
                "description": "Communicate the result in a memorandum of at most two pages.",
                "evidence_ids": ["ev_memo"],
            }
        ],
        "datasets": [],
        "constraints": [
            {
                "constraint_id": "con_cash",
                "subject": "initial_cash",
                "statement": "A trader starts with $1,000 on 2016-09-11.",
                "kind": "official",
                "evidence_ids": ["ev_cash"],
                "value": "$1,000",
            }
        ],
        "uncertainties": [],
        "proposed_modeling_directions": [_direction()],
        "evidence": [
            {
                "evidence_id": "ev_cash",
                "source": "problem_text",
                "quote": "A trader starts with $1,000 on 2016-09-11.",
            },
            {
                "evidence_id": "ev_window",
                "source": "problem_text",
                "quote": "The trading period runs from 2016-09-11 to 2021-09-10.",
            },
            {
                "evidence_id": "ev_memo",
                "source": "problem_text",
                "quote": "Communicate the result in a memorandum of at most two pages.",
            },
        ],
    }
    payload.update(overrides)
    return payload


def test_schema_rejects_missing_questions_and_unknown_fields():
    with pytest.raises(ValidationError):
        ProblemSpecificationBody.model_validate({"schema_version": "problem-specification-v1"})
    payload = _body()
    payload["invented_field"] = "nope"
    with pytest.raises(ValidationError):
        ProblemSpecificationBody.model_validate(payload)


def test_schema_rejects_contradictory_official_values():
    payload = _body()
    payload["constraints"] = [
        {
            "constraint_id": "con_fee_a",
            "subject": "gold_commission",
            "statement": "The commission for gold is 1% of the amount traded.",
            "kind": "official",
            "evidence_ids": ["ev_fee_a"],
            "value": "1%",
        },
        {
            "constraint_id": "con_fee_b",
            "subject": "gold_commission",
            "statement": "The commission for gold is 5% of the amount traded.",
            "kind": "official",
            "evidence_ids": ["ev_fee_b"],
            "value": "5%",
        },
    ]
    payload["evidence"] = [
        *payload["evidence"],
        {
            "evidence_id": "ev_fee_a",
            "source": "problem_text",
            "quote": "The commission for gold is 1% of the amount traded.",
        },
        {
            "evidence_id": "ev_fee_b",
            "source": "problem_text",
            "quote": "The commission for gold is 5% of the amount traded.",
        },
    ]
    with pytest.raises(ValidationError, match="Contradictory official constraints"):
        ProblemSpecificationBody.model_validate(payload)


def test_official_constraint_cannot_cite_metadata_or_omit_evidence():
    payload = _body()
    payload["evidence"][0]["source"] = "dataset_metadata"
    with pytest.raises(ValidationError, match="must cite problem text"):
        ProblemSpecificationBody.model_validate(payload)
    payload = _body()
    payload["constraints"][0]["evidence_ids"] = ["ev_missing"]
    with pytest.raises(ValidationError, match="missing evidence"):
        ProblemSpecificationBody.model_validate(payload)


def test_grounding_rejects_invented_fee_and_future_leakage():
    body = ProblemSpecificationBody.model_validate(_body())
    body.constraints[0].value = "9%"
    body.constraints[0].statement = "The commission for gold is 9% of the amount traded."
    with pytest.raises(ValueError, match="9%"):
        assert_grounded(body, problem_text=EXCERPT, bulletin="")

    leaked = _body()
    leaked["constraints"].append(
        {
            "constraint_id": "con_leak",
            "subject": "information_set",
            "statement": "Look-ahead is allowed.",
            "kind": "official",
            "evidence_ids": ["ev_leak"],
            "value": None,
        }
    )
    leaked["evidence"].append(
        {
            "evidence_id": "ev_leak",
            "source": "problem_text",
            "quote": "No look-ahead is allowed.",
        }
    )
    leaked_body = ProblemSpecificationBody.model_validate(leaked)
    with pytest.raises(ValueError, match="Look-ahead claim|Future-data leakage"):
        assert_grounded(leaked_body, problem_text=EXCERPT, bulletin="")


def test_offline_fixture_is_not_a_completed_llm_analysis():
    spec = interpret_problem_offline(
        problem_text=EXCERPT,
        project_id="mcm-2022-c",
        run_id=RUN,
        input_signature=SIGNATURE,
    )
    assert spec.generation_mode == "offline_fixture"
    assert spec.llm_analysis_complete is False
    assert spec.trades_performed is False
    with pytest.raises(ValidationError, match="offline fixture"):
        ProblemSpecification.model_validate(
            {**spec.model_dump(mode="python"), "llm_analysis_complete": True}
        )


def test_excerpt_identifies_2022_facts_without_hardcoding_another_problem():
    spec = interpret_problem_offline(
        problem_text=EXCERPT,
        project_id="mcm-2022-c",
        run_id=RUN,
        input_signature=SIGNATURE,
        uploaded_files=[
            {
                "dataset_id": "ds_lbma_gold_test01",
                "file_name": "LBMA-GOLD.csv",
                "sha256": "ab" * 32,
                "row_count": 4,
                "column_count": 2,
                "column_names": ["Date", "USD (PM)"],
            },
            {
                "dataset_id": "ds_bchain_test0001",
                "file_name": "BCHAIN-MKPRU.csv",
                "sha256": "cd" * 32,
                "row_count": 5,
                "column_count": 2,
                "column_names": ["Date", "Value"],
            },
        ],
        dataset_metadata={"dataset_count": 2},
    )
    official = "\n".join(
        item.statement for item in spec.constraints if item.kind == "official"
    )
    assert "$1,000" in official
    assert "2016-09-11" in official and "2021-09-10" in official
    assert "market is open" in official
    assert "every day" in official and "Bitcoin" in official
    assert "1%" in official and "2%" in official
    assert "look-ahead" in official.lower() or "cannot see the future" in official
    assert "final portfolio value" in official and "justify" in official
    assert "sensitive" in official.lower()
    assert "memorandum" in official.lower()
    assert {item.file_name for item in spec.datasets} == {"LBMA-GOLD.csv", "BCHAIN-MKPRU.csv"}
    assert all(item.confirmed_fact is False for item in spec.proposed_modeling_directions)

    generic = interpret_problem_offline(
        problem_text=(
            "A store must schedule staff for the next month. "
            "Explain the recommendation in a short note. "
            "No prices or trading fees are stated."
        ),
        project_id="generic-c",
        run_id=RUN,
        input_signature=SIGNATURE,
    )
    generic_official = " ".join(
        item.statement for item in generic.constraints if item.kind == "official"
    )
    assert "1%" not in generic_official
    assert "2%" not in generic_official
    assert "$1,000" not in generic_official
    assert "Bitcoin" not in generic_official
    assert generic.llm_analysis_complete is False
