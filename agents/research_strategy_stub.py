"""Phase 5 placeholder — Research Strategy / Debate / H1 are out of Phase 4 scope.

This module only advertises the future interface so Phase 4 does not claim
strategy approval or modeling readiness.
"""

from __future__ import annotations

from typing import Any

PHASE5_NOT_IMPLEMENTED = (
    "Research Strategy, Debate/Critic, and H1 approval are Phase 5+. "
    "Literature evidence cards may inform a future proposal but do not constitute "
    "an approved research plan."
)


def research_strategy_status() -> dict[str, Any]:
    """Return an explicit not-implemented marker for UI / docs."""
    return {
        "implemented": False,
        "phase": 5,
        "message": PHASE5_NOT_IMPLEMENTED,
        "h1_available": False,
    }
