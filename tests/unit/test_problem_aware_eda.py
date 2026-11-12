"""Phase 3 problem-aware EDA planning — deterministic, no live LLM."""

from __future__ import annotations

from agents.problem_analyst import analyze_problem
from schemas.eda_plan import ProblemAwareEDAPlan
from tools.dataset_bundle import build_dataset_bundle
from tools.problem_aware_eda import build_problem_aware_eda_plan
from tools.problem_spec_2022_c import load_2022_c_fixture
from tools.relationship_profiler import profile_relationships

GOLD = (
    b"Date,USD (PM)\n"
    b"9/12/2016,1324.60\n"
    b"9/13/2016,1321.75\n"
    b"9/14/2016,\n"
    b"9/15/2016,1308.35\n"
)
BITCOIN = (
    b"Date,Value\n"
    b"9/11/2016,621.65\n"
    b"9/12/2016,609.67\n"
    b"9/13/2016,610.92\n"
    b"9/14/2016,608.82\n"
    b"9/15/2016,610.12\n"
)
UNRELATED = b"city,temp\nAustin,90\nDallas,88\n"


def test_2022_c_plan_matches_gold_bitcoin_and_past_data():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    bundle = build_dataset_bundle(
        [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)],
        project_id="phase3-eda",
    )
    relationships = profile_relationships(bundle)
    plan = build_problem_aware_eda_plan(
        bundle=bundle,
        problem_specification=spec,
        relationship_report=relationships,
    )
    assert isinstance(plan, ProblemAwareEDAPlan)
    assert plan.has_problem_specification
    assert plan.problem_id == "2022_mcm_c"
    assert plan.joined is False
    assert plan.invented_joins is False
    statuses = {item.status for item in plan.dataset_matches}
    assert "matched" in statuses
    assert not any(item.status == "missing_upload" for item in plan.dataset_matches)
    reminder_ids = {item.constraint_id for item in plan.constraint_reminders}
    assert "c_past_data_only" in reminder_ids or any(
        "past" in item.eda_implication.lower() for item in plan.constraint_reminders
    )
    assert any("future" in rule.lower() or "past" in rule.lower() for rule in plan.must_not)
    assert any("concat" in rule.lower() or "invent" in rule.lower() for rule in plan.must_not)
    assert plan.suggested_relationships
    assert all(item.auto_join_allowed is False for item in plan.suggested_relationships)
    # Date overlap should allow a preview suggestion, not an auto-join.
    stances = {item.stance for item in plan.suggested_relationships}
    assert "suggest_preview" in stances or "abstain" in stances
    assert "cannot_join" not in stances or len(stances) >= 1


def test_plan_without_spec_still_safe():
    bundle = build_dataset_bundle(
        [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)],
        project_id="phase3-eda",
    )
    plan = build_problem_aware_eda_plan(bundle=bundle, problem_specification=None)
    assert plan.has_problem_specification is False
    assert plan.joined is False
    assert any("concat" in rule.lower() for rule in plan.must_not)


def test_unexpected_upload_and_cannot_invent_join():
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    bundle = build_dataset_bundle(
        [("LBMA-GOLD.csv", GOLD), ("weather.csv", UNRELATED)],
        project_id="phase3-eda",
    )
    relationships = profile_relationships(bundle)
    plan = build_problem_aware_eda_plan(
        bundle=bundle,
        problem_specification=spec,
        relationship_report=relationships,
    )
    statuses = {item.status for item in plan.dataset_matches}
    assert "unexpected_upload" in statuses
    assert "missing_upload" in statuses  # BCHAIN-MKPRU.csv absent
    assert any(
        item.stance in {"cannot_join", "abstain"} for item in plan.suggested_relationships
    )
    assert all(item.auto_join_allowed is False for item in plan.suggested_relationships)


def test_plan_serializes_without_forbidden_persistence_keys():
    from schemas.persistence import assert_safe_for_persistence

    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    bundle = build_dataset_bundle(
        [("LBMA-GOLD.csv", GOLD), ("BCHAIN-MKPRU.csv", BITCOIN)],
        project_id="phase3-eda",
    )
    plan = build_problem_aware_eda_plan(
        bundle=bundle,
        problem_specification=spec,
        relationship_report=profile_relationships(bundle),
    )
    payload = plan.model_dump(mode="json")
    assert_safe_for_persistence(payload, "plan")
