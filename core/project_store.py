"""Project / run persistence with PostgreSQL preferred and a local fallback.

When ``database_url`` is reachable, projects and ResearchState snapshots are
saved in Postgres. Otherwise the same layout is written under
``{projects_root}/{project_id}/runs/{run_id}/``. Raw file bytes and API keys
are never persisted in either backend.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from core.ids import (
    new_approval_id,
    new_artifact_id,
    new_run_id,
    utc_now_iso,
    validate_project_id,
    validate_run_id,
)
from core.lifecycle import (
    LIFECYCLE_DATASETS_RECORDED,
    LIFECYCLE_PROJECT_INITIALIZED,
    lifecycle_from_state,
)
from database.models import (
    ApprovalDecisionRow,
    ArtifactRefRow,
    Base,
    DatasetRefRow,
    ProjectRow,
    ResearchRunRow,
)
from schemas.persistence import (
    REUPLOAD_REQUIRED_MESSAGE,
    ApprovalDecisionRecord,
    ArtifactRefRecord,
    DatasetRefRecord,
    ProjectHistoryEntry,
    ProjectRecord,
    ResearchRunRecord,
    StoreInfo,
    sanitize_state_for_persistence,
)

logger = logging.getLogger(__name__)

PROJECTS_DIRNAME = "projects"
BACKEND_MARKER = ".last_store_backend"


def _iso(value: Any) -> str:
    if value is None:
        return utc_now_iso()
    if isinstance(value, str):
        return value
    try:
        return value.isoformat().replace("+00:00", "Z")
    except AttributeError:
        return str(value)


def _datasets_from_state(state: dict[str, Any], *, project_id: str, run_id: str) -> list[DatasetRefRecord]:
    records: list[DatasetRefRecord] = []
    for index, item in enumerate(state.get("uploaded_files") or []):
        if not isinstance(item, dict):
            continue
        if not (item.get("dataset_id") and item.get("file_name") and item.get("sha256")):
            continue
        records.append(
            DatasetRefRecord(
                dataset_id=str(item["dataset_id"]),
                project_id=project_id,
                run_id=run_id,
                file_name=str(item["file_name"]),
                display_name=str(item.get("display_name") or item["file_name"]),
                sha256=str(item["sha256"]),
                file_extension=str(item.get("file_extension") or Path(str(item["file_name"])).suffix),
                file_size_bytes=int(item.get("file_size_bytes") or 1),
                row_count=int(item.get("row_count") or 0),
                column_count=int(item.get("column_count") or 0),
                column_names=list(item.get("column_names") or []),
                qualified_column_names=list(item.get("qualified_column_names") or []),
                warnings=list(item.get("warnings") or []),
                position=int(item.get("position", index)),
            )
        )
    return records


def _sanitize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Fail closed: nested secrets / bytes raise; never reach disk or DB."""
    return sanitize_state_for_persistence(state)


def _backend_marker_path(projects_root: Path) -> Path:
    return Path(projects_root) / BACKEND_MARKER


def read_last_backend(projects_root: Path) -> str | None:
    path = _backend_marker_path(projects_root)
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip().lower()
    return value or None


def write_last_backend(projects_root: Path, backend: str) -> None:
    root = Path(projects_root)
    root.mkdir(parents=True, exist_ok=True)
    _backend_marker_path(root).write_text(backend + "\n", encoding="utf-8")


def backend_mismatch_message(previous: str | None, current: str, *, local_root: Path) -> str | None:
    if not previous or previous == current:
        return None
    if previous == "local" and current == "postgres":
        return (
            f"Project store backend changed from local → postgres. "
            f"Projects previously saved under `{local_root}` are not auto-imported. "
            "They are not lost on disk — switch PROJECT_STORE_BACKEND=local to reopen them, "
            "or re-save into Postgres after review."
        )
    if previous == "postgres" and current == "local":
        return (
            "Project store backend changed from postgres → local. "
            "Projects that lived only in PostgreSQL will not appear in this local root. "
            "Restore DATABASE_URL / PROJECT_STORE_BACKEND=postgres to reopen them; "
            "they are not silently deleted."
        )
    return (
        f"Project store backend changed from {previous} → {current}. "
        "Confirm where projects were last saved before assuming they are missing."
    )


class ProjectStore(ABC):
    """Save, reopen, continue, and list history for research projects."""

    @abstractmethod
    def info(self) -> StoreInfo: ...

    @abstractmethod
    def list_projects(self) -> list[ProjectRecord]: ...

    @abstractmethod
    def get_project(self, project_id: str) -> ProjectRecord | None: ...

    @abstractmethod
    def save_project_state(
        self,
        *,
        project_id: str,
        project_name: str,
        state: dict[str, Any],
        input_signature: str,
        description: str = "",
        force_new_run: bool = False,
        note: str = "",
    ) -> tuple[ProjectRecord, ResearchRunRecord, dict[str, Any]]:
        """Persist state. Bumps a new run version when the input signature changes."""

    @abstractmethod
    def load_active_state(self, project_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def load_run_state(self, project_id: str, run_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def history(self, project_id: str) -> list[ProjectHistoryEntry]: ...

    @abstractmethod
    def continue_run(self, project_id: str, run_id: str | None = None) -> dict[str, Any] | None:
        """Reopen a run for continuation. Refuses stale runs unless explicitly selected."""

    @abstractmethod
    def add_artifact(self, artifact: ArtifactRefRecord) -> ArtifactRefRecord: ...

    @abstractmethod
    def list_artifacts(self, project_id: str, run_id: str | None = None) -> list[ArtifactRefRecord]: ...

    @abstractmethod
    def add_approval(self, decision: ApprovalDecisionRecord) -> ApprovalDecisionRecord: ...

    @abstractmethod
    def invalidate_approvals(self, project_id: str, run_id: str, *, reason: str) -> int: ...

    def mark_stale_if_signature_changed(
        self, project_id: str, current_signature: str
    ) -> bool:
        """Return True when the active run is stale relative to ``current_signature``."""
        project = self.get_project(project_id)
        if project is None or not project.input_signature:
            return False
        return project.input_signature != current_signature


class LocalProjectStore(ProjectStore):
    """Filesystem layout under ``root / project_id / runs / run_id``."""

    def __init__(
        self,
        root: Path,
        *,
        backend_changed: bool = False,
        previous_backend: str | None = None,
        mismatch_message: str | None = None,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._backend_changed = backend_changed
        self._previous_backend = previous_backend
        self._mismatch_message = mismatch_message

    def info(self) -> StoreInfo:
        return StoreInfo(
            backend="local",
            detail=(
                "PostgreSQL unavailable or unreachable; using local project store. "
                "Organize files by project_id/run_id under this root. "
                + REUPLOAD_REQUIRED_MESSAGE
            ),
            root=str(self.root.resolve()),
            backend_changed=self._backend_changed,
            previous_backend=self._previous_backend,
            backend_mismatch_message=self._mismatch_message,
        )

    def _project_dir(self, project_id: str) -> Path:
        return self.root / validate_project_id(project_id)

    def _project_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def _runs_dir(self, project_id: str, *, create: bool = True) -> Path:
        path = self._project_dir(project_id) / "runs"
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def _run_dir(self, project_id: str, run_id: str, *, create: bool = True) -> Path:
        """Resolve a run directory. Always validates ``run_id``; mkdir only when create=True."""
        safe_run = validate_run_id(run_id)
        runs_dir = self._runs_dir(project_id, create=create)
        path = (runs_dir / safe_run).resolve()
        runs_root = runs_dir.resolve()
        if path != runs_root and runs_root not in path.parents:
            raise ValueError("run_id resolves outside the project runs directory.")
        if path.name != safe_run:
            raise ValueError("run_id path segment mismatch.")
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: dict[str, Any] | list[Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def list_projects(self) -> list[ProjectRecord]:
        records: list[ProjectRecord] = []
        if not self.root.exists():
            return records
        for child in sorted(self.root.iterdir()):
            if not child.is_dir():
                continue
            data = self._read_json(child / "project.json")
            if data:
                records.append(ProjectRecord.model_validate(data))
        return records

    def get_project(self, project_id: str) -> ProjectRecord | None:
        data = self._read_json(self._project_path(project_id))
        return ProjectRecord.model_validate(data) if data else None

    def _next_version(self, project_id: str) -> int:
        versions = [entry.version for entry in self.history(project_id)]
        return (max(versions) if versions else 0) + 1

    def _write_run_bundle(
        self,
        *,
        project: ProjectRecord,
        run: ResearchRunRecord,
        state: dict[str, Any],
        datasets: list[DatasetRefRecord],
        mark_previous_stale: bool,
    ) -> None:
        if mark_previous_stale:
            for entry in self.history(project.project_id):
                if entry.status != "active":
                    continue
                run_path = self._run_dir(project.project_id, entry.run_id) / "run.json"
                existing = self._read_json(run_path)
                if not existing:
                    continue
                existing["status"] = "stale"
                existing["updated_at"] = utc_now_iso()
                self._write_json(run_path, existing)
                # Invalidate approvals on the previous active run.
                approvals_path = self._run_dir(project.project_id, entry.run_id) / "approvals.json"
                approvals = self._read_json(approvals_path) or []
                changed = False
                for item in approvals:
                    if item.get("status") in {"approved", "pending"}:
                        item["status"] = "invalidated"
                        item["notes"] = (item.get("notes") or "") + " [invalidated: input signature changed]"
                        changed = True
                if changed:
                    self._write_json(approvals_path, approvals)

        run_dir = self._run_dir(project.project_id, run.run_id)
        self._write_json(run_dir / "run.json", run.model_dump(mode="python"))
        self._write_json(run_dir / "state.json", state)
        self._write_json(
            run_dir / "datasets.json",
            [item.model_dump(mode="python") for item in datasets],
        )
        if not (run_dir / "artifacts.json").exists():
            self._write_json(run_dir / "artifacts.json", [])
        if not (run_dir / "approvals.json").exists():
            self._write_json(run_dir / "approvals.json", [])
        self._write_json(self._project_path(project.project_id), project.model_dump(mode="python"))

    def save_project_state(
        self,
        *,
        project_id: str,
        project_name: str,
        state: dict[str, Any],
        input_signature: str,
        description: str = "",
        force_new_run: bool = False,
        note: str = "",
    ) -> tuple[ProjectRecord, ResearchRunRecord, dict[str, Any]]:
        project_id = validate_project_id(project_id)
        now = utc_now_iso()
        existing = self.get_project(project_id)
        sanitized = _sanitize_state(state)
        lifecycle = lifecycle_from_state(sanitized)
        if lifecycle == LIFECYCLE_PROJECT_INITIALIZED and sanitized.get("uploaded_files"):
            lifecycle = LIFECYCLE_DATASETS_RECORDED
        sanitized["lifecycle"] = lifecycle
        sanitized["project_id"] = project_id
        sanitized["project_name"] = project_name.strip()

        same_signature = (
            existing is not None
            and existing.input_signature == input_signature
            and existing.active_run_id
            and not force_new_run
        )
        run_data: dict[str, Any] | None = None
        if same_signature and existing and existing.active_run_id:
            run_id = existing.active_run_id
            run_data = self._read_json(self._run_dir(project_id, run_id, create=False) / "run.json")
            version = int(run_data["version"]) if run_data else 1
            parent_run_id = run_data.get("parent_run_id") if run_data else None
            mark_previous_stale = False
        else:
            run_id = new_run_id()
            version = self._next_version(project_id)
            parent_run_id = existing.active_run_id if existing else None
            mark_previous_stale = existing is not None and bool(existing.active_run_id)

        sanitized["run_id"] = run_id
        run = ResearchRunRecord(
            run_id=run_id,
            project_id=project_id,
            version=version,
            status="active",
            lifecycle=lifecycle,  # type: ignore[arg-type]
            input_signature=input_signature,
            created_at=now if not same_signature else (run_data or {}).get("created_at", now),
            updated_at=now,
            parent_run_id=parent_run_id,
            note=note,
        )
        project = ProjectRecord(
            project_id=project_id,
            project_name=project_name.strip(),
            description=description if description or not existing else existing.description,
            lifecycle=lifecycle,  # type: ignore[arg-type]
            active_run_id=run_id,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            input_signature=input_signature,
        )
        datasets = _datasets_from_state(sanitized, project_id=project_id, run_id=run_id)
        self._write_run_bundle(
            project=project,
            run=run,
            state=sanitized,
            datasets=datasets,
            mark_previous_stale=mark_previous_stale,
        )
        return project, run, sanitized

    def load_active_state(self, project_id: str) -> dict[str, Any] | None:
        """Reopen the active run. Provenance only — frames require re-upload."""
        return self.continue_run(project_id)

    def load_run_state(self, project_id: str, run_id: str) -> dict[str, Any] | None:
        try:
            path = self._run_dir(project_id, run_id, create=False) / "state.json"
        except ValueError:
            return None
        data = self._read_json(path)
        return _sanitize_state(data) if data else None

    def history(self, project_id: str) -> list[ProjectHistoryEntry]:
        project_id = validate_project_id(project_id)
        runs_dir = self._runs_dir(project_id, create=False)
        if not runs_dir.exists():
            return []
        entries: list[ProjectHistoryEntry] = []
        for child in runs_dir.iterdir():
            if not child.is_dir():
                continue
            try:
                validate_run_id(child.name)
            except ValueError:
                continue
            run_data = self._read_json(child / "run.json")
            if not run_data:
                continue
            state = self._read_json(child / "state.json") or {}
            entries.append(
                ProjectHistoryEntry(
                    run_id=run_data["run_id"],
                    version=int(run_data["version"]),
                    status=run_data.get("status", "active"),
                    lifecycle=run_data.get("lifecycle", "project_initialized"),
                    input_signature=run_data["input_signature"],
                    created_at=run_data["created_at"],
                    updated_at=run_data["updated_at"],
                    note=run_data.get("note") or "",
                    dataset_count=len(state.get("uploaded_files") or []),
                )
            )
        return sorted(entries, key=lambda item: item.version, reverse=True)

    def continue_run(self, project_id: str, run_id: str | None = None) -> dict[str, Any] | None:
        project = self.get_project(project_id)
        if not project:
            return None
        target = run_id or project.active_run_id
        if not target:
            return None
        try:
            run_path = self._run_dir(project_id, target, create=False) / "run.json"
        except ValueError:
            return None
        run_data = self._read_json(run_path)
        if not run_data:
            return None
        state = self.load_run_state(project_id, target)
        if state is None:
            return None
        state = dict(state)
        state["data_resume"] = "reupload_required"
        state.setdefault("errors", [])
        if not any(err.get("code") == "reupload_required" for err in state["errors"]):
            state["errors"] = list(state["errors"]) + [
                {"code": "reupload_required", "message": REUPLOAD_REQUIRED_MESSAGE}
            ]
        if run_data.get("status") == "stale" and target != project.active_run_id:
            state["errors"] = list(state["errors"]) + [
                {
                    "code": "stale_run",
                    "message": (
                        "This run was invalidated by later input changes. "
                        "Do not reuse its approvals; start from the active run or recompute."
                    ),
                }
            ]
        return state

    def add_artifact(self, artifact: ArtifactRefRecord) -> ArtifactRefRecord:
        path = self._run_dir(artifact.project_id, artifact.run_id, create=True) / "artifacts.json"
        items = self._read_json(path) or []
        payload = artifact.model_dump(mode="python")
        items = [item for item in items if item.get("artifact_id") != artifact.artifact_id]
        items.append(payload)
        self._write_json(path, items)
        return artifact

    def list_artifacts(self, project_id: str, run_id: str | None = None) -> list[ArtifactRefRecord]:
        project = self.get_project(project_id)
        if not project:
            return []
        target = run_id or project.active_run_id
        if not target:
            return []
        try:
            path = self._run_dir(project_id, target, create=False) / "artifacts.json"
        except ValueError:
            return []
        items = self._read_json(path) or []
        return [ArtifactRefRecord.model_validate(item) for item in items]

    def add_approval(self, decision: ApprovalDecisionRecord) -> ApprovalDecisionRecord:
        path = self._run_dir(decision.project_id, decision.run_id, create=True) / "approvals.json"
        items = self._read_json(path) or []
        payload = decision.model_dump(mode="python")
        items = [item for item in items if item.get("approval_id") != decision.approval_id]
        items.append(payload)
        self._write_json(path, items)
        return decision

    def invalidate_approvals(self, project_id: str, run_id: str, *, reason: str) -> int:
        try:
            path = self._run_dir(project_id, run_id, create=False) / "approvals.json"
        except ValueError:
            return 0
        items = self._read_json(path) or []
        if not items:
            return 0
        count = 0
        for item in items:
            if item.get("status") in {"approved", "pending"}:
                item["status"] = "invalidated"
                item["notes"] = ((item.get("notes") or "") + f" [invalidated: {reason}]").strip()
                count += 1
        if count:
            self._write_json(path, items)
        return count


class PostgresProjectStore(ProjectStore):
    """SQLAlchemy-backed project store."""

    def __init__(
        self,
        engine: Engine,
        *,
        backend_changed: bool = False,
        previous_backend: str | None = None,
        mismatch_message: str | None = None,
        local_root_hint: Path | None = None,
    ):
        self.engine = engine
        Base.metadata.create_all(engine)
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        self._backend_changed = backend_changed
        self._previous_backend = previous_backend
        self._mismatch_message = mismatch_message
        self._local_root_hint = local_root_hint

    def info(self) -> StoreInfo:
        root = str(self._local_root_hint.resolve()) if self._local_root_hint else None
        return StoreInfo(
            backend="postgres",
            detail=(
                "Projects, runs, dataset refs, artifacts, and approvals stored in PostgreSQL. "
                + REUPLOAD_REQUIRED_MESSAGE
            ),
            root=root,
            backend_changed=self._backend_changed,
            previous_backend=self._previous_backend,
            backend_mismatch_message=self._mismatch_message,
        )

    def _session(self) -> Session:
        return self._session_factory()

    def list_projects(self) -> list[ProjectRecord]:
        with self._session() as session:
            rows = session.scalars(select(ProjectRow).order_by(ProjectRow.updated_at.desc())).all()
            return [self._project_record(row) for row in rows]

    def get_project(self, project_id: str) -> ProjectRecord | None:
        project_id = validate_project_id(project_id)
        with self._session() as session:
            row = session.get(ProjectRow, project_id)
            return self._project_record(row) if row else None

    @staticmethod
    def _project_record(row: ProjectRow) -> ProjectRecord:
        return ProjectRecord(
            project_id=row.project_id,
            project_name=row.project_name,
            description=row.description or "",
            lifecycle=row.lifecycle,  # type: ignore[arg-type]
            active_run_id=row.active_run_id,
            created_at=_iso(row.created_at),
            updated_at=_iso(row.updated_at),
            input_signature=row.input_signature,
        )

    def _next_version(self, session: Session, project_id: str) -> int:
        rows = session.scalars(
            select(ResearchRunRow.version).where(ResearchRunRow.project_id == project_id)
        ).all()
        return (max(rows) if rows else 0) + 1

    def save_project_state(
        self,
        *,
        project_id: str,
        project_name: str,
        state: dict[str, Any],
        input_signature: str,
        description: str = "",
        force_new_run: bool = False,
        note: str = "",
    ) -> tuple[ProjectRecord, ResearchRunRecord, dict[str, Any]]:
        project_id = validate_project_id(project_id)
        sanitized = _sanitize_state(state)
        lifecycle = lifecycle_from_state(sanitized)
        if lifecycle == LIFECYCLE_PROJECT_INITIALIZED and sanitized.get("uploaded_files"):
            lifecycle = LIFECYCLE_DATASETS_RECORDED
        sanitized["lifecycle"] = lifecycle
        sanitized["project_id"] = project_id
        sanitized["project_name"] = project_name.strip()
        now = utc_now_iso()

        with self._session() as session:
            project_row = session.get(ProjectRow, project_id)
            same_signature = (
                project_row is not None
                and project_row.input_signature == input_signature
                and project_row.active_run_id
                and not force_new_run
            )
            parent_run_id = project_row.active_run_id if project_row else None
            if same_signature and project_row and project_row.active_run_id:
                run_row = session.get(ResearchRunRow, project_row.active_run_id)
                if run_row is None:
                    same_signature = False
                else:
                    run_id = run_row.run_id
                    version = run_row.version
                    created_at = _iso(run_row.created_at)
                    parent_run_id = run_row.parent_run_id
            if not same_signature:
                if project_row and project_row.active_run_id:
                    previous = session.get(ResearchRunRow, project_row.active_run_id)
                    if previous and previous.status == "active":
                        previous.status = "stale"
                        for approval in session.scalars(
                            select(ApprovalDecisionRow).where(
                                ApprovalDecisionRow.run_id == previous.run_id,
                                ApprovalDecisionRow.status.in_(("approved", "pending")),
                            )
                        ).all():
                            approval.status = "invalidated"
                            approval.notes = (
                                (approval.notes or "")
                                + " [invalidated: input signature changed]"
                            ).strip()
                run_id = new_run_id()
                version = self._next_version(session, project_id)
                created_at = now

            sanitized["run_id"] = run_id
            if project_row is None:
                project_row = ProjectRow(
                    project_id=project_id,
                    project_name=project_name.strip(),
                    description=description,
                    lifecycle=lifecycle,
                    active_run_id=run_id,
                    input_signature=input_signature,
                )
                session.add(project_row)
            else:
                project_row.project_name = project_name.strip()
                if description:
                    project_row.description = description
                project_row.lifecycle = lifecycle
                project_row.active_run_id = run_id
                project_row.input_signature = input_signature

            run_row = session.get(ResearchRunRow, run_id)
            if run_row is None:
                run_row = ResearchRunRow(
                    run_id=run_id,
                    project_id=project_id,
                    version=version,
                    status="active",
                    lifecycle=lifecycle,
                    input_signature=input_signature,
                    parent_run_id=parent_run_id if not same_signature else parent_run_id,
                    note=note,
                    state_json=sanitized,
                )
                session.add(run_row)
            else:
                run_row.status = "active"
                run_row.lifecycle = lifecycle
                run_row.input_signature = input_signature
                run_row.note = note or run_row.note
                run_row.state_json = sanitized

            # Replace dataset refs for this run.
            for old in session.scalars(
                select(DatasetRefRow).where(DatasetRefRow.run_id == run_id)
            ).all():
                session.delete(old)
            for item in _datasets_from_state(sanitized, project_id=project_id, run_id=run_id):
                session.add(
                    DatasetRefRow(
                        dataset_id=item.dataset_id,
                        project_id=item.project_id,
                        run_id=item.run_id,
                        file_name=item.file_name,
                        display_name=item.display_name,
                        sha256=item.sha256,
                        file_extension=item.file_extension,
                        file_size_bytes=item.file_size_bytes,
                        row_count=item.row_count,
                        column_count=item.column_count,
                        column_names=item.column_names,
                        qualified_column_names=item.qualified_column_names,
                        warnings=item.warnings,
                        position=item.position,
                    )
                )
            session.commit()
            session.refresh(project_row)
            session.refresh(run_row)
            project = self._project_record(project_row)
            run = ResearchRunRecord(
                run_id=run_row.run_id,
                project_id=run_row.project_id,
                version=run_row.version,
                status=run_row.status,  # type: ignore[arg-type]
                lifecycle=run_row.lifecycle,  # type: ignore[arg-type]
                input_signature=run_row.input_signature,
                created_at=created_at,
                updated_at=_iso(run_row.updated_at),
                parent_run_id=run_row.parent_run_id,
                note=run_row.note or "",
            )
            return project, run, sanitized

    def load_active_state(self, project_id: str) -> dict[str, Any] | None:
        """Reopen the active run. Provenance only — frames require re-upload."""
        return self.continue_run(project_id)

    def load_run_state(self, project_id: str, run_id: str) -> dict[str, Any] | None:
        try:
            safe_run = validate_run_id(run_id)
        except ValueError:
            return None
        with self._session() as session:
            row = session.get(ResearchRunRow, safe_run)
            if row is None or row.project_id != validate_project_id(project_id):
                return None
            return _sanitize_state(dict(row.state_json or {}))

    def history(self, project_id: str) -> list[ProjectHistoryEntry]:
        project_id = validate_project_id(project_id)
        with self._session() as session:
            rows = session.scalars(
                select(ResearchRunRow)
                .where(ResearchRunRow.project_id == project_id)
                .order_by(ResearchRunRow.version.desc())
            ).all()
            entries: list[ProjectHistoryEntry] = []
            for row in rows:
                state = row.state_json or {}
                entries.append(
                    ProjectHistoryEntry(
                        run_id=row.run_id,
                        version=row.version,
                        status=row.status,  # type: ignore[arg-type]
                        lifecycle=row.lifecycle,  # type: ignore[arg-type]
                        input_signature=row.input_signature,
                        created_at=_iso(row.created_at),
                        updated_at=_iso(row.updated_at),
                        note=row.note or "",
                        dataset_count=len(state.get("uploaded_files") or []),
                    )
                )
            return entries

    def continue_run(self, project_id: str, run_id: str | None = None) -> dict[str, Any] | None:
        project = self.get_project(project_id)
        if not project:
            return None
        target = run_id or project.active_run_id
        if not target:
            return None
        try:
            safe_run = validate_run_id(target)
        except ValueError:
            return None
        with self._session() as session:
            row = session.get(ResearchRunRow, safe_run)
            if row is None or row.project_id != validate_project_id(project_id):
                return None
            state = _sanitize_state(dict(row.state_json or {}))
            state["data_resume"] = "reupload_required"
            state.setdefault("errors", [])
            if not any(err.get("code") == "reupload_required" for err in state["errors"]):
                state["errors"] = list(state["errors"]) + [
                    {"code": "reupload_required", "message": REUPLOAD_REQUIRED_MESSAGE}
                ]
            if row.status == "stale" and safe_run != project.active_run_id:
                state["errors"] = list(state["errors"]) + [
                    {
                        "code": "stale_run",
                        "message": (
                            "This run was invalidated by later input changes. "
                            "Do not reuse its approvals; start from the active run or recompute."
                        ),
                    }
                ]
            return state

    def add_artifact(self, artifact: ArtifactRefRecord) -> ArtifactRefRecord:
        validate_run_id(artifact.run_id)
        with self._session() as session:
            row = session.get(ArtifactRefRow, artifact.artifact_id)
            if row is None:
                row = ArtifactRefRow(artifact_id=artifact.artifact_id)
                session.add(row)
            row.project_id = artifact.project_id
            row.run_id = artifact.run_id
            row.kind = artifact.kind
            row.uri = artifact.uri
            row.sha256 = artifact.sha256
            row.label = artifact.label
            row.meta_json = artifact.metadata
            session.commit()
            return artifact

    def list_artifacts(self, project_id: str, run_id: str | None = None) -> list[ArtifactRefRecord]:
        project = self.get_project(project_id)
        if not project:
            return []
        target = run_id or project.active_run_id
        if not target:
            return []
        try:
            safe_run = validate_run_id(target)
        except ValueError:
            return []
        with self._session() as session:
            rows = session.scalars(
                select(ArtifactRefRow).where(
                    ArtifactRefRow.project_id == validate_project_id(project_id),
                    ArtifactRefRow.run_id == safe_run,
                )
            ).all()
            return [
                ArtifactRefRecord(
                    artifact_id=row.artifact_id,
                    project_id=row.project_id,
                    run_id=row.run_id,
                    kind=row.kind,
                    uri=row.uri,
                    sha256=row.sha256,
                    label=row.label or "",
                    created_at=_iso(row.created_at),
                    metadata=dict(row.meta_json or {}),
                )
                for row in rows
            ]

    def add_approval(self, decision: ApprovalDecisionRecord) -> ApprovalDecisionRecord:
        validate_run_id(decision.run_id)
        with self._session() as session:
            row = session.get(ApprovalDecisionRow, decision.approval_id)
            if row is None:
                row = ApprovalDecisionRow(approval_id=decision.approval_id)
                session.add(row)
            row.project_id = decision.project_id
            row.run_id = decision.run_id
            row.gate = decision.gate
            row.status = decision.status
            row.version = decision.version
            row.notes = decision.notes
            row.subject_sha256 = decision.subject_sha256
            session.commit()
            return decision

    def invalidate_approvals(self, project_id: str, run_id: str, *, reason: str) -> int:
        try:
            safe_run = validate_run_id(run_id)
        except ValueError:
            return 0
        with self._session() as session:
            rows = session.scalars(
                select(ApprovalDecisionRow).where(
                    ApprovalDecisionRow.project_id == validate_project_id(project_id),
                    ApprovalDecisionRow.run_id == safe_run,
                    ApprovalDecisionRow.status.in_(("approved", "pending")),
                )
            ).all()
            for row in rows:
                row.status = "invalidated"
                row.notes = ((row.notes or "") + f" [invalidated: {reason}]").strip()
            session.commit()
            return len(rows)


def probe_postgres(database_url: str, *, timeout_seconds: float = 2.0) -> Engine | None:
    """Return an engine when Postgres accepts a connection; otherwise None."""
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": max(1, int(timeout_seconds))},
        )
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return engine
    except Exception as exc:  # noqa: BLE001 — intentional soft fallback
        logger.info("PostgreSQL unavailable (%s); using local project store.", exc)
        return None


def open_project_store(
    *,
    database_url: str,
    projects_root: Path,
    prefer_postgres: bool = True,
    force_backend: str | None = None,
) -> ProjectStore:
    """Open Postgres when reachable; otherwise a documented local fallback.

    ``force_backend`` may be ``local`` or ``postgres``. Schema-init failures
    always fall back to local so Streamlit still boots without a migrated DB.
    A backend change since the last process is recorded on ``StoreInfo`` so the
    UI can warn that projects are not silently lost.
    """
    root = Path(projects_root)
    root.mkdir(parents=True, exist_ok=True)
    previous = read_last_backend(root)

    def _finish(store: ProjectStore, backend: str) -> ProjectStore:
        write_last_backend(root, backend)
        logger.info("Project store backend: %s", backend)
        return store

    def _local(*, changed: bool = False, message: str | None = None) -> LocalProjectStore:
        return LocalProjectStore(
            root,
            backend_changed=changed,
            previous_backend=previous,
            mismatch_message=message,
        )

    backend = (force_backend or ("postgres" if prefer_postgres else "local")).lower()
    if backend == "local" or (backend not in {"postgres", "auto"} and not prefer_postgres):
        message = backend_mismatch_message(previous, "local", local_root=root.resolve())
        return _finish(_local(changed=bool(message), message=message), "local")

    engine = probe_postgres(database_url)
    if engine is None:
        if force_backend == "postgres":
            raise RuntimeError("PostgreSQL was required but is unreachable.")
        message = backend_mismatch_message(previous, "local", local_root=root.resolve())
        return _finish(_local(changed=bool(message), message=message), "local")
    try:
        message = backend_mismatch_message(previous, "postgres", local_root=root.resolve())
        store: ProjectStore = PostgresProjectStore(
            engine,
            backend_changed=bool(message),
            previous_backend=previous,
            mismatch_message=message,
            local_root_hint=root,
        )
    except Exception as exc:  # noqa: BLE001 — soft fallback for schema clashes
        logger.warning(
            "PostgreSQL project schema unavailable (%s); using local project store.",
            exc,
        )
        if force_backend == "postgres":
            raise
        message = backend_mismatch_message(previous, "local", local_root=root.resolve())
        return _finish(_local(changed=bool(message), message=message), "local")
    return _finish(store, "postgres")


def default_projects_root(upload_dir: Path | None = None, output_dir: Path | None = None) -> Path:
    """Prefer ``data/projects`` next to uploads; fall back beside outputs."""
    if upload_dir is not None:
        return Path(upload_dir).resolve().parent / PROJECTS_DIRNAME
    if output_dir is not None:
        return Path(output_dir).resolve().parent / "data" / PROJECTS_DIRNAME
    return Path("data") / PROJECTS_DIRNAME


def make_artifact(
    *,
    project_id: str,
    run_id: str,
    kind: str,
    uri: str,
    sha256: str | None = None,
    label: str = "",
    metadata: dict[str, Any] | None = None,
) -> ArtifactRefRecord:
    return ArtifactRefRecord(
        artifact_id=new_artifact_id(),
        project_id=project_id,
        run_id=run_id,
        kind=kind,
        uri=uri,
        sha256=sha256,
        label=label,
        created_at=utc_now_iso(),
        metadata=metadata or {},
    )


def make_approval(
    *,
    project_id: str,
    run_id: str,
    gate: str,
    status: str,
    notes: str = "",
    subject_sha256: str | None = None,
    version: int = 1,
) -> ApprovalDecisionRecord:
    return ApprovalDecisionRecord(
        approval_id=new_approval_id(),
        project_id=project_id,
        run_id=run_id,
        gate=gate,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        version=version,
        decided_at=utc_now_iso() if status in {"approved", "rejected"} else None,
        notes=notes,
        subject_sha256=subject_sha256,
    )
