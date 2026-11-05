"""In-memory multi-dataset registry.

Each upload is loaded with ``load_dataset`` and profiled with ``build_eda_report``.
Files stay separate: this module does not concatenate, join, align, or chart them.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from schemas.dataset_bundle import (
    BUNDLE_VERSION,
    DatasetBundleManifest,
    DatasetProfileContract,
    DatasetRef,
)
from tools.data_loader import (
    DEFAULT_MAX_FILE_SIZE,
    LoadedDataset,
    load_dataset,
    safe_project_id,
)
from tools.eda_engine import build_eda_report

ABSOLUTE_MAX_DATASETS = 5
DEFAULT_MAX_BUNDLE_BYTES = 50 * 1024 * 1024

Upload = tuple[str, bytes | BinaryIO]


@dataclass(frozen=True)
class DatasetUpload:
    """One named file. ``content`` is the raw CSV or XLSX payload."""

    file_name: str
    content: bytes | BinaryIO


@dataclass
class DatasetBundle:
    """Ordered datasets plus the provenance manifest.

    Loaded frames stay on this object for local profiling. They are excluded
    from ``manifest`` and from its string form.
    """

    manifest: DatasetBundleManifest
    _loaded_by_id: dict[str, LoadedDataset] = field(repr=False)

    @property
    def project_id(self) -> str:
        return self.manifest.project_id

    @property
    def fingerprint(self) -> str:
        return self.manifest.fingerprint

    @property
    def datasets(self) -> list[DatasetRef]:
        return self.manifest.datasets

    def loaded_dataset(self, dataset_id: str) -> LoadedDataset:
        try:
            return self._loaded_by_id[dataset_id]
        except KeyError as exc:
            raise KeyError(f"Unknown dataset ID '{dataset_id}'.") from exc


def build_dataset_bundle(
    uploads: Iterable[DatasetUpload | Upload],
    *,
    project_id: str,
    max_datasets: int = ABSOLUTE_MAX_DATASETS,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    max_aggregate_bytes: int = DEFAULT_MAX_BUNDLE_BYTES,
) -> DatasetBundle:
    """Load 1–5 CSV/XLSX files into a deterministic bundle.

    Duplicate byte content is rejected. The same file name may appear more than
    once only when the bytes differ; display names and dataset IDs stay distinct.
    """
    if max_datasets < 1 or max_datasets > ABSOLUTE_MAX_DATASETS:
        raise ValueError(f"max_datasets must be between 1 and {ABSOLUTE_MAX_DATASETS}.")
    if max_aggregate_bytes < 1:
        raise ValueError("max_aggregate_bytes must be positive.")
    normalized = _normalize_uploads(uploads)
    if not normalized:
        raise ValueError("Dataset bundle must contain at least one file.")
    if len(normalized) > max_datasets:
        raise ValueError(
            f"Dataset bundle accepts at most {max_datasets} files; received {len(normalized)}."
        )
    _reject_aggregate_overflow(normalized, max_aggregate_bytes)
    loaded_rows = _load_all(normalized, max_file_size=max_file_size)
    _reject_duplicate_content(loaded_rows)
    stable_project_id = safe_project_id(project_id)
    refs = _build_refs(loaded_rows)
    manifest = DatasetBundleManifest(
        bundle_version=BUNDLE_VERSION,
        project_id=stable_project_id,
        datasets=refs,
        fingerprint=_fingerprint(stable_project_id, refs),
    )
    loaded_by_id = {
        ref.dataset_id: loaded for ref, loaded in zip(refs, loaded_rows, strict=True)
    }
    return DatasetBundle(manifest=manifest, _loaded_by_id=loaded_by_id)


def build_bundle_profiles(
    bundle: DatasetBundle,
    *,
    column_units_by_dataset: Mapping[str, Mapping[str, str]] | None = None,
    data_source_by_dataset: Mapping[str, str | None] | None = None,
    temporal_frequency_by_dataset: Mapping[str, str | None] | None = None,
) -> dict[str, DatasetProfileContract]:
    """Map each dataset ID to its own ``EDAReport``.

    The returned contracts share the bundle project ID. Metadata stays on the
    dataset it came from. No frames are merged and none are attached to the
    contracts.
    """
    known = {ref.dataset_id for ref in bundle.datasets}
    _reject_unknown_ids("column units", column_units_by_dataset, known)
    _reject_unknown_ids("data sources", data_source_by_dataset, known)
    _reject_unknown_ids("temporal frequencies", temporal_frequency_by_dataset, known)
    units = column_units_by_dataset or {}
    sources = data_source_by_dataset or {}
    frequencies = temporal_frequency_by_dataset or {}
    profiles: dict[str, DatasetProfileContract] = {}
    for ref in bundle.datasets:
        report = build_eda_report(
            bundle.loaded_dataset(ref.dataset_id),
            bundle.project_id,
            data_source=sources.get(ref.dataset_id),
            temporal_frequency=frequencies.get(ref.dataset_id),
            column_units=dict(units.get(ref.dataset_id, {})),
        )
        profiles[ref.dataset_id] = DatasetProfileContract(
            dataset_id=ref.dataset_id,
            project_id=bundle.project_id,
            display_name=ref.display_name,
            file_name=ref.file_name,
            sha256=ref.sha256,
            report=report,
        )
    return profiles


def _normalize_uploads(uploads: Iterable[DatasetUpload | Upload]) -> list[tuple[str, bytes]]:
    if isinstance(uploads, (str, bytes)):
        raise ValueError("Dataset bundle uploads must be an ordered list of files.")
    try:
        items = list(uploads)
    except TypeError as exc:
        raise ValueError("Dataset bundle uploads must be an ordered list of files.") from exc
    normalized: list[tuple[str, bytes]] = []
    for index, item in enumerate(items, start=1):
        file_name, source = _coerce_item(item, index)
        raw = _read_bytes(source, index, file_name)
        safe_name = Path(file_name).name
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError(f"Upload {index} has an invalid file name.")
        normalized.append((safe_name, raw))
    return normalized


def _coerce_item(item: DatasetUpload | Upload, index: int) -> tuple[str, bytes | BinaryIO]:
    if isinstance(item, DatasetUpload):
        file_name, source = item.file_name, item.content
    elif isinstance(item, tuple) and len(item) == 2:
        file_name, source = item
    else:
        raise ValueError(
            f"Upload {index} must be a (file_name, content) pair or DatasetUpload."
        )
    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError(f"Upload {index} is missing a file name.")
    return file_name, source


def _read_bytes(source: bytes | BinaryIO, index: int, file_name: str) -> bytes:
    if isinstance(source, bytes):
        return source
    read = getattr(source, "read", None)
    if read is None:
        raise ValueError(f"Upload {index} ('{Path(file_name).name}') must be readable as bytes.")
    raw = read()
    if not isinstance(raw, bytes):
        raise ValueError(f"Upload {index} ('{Path(file_name).name}') must be readable as bytes.")
    return raw


def _reject_aggregate_overflow(uploads: list[tuple[str, bytes]], max_aggregate_bytes: int) -> None:
    running = 0
    for index, (file_name, raw) in enumerate(uploads, start=1):
        running += len(raw)
        if running > max_aggregate_bytes:
            raise ValueError(
                "Combined upload size exceeds the aggregate limit of "
                f"{max_aggregate_bytes} bytes at '{file_name}' (upload {index})."
            )


def _load_all(
    uploads: list[tuple[str, bytes]],
    *,
    max_file_size: int,
) -> list[LoadedDataset]:
    loaded_rows: list[LoadedDataset] = []
    total = len(uploads)
    for index, (file_name, raw) in enumerate(uploads, start=1):
        try:
            loaded_rows.append(load_dataset(raw, file_name, max_file_size=max_file_size))
        except ValueError as exc:
            raise ValueError(
                f"Could not load '{file_name}' (upload {index} of {total}): {exc}"
            ) from exc
    return loaded_rows


def _reject_duplicate_content(loaded_rows: list[LoadedDataset]) -> None:
    first_index: dict[str, int] = {}
    for index, loaded in enumerate(loaded_rows):
        previous = first_index.get(loaded.sha256)
        if previous is not None:
            earlier = loaded_rows[previous]
            raise ValueError(
                "Duplicate dataset content is not allowed. "
                f"'{earlier.file_name}' and '{loaded.file_name}' have the same SHA-256 "
                f"{loaded.sha256}."
            )
        first_index[loaded.sha256] = index


def _file_slug(file_name: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in Path(file_name).stem)
    collapsed = "-".join(part for part in slug.split("-") if part)
    return (collapsed or "dataset")[:40]


def _dataset_id(file_name: str, sha256: str, used: set[str]) -> str:
    base = f"ds_{_file_slug(file_name)}_{sha256[:12]}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _display_name(file_name: str, sha256: str, name_counts: Counter[str], used: set[str]) -> str:
    if name_counts[file_name] == 1:
        candidate = file_name
    else:
        candidate = f"{file_name}#{sha256[:8]}"
    if candidate in used:
        candidate = f"{file_name}#{sha256[:16]}"
    if candidate in used:
        candidate = f"{file_name}#{sha256}"
    used.add(candidate)
    return candidate


def _build_refs(loaded_rows: list[LoadedDataset]) -> list[DatasetRef]:
    name_counts: Counter[str] = Counter(loaded.file_name for loaded in loaded_rows)
    used_ids: set[str] = set()
    used_names: set[str] = set()
    refs: list[DatasetRef] = []
    for position, loaded in enumerate(loaded_rows):
        dataset_id = _dataset_id(loaded.file_name, loaded.sha256, used_ids)
        columns = [str(column) for column in loaded.frame.columns]
        refs.append(
            DatasetRef(
                dataset_id=dataset_id,
                position=position,
                file_name=loaded.file_name,
                display_name=_display_name(
                    loaded.file_name, loaded.sha256, name_counts, used_names
                ),
                file_extension=loaded.file_extension,
                file_size_bytes=loaded.file_size_bytes,
                sha256=loaded.sha256,
                column_names=columns,
                qualified_column_names=[f"{dataset_id}.{column}" for column in columns],
            )
        )
    return refs


def _fingerprint(project_id: str, refs: list[DatasetRef]) -> str:
    payload = {
        "bundle_version": BUNDLE_VERSION,
        "project_id": project_id,
        "datasets": [
            {
                "position": ref.position,
                "dataset_id": ref.dataset_id,
                "file_name": ref.file_name,
                "display_name": ref.display_name,
                "file_extension": ref.file_extension,
                "file_size_bytes": ref.file_size_bytes,
                "sha256": ref.sha256,
                "columns": ref.column_names,
                "qualified_columns": ref.qualified_column_names,
            }
            for ref in refs
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _reject_unknown_ids(
    label: str,
    mapping: Mapping[str, object] | None,
    known: set[str],
) -> None:
    if not mapping:
        return
    unknown = sorted(set(mapping) - known)
    if unknown:
        raise ValueError(f"Unknown dataset ID(s) in {label}: {', '.join(unknown)}.")
