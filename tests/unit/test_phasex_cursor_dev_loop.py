"""Phase X — machine-checkable Cursor development loop invariants (offline)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas.paper import H3Decision
from schemas.research import H1Decision
from schemas.validation import H2Decision
from scripts.phasex.render_handoff_comment import TEMPLATES, render, template_path

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE_X_DOC = REPO_ROOT / "docs" / "PHASEX_CURSOR_DEV_LOOP.md"
INVARIANTS_JSON = REPO_ROOT / "docs" / "phasex" / "invariants.json"
EVALUATOR_GATE_DOC = REPO_ROOT / "docs" / "phasex" / "PHASE_EVALUATOR_GATE.md"
BASELINE_AUDIT = REPO_ROOT / "docs" / "BASELINE_AUDIT.md"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
BUILDER_SOURCES = (
    REPO_ROOT / "tools" / "research_persistence.py",
    REPO_ROOT / "tools" / "validation_persistence.py",
    REPO_ROOT / "tools" / "paper_persistence.py",
)

PRODUCT_RUNTIME_DIRS = ("app", "agents", "core", "llm", "modeling", "validation", "paper", "tools")
FORBIDDEN_SECRET_PATTERNS = (
    re.compile(r"CURSOR_API_KEY\s*=\s*['\"][^'\"]+['\"]"),
    re.compile(r"cursor\.com/api/[^\s\"']+"),
    re.compile(r"Bearer\s+cursor_[A-Za-z0-9_-]{16,}"),
)
FORBIDDEN_SPAWN_PATTERNS = (
    re.compile(r"start_cloud_agent\s*\("),
    re.compile(r"launch_cursor_agent\s*\("),
    re.compile(r"cursor_cloud\.agents\.create"),
)
MERGE_MAIN_PATTERNS = (
    re.compile(r"gh\s+pr\s+merge"),
    re.compile(r"git\s+push\s+[^\n]*\bmain\b"),
    re.compile(r"merge.*into\s+main", re.IGNORECASE),
)


def _load_invariants() -> dict:
    data = json.loads(INVARIANTS_JSON.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_invariants_catalog_complete():
    data = _load_invariants()
    ids = [item["id"] for item in data["invariants"]]
    assert ids == ["PX-I1", "PX-I2", "PX-I3", "PX-I4", "PX-I5", "PX-I6"]
    assert data["phase"] == "X"


def test_phase_x_doc_exists_and_marks_invariants():
    assert PHASE_X_DOC.is_file()
    text = PHASE_X_DOC.read_text(encoding="utf-8")
    data = _load_invariants()
    for item in data["invariants"]:
        assert item["doc_marker"] in text, f"missing {item['doc_marker']}"
    assert "Coordinator → Builder → CI → Independent Evaluator" in text
    assert "Do **not** merge to `main`" in text
    assert "Do **not** deploy" in text


def test_evaluator_gate_doc_exists():
    """Invariant PX-I3 — evaluator gate file exists (in-repo mirror)."""
    assert EVALUATOR_GATE_DOC.is_file()
    text = EVALUATOR_GATE_DOC.read_text(encoding="utf-8")
    assert "Independent Evaluator" in text
    assert "merge to `main`" in text
    assert "H1" in text and "H2" in text and "H3" in text
    phase_x = PHASE_X_DOC.read_text(encoding="utf-8")
    assert "PHASE_EVALUATOR_GATE.md" in phase_x
    assert "Invariant PX-I3" in phase_x


def test_ci_workflow_has_no_merge_main_automation():
    """Invariant PX-I1 — no merge-to-main automation."""
    assert CI_WORKFLOW.is_file()
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    for pattern in MERGE_MAIN_PATTERNS:
        assert pattern.search(text) is None, f"forbidden merge automation: {pattern.pattern}"
    assert "pytest" in text
    phase_x = PHASE_X_DOC.read_text(encoding="utf-8")
    assert "Invariant PX-I1" in phase_x
    assert "No merge-to-main automation" in phase_x


def test_product_schemas_reject_auto_approved_h_gates():
    """Invariant PX-I2 — schemas refuse auto_approved=True."""
    with pytest.raises(ValidationError):
        H1Decision.model_validate(
            {
                "decision_id": "h1d_px_bad",
                "status": "approved",
                "proposal_id": "prop_px",
                "selected_candidate_id": "cand_px",
                "decided_by": "human",
                "auto_approved": True,
                "decided_at_utc": "2026-11-12T00:00:00Z",
            }
        )
    with pytest.raises(ValidationError):
        H2Decision.model_validate(
            {
                "decision_id": "h2d_px_bad",
                "status": "approved",
                "validation_report_id": "vrep_px",
                "decided_by": "human",
                "auto_approved": True,
                "decided_at_utc": "2026-11-12T00:00:00Z",
            }
        )
    with pytest.raises(ValidationError):
        H3Decision.model_validate(
            {
                "decision_id": "h3d_px_bad",
                "status": "approved",
                "package_id": "ppkg_px",
                "decided_by": "human",
                "auto_approved": True,
                "decided_at_utc": "2026-11-12T00:00:00Z",
            }
        )


def test_product_builders_force_auto_approved_false():
    """Invariant PX-I2 — persistence builders hard-code auto_approved=False."""
    for path in BUILDER_SOURCES:
        text = path.read_text(encoding="utf-8")
        assert "auto_approved=False" in text, path.name
        assert "Never sets auto_approved" in text or "never be auto-approved" in text.lower()


def test_lane_separation_stated_in_docs():
    """Invariant PX-I4 — research vs Cursor-dev separation stated."""
    phase_x = PHASE_X_DOC.read_text(encoding="utf-8")
    assert "Invariant PX-I4" in phase_x
    assert "Product research Agents" in phase_x
    assert "Cursor development Agents" in phase_x
    baseline = BASELINE_AUDIT.read_text(encoding="utf-8")
    assert "Product vs Cursor-development agents" in baseline
    assert "not** merged into product code" in baseline


def test_owner_gates_documented():
    """Invariant PX-I6 — owner gates for merge/deploy/H1–H3."""
    text = PHASE_X_DOC.read_text(encoding="utf-8")
    assert "Invariant PX-I6" in text
    assert "Merge to `main`" in text
    assert "Deploy" in text
    assert "H1" in text and "H2" in text and "H3" in text


def test_product_runtime_has_no_cursor_cloud_secrets_or_spawn():
    """Invariant PX-I5 — no live Cursor Cloud credentials / agent spawn in product runtime."""
    for dirname in PRODUCT_RUNTIME_DIRS:
        root = REPO_ROOT / dirname
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_SECRET_PATTERNS:
                assert pattern.search(text) is None, f"{path}: secret-like pattern {pattern.pattern}"
            for pattern in FORBIDDEN_SPAWN_PATTERNS:
                assert pattern.search(text) is None, f"{path}: spawn pattern {pattern.pattern}"
    phase_x = PHASE_X_DOC.read_text(encoding="utf-8")
    assert "Invariant PX-I5" in phase_x
    assert "Never embed live Cursor Cloud credentials" in phase_x


def test_handoff_templates_and_renderer_offline():
    builder = render("builder", {"phase": "X", "head_sha": "abc123"})
    assert "abc123" in builder
    assert "No merge to `main`" in builder
    assert "{{head_sha}}" not in builder

    evaluator = render("evaluator", {"phase": "X", "head_sha": "def456", "verdict": "PASS"})
    assert "def456" in evaluator
    assert "**PASS**" in evaluator
    assert "merge to `main`" in evaluator
    assert "{{verdict}}" not in evaluator

    for name in TEMPLATES:
        assert template_path(name).is_file()
