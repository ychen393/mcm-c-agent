"""Engine helpers and the Phase 1 project-store factory."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import Settings
from core.project_store import (
    ProjectStore,
    default_projects_root,
    open_project_store,
)
from database.models import Base


def build_engine(settings: Settings):
    return create_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(settings: Settings):
    return sessionmaker(bind=build_engine(settings), expire_on_commit=False)


def initialize_schema(settings: Settings) -> None:
    Base.metadata.create_all(build_engine(settings))


def build_project_store(
    settings: Settings,
    *,
    projects_root: Path | None = None,
    prefer_postgres: bool | None = None,
) -> ProjectStore:
    """Prefer PostgreSQL; fall back to ``data/projects`` when DB is down."""
    root = projects_root or default_projects_root(settings.upload_dir, settings.output_dir)
    backend = getattr(settings, "project_store_backend", "auto")
    if prefer_postgres is None:
        prefer_postgres = backend != "local"
    force = None if backend == "auto" else backend
    return open_project_store(
        database_url=settings.database_url,
        projects_root=root,
        prefer_postgres=prefer_postgres,
        force_backend=force,
    )
