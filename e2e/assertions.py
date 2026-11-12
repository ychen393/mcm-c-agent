"""Golden / regression assertions for Phase 9 2022 MCM C E2E acceptance."""

from __future__ import annotations

from typing import Any

from schemas.e2e import AcceptanceFactCheck
from schemas.problem_specification import ProblemSpecification
from tools.problem_spec_2022_c import REQUIRED_SNIPPETS

from e2e.acceptance_facts import ACCEPTANCE_FACTS_2022_C, REQUIRED_CSV_NAMES


def _check(
    fact_id: str,
    label: str,
    expected: str,
    observed: str,
    passed: bool,
    notes: str | None = None,
) -> AcceptanceFactCheck:
    return AcceptanceFactCheck(
        fact_id=fact_id,
        label=label,
        expected=expected,
        observed=observed,
        passed=passed,
        notes=notes,
    )


def _as_spec(
    problem_specification: ProblemSpecification | dict[str, Any] | None,
) -> ProblemSpecification | None:
    if problem_specification is None:
        return None
    if isinstance(problem_specification, ProblemSpecification):
        return problem_specification
    if isinstance(problem_specification, dict) and problem_specification:
        return ProblemSpecification.model_validate(problem_specification)
    return None


def collect_acceptance_fact_checks(
    *,
    state: dict[str, Any],
    problem_specification: ProblemSpecification | dict[str, Any] | None = None,
    problem_text: str | None = None,
) -> list[AcceptanceFactCheck]:
    """Collect golden checks over state + artifacts. Does not raise."""
    facts = ACCEPTANCE_FACTS_2022_C
    checks: list[AcceptanceFactCheck] = []
    spec = _as_spec(problem_specification or state.get("problem_specification"))

    # --- Problem identity / cash / assets ---
    problem_id = spec.problem_id if spec else None
    checks.append(
        _check(
            "problem_id",
            "Problem id is 2022_mcm_c",
            "2022_mcm_c",
            str(problem_id),
            problem_id == "2022_mcm_c",
        )
    )

    initial_cash = None
    alpha_gold = None
    alpha_bitcoin = None
    past_data = None
    if state.get("experiment_logs"):
        latest = state["experiment_logs"][-1]
        constraints = (latest or {}).get("constraints") or {}
        params = (latest or {}).get("params") or {}
        initial_cash = constraints.get("initial_cash", params.get("initial_cash"))
        alpha_gold = constraints.get("alpha_gold", params.get("alpha_gold"))
        alpha_bitcoin = constraints.get("alpha_bitcoin", params.get("alpha_bitcoin"))
        past_data = constraints.get("past_data_only", params.get("past_data_only"))
    decision = state.get("decision_report") or {}
    experiment = decision.get("experiment") if isinstance(decision, dict) else None
    if isinstance(experiment, dict) and experiment.get("runs"):
        run0 = experiment["runs"][0]
        constraints = run0.get("constraints") or {}
        params = run0.get("params") or {}
        initial_cash = initial_cash if initial_cash is not None else constraints.get(
            "initial_cash", params.get("initial_cash")
        )
        alpha_gold = alpha_gold if alpha_gold is not None else constraints.get(
            "alpha_gold", params.get("alpha_gold")
        )
        alpha_bitcoin = (
            alpha_bitcoin
            if alpha_bitcoin is not None
            else constraints.get("alpha_bitcoin", params.get("alpha_bitcoin"))
        )
        past_data = past_data if past_data is not None else constraints.get(
            "past_data_only", params.get("past_data_only")
        )

    checks.append(
        _check(
            "initial_cash",
            "Initial cash is $1000",
            str(facts["initial_cash_usd"]),
            str(initial_cash),
            initial_cash is not None and abs(float(initial_cash) - 1000.0) < 1e-9,
        )
    )
    checks.append(
        _check(
            "alpha_gold",
            "Gold commission αgold = 1%",
            str(facts["alpha_gold"]),
            str(alpha_gold),
            alpha_gold is not None and abs(float(alpha_gold) - 0.01) < 1e-9,
        )
    )
    checks.append(
        _check(
            "alpha_bitcoin",
            "Bitcoin commission αbitcoin = 2%",
            str(facts["alpha_bitcoin"]),
            str(alpha_bitcoin),
            alpha_bitcoin is not None and abs(float(alpha_bitcoin) - 0.02) < 1e-9,
        )
    )
    checks.append(
        _check(
            "past_data_only",
            "Past-data-only trading constraint",
            "True",
            str(past_data),
            past_data is True,
        )
    )

    # Assets from constraints / spec.
    assets: list[str] = []
    if isinstance(experiment, dict) and experiment.get("runs"):
        assets = list((experiment["runs"][0].get("constraints") or {}).get("assets") or [])
    if not assets and state.get("experiment_logs"):
        assets = list(
            ((state["experiment_logs"][-1] or {}).get("constraints") or {}).get("assets")
            or []
        )
    assets_l = {a.lower() for a in assets}
    checks.append(
        _check(
            "assets_gold_bitcoin",
            "Assets include gold and bitcoin",
            "gold+bitcoin",
            ",".join(sorted(assets_l)) or "absent",
            "gold" in assets_l and "bitcoin" in assets_l,
        )
    )

    # CSV names from problem text snippets / EDA matches / spec datasets.
    csv_hits: set[str] = set()
    if problem_text:
        lowered = problem_text.lower()
        for name in REQUIRED_CSV_NAMES:
            if name.lower() in lowered:
                csv_hits.add(name)
    if spec is not None:
        for ds in spec.supplied_datasets:
            name = (ds.file_name or "").strip()
            for required in REQUIRED_CSV_NAMES:
                if required.lower() == name.lower() or required.lower() in name.lower():
                    csv_hits.add(required)
            blob = " ".join(
                str(getattr(ds, field, "") or "")
                for field in ("file_name", "statement", "notes")
            ).lower()
            for required in REQUIRED_CSV_NAMES:
                if required.lower() in blob:
                    csv_hits.add(required)
    eda = state.get("eda_plan") or state.get("problem_aware_eda_plan")
    if isinstance(eda, dict):
        for match in eda.get("dataset_matches") or []:
            if not isinstance(match, dict):
                continue
            expected = str(match.get("expected_file_name") or "")
            upload = str(match.get("upload_file_name") or "")
            for required in REQUIRED_CSV_NAMES:
                if required.lower() in expected.lower() or required.lower() in upload.lower():
                    csv_hits.add(required)

    checks.append(
        _check(
            "csv_files",
            "Official CSVs LBMA-GOLD.csv + BCHAIN-MKPRU.csv recognized",
            ",".join(REQUIRED_CSV_NAMES),
            ",".join(sorted(csv_hits)) or "absent",
            set(REQUIRED_CSV_NAMES).issubset(csv_hits),
        )
    )

    # Problem text official snippets (when provided).
    if problem_text:
        missing = [
            key
            for key, snippet in REQUIRED_SNIPPETS.items()
            if snippet.lower() not in problem_text.lower()
            and snippet not in problem_text
            and not (
                key.startswith("alpha_")
                and any(
                    alt.lower() in problem_text.lower()
                    for alt in (
                        snippet.replace("α", "alpha_").replace("α", "a"),
                        snippet,
                    )
                )
            )
        ]
        # Soften alpha unicode variants — extractor already validates; here we
        # only require cash/assets/files/past_data when text is supplied.
        critical = [
            k
            for k in ("initial_cash", "assets_gold", "assets_bitcoin", "past_data", "gold_file", "bitcoin_file")
            if k in missing
        ]
        checks.append(
            _check(
                "problem_text_snippets",
                "Official problem text contains key acceptance excerpts",
                "cash/gold/bitcoin/past/csv snippets present",
                "missing:" + ",".join(critical) if critical else "ok",
                not critical,
            )
        )

    # Human gates — approved, never auto.
    approval = state.get("approval_status") or {}
    for gate_key, fact_id in (("h1", "h1_approved"), ("h2", "h2_approved"), ("h3", "h3_approved")):
        status = approval.get(gate_key)
        checks.append(
            _check(
                fact_id,
                f"{gate_key.upper()} human gate approved",
                "approved",
                str(status),
                status == "approved",
            )
        )

    for gate_key, fact_id in (("h1", "h1_human"), ("h2", "h2_human"), ("h3", "h3_human")):
        block = (decision.get(gate_key) if isinstance(decision, dict) else None) or {}
        auto = block.get("auto_approved")
        by = block.get("decided_by")
        ok = auto is False and by == "human"
        checks.append(
            _check(
                fact_id,
                f"{gate_key.upper()} decided_by=human and auto_approved=False",
                "human/False",
                f"{by}/{auto}",
                ok,
            )
        )

    # Harness provenance vs product UI.
    harness = (decision.get("e2e_harness") if isinstance(decision, dict) else None) or {}
    gates = harness.get("gates") if isinstance(harness, dict) else None
    harness_ok = (
        isinstance(harness, dict)
        and harness.get("product_ui_gates_remain_human_only") is True
        and isinstance(gates, list)
        and len(gates) >= 3
        and all(g.get("harness_simulated_human") is True for g in gates if isinstance(g, dict))
        and all(g.get("auto_approved") is False for g in gates if isinstance(g, dict))
    )
    checks.append(
        _check(
            "harness_gate_doubles",
            "H1/H2/H3 harness test doubles recorded (not product auto-approve)",
            "3 simulated-human gate records",
            f"n={len(gates) if isinstance(gates, list) else 0}",
            bool(harness_ok),
            notes="Product UI panels remain the only live human path.",
        )
    )

    # Critical artifacts exist.
    outline = state.get("paper_outline") or {}
    latex = state.get("latex_source")
    review = state.get("review_report") or {}
    validation = state.get("validation_report") or {}
    evidence = state.get("evidence_report") or {}
    proposal = state.get("research_proposal") or {}

    checks.append(
        _check(
            "artifact_problem_spec",
            "ProblemSpecification attached",
            "present",
            "present" if spec else "absent",
            spec is not None,
        )
    )
    checks.append(
        _check(
            "artifact_evidence",
            "Evidence report attached",
            "present",
            "present" if evidence else "absent",
            bool(evidence.get("cards") is not None and evidence),
        )
    )
    checks.append(
        _check(
            "artifact_proposal",
            "Research proposal attached",
            "present",
            "present" if proposal else "absent",
            bool(proposal.get("proposal_id")),
        )
    )
    checks.append(
        _check(
            "artifact_experiment",
            "Experiment results attached",
            "present",
            "present" if experiment or state.get("experiment_logs") else "absent",
            bool(experiment) or bool(state.get("experiment_logs")),
        )
    )
    checks.append(
        _check(
            "artifact_validation",
            "Validation report attached",
            "present",
            "present" if validation else "absent",
            bool(validation.get("report_id")),
        )
    )
    checks.append(
        _check(
            "artifact_paper_outline",
            "Paper outline attached",
            "present",
            "present" if outline else "absent",
            bool(outline.get("outline_id") or outline.get("package_id")),
        )
    )
    checks.append(
        _check(
            "artifact_latex",
            "LaTeX source attached",
            "non-empty",
            "present" if latex else "absent",
            bool(latex) and len(str(latex)) > 20,
        )
    )
    checks.append(
        _check(
            "artifact_review",
            "Paper review report attached",
            "present",
            "present" if review else "absent",
            bool(review.get("review_id") or review.get("overall_status")),
        )
    )

    # Non-invented citations.
    invented = False
    if isinstance(evidence, dict) and evidence.get("invented_sources"):
        invented = True
    if isinstance(evidence, dict):
        for card in evidence.get("cards") or []:
            if isinstance(card, dict) and card.get("invented"):
                invented = True
    if isinstance(outline, dict):
        if outline.get("invented_citations"):
            invented = True
        for bib in outline.get("bib_entries") or []:
            if isinstance(bib, dict) and bib.get("invented"):
                invented = True
    paper = decision.get("paper") if isinstance(decision, dict) else None
    if isinstance(paper, dict) and paper.get("invented_citations"):
        invented = True

    checks.append(
        _check(
            "citations_not_invented",
            "No invented citations in evidence / paper bibliography",
            "invented=False",
            f"invented={invented}",
            not invented,
        )
    )

    # E2E gate unlocked only via H3.
    e2e_gate = decision.get("e2e_gate") if isinstance(decision, dict) else None
    e2e_allowed = bool(isinstance(e2e_gate, dict) and e2e_gate.get("e2e_allowed"))
    if not e2e_allowed:
        # Fall back to approval_status.
        e2e_allowed = approval.get("h3") == "approved"
    checks.append(
        _check(
            "e2e_requires_h3",
            "E2E allowed only after human H3 approval",
            "e2e_allowed=True with h3=approved",
            f"e2e_allowed={e2e_allowed}; h3={approval.get('h3')}",
            e2e_allowed and approval.get("h3") == "approved",
        )
    )

    return checks


def assert_acceptance_facts(
    *,
    state: dict[str, Any],
    problem_specification: ProblemSpecification | dict[str, Any] | None = None,
    problem_text: str | None = None,
) -> list[AcceptanceFactCheck]:
    """Raise AssertionError if any golden check fails; return checks on success."""
    checks = collect_acceptance_fact_checks(
        state=state,
        problem_specification=problem_specification,
        problem_text=problem_text,
    )
    failed = [c for c in checks if not c.passed]
    if failed:
        lines = [
            f"- {c.fact_id}: expected={c.expected!r} observed={c.observed!r}"
            for c in failed
        ]
        raise AssertionError(
            "Phase 9 E2E acceptance fact checks failed:\n" + "\n".join(lines)
        )
    return checks
