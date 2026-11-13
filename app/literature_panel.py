"""Streamlit panel: run Literature & Evidence Agent and attach cards to state."""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st
from app.i18n import t

from agents.literature_evidence import gather_literature_evidence
from app.persistence_panel import get_or_create_store
from core.config import Settings
from database.repositories import build_project_store
from tools.evidence_persistence import persist_evidence_into_state

EVIDENCE_REPORT_SESSION_KEY = "literature_evidence_report"


def clear_literature_evidence_cache(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop orphan literature evidence UI cache."""
    state = st.session_state if session_state is None else session_state
    state.pop(EVIDENCE_REPORT_SESSION_KEY, None)


def resolve_displayed_evidence_report(
    recorded_state: dict[str, Any] | None,
    session_state: MutableMapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Prefer recorded ResearchState over an orphan session cache."""
    state = st.session_state if session_state is None else session_state
    if recorded_state is not None:
        existing = recorded_state.get("evidence_report")
        if isinstance(existing, dict) and existing:
            return existing
        return None
    cached = state.get(EVIDENCE_REPORT_SESSION_KEY)
    if isinstance(cached, dict) and cached:
        return cached
    return None


def render_literature_evidence_panel(
    *,
    settings: Settings,
    problem_specification: dict[str, Any] | None,
    eda_plan: dict[str, Any] | None = None,
    eda_report: dict[str, Any] | None = None,
    recorded_state: dict[str, Any] | None = None,
    project_id: str | None = None,
    project_name: str | None = None,
    input_signature: str | None = None,
) -> dict[str, Any] | None:
    """Render literature controls. Returns the latest evidence report dict if any."""
    st.subheader(t("lit.subheader"))
    st.caption(t("lit.caption"))

    use_live = st.checkbox(
        t("lit.live"),
        value=bool(settings.literature_live_retrieval),
        help=t("lit.live_help"),
        key="literature_live_retrieval_ui",
    )

    col_a, col_b = st.columns([1, 2])
    with col_a:
        run = st.button(t("lit.gather"), type="primary", key="run_literature_evidence")
    with col_b:
        st.caption(
            t(
                "lit.effective",
                effective=use_live,
                settings=settings.literature_live_retrieval,
            )
        )

    report_dict = resolve_displayed_evidence_report(recorded_state)

    if run:
        if not problem_specification:
            st.warning(t("lit.no_spec"))
        try:
            report = gather_literature_evidence(
                problem_specification=problem_specification,
                eda_plan=eda_plan,
                eda_report=eda_report,
                use_live=use_live,
                settings=settings,
            )
        except Exception as exc:
            st.error(t("lit.failed", err=f"{type(exc).__name__}: {exc}"))
        else:
            report_dict = report.model_dump(mode="json")
            st.session_state[EVIDENCE_REPORT_SESSION_KEY] = report_dict
            if st.session_state.get("last_run") is not None:
                updated = dict(st.session_state["last_run"])
                updated["evidence_report"] = report_dict
                st.session_state["last_run"] = updated
            st.success(
                t(
                    "lit.ready",
                    cards=len(report.cards),
                    gaps=len(report.gaps),
                    strategy=report.strategy,
                )
            )
            if report.live_retrieval_attempted and report.live_retrieval_note:
                st.info(report.live_retrieval_note)
            if report.invented_sources:
                st.error(t("lit.invented"))

    if report_dict:
        cards = report_dict.get("cards") or []
        gaps = report_dict.get("gaps") or []
        st.markdown(
            t(
                "lit.summary",
                cards=len(cards),
                gaps=len(gaps),
                pg=("yes" if report_dict.get("problem_specification_present") else "no"),
                eda=("yes" if report_dict.get("eda_context_present") else "no"),
            )
        )
        for card in cards:
            source = card.get("source") or {}
            with st.expander(
                f"{card.get('card_id')} · {source.get('title', 'Untitled')} · "
                f"{card.get('verification_status')}",
                expanded=False,
            ):
                st.caption(
                    f"source_id={source.get('source_id')} · "
                    f"type={source.get('source_type')} · "
                    f"locator={card.get('locator_status')} · "
                    f"citation={((card.get('citation') or {}).get('citation_key'))}"
                )
                st.write(card.get("claim_summary") or "")
                for snippet in card.get("snippets") or []:
                    st.markdown(f"> {snippet.get('text')}")
                    if snippet.get("locator"):
                        st.caption(t("lit.locator", locator=snippet["locator"]))
                if card.get("method_notes"):
                    st.markdown(t("lit.method_notes"))
                    for note in card["method_notes"]:
                        st.write(
                            f"- **{note.get('method_name')}**: {note.get('summary')}"
                        )
                if card.get("grounding"):
                    st.markdown(t("lit.grounding"))
                    for link in card["grounding"]:
                        st.write(
                            f"- `{link.get('kind')}` `{link.get('target_id')}` "
                            f"({link.get('strength')}): {link.get('relevance')}"
                        )
        if gaps:
            # UX-A leftover / UX-B fold: badge + collapsed list; at most 3 always-on.
            always_on = gaps[:3]
            remainder = gaps[3:]
            st.markdown(t("lit.gaps_badge", n=len(gaps)))
            for gap in always_on:
                st.warning(
                    f"`{gap.get('gap_id')}` · {gap.get('sufficiency')} · "
                    f"{gap.get('statement')}"
                )
            with st.expander(
                t("lit.gaps_expander", n=len(gaps)),
                expanded=False,
            ):
                for gap in gaps:
                    st.warning(
                        f"`{gap.get('gap_id')}` · {gap.get('sufficiency')} · "
                        f"{gap.get('statement')}"
                    )
                if remainder:
                    st.caption(
                        t(
                            "lit.gaps_preview_caption",
                            n=len(gaps),
                            previewed=len(always_on),
                        )
                    )

        attach = st.button(
            t("lit.attach"),
            key="persist_literature_evidence",
            help=t("lit.attach_help"),
        )
        if attach:
            recorded = st.session_state.get("last_run")
            form_sig = input_signature or st.session_state.get("foundation_input_signature")
            if not isinstance(recorded, dict) or not recorded.get("run_id"):
                st.error(t("lit.init_before"))
            elif not form_sig:
                st.error(t("common.sig_missing"))
            else:
                try:
                    store = get_or_create_store(lambda: build_project_store(settings))
                    saved = persist_evidence_into_state(
                        store,
                        project_id=str(
                            project_id or recorded.get("project_id") or "mcm-c-demo"
                        ),
                        project_name=str(
                            project_name or recorded.get("project_name") or "MCM C Demo Project"
                        ),
                        state=recorded,
                        input_signature=str(form_sig),
                        report=report_dict,
                    )
                    st.session_state["last_run"] = saved
                    st.session_state[EVIDENCE_REPORT_SESSION_KEY] = saved.get(
                        "evidence_report"
                    )
                    st.success(
                        t(
                            "lit.attached",
                            citations=len(saved.get("citations") or []),
                            lifecycle=saved.get("lifecycle"),
                        )
                    )
                except Exception as exc:
                    st.error(t("lit.persist_failed", err=f"{type(exc).__name__}: {exc}"))
    else:
        st.info(t("lit.none_yet"))

    return report_dict
