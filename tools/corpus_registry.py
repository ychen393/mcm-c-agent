"""Corpus Registry loader and M1 copyright/compliance gate helpers.

Registry rows must exist before full-text ingest. Supported acquisition_method
values for this slice: fixture | owner_provided | licensed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "knowledge" / "corpus_registry.csv"
TEMPLATE_PATH = REPO_ROOT / "knowledge" / "CORPUS_REGISTRY_TEMPLATE.csv"

AcquisitionKind = Literal["fixture", "owner_provided", "licensed"]
ALLOWED_ACQUISITION = frozenset({"fixture", "owner_provided", "licensed"})
TRUTHY = frozenset({"1", "true", "yes", "y", "on"})
FALSY = frozenset({"0", "false", "no", "n", "off", ""})


@dataclass(frozen=True)
class CorpusRegistryRow:
    source_id: str
    title: str
    author_or_org: str
    year: int | None
    original_url: str | None
    acquired_at: str | None
    publisher: str | None
    license_or_rights_statement: str | None
    terms_url: str | None
    acquisition_method: str
    allowed_operations: tuple[str, ...]
    full_text_storage_allowed: bool
    excerpt_allowed: bool
    redistribution_allowed: bool
    external_llm_upload_allowed: bool
    review_status: str
    reviewer: str | None
    reviewed_at: str | None
    notes: str | None
    local_path: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "author_or_org": self.author_or_org,
            "year": self.year,
            "original_url": self.original_url,
            "acquired_at": self.acquired_at,
            "publisher": self.publisher,
            "license_or_rights_statement": self.license_or_rights_statement,
            "terms_url": self.terms_url,
            "acquisition_method": self.acquisition_method,
            "allowed_operations": list(self.allowed_operations),
            "full_text_storage_allowed": self.full_text_storage_allowed,
            "excerpt_allowed": self.excerpt_allowed,
            "redistribution_allowed": self.redistribution_allowed,
            "external_llm_upload_allowed": self.external_llm_upload_allowed,
            "review_status": self.review_status,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
            "notes": self.notes,
            "local_path": self.local_path,
        }


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in TRUTHY:
        return True
    if text in FALSY:
        return False
    return default


def _parse_year(value: str | None) -> int | None:
    text = _blank(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _parse_ops(value: str | None) -> tuple[str, ...]:
    text = _blank(value) or ""
    parts = [part.strip() for part in text.replace("|", ";").split(";")]
    return tuple(part for part in parts if part)


def load_corpus_registry(path: Path | None = None) -> list[CorpusRegistryRow]:
    registry_path = path or DEFAULT_REGISTRY_PATH
    if not registry_path.is_file():
        raise FileNotFoundError(f"Corpus registry not found: {registry_path}")
    rows: list[CorpusRegistryRow] = []
    with registry_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            if not raw or not any((value or "").strip() for value in raw.values()):
                continue
            source_id = (_blank(raw.get("source_id")) or "").lower()
            if not source_id:
                raise ValueError("Corpus registry row missing source_id")
            rows.append(
                CorpusRegistryRow(
                    source_id=source_id,
                    title=_blank(raw.get("title")) or source_id,
                    author_or_org=_blank(raw.get("author_or_org")) or "",
                    year=_parse_year(raw.get("year")),
                    original_url=_blank(raw.get("original_url")),
                    acquired_at=_blank(raw.get("acquired_at")),
                    publisher=_blank(raw.get("publisher")),
                    license_or_rights_statement=_blank(
                        raw.get("license_or_rights_statement")
                    ),
                    terms_url=_blank(raw.get("terms_url")),
                    acquisition_method=(
                        _blank(raw.get("acquisition_method")) or "fixture"
                    ).lower(),
                    allowed_operations=_parse_ops(raw.get("allowed_operations")),
                    full_text_storage_allowed=_parse_bool(
                        raw.get("full_text_storage_allowed")
                    ),
                    excerpt_allowed=_parse_bool(raw.get("excerpt_allowed"), default=True),
                    redistribution_allowed=_parse_bool(
                        raw.get("redistribution_allowed")
                    ),
                    external_llm_upload_allowed=_parse_bool(
                        raw.get("external_llm_upload_allowed")
                    ),
                    review_status=(_blank(raw.get("review_status")) or "pending").lower(),
                    reviewer=_blank(raw.get("reviewer")),
                    reviewed_at=_blank(raw.get("reviewed_at")),
                    notes=_blank(raw.get("notes")),
                    local_path=_blank(raw.get("local_path")),
                )
            )
    return rows


def registry_by_id(rows: Iterable[CorpusRegistryRow]) -> dict[str, CorpusRegistryRow]:
    return {row.source_id: row for row in rows}


def copyright_gate_errors(row: CorpusRegistryRow) -> list[str]:
    """Return blocking issues that must be resolved before full-text ingest."""
    errors: list[str] = []
    if row.acquisition_method not in ALLOWED_ACQUISITION:
        errors.append(
            f"{row.source_id}: acquisition_method must be one of "
            f"{sorted(ALLOWED_ACQUISITION)} (got {row.acquisition_method!r})"
        )
    if not row.license_or_rights_statement:
        errors.append(f"{row.source_id}: license_or_rights_statement is required")
    if row.acquisition_method == "fixture":
        if row.review_status not in {"fixture", "approved"}:
            errors.append(
                f"{row.source_id}: fixture rows need review_status=fixture|approved"
            )
        return errors
    # owner_provided / licensed — M1 gate
    if row.review_status != "approved":
        errors.append(
            f"{row.source_id}: non-fixture rows require review_status=approved "
            f"before full-text ingest (got {row.review_status!r})"
        )
    if not row.reviewer:
        errors.append(f"{row.source_id}: reviewer required for non-fixture ingest")
    if not row.full_text_storage_allowed:
        errors.append(
            f"{row.source_id}: full_text_storage_allowed=no — keep metadata/link-only"
        )
    if "internal_fulltext" not in row.allowed_operations and "excerpt_quote" not in row.allowed_operations:
        errors.append(
            f"{row.source_id}: allowed_operations must include internal_fulltext "
            "or excerpt_quote for text ingest"
        )
    return errors


def assert_ingest_allowed(row: CorpusRegistryRow) -> None:
    errors = copyright_gate_errors(row)
    if errors:
        raise PermissionError("; ".join(errors))


def resolve_local_text_path(
    row: CorpusRegistryRow, *, repo_root: Path | None = None
) -> Path | None:
    if not row.local_path:
        return None
    root = repo_root or REPO_ROOT
    path = Path(row.local_path)
    if not path.is_absolute():
        path = root / path
    return path if path.is_file() else None
