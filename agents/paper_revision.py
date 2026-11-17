"""Human H3 revision of grounded paper sections with genuine two-role model review.

AI can edit prose but not fabricate figures, citations, experiment outputs or
approval. The revised LaTeX is re-emitted from the typed outline and checked by
the deterministic paper reviewer before it can be saved.
"""
from __future__ import annotations
import hashlib
import json
import re
from typing import Any

from agents.research_revision import _parse_json_object
from core.config import Settings
from llm.base import BaseLLM
from llm.factory import LLMFactory
from paper.latex import build_latex_bundle
from paper.reviewer import review_paper_outline
from schemas.paper import PaperPackage
from tools.paper_persistence import as_paper_package


_NUMBERS = re.compile(r"(?<![\w])\d+(?:\.\d+)?%?(?![\w])")


def _source_numbers(state: dict[str,Any], package: PaperPackage) -> set[str]:
    """Numbers already present in immutable evidence or prior paper."""
    decision=state.get("decision_report") or {}
    history=[
        state.get("problem_specification"),
        state.get("eda_report"),
        decision.get("experiment"),
        state.get("validation_report"),
        package.model_dump(mode="json"),
    ]
    # Numerical tokens can be restated but never invented by an editing model.
    result=set()
    for item in history:
        if item is not None:
            result.update(_NUMBERS.findall(json.dumps(item,ensure_ascii=False)))
    return result


def revise_paper_with_feedback(
    *,
    state: dict[str,Any],
    package: PaperPackage | dict[str,Any],
    feedback: str,
    settings: Settings,
    llm: BaseLLM | None = None,
    language: str = "zh",
) -> tuple[PaperPackage, dict[str,str]]:
    feedback=feedback.strip()
    if not 12 <= len(feedback) <= 2400:
        raise ValueError("H3 feedback must contain 12–2400 characters")
    current=as_paper_package(package)
    status=(state.get("approval_status") or {}).get("h3")
    decision=state.get("decision_report") or {}
    if status!="revision_requested" or (decision.get("h3") or {}).get("status")!="revision_requested":
        raise PermissionError("H3 must first be explicitly returned for revision")
    if (state.get("approval_status") or {}).get("h2")!="approved":
        raise PermissionError("H3 revisions require approved H2 validation")
    validation=state.get("validation_report") or {}
    if current.outline.validation_report_id != validation.get("report_id"):
        raise ValueError("Paper validation provenance is stale; rerun paper generation")
    if not current.latex or not current.latex.tex_source:
        raise ValueError("An existing compiled-source draft is needed to revise")
    sections={s.section_id:s for s in current.outline.sections}
    if not sections:
        raise ValueError("No paper sections to revise")
    lang="Chinese" if language=="zh" else "English"
    observed={}
    for metric in validation.get("baseline_metrics") or []:
        if isinstance(metric,dict):
            observed[str(metric.get("metric_id"))]=metric.get("value")
    src_nums=_source_numbers(state,current)
    provider=llm or LLMFactory.create(settings)
    payload={
        "human_feedback":feedback,
        "paper_title":current.outline.title,
        "paper_sections":[{
            "section_id":s.section_id,
            "title":s.title,
            "summary":s.summary[:2000],
            "citation_keys":s.citation_keys,
            "grounded_artifact_ids":[r.ref_id for r in s.artifact_refs],
        } for s in current.outline.sections],
        "verified_validation_report_id":validation.get("report_id"),
        "measured_baseline_metrics":observed,
        "unresolved_citation_gaps":current.outline.citation_gaps,
        "constraint":"Prose edits only; do not change measured results, research model, citations or verified datasets.",
    }
    plan=provider.invoke([
        {"role":"system","content":(
            "You are a research paper editor responding to explicit H3 human "
            "review feedback. Revise actual section prose rather than only "
            "explaining how it might be edited. Return ONLY JSON object with "
            "keys edits (1–5 objects, each section_id, revised_text, why), "
            "changes_made (string). The section IDs MUST already exist and cannot "
            "be references/bibliography. revised_text should be one or more "
            "substantive publication-style paragraphs, 80–1800 characters each. "
            "No new numeric observations unless supplied in prior sections or "
            "measured_baseline_metrics; no invented citations, experiments, "
            "bibliography, extra models, or validated optimality claims. "
            "For requests requiring new experiments, return JSON with "
            "unsupported_changes describing what must first be done in H2. "
            f"Respond in {lang}."
        )},
        {"role":"user","content":json.dumps(payload,ensure_ascii=False)},
    ])
    patch=_parse_json_object(str(plan.content))
    if patch.get("unsupported_changes"):
        raise ValueError(
            "The feedback requires new research/validation before H3 can be revised: "+
            str(patch["unsupported_changes"])[:350]
        )
    edits=patch.get("edits")
    explanation=str(patch.get("changes_made") or "").strip()
    if not isinstance(edits,list) or not 1 <= len(edits) <= 5:
        raise ValueError("H3 reviser returned no executable section edits")
    if not 20 <= len(explanation) <= 900:
        raise ValueError("H3 reviser must explain how feedback was addressed")
    seen=set()
    before=[]
    after=[]
    updated_sections=[]
    changes={}
    for item in edits:
        if not isinstance(item,dict) or not {"section_id","revised_text","why"}.issubset(item):
            raise ValueError("Invalid H3 section edit format")
        sid=str(item["section_id"])
        if sid in seen or sid not in sections:
            raise ValueError("Unknown or duplicate section id")
        if sections[sid].kind=="references":
            raise ValueError("AI cannot modify references or citation registry")
        old=sections[sid]
        revised=str(item["revised_text"]).strip()
        reason=str(item["why"]).strip()
        if not 80 <= len(revised) <= 1800 or len(reason) < 10:
            raise ValueError("Missing substantial revised paper prose or explanation")
        invalid_numbers=set(_NUMBERS.findall(revised))-src_nums
        if invalid_numbers:
            raise ValueError(
                "Paper edits introduce unsupported numbers: "+
                ", ".join(sorted(invalid_numbers)[:5])
            )
        if revised==old.summary:
            raise ValueError("Requested rewrite did not change the original section")
        seen.add(sid)
        changes[sid]=revised
        before.append(f"{old.title}: {old.summary[:600]}")
        after.append(f"{old.title}: {revised[:1100]}")
    for section in current.outline.sections:
        if section.section_id in changes:
            updated_sections.append(section.model_copy(update={
                "summary":changes[section.section_id]
            }))
        else:
            updated_sections.append(section)
    digest=hashlib.sha256(json.dumps({
        "old":current.package_id,
        "feedback":feedback,
        "changes":changes,
    },ensure_ascii=False,sort_keys=True).encode("utf-8")).hexdigest()[:14]
    next_outline=current.outline.model_copy(update={
        "outline_id":f"out_{digest}",
        "sections":updated_sections,
        "llm_attempted":True,
        "llm_note":"Feedback-directed editorial rewrite; no new experimental results.",
        "analysis_notes":(list(current.outline.analysis_notes)+[
            f"Human H3 feedback: {feedback[:500]}",
            f"Editor changes: {explanation[:600]}",
        ])[-32:],
    })
    # Verifiable re-emission: regenerate BOTH files from the new typed outline
    # and perform the existing deterministic structural/citation review.
    latex=build_latex_bundle(next_outline,attempt_compile=False)
    deterministic=review_paper_outline(next_outline,latex=latex)
    if deterministic.overall_status=="fail":
        raise ValueError("Revised paper failed deterministic structural/citation audit")

    # Second call is an independent text critic; it may not modify evidence.
    critique=provider.invoke([
        {"role":"system","content":(
            "You are an independent paper reviewer, not the editor. Compare the "
            "actual rewritten sections with the human feedback and identify "
            "remaining clarity, evidence, citation and causal validity concerns. "
            "Do not invent citations or measured results; do not approve H3. "
            f"Respond in {lang} with 3–6 actionable points."
        )},
        {"role":"user","content":json.dumps({
            "feedback":feedback,
            "editor_change_summary":explanation,
            "before":before,
            "after":after,
            "known_citation_gaps":current.outline.citation_gaps,
            "deterministic_review_status":deterministic.overall_status,
        },ensure_ascii=False)},
    ])
    review_text=str(critique.content).strip()[:3200]
    if len(review_text)<20:
        raise ValueError("Independent H3 model reviewer returned insufficient critique")
    next_package=PaperPackage.model_validate({
        **current.model_dump(mode="json"),
        "package_id":f"pkg_{digest}",
        "outline":next_outline.model_dump(mode="json"),
        "latex":latex.model_dump(mode="json"),
        "review":deterministic.model_dump(mode="json"),
    })
    audit={
        "feedback":feedback,
        "before":"\n\n".join(before)[:2900],
        "after":"\n\n".join(after)[:2900],
        "changes_made":explanation,
        "critic_feedback":review_text,
        "previous_package_id":current.package_id,
        "new_package_id":next_package.package_id,
        "validation_report_id":str(validation.get("report_id")),
        "mode":"two_live_llm_calls_plus_latex_regeneration",
        "provider":str(plan.provider)[:80],
        "model":str(plan.model)[:100],
        "latex_rebuilt":"True",
        "deterministic_review_status":deterministic.overall_status,
    }
    return next_package,audit
