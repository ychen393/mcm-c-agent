"""Backward-compatible export for Phase 4 call sites.

Phase 5 implements Research Strategy / Debate / H1. Prefer importing from
``agents.research_strategy`` directly.
"""

from __future__ import annotations

from agents.research_strategy import research_strategy_status

__all__ = ["research_strategy_status"]
