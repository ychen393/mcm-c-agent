#!/usr/bin/env python3
"""Pre-deploy readiness checks for Railway packaging (no cloud resources created).

Usage:
  APP_ENV=production APP_PASSWORD=... PROJECT_STORE_BACKEND=postgres \\
    DATABASE_URL=... python -m scripts.pre_deploy_check

Exit 0 on pass; non-zero on fail. Never prints secret values.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow `python scripts/pre_deploy_check.py` from repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import assert_auth_config, auth_is_configured, is_production_like  # noqa: E402
from core.config import Settings  # noqa: E402


def _ok(msg: str) -> None:
    print(f"PASS  {msg}")


def _fail(msg: str, errors: list[str]) -> None:
    print(f"FAIL  {msg}")
    errors.append(msg)


def main() -> int:
    errors: list[str] = []
    # Fresh Settings from process env / .env (not the lru_cached get_settings singleton).
    settings = Settings()

    env = settings.app_env
    _ok(f"APP_ENV={env!r}")

    try:
        assert_auth_config(settings)
        if is_production_like(env):
            _ok("production-like env has APP_PASSWORD configured (value not printed)")
        elif auth_is_configured(settings):
            _ok("APP_PASSWORD configured (optional for this APP_ENV)")
        else:
            _ok("APP_PASSWORD unset (allowed for non-production APP_ENV)")
    except RuntimeError as exc:
        _fail(str(exc), errors)

    backend = settings.project_store_backend
    if is_production_like(env) and backend != "postgres":
        _fail(
            f"PROJECT_STORE_BACKEND should be 'postgres' for production-like deploys (got {backend!r})",
            errors,
        )
    else:
        _ok(f"PROJECT_STORE_BACKEND={backend!r}")

    for flag_name in (
        "problem_analyst_use_llm",
        "literature_live_retrieval",
        "research_strategy_use_llm",
        "validation_use_llm",
        "paper_use_llm",
    ):
        value = getattr(settings, flag_name)
        if is_production_like(env) and value:
            _fail(f"{flag_name} must be false for LLM-off demo deploy (got {value!r})", errors)
        else:
            _ok(f"{flag_name}={value!r}")

    for label, path in (
        ("UPLOAD_DIR", settings.upload_dir),
        ("OUTPUT_DIR", settings.output_dir),
        ("PROJECTS_DIR", settings.resolved_projects_dir()),
    ):
        p = Path(path)
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                _fail(f"{label}={p} not creatable: {exc}", errors)
                continue
        if p.is_dir():
            _ok(f"{label}={p} (directory ready)")
        else:
            _fail(f"{label}={p} is not a directory", errors)

    if is_production_like(env):
        db = settings.database_url or ""
        if "mcm_dev_password" in db:
            _fail("DATABASE_URL still contains mcm_dev_password — rotate before deploy", errors)
        elif not db:
            _fail("DATABASE_URL is empty", errors)
        else:
            _ok("DATABASE_URL set (credentials not printed)")
        if not os.environ.get("PORT") and not is_production_like(env):
            pass
        # PORT is injected by Railway at runtime; warn only.
        if not os.environ.get("PORT"):
            print("WARN  PORT unset (Railway injects this at runtime)")

    packaging = [
        ROOT / "Dockerfile",
        ROOT / "railway.toml",
        ROOT / ".dockerignore",
        ROOT / "docs" / "RAILWAY_DEPLOY.md",
    ]
    for path in packaging:
        if path.is_file():
            _ok(f"packaging file present: {path.relative_to(ROOT)}")
        else:
            _fail(f"missing packaging file: {path.relative_to(ROOT)}", errors)

    if errors:
        print(f"\n{len(errors)} check(s) failed.")
        return 1
    print("\nAll pre-deploy checks passed (no Railway resources were created).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
