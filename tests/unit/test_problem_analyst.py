"""Phase 2 Problem Analyst — fixture-backed acceptance (no live LLM)."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from agents.problem_analyst import (
    PROMPT_VERSION,
    analyze_problem,
    parse_problem_specification,
)
from llm.base import LLMResponse
from schemas.problem_specification import ProblemSpecification, ResearchQuestion
from tools.problem_spec_2022_c import (
    acceptance_checklist_2022_c,
    build_2022_c_specification,
    detect_2022_mcm_c,
    load_2022_c_fixture,
)


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return LLMResponse(content=result, provider="deepseek", model="test-model", usage=None)


@pytest.fixture(scope="module")
def fixture_text() -> str:
    return load_2022_c_fixture()


def test_fixture_contains_acceptance_snippets(fixture_text: str):
    assert "$1000" in fixture_text
    assert "[1000, 0, 0]" in fixture_text
    assert "gold" in fixture_text.lower() and "bitcoin" in fixture_text.lower()
    assert "αgold = 1%" in fixture_text
    assert "αbitcoin = 2%" in fixture_text
    assert "only the past stream of daily prices" in fixture_text
    assert "gold is only traded on days the market is open" in fixture_text
    assert "bitcoin can be traded every day" in fixture_text
    assert "LBMA-GOLD.csv" in fixture_text
    assert "BCHAIN-MKPRU.csv" in fixture_text


def test_detect_and_build_2022_c(fixture_text: str):
    assert detect_2022_mcm_c(fixture_text)
    spec = build_2022_c_specification(fixture_text)
    assert isinstance(spec, ProblemSpecification)
    assert spec.strategy == "deterministic"
    assert spec.problem_id == "2022_mcm_c"
    assert "Trading" in spec.title


def test_2022_c_acceptance_checklist(fixture_text: str):
    spec = analyze_problem(fixture_text, use_llm=False)
    checks = acceptance_checklist_2022_c(spec)
    assert all(checks.values()), f"failed checks: {[k for k, v in checks.items() if not v]}"


def test_analyze_problem_default_is_deterministic(fixture_text: str):
    spec = analyze_problem(fixture_text)
    assert spec.strategy == "deterministic"
    assert spec.analyst_prompt_version == PROMPT_VERSION
    assert any(c.id == "c_initial_capital" for c in spec.constraints)
    assert any(c.id == "c_past_data_only" for c in spec.constraints)
    assert any(c.id == "c_transaction_costs" for c in spec.constraints)
    assert {d.file_name for d in spec.supplied_datasets} == {
        "LBMA-GOLD.csv",
        "BCHAIN-MKPRU.csv",
    }
    assert any(r.id == "tr_past_prices_only" for r in spec.trading_rules)
    assert any(n.id == "n_initial_cash" and n.value == "1000" for n in spec.numeric_conditions)
    assert any(n.id == "n_alpha_gold" and n.value == "1" for n in spec.numeric_conditions)
    assert any(n.id == "n_alpha_bitcoin" and n.value == "2" for n in spec.numeric_conditions)


def test_official_vs_inferred_vs_unknown(fixture_text: str):
    spec = analyze_problem(fixture_text, use_llm=False)
    provenances = {item.provenance for item in spec.constraints}
    assert "official" in provenances
    assert any(a.provenance == "inferred" for a in spec.assumptions_to_validate)
    assert any(a.provenance == "unknown" for a in spec.assumptions_to_validate)
    assert all(u.provenance == "unknown" for u in spec.unknowns_or_risks)
    for item in spec.constraints:
        if item.provenance == "official":
            assert item.source_excerpt
    for rule in spec.trading_rules:
        if rule.provenance == "official":
            assert rule.source_excerpt
    for formula in spec.key_formulas:
        if formula.provenance == "official":
            assert formula.source_excerpt


def test_subproblems_have_io_evidence_methods_acceptance(fixture_text: str):
    spec = analyze_problem(fixture_text, use_llm=False)
    assert len(spec.subproblems) >= 4
    for sub in spec.subproblems:
        assert sub.inputs
        assert sub.outputs
        assert sub.evidence_needed
        assert sub.candidate_methods
        assert sub.acceptance_criteria


def test_missing_acceptance_fact_raises(fixture_text: str):
    corrupted = fixture_text.replace("$1000", "$0").replace("[1000, 0, 0]", "[0, 0, 0]")
    # Still may detect via other signals; force removal of cash markers more thoroughly
    corrupted = corrupted.replace("1000", "999")
    with pytest.raises(ValueError, match="acceptance fact|signature|not match"):
        build_2022_c_specification(corrupted)


def test_unknown_problem_returns_explicit_unknown_spec():
    spec = analyze_problem("A short unrelated prompt about weather.", use_llm=False)
    assert spec.problem_id == "unknown_mcm_c"
    assert spec.fallback_reason
    assert spec.unknowns_or_risks
    assert spec.subproblems


def test_empty_problem_is_unknown():
    spec = analyze_problem("   ", use_llm=False)
    assert spec.problem_id == "unknown_mcm_c"


def test_schema_rejects_official_without_excerpt():
    with pytest.raises(ValidationError):
        ResearchQuestion(
            id="rq_bad",
            statement="Something official sounding.",
            provenance="official",
            source_excerpt=None,
        )


def test_llm_path_validates_and_sets_agent_strategy(fixture_text: str):
    base = analyze_problem(fixture_text, use_llm=False)
    payload = base.model_dump(mode="json")
    payload["strategy"] = "agent"
    llm = FakeLLM([json.dumps(payload)])
    spec = analyze_problem(fixture_text, use_llm=True, llm=llm)
    assert spec.strategy == "agent"
    assert spec.analyst_provider == "deepseek"
    assert spec.analyst_model == "test-model"
    assert len(llm.calls) == 1
    assert acceptance_checklist_2022_c(spec)


def test_llm_repair_then_success(fixture_text: str):
    base = analyze_problem(fixture_text, use_llm=False)
    good = base.model_dump(mode="json")
    good["strategy"] = "agent"
    llm = FakeLLM(["not-json", json.dumps(good)])
    spec = analyze_problem(fixture_text, use_llm=True, llm=llm)
    assert spec.strategy == "agent"
    assert len(llm.calls) == 2


def test_llm_double_failure_recovers_deterministic_for_2022_c(fixture_text: str):
    llm = FakeLLM(["not-json", "still-not-json"])
    spec = analyze_problem(fixture_text, use_llm=True, llm=llm)
    assert spec.strategy == "deterministic"
    assert spec.fallback_reason
    assert acceptance_checklist_2022_c(spec)


def test_parse_problem_specification_strips_fence(fixture_text: str):
    base = analyze_problem(fixture_text, use_llm=False)
    fenced = "```json\n" + base.model_dump_json() + "\n```"
    parsed = parse_problem_specification(fenced)
    assert parsed.problem_id == base.problem_id
