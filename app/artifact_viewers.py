"""Human-facing artifact viewers for modeling / validation / paper (UX-B)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from modeling.fixture_data import PRICE_FIXTURE_ID, load_price_fixture


def _candidate_by_id(
    proposal: dict[str, Any] | None, candidate_id: str | None
) -> dict[str, Any] | None:
    if not isinstance(proposal, dict) or not candidate_id:
        return None
    for cand in proposal.get("candidates") or []:
        if isinstance(cand, dict) and cand.get("candidate_id") == candidate_id:
            return cand
    return None


def candidate_display_label(cand: dict[str, Any] | None, *, fallback_id: str = "") -> str:
    """Human label: title first, ID secondary."""
    if not isinstance(cand, dict):
        return fallback_id or "(unknown)"
    title = str(cand.get("title") or "").strip()
    cid = str(cand.get("candidate_id") or fallback_id or "").strip()
    if title and cid:
        return f"{title} ({cid})"
    return title or cid or "(unknown)"


def render_chip_row(chips: list[str]) -> None:
    """Compact status chips as a single caption line."""
    cleaned = [c.strip() for c in chips if isinstance(c, str) and c.strip()]
    if cleaned:
        st.caption(" · ".join(cleaned))


def render_h1_approval_card(
    *,
    candidate: dict[str, Any] | None,
    critique: dict[str, Any] | None = None,
    recommended: bool = False,
) -> None:
    """Primary H1 review card: title, summary, why, critique / evidence chips."""
    if not isinstance(candidate, dict):
        st.info("No candidate selected for review.")
        return
    title = str(candidate.get("title") or candidate.get("candidate_id") or "Candidate")
    heading = f"**Recommended plan:** {title}" if recommended else f"**Plan:** {title}"
    st.markdown(heading)
    st.caption(
        f"id={candidate.get('candidate_id')} · family={candidate.get('method_family')} · "
        f"status={candidate.get('status')}"
    )
    summary = candidate.get("summary")
    if summary:
        st.write(summary)

    strengths = [s for s in (candidate.get("strengths") or []) if isinstance(s, str)]
    if strengths:
        st.markdown("**Why recommended**")
        for item in strengths[:5]:
            st.write(f"- {item}")
    elif recommended:
        st.caption("No explicit strength bullets — review summary and hypotheses above.")

    evidence_n = len(candidate.get("evidence_card_ids") or [])
    gap_n = len(candidate.get("evidence_gap_ids") or [])
    blocking = 0
    if isinstance(critique, dict):
        blocking = int(critique.get("blocking_count") or 0)
        findings = critique.get("findings") or []
        if not blocking and isinstance(findings, list):
            blocking = sum(
                1
                for f in findings
                if isinstance(f, dict) and f.get("severity") == "blocking"
            )
    render_chip_row(
        [
            f"Evidence cards: {evidence_n}",
            f"Evidence gaps: {gap_n}",
            f"Critique blockers: {blocking}",
        ]
    )


def render_approved_banner(gate: str, summary: str) -> None:
    """Read-only post-approval banner."""
    st.success(f"Approved: {summary}")
    st.caption(f"{gate} decision recorded — controls below are read-only.")


def render_fixture_vs_uploads_banner(
    *,
    upload_count: int,
    fixture_id: str = PRICE_FIXTURE_ID,
) -> None:
    """Warn when Dataset Explorer has uploads but modeling uses synthetic fixture."""
    if upload_count <= 0:
        return
    st.warning(
        f"**Fixture ≠ uploads:** Dataset Explorer has **{upload_count}** uploaded file(s), "
        f"but this Modeling run uses synthetic price fixture `{fixture_id}` — "
        "uploaded CSVs are **not** driving the backtest."
    )


def _equity_frame(payload: dict[str, Any]) -> pd.DataFrame | None:
    series = payload.get("series")
    if isinstance(series, list) and series:
        rows = []
        for item in series:
            if not isinstance(item, dict):
                continue
            equity = item.get("equity")
            if equity is None:
                continue
            rows.append(
                {
                    "date": item.get("date") or item.get("day_index"),
                    "equity": float(equity),
                }
            )
        if rows:
            frame = pd.DataFrame(rows)
            return frame.set_index("date")
    samples = payload.get("sample_points")
    if isinstance(samples, list) and samples:
        values = [float(v) for v in samples if isinstance(v, (int, float))]
        if values:
            return pd.DataFrame({"equity": values})
    return None


def render_modeling_artifact_viewers(
    artifacts: list[Any],
    *,
    fixture_id: str = PRICE_FIXTURE_ID,
) -> None:
    """Plot equity curve and fixture price series; raw JSON stays in expanders."""
    arts = [a for a in artifacts if isinstance(a, dict)]
    equity_art = next((a for a in arts if a.get("kind") == "equity_curve_summary"), None)
    fixture_art = next((a for a in arts if a.get("kind") == "price_fixture_ref"), None)

    st.markdown("**Result viewers**")
    if equity_art:
        payload = equity_art.get("payload") or {}
        if isinstance(payload, dict):
            frame = _equity_frame(payload)
            if frame is not None and not frame.empty:
                st.caption("Equity curve (fixture backtest)")
                st.line_chart(frame, use_container_width=True)
            else:
                st.caption("Equity artifact present but no plottable series.")
    else:
        st.caption("No equity_curve_summary artifact on this run.")

    resolved_fixture = fixture_id
    if isinstance(fixture_art, dict):
        payload = fixture_art.get("payload") or {}
        if isinstance(payload, dict) and payload.get("fixture_id"):
            resolved_fixture = str(payload["fixture_id"])

    try:
        bars = load_price_fixture(resolved_fixture)
    except Exception:
        bars = []
    if bars:
        price_rows = [
            {
                "date": bar.date,
                "bitcoin": bar.bitcoin,
                "gold": bar.gold if bar.gold is not None else float("nan"),
            }
            for bar in bars
        ]
        price_frame = pd.DataFrame(price_rows).set_index("date")
        st.caption(f"Key price series · fixture `{resolved_fixture}` (synthetic)")
        st.line_chart(price_frame, use_container_width=True)


def build_h2_scenario_delta_table(report: dict[str, Any]) -> pd.DataFrame:
    """One row per scenario × primary metric delta for table + chart."""
    rows: list[dict[str, Any]] = []
    for scn in report.get("scenarios") or []:
        if not isinstance(scn, dict):
            continue
        sid = str(scn.get("scenario_id") or "")
        label = str(scn.get("label") or sid)
        kind = str(scn.get("kind") or "")
        deltas = scn.get("deltas") or []
        if not deltas:
            rows.append(
                {
                    "scenario": label,
                    "scenario_id": sid,
                    "kind": kind,
                    "metric": "(none)",
                    "baseline": None,
                    "scenario_value": None,
                    "absolute_delta": None,
                    "relative_delta_pct": None,
                }
            )
            continue
        for delta in deltas:
            if not isinstance(delta, dict):
                continue
            rel = delta.get("relative_delta")
            rows.append(
                {
                    "scenario": label,
                    "scenario_id": sid,
                    "kind": kind,
                    "metric": str(delta.get("label") or delta.get("metric_id") or ""),
                    "baseline": delta.get("baseline_value"),
                    "scenario_value": delta.get("scenario_value"),
                    "absolute_delta": delta.get("absolute_delta"),
                    "relative_delta_pct": round(float(rel) * 100.0, 3)
                    if isinstance(rel, (int, float))
                    else None,
                }
            )
    return pd.DataFrame(rows)


def render_h2_scenario_viewers(report: dict[str, Any]) -> None:
    """Baseline-vs-scenario table + sensitivity chart."""
    frame = build_h2_scenario_delta_table(report)
    st.markdown("**Sensitivity table**")
    if frame.empty:
        st.caption("No scenario deltas to display.")
        return
    display_cols = [
        c
        for c in (
            "scenario",
            "kind",
            "metric",
            "baseline",
            "scenario_value",
            "absolute_delta",
            "relative_delta_pct",
        )
        if c in frame.columns
    ]
    st.dataframe(frame[display_cols], use_container_width=True, hide_index=True)

    # Chart: terminal_value (or first metric) absolute deltas by scenario
    preferred = frame[frame["metric"].str.contains("terminal|return|value", case=False, na=False)]
    chart_src = preferred if not preferred.empty else frame
    chart_src = chart_src.dropna(subset=["absolute_delta"])
    if chart_src.empty:
        st.caption("No numeric deltas available for chart.")
        return
    # One bar per scenario for the first preferred metric
    first_metric = chart_src["metric"].iloc[0]
    subset = chart_src[chart_src["metric"] == first_metric]
    if subset.empty:
        subset = chart_src.drop_duplicates(subset=["scenario"], keep="first")
    plot = subset.set_index("scenario")[["absolute_delta"]].rename(
        columns={"absolute_delta": first_metric or "delta"}
    )
    st.caption(f"Scenario deltas · {first_metric}")
    st.bar_chart(plot, use_container_width=True)


def render_h2_approval_card(report: dict[str, Any]) -> None:
    """Compact H2 review card from validation report."""
    st.markdown("**Validation package**")
    st.caption(
        f"report={report.get('report_id')} · baseline={report.get('baseline_run_id')} · "
        f"candidate={report.get('selected_candidate_id')} · "
        f"scenarios={len(report.get('scenarios') or [])}"
    )
    baseline = report.get("baseline_metrics") or []
    if baseline:
        st.markdown("**Baseline metrics**")
        for metric in baseline[:6]:
            if not isinstance(metric, dict):
                continue
            st.write(
                f"- {metric.get('label')}: **{metric.get('value')}** "
                f"{metric.get('unit') or ''}".rstrip()
            )
    notes = report.get("robustness_notes") or []
    high = [
        n
        for n in notes
        if isinstance(n, dict) and n.get("severity") in {"high", "blocking"}
    ]
    render_chip_row(
        [
            f"Scenarios: {len(report.get('scenarios') or [])}",
            f"High/blocking notes: {len(high)}",
            f"Total robustness notes: {len(notes)}",
        ]
    )


def render_h3_approval_card(package: dict[str, Any]) -> None:
    """Paper package review card: title, TOC, review chips."""
    outline = package.get("outline") or {}
    review = package.get("review") or {}
    latex = package.get("latex") or {}
    title = str(outline.get("title") or "Paper package")
    st.markdown(f"**Paper:** {title}")
    st.caption(
        f"package={package.get('package_id')} · outline={outline.get('outline_id')} · "
        f"sections={len(outline.get('sections') or [])} · "
        f"bib={len(outline.get('bib_entries') or [])}"
    )
    sections = outline.get("sections") or []
    if sections:
        st.markdown("**Outline**")
        for section in sections:
            if not isinstance(section, dict):
                continue
            st.write(
                f"- {section.get('title')} ({section.get('kind') or section.get('section_id')})"
            )
    compile_ok = latex.get("compile_ok") if isinstance(latex, dict) else None
    render_chip_row(
        [
            f"Review: {review.get('overall_status') or 'n/a'}",
            f"structure_ok={review.get('structure_ok')}",
            f"citations_ok={review.get('citations_ok')}",
            f"PDF compile_ok={compile_ok}",
        ]
    )


def render_paper_pdf_preview(package: dict[str, Any]) -> None:
    """Show PDF when compiled path exists; otherwise clear outline-only message."""
    latex = package.get("latex") if isinstance(package.get("latex"), dict) else {}
    pdf_path = latex.get("pdf_path") if isinstance(latex, dict) else None
    compile_ok = latex.get("compile_ok") if isinstance(latex, dict) else None
    compile_note = latex.get("compile_note") if isinstance(latex, dict) else None

    st.markdown("**Paper preview**")
    if pdf_path and compile_ok:
        path = Path(str(pdf_path))
        if path.is_file():
            try:
                st.pdf(str(path))
                return
            except Exception as exc:
                st.warning(f"PDF exists but preview failed: {type(exc).__name__}: {exc}")
                st.download_button(
                    "Download compiled PDF",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="application/pdf",
                    key="paper_pdf_download",
                )
                return
        st.warning(
            f"PDF compile reported ok but file is missing: `{pdf_path}`. "
            "Showing outline-only view."
        )
    elif latex.get("compile_attempted") and not compile_ok:
        st.info(
            "Outline-only view — PDF was not compiled. "
            + (str(compile_note) if compile_note else "TeX tooling may be unavailable.")
        )
    else:
        st.info(
            "Outline-only view — PDF not compiled. "
            "Enable “Attempt PDF compile” when generating if a local TeX install is available."
        )


def resolve_h1_selected_candidate(
    recorded_state: dict[str, Any] | None,
    proposal: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any] | None, str | None]:
    """Return (status, candidate dict, display title) for approved/pending H1."""
    if not isinstance(recorded_state, dict):
        return None, None, None
    decision = recorded_state.get("decision_report") or {}
    h1 = decision.get("h1") if isinstance(decision, dict) else None
    status = None
    selected_id = None
    if isinstance(h1, dict):
        status = h1.get("status")
        selected_id = h1.get("selected_candidate_id")
    if not status:
        status = (recorded_state.get("approval_status") or {}).get("h1")
    cand = _candidate_by_id(proposal, selected_id)
    if cand is None and isinstance(proposal, dict):
        cand = _candidate_by_id(proposal, proposal.get("recommended_candidate_id"))
    title = None
    if isinstance(cand, dict):
        title = str(cand.get("title") or cand.get("candidate_id"))
    elif selected_id:
        title = str(selected_id)
    return (str(status) if status else None), cand, title
