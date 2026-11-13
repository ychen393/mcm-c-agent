"""Streamlit panel: Paper Planner / LaTeX / Reviewer → human H3 gate (Phase 8).

Shows deterministic outline, offline .tex/.bib emission, and light reviewer
checklist. Human Approve / Request-revision only — H3 is never auto-approved.
Phase 9 E2E stays blocked until H3 is approved. Paper generation requires H2.
"""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from agents.paper_planner import paper_planner_status, run_paper_planner
from app.artifact_viewers import (
    render_approved_banner,
    render_h3_approval_card,
    render_paper_pdf_preview,
)
from app.persistence_panel import get_or_create_store
from core.config import Settings
from database.repositories import build_project_store
from paper.gate import e2e_gate_status, paper_allowed, paper_generation_gate_status
from tools.paper_persistence import (
    build_h3_decision,
    persist_h3_decision_into_state,
    persist_paper_into_state,
)

PAPER_SESSION_KEY = "paper_planner_draft"


def clear_paper_h3_caches(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop orphan Phase 8 paper / H3 UI caches."""
    state = st.session_state if session_state is None else session_state
    state.pop(PAPER_SESSION_KEY, None)


def resolve_displayed_paper_package(
    recorded_state: dict[str, Any] | None,
    session_state: MutableMapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Prefer recorded paper package over an orphan session cache."""
    state = st.session_state if session_state is None else session_state
    if recorded_state is not None:
        decision = recorded_state.get("decision_report") or {}
        if isinstance(decision, dict):
            nested = decision.get("paper")
            if isinstance(nested, dict) and nested:
                return nested
        outline = recorded_state.get("paper_outline")
        if isinstance(outline, dict) and outline:
            # Reconstruct a minimal package view from state fields.
            review = recorded_state.get("review_report") or {}
            latex_source = recorded_state.get("latex_source") or ""
            return {
                "package_id": outline.get("package_id") or outline.get("outline_id"),
                "outline": outline,
                "latex": {
                    "bundle_id": (review or {}).get("latex_bundle_id"),
                    "outline_id": outline.get("outline_id"),
                    "tex_source": latex_source,
                    "bib_source": (review or {}).get("bib_source") or "",
                    "compile_attempted": (review or {}).get("compile_attempted"),
                    "compile_ok": (review or {}).get("compile_ok"),
                    "compile_note": (review or {}).get("compile_note"),
                }
                if latex_source
                else None,
                "review": review if isinstance(review, dict) and review else None,
            }
        return None
    cached = state.get(PAPER_SESSION_KEY)
    if isinstance(cached, dict) and cached:
        return cached
    return None


def render_paper_h3_panel(
    *,
    settings: Settings,
    problem_specification: dict[str, Any] | None = None,
    recorded_state: dict[str, Any] | None = None,
    project_id: str | None = None,
    project_name: str | None = None,
    input_signature: str | None = None,
) -> dict[str, Any] | None:
    """Render Paper Planner / LaTeX + human H3 controls."""
    st.subheader("Paper Planner / LaTeX → H3")
    status = paper_planner_status(settings)
    st.caption(
        "Builds a CI-safe deterministic paper outline for 2022 MCM C grounded in "
        "ProblemSpecification, evidence, experiments, and validation. Emits "
        "offline .tex / .bib (PDF compile optional, not required for CI). "
        "Requires human H2 approval. H3 is never auto-approved. Phase 9 E2E "
        "stays blocked until H3 is approved. Citations are never invented."
    )

    p_gate = paper_generation_gate_status(
        recorded_state if isinstance(recorded_state, dict) else None
    )
    if p_gate.paper_allowed:
        st.success(p_gate.message)
    else:
        st.warning(p_gate.message)

    e_gate = e2e_gate_status(
        recorded_state if isinstance(recorded_state, dict) else None
    )
    if e_gate.e2e_allowed:
        st.info(e_gate.message)
    else:
        st.caption(f"E2E gate: {e_gate.message}")

    st.caption(
        f"prompt={status['prompt_version']} · invented_citations={status['invented_citations']} · "
        f"h3_auto_approve={status['h3_auto_approve']} · "
        f"pdf_compile_required_for_ci={status['pdf_compile_required_for_ci']}"
    )

    use_llm = st.checkbox(
        "Attempt LLM paper outline (optional stub)",
        value=bool(settings.paper_use_llm),
        help=(
            "Default off. Phase 8 LLM path records an unavailable stub note; "
            "deterministic fixture outline remains authoritative."
        ),
        key="paper_use_llm_ui",
    )
    st.caption(
        f"Paper LLM effective={use_llm} (settings={settings.paper_use_llm})"
    )
    attempt_pdf = st.checkbox(
        "Attempt PDF compile (optional; soft-fails without TeX)",
        value=False,
        help="Not required for CI green. Soft-fails when pdflatex is missing.",
        key="paper_attempt_pdf_ui",
    )

    package_dict = resolve_displayed_paper_package(recorded_state)

    run_disabled = not p_gate.paper_allowed
    run = st.button(
        "Run deterministic paper planner + LaTeX + review",
        type="primary",
        key="run_paper_planner",
        disabled=run_disabled,
        help="Blocked until human H2 is approved on project state.",
    )

    if run:
        if not paper_allowed(
            recorded_state if isinstance(recorded_state, dict) else None
        ):
            st.error("Paper generation refused: need H2 approved.")
        elif not isinstance(recorded_state, dict):
            st.error("Initialize the project and approve H2 before paper generation.")
        else:
            try:
                package = run_paper_planner(
                    state=recorded_state,
                    problem_specification=problem_specification
                    or recorded_state.get("problem_specification"),
                    use_llm=use_llm,
                    attempt_pdf_compile=attempt_pdf,
                    settings=settings,
                )
            except PermissionError as exc:
                st.error(f"Paper gate blocked run: {exc}")
            except Exception as exc:
                st.error(f"Paper planner failed: {type(exc).__name__}: {exc}")
            else:
                package_dict = package.model_dump(mode="json")
                st.session_state[PAPER_SESSION_KEY] = package_dict
                outline = package.outline
                st.success(
                    f"Paper package ready · package={package.package_id} · "
                    f"outline={outline.outline_id} · sections={len(outline.sections)} · "
                    f"bib={len(outline.bib_entries)} · "
                    f"review={package.review.overall_status if package.review else 'n/a'}"
                )
                if outline.llm_attempted and outline.llm_note:
                    st.info(outline.llm_note)
                if package.latex and package.latex.compile_attempted:
                    if package.latex.compile_ok:
                        st.success(package.latex.compile_note or "PDF compiled.")
                    else:
                        st.warning(
                            package.latex.compile_note
                            or "PDF compile soft-failed (not required for CI)."
                        )

    if package_dict:
        outline = package_dict.get("outline") or {}
        latex = package_dict.get("latex") or {}
        review = package_dict.get("review") or {}
        st.markdown(
            f"**Package:** `{package_dict.get('package_id')}` · "
            f"**Outline:** `{outline.get('outline_id')}` · "
            f"**Title:** {outline.get('title')} · "
            f"**Sections:** {len(outline.get('sections') or [])} · "
            f"**Bib entries:** {len(outline.get('bib_entries') or [])}"
        )

        render_paper_pdf_preview(package_dict)

        for section in outline.get("sections") or []:
            with st.expander(
                f"{section.get('section_id')} · {section.get('title')} · {section.get('kind')}",
                expanded=section.get("kind") in {"abstract", "methods"},
            ):
                st.write(section.get("summary") or "")
                if section.get("citation_keys"):
                    st.caption("citations: " + ", ".join(section["citation_keys"]))
                for ref in section.get("artifact_refs") or []:
                    st.caption(f"grounded ← {ref.get('kind')}:{ref.get('ref_id')}")

        gaps = outline.get("citation_gaps") or []
        if gaps:
            st.warning("Citation gaps (no invented sources): " + ", ".join(gaps))

        bib_entries = outline.get("bib_entries") or []
        if bib_entries:
            st.markdown("**Bibliography (grounded only)**")
            for entry in bib_entries:
                st.write(
                    f"- `{entry.get('citation_key')}` — {entry.get('title')} "
                    f"({entry.get('year') or 'n.d.'})"
                )

        if review:
            st.markdown(
                f"**Reviewer:** `{review.get('overall_status')}` · "
                f"structure_ok={review.get('structure_ok')} · "
                f"citations_ok={review.get('citations_ok')} · "
                f"topic_coverage_ok={review.get('topic_coverage_ok')}"
            )
            for finding in review.get("findings") or []:
                text = (
                    f"`{finding.get('finding_id')}` · {finding.get('category')} · "
                    f"{finding.get('status')} · {finding.get('summary')}"
                )
                if finding.get("status") == "fail":
                    st.error(text)
                elif finding.get("status") == "warn":
                    st.warning(text)
                else:
                    st.info(text)

        if latex and latex.get("tex_source"):
            with st.expander("LaTeX source (.tex)", expanded=False):
                st.code(latex.get("tex_source"), language="latex")
            if latex.get("bib_source"):
                with st.expander("BibTeX source (.bib)", expanded=False):
                    st.code(latex.get("bib_source"), language="bibtex")

        for note in outline.get("analysis_notes") or []:
            st.caption(note)

        attach = st.button(
            "Attach paper package into project state",
            key="persist_paper_package",
            disabled=not p_gate.paper_allowed,
            help=(
                "Stores sanitized paper_outline / latex_source / review_report via "
                "Phase 1 persistence and sets H3=pending. Does not approve H3 or "
                "unlock Phase 9 E2E."
            ),
        )
        if attach:
            recorded = st.session_state.get("last_run")
            form_sig = input_signature or st.session_state.get("foundation_input_signature")
            if not isinstance(recorded, dict) or not recorded.get("run_id"):
                st.error("Initialize the project before attaching the paper package.")
            elif not form_sig:
                st.error("Foundation signature missing; re-initialize the project.")
            elif not paper_allowed(recorded):
                st.error("Attach refused: need H2 approved.")
            else:
                try:
                    store = get_or_create_store(lambda: build_project_store(settings))
                    saved = persist_paper_into_state(
                        store,
                        project_id=str(
                            project_id or recorded.get("project_id") or "mcm-c-demo"
                        ),
                        project_name=str(
                            project_name
                            or recorded.get("project_name")
                            or "MCM C Demo Project"
                        ),
                        state=recorded,
                        input_signature=str(form_sig),
                        package=package_dict,
                    )
                    st.session_state["last_run"] = saved
                    nested = (saved.get("decision_report") or {}).get("paper") or package_dict
                    st.session_state[PAPER_SESSION_KEY] = nested
                    st.success(
                        "Paper package attached with H3=pending. "
                        f"e2e_allowed="
                        f"{((saved.get('decision_report') or {}).get('e2e_gate') or {}).get('e2e_allowed')}"
                    )
                except PermissionError as exc:
                    st.error(f"Paper gate blocked attach: {exc}")
                except Exception as exc:
                    st.error(f"Persist paper failed: {type(exc).__name__}: {exc}")

    # --- Human H3 gate (never auto) ---
    st.markdown("### Human Approval Gate H3")
    gate_state = (
        recorded_state
        if isinstance(recorded_state, dict)
        else st.session_state.get("last_run")
    )
    e2e = e2e_gate_status(gate_state if isinstance(gate_state, dict) else None)
    if e2e.e2e_allowed:
        st.success(e2e.message)
    else:
        st.warning(e2e.message)

    if not package_dict:
        st.info("Run and review the paper package before H3.")
        return package_dict

    h3_status = None
    if isinstance(gate_state, dict):
        h3_status = ((gate_state.get("decision_report") or {}).get("h3") or {}).get(
            "status"
        ) or (gate_state.get("approval_status") or {}).get("h3")
    outline_title = str(
        ((package_dict.get("outline") or {}).get("title"))
        or package_dict.get("package_id")
        or "paper package"
    )
    if h3_status == "approved":
        render_approved_banner("H3", outline_title)
        render_h3_approval_card(package_dict)
        with st.expander("H3 decision details (read-only)", expanded=False):
            st.caption(f"h3_status={h3_status}")
        return package_dict

    st.markdown("#### Approval card")
    render_h3_approval_card(package_dict)

    h3_notes = st.text_area(
        "H3 reviewer notes",
        value="",
        height=80,
        key="h3_reviewer_notes",
        help="Required context for Approve / Request-revision decisions.",
    )

    approve_col, revise_col = st.columns(2)
    with approve_col:
        approve_clicked = st.button(
            "Approve paper (H3)",
            type="primary",
            key="h3_approve",
            help="Human-only. Never auto-approved. Unlocks the E2E gate flag only.",
        )
    with revise_col:
        revise_clicked = st.button(
            "Request revision (H3)",
            key="h3_request_revision",
            help="Returns paper for revision; Phase 9 E2E remains blocked.",
        )

    if approve_clicked or revise_clicked:
        recorded = st.session_state.get("last_run")
        form_sig = input_signature or st.session_state.get("foundation_input_signature")
        if not isinstance(recorded, dict) or not recorded.get("run_id"):
            st.error("Initialize the project and attach the paper package before H3.")
        elif not form_sig:
            st.error("Foundation signature missing; re-initialize the project.")
        else:
            status_value = "approved" if approve_clicked else "revision_requested"
            try:
                store = get_or_create_store(lambda: build_project_store(settings))
                if not (
                    (recorded.get("paper_outline") or {}).get("outline_id")
                    or (recorded.get("decision_report") or {}).get("paper")
                ):
                    recorded = persist_paper_into_state(
                        store,
                        project_id=str(
                            project_id or recorded.get("project_id") or "mcm-c-demo"
                        ),
                        project_name=str(
                            project_name
                            or recorded.get("project_name")
                            or "MCM C Demo Project"
                        ),
                        state=recorded,
                        input_signature=str(form_sig),
                        package=package_dict,
                    )
                decision = build_h3_decision(
                    status=status_value,  # type: ignore[arg-type]
                    package=package_dict,
                    notes=h3_notes or f"Human H3 {status_value}",
                )
                saved = persist_h3_decision_into_state(
                    store,
                    project_id=str(project_id or recorded.get("project_id") or "mcm-c-demo"),
                    project_name=str(
                        project_name or recorded.get("project_name") or "MCM C Demo Project"
                    ),
                    state=recorded,
                    input_signature=str(form_sig),
                    decision=decision,
                )
                st.session_state["last_run"] = saved
                e2e_after = e2e_gate_status(saved)
                if status_value == "approved":
                    render_approved_banner("H3", outline_title)
                    st.success(
                        "H3 approved by human. "
                        f"e2e_allowed={e2e_after.e2e_allowed}. "
                        "Phase 9 E2E is not started by this action."
                    )
                else:
                    st.warning(
                        "H3 revision requested. Phase 9 E2E remains blocked. "
                        f"reason={e2e_after.reason}"
                    )
            except Exception as exc:
                st.error(f"H3 decision failed: {type(exc).__name__}: {exc}")

    return package_dict
