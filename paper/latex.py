"""Offline LaTeX / BibTeX emission from a PaperOutline (Phase 8).

PDF compilation is optional and best-effort: missing TeX tooling must soft-fail
so CI stays green without requiring a TeX install.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from schemas.paper import BibEntry, LatexBundle, PaperOutline

_TEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _escape_tex(text: str) -> str:
    out: list[str] = []
    for ch in text:
        out.append(_TEX_SPECIAL.get(ch, ch))
    return "".join(out)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"[:64]


def _bibtex_type(entry: BibEntry) -> str:
    mapping = {
        "fixture": "misc",
        "online": "misc",
        "article": "article",
        "book": "book",
        "inproceedings": "inproceedings",
        "techreport": "techreport",
        "misc": "misc",
    }
    return mapping.get(entry.entry_type, "misc")


def emit_bib_source(outline: PaperOutline) -> str:
    """Emit a .bib string from grounded bibliography entries only."""
    blocks: list[str] = [
        "% Auto-generated from PaperOutline bib_entries — no invented citations.",
    ]
    for entry in outline.bib_entries:
        if entry.invented:
            raise ValueError(f"Refusing to emit invented bib entry '{entry.citation_key}'")
        etype = _bibtex_type(entry)
        fields: dict[str, str] = dict(entry.bibtex_fields)
        fields.setdefault("title", entry.title)
        if entry.authors:
            fields.setdefault("author", " and ".join(entry.authors))
        if entry.year is not None:
            fields.setdefault("year", str(entry.year))
        if entry.venue:
            fields.setdefault("howpublished", entry.venue)
        if entry.source_id:
            fields.setdefault("note", f"source_id={entry.source_id}; fixture/grounded")
        else:
            fields.setdefault("note", "grounded evidence citation")
        lines = [f"@{etype}{{{entry.citation_key},"]
        for key, value in fields.items():
            safe = str(value).replace("{", "").replace("}", "")
            lines.append(f"  {key} = {{{safe}}},")
        lines.append("}")
        blocks.append("\n".join(lines))
    if len(blocks) == 1:
        blocks.append(
            "% No grounded bib entries were available on the outline; "
            "do not invent citations."
        )
    return "\n\n".join(blocks) + "\n"


def emit_tex_source(outline: PaperOutline, *, bib_filename: str = "refs.bib") -> str:
    """Emit a minimal article .tex draft from the outline / section map."""
    title = _escape_tex(outline.title)
    lines = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{hyperref}",
        r"\begin{document}",
        rf"\title{{{title}}}",
        r"\author{MCM C Agent (Phase 8 deterministic draft)}",
        r"\date{}",
        r"\maketitle",
        "",
    ]
    for section in sorted(outline.sections, key=lambda s: s.order):
        if section.kind == "abstract":
            lines.append(r"\begin{abstract}")
            lines.append(_escape_tex(section.summary))
            lines.append(r"\end{abstract}")
            lines.append("")
            continue
        if section.kind == "references":
            lines.append(r"\section*{References}")
            lines.append(_escape_tex(section.summary))
            if outline.bib_entries:
                lines.append(rf"\bibliographystyle{{plain}}")
                lines.append(rf"\bibliography{{{Path(bib_filename).stem}}}")
                cite_keys = [e.citation_key for e in outline.bib_entries]
                # Ensure keys are referenced so bib entries are not dropped.
                lines.append(
                    "Citations: "
                    + ", ".join(rf"\cite{{{_escape_tex(k)}}}" for k in cite_keys)
                    + "."
                )
            elif outline.citation_gaps:
                lines.append(
                    _escape_tex(
                        "Citation gaps (no invented sources): "
                        + ", ".join(outline.citation_gaps)
                    )
                )
            lines.append("")
            continue

        lines.append(rf"\section{{{_escape_tex(section.title)}}}")
        lines.append(_escape_tex(section.summary))
        if section.citation_keys:
            cites = ", ".join(
                rf"\cite{{{_escape_tex(k)}}}" for k in section.citation_keys
            )
            lines.append(f"Related citations: {cites}.")
        if section.artifact_refs:
            refs = "; ".join(
                f"{ref.kind}:{ref.ref_id}" for ref in section.artifact_refs
            )
            lines.append(r"\par\textit{Grounding: " + _escape_tex(refs) + r"}")
        lines.append("")

    lines.append(r"\end{document}")
    lines.append("")
    return "\n".join(lines)


def build_latex_bundle(
    outline: PaperOutline,
    *,
    attempt_compile: bool = False,
    work_dir: Path | str | None = None,
) -> LatexBundle:
    """Emit .tex/.bib; optionally attempt PDF compile (soft-fail if TeX missing)."""
    bib = emit_bib_source(outline)
    tex = emit_tex_source(outline)
    bundle_id = _stable_id("ltx", outline.outline_id, hashlib.sha256(tex.encode()).hexdigest()[:8])

    compile_attempted = False
    compile_ok: bool | None = None
    compile_note: str | None = None
    pdf_path: str | None = None

    if attempt_compile:
        compile_attempted = True
        compile_ok, compile_note, pdf_path = try_compile_pdf(
            tex_source=tex,
            bib_source=bib,
            work_dir=work_dir,
        )

    return LatexBundle(
        bundle_id=bundle_id,
        outline_id=outline.outline_id,
        tex_source=tex,
        bib_source=bib,
        tex_filename="main.tex",
        bib_filename="refs.bib",
        compile_attempted=compile_attempted,
        compile_ok=compile_ok,
        compile_note=compile_note,
        pdf_path=pdf_path,
    )


def try_compile_pdf(
    *,
    tex_source: str,
    bib_source: str = "",
    work_dir: Path | str | None = None,
) -> tuple[bool, str, str | None]:
    """Best-effort pdflatex(+bibtex). Soft-fails when TeX is not installed."""
    engine = shutil.which("pdflatex")
    if not engine:
        return (
            False,
            "pdflatex not found on PATH; PDF compile skipped (CI-safe soft-fail).",
            None,
        )

    cleanup = False
    root: Path
    if work_dir is None:
        root = Path(tempfile.mkdtemp(prefix="mcm_paper_"))
        cleanup = False  # leave for inspection if caller wants; still soft
    else:
        root = Path(work_dir)
        root.mkdir(parents=True, exist_ok=True)

    tex_path = root / "main.tex"
    bib_path = root / "refs.bib"
    tex_path.write_text(tex_source, encoding="utf-8")
    bib_path.write_text(bib_source or "% empty\n", encoding="utf-8")

    try:
        # Two-pass pdflatex; bibtex when available.
        for _ in range(2):
            proc = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if proc.returncode != 0:
                tail = (proc.stdout or proc.stderr or "")[-800:]
                return False, f"pdflatex failed (exit {proc.returncode}): {tail}", None
        bibtex = shutil.which("bibtex")
        if bibtex and bib_source.strip() and not bib_source.strip().startswith("% No grounded"):
            subprocess.run(
                [bibtex, "main"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        pdf = root / "main.pdf"
        if pdf.is_file():
            return True, f"PDF compiled at {pdf}", str(pdf)
        return False, "pdflatex finished but main.pdf was not produced.", None
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"PDF compile soft-failed: {type(exc).__name__}: {exc}", None
    finally:
        if cleanup:
            shutil.rmtree(root, ignore_errors=True)


def latex_looks_structured(tex_source: str) -> bool:
    """Cheap structural sanity check used by reviewer / tests."""
    if not tex_source or "\\begin{document}" not in tex_source:
        return False
    if "\\end{document}" not in tex_source:
        return False
    return bool(re.search(r"\\(section\*?|begin\{abstract\})", tex_source))


def dump_latex_files(
    bundle: LatexBundle,
    directory: Path | str,
) -> dict[str, Any]:
    """Write .tex / .bib to a directory (offline; no compile)."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    tex_path = root / bundle.tex_filename
    bib_path = root / bundle.bib_filename
    tex_path.write_text(bundle.tex_source, encoding="utf-8")
    bib_path.write_text(bundle.bib_source or "% empty\n", encoding="utf-8")
    return {
        "tex_path": str(tex_path),
        "bib_path": str(bib_path),
        "bundle_id": bundle.bundle_id,
    }
