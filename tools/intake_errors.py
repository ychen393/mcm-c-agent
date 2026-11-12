"""Per-file upload diagnostics for multi-dataset intake (Phase 3).

``build_dataset_bundle`` remains all-or-nothing for a clean registry. This helper
probes each file so the UI can show clear per-file errors when a selection fails
or when the caller wants a pre-check report.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from tools.data_loader import DEFAULT_MAX_FILE_SIZE, load_dataset
from tools.dataset_bundle import (
    ABSOLUTE_MAX_DATASETS,
    DEFAULT_MAX_BUNDLE_BYTES,
    DatasetUpload,
    Upload,
    _coerce_item,
    _read_bytes,
)

UploadInput = DatasetUpload | Upload


@dataclass(frozen=True)
class FileIntakeResult:
    index: int
    file_name: str
    ok: bool
    error: str | None = None
    sha256: str | None = None
    row_count: int | None = None
    column_count: int | None = None
    size_bytes: int | None = None


def classify_upload_errors(
    uploads: Iterable[UploadInput],
    *,
    max_datasets: int = ABSOLUTE_MAX_DATASETS,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    max_aggregate_bytes: int = DEFAULT_MAX_BUNDLE_BYTES,
) -> list[FileIntakeResult]:
    """Return one diagnostic row per upload (plus a synthetic row for count overflow)."""
    items = list(uploads)
    results: list[FileIntakeResult] = []
    if len(items) > max_datasets:
        results.append(
            FileIntakeResult(
                index=0,
                file_name="*",
                ok=False,
                error=(
                    f"Dataset bundle accepts at most {max_datasets} files; "
                    f"received {len(items)}."
                ),
            )
        )
        # Still probe the first max_datasets+1 names for clarity.
        items = items[: max_datasets + 1]

    total_bytes = 0
    seen_hashes: dict[str, str] = {}
    for index, item in enumerate(items, start=1):
        try:
            file_name, source = _coerce_item(item, index)
            safe_name = Path(str(file_name).replace("\\", "/")).name
            if not safe_name or safe_name in {".", ".."}:
                raise ValueError("invalid file name")
            remaining = max(0, max_aggregate_bytes - total_bytes)
            raw = _read_bytes(
                source,  # type: ignore[arg-type]
                index,
                safe_name,
                max_bytes=min(max_file_size, remaining) + 1,
            )
            if len(raw) > max_file_size:
                raise ValueError(f"file exceeds the {max_file_size} byte upload limit")
            if total_bytes + len(raw) > max_aggregate_bytes:
                raise ValueError(
                    f"combined upload size exceeds the aggregate limit of "
                    f"{max_aggregate_bytes} bytes"
                )
            loaded = load_dataset(raw, safe_name, max_file_size=max_file_size)
            prior = seen_hashes.get(loaded.sha256)
            if prior is not None:
                raise ValueError(
                    f"duplicate content SHA-256 matches earlier file '{prior}'"
                )
            seen_hashes[loaded.sha256] = safe_name
            total_bytes += len(raw)
            results.append(
                FileIntakeResult(
                    index=index,
                    file_name=safe_name,
                    ok=True,
                    sha256=loaded.sha256,
                    row_count=len(loaded.frame),
                    column_count=len(loaded.frame.columns),
                    size_bytes=len(raw),
                )
            )
        except Exception as exc:  # noqa: BLE001 — surface any per-file failure cleanly
            name = "?"
            try:
                name = Path(str(_coerce_item(item, index)[0]).replace("\\", "/")).name
            except Exception:  # noqa: BLE001
                name = f"upload-{index}"
            results.append(
                FileIntakeResult(
                    index=index,
                    file_name=name or f"upload-{index}",
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return results


def format_intake_error_messages(results: list[FileIntakeResult]) -> list[str]:
    """Human-readable messages for failed rows only."""
    messages: list[str] = []
    for row in results:
        if row.ok:
            continue
        if row.file_name == "*":
            messages.append(row.error or "Upload selection rejected.")
        else:
            messages.append(
                f"Could not load '{row.file_name}' (upload {row.index}): {row.error}"
            )
    return messages
