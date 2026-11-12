"""Render Phase X PR handoff comment templates offline.

No network. No secrets. Placeholders only — safe for CI smoke tests.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = REPO_ROOT / "docs" / "phasex" / "templates"

TEMPLATES = {
    "builder": "builder_handoff_pr_comment.md",
    "evaluator": "evaluator_verdict_pr_comment.md",
}

DEFAULTS = {
    "phase": "X",
    "pr_url": "<draft-pr-url>",
    "branch": "cursor/phasex-…",
    "head_sha": "<head-sha>",
    "base_branch": "cursor/phase9-…",
    "base_sha": "<base-sha>",
    "pytest_summary": "<n passed>",
    "ci_status": "pending",
    "delivered_bullets": "- <item>",
    "out_of_scope_bullets": "- merge to main / deploy",
    "verdict": "PASS | PASS_WITH_NOTES | FAIL",
    "p0_count": "0",
    "p1_count": "0",
    "p2_count": "0",
    "summary": "<one-paragraph summary>",
}


def template_path(name: str) -> Path:
    try:
        filename = TEMPLATES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown template {name!r}; choose from {sorted(TEMPLATES)}") from exc
    path = TEMPLATE_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def render(name: str, values: dict[str, str] | None = None) -> str:
    """Fill `{{placeholders}}` in a template. Missing keys keep defaults."""
    merged = {**DEFAULTS, **(values or {})}
    text = template_path(name).read_text(encoding="utf-8")
    for key, value in merged.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template",
        choices=sorted(TEMPLATES),
        default="builder",
        help="Which handoff template to render",
    )
    args = parser.parse_args(argv)
    body = render(args.template)
    print(body, end="" if body.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
