"""Stable application IDs for projects, runs, datasets, and artifacts.

``dataset_id`` generation stays in ``tools.dataset_bundle``. This module only
mints run and artifact IDs and validates project IDs.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from tools.data_loader import safe_project_id

_RUN_RE = re.compile(r"^run_[0-9a-f]{12}$")
_ARTIFACT_RE = re.compile(r"^art_[0-9a-f]{12}$")
_APPROVAL_RE = re.compile(r"^apr_[0-9a-f]{12}$")


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:12]}"


def new_artifact_id() -> str:
    return f"art_{uuid.uuid4().hex[:12]}"


def new_approval_id() -> str:
    return f"apr_{uuid.uuid4().hex[:12]}"


def validate_project_id(value: str) -> str:
    return safe_project_id(value)


def validate_run_id(value: str) -> str:
    if not _RUN_RE.fullmatch(value):
        raise ValueError("run_id must look like run_<12 hex chars>.")
    return value


def validate_artifact_id(value: str) -> str:
    if not _ARTIFACT_RE.fullmatch(value):
        raise ValueError("artifact_id must look like art_<12 hex chars>.")
    return value


def validate_approval_id(value: str) -> str:
    if not _APPROVAL_RE.fullmatch(value):
        raise ValueError("approval_id must look like apr_<12 hex chars>.")
    return value


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
