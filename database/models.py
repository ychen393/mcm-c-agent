"""SQLAlchemy ORM for Phase 1 project / run / dataset / artifact persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


# JSONB on Postgres; plain JSON elsewhere (tests / unexpected dialects).
JsonType = JSON().with_variant(JSONB(), "postgresql")


class ProjectRow(Base):
    # Distinct from the M0 UUID ``projects`` scaffold table.
    __tablename__ = "research_projects"

    project_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    lifecycle: Mapped[str] = mapped_column(String(40), default="created", nullable=False)
    active_run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_signature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ResearchRunRow(Base):
    __tablename__ = "research_runs"

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("research_projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(40), nullable=False)
    input_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    state_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DatasetRefRow(Base):
    __tablename__ = "dataset_refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("research_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_names: Mapped[list[Any]] = mapped_column(JsonType, nullable=False, default=list)
    qualified_column_names: Mapped[list[Any]] = mapped_column(JsonType, nullable=False, default=list)
    warnings: Mapped[list[Any]] = mapped_column(JsonType, nullable=False, default=list)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ArtifactRefRow(Base):
    __tablename__ = "artifact_refs"

    artifact_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("research_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str] = mapped_column(String(255), default="")
    meta_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApprovalDecisionRow(Base):
    __tablename__ = "approval_decisions"

    approval_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("research_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    gate: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    subject_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
