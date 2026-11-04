from __future__ import annotations
import csv
import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
import pandas as pd

ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
DEFAULT_MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_ROWS = 500_000
MAX_COLUMNS = 500

@dataclass
class LoadedDataset:
    frame: pd.DataFrame
    file_name: str
    file_extension: str
    file_size_bytes: int
    sha256: str
    raw_bytes: bytes

def safe_project_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-_")
    if not cleaned:
        raise ValueError("Project ID must contain at least one letter or number.")
    return cleaned[:80]

def load_dataset(source: bytes | BinaryIO, file_name: str, *, max_file_size: int = DEFAULT_MAX_FILE_SIZE) -> LoadedDataset:
    """Load a CSV/XLSX upload with strict size, extension and shape checks."""
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{extension or '(no extension)'}'. Use CSV or XLSX.")
    raw = source if isinstance(source, bytes) else source.read()
    if not isinstance(raw, bytes):
        raise ValueError("Uploaded file must be readable as bytes.")
    if not raw:
        raise ValueError("Uploaded file is empty.")
    if len(raw) > max_file_size:
        raise ValueError(f"File exceeds the {max_file_size // (1024 * 1024)} MB upload limit.")
    try:
        if extension == ".csv":
            header = next(csv.reader(io.StringIO(raw.decode("utf-8-sig"))), [])
        else:
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            try:
                header = list(next(workbook.active.iter_rows(min_row=1, max_row=1, values_only=True), []))
            finally:
                workbook.close()
        if not header or any(value is None or not str(value).strip() for value in header):
            raise ValueError("Column names must not be blank.")
        normalized_headers = [str(value).strip() for value in header]
        if len(normalized_headers) != len(set(normalized_headers)):
            raise ValueError("Duplicate column names are not allowed.")
        if extension == ".csv":
            frame = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
        else:
            frame = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Could not read {extension.upper()} file: {exc}") from exc
    if frame.empty or len(frame.columns) == 0:
        raise ValueError("Dataset contains no rows or columns.")
    if len(frame) > MAX_ROWS:
        raise ValueError(f"Dataset has more than {MAX_ROWS:,} rows.")
    if len(frame.columns) > MAX_COLUMNS:
        raise ValueError(f"Dataset has more than {MAX_COLUMNS} columns.")
    if any(not str(column).strip() for column in frame.columns):
        raise ValueError("Column names must not be blank.")
    if frame.columns.duplicated().any():
        duplicates = frame.columns[frame.columns.duplicated()].astype(str).tolist()
        raise ValueError(f"Duplicate column names are not allowed: {duplicates}")
    return LoadedDataset(frame, Path(file_name).name, extension, len(raw), hashlib.sha256(raw).hexdigest(), raw)
