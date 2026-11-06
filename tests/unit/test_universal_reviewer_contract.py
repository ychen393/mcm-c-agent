"""Offline sanity checks for the reviewer prompt/profile contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / ".cursor/agents/universal-reviewer.md"
PROFILE = ROOT / ".cursor/review-profiles/mcm.md"
RUNBOOK = ROOT / "docs/UNIVERSAL_REVIEWER_RUNBOOK.md"


def test_universal_reviewer_role_and_boundaries():
    text = CORE.read_text(encoding="utf-8")
    assert text.startswith("---\nname: universal-reviewer\n")
    for term in ("model: inherit", "NEEDS_FIX", "BLOCKED",
                 "isolation_verified", "HEAD SHA", "Do not edit files",
                 "USD $0", "separate principal"):
        assert term in text


def test_mcm_profile_is_separate_and_state_safe():
    core = CORE.read_text(encoding="utf-8")
    profile = PROFILE.read_text(encoding="utf-8")
    assert "Statistical and mathematical validity" not in core
    assert ".cursor/review-profiles/mcm.md" in core
    for term in ("docs/AUTONOMY_POLICY.md", "docs/mcm-runtime-checkpoint",
                 "timed_out", "cancelled", "startup_failure",
                 "Phase B", "owner review"):
        assert term in profile


def test_runbook_does_not_claim_cloud_is_configured():
    text = RUNBOOK.read_text(encoding="utf-8")
    for term in ("CLOUD RUNTIME UNVERIFIED", "No Cursor Cloud Agent",
                 "No Automation trigger yet", "zero extra billed usage",
                 "independent isolation BLOCKED"):
        assert term in text
