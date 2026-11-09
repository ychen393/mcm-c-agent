"""Conservative, deterministic, read-only relationship inspection for dataset bundles."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

import pandas as pd

from tools.dataset_bundle import DatasetBundle

MAX_PREVIEW_ROWS = 50
MAX_JOIN_ROWS = 100_000


@dataclass(frozen=True)
class Candidate:
    left_id: str
    right_id: str
    left_key: str
    right_key: str
    left_rows: int
    right_rows: int
    left_missing: int
    right_missing: int
    left_duplicates: int
    right_duplicates: int
    overlap: int
    relationship: str
    safe_to_preview: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _key_values(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame.columns:
        raise ValueError(f"Unknown key: {name}")
    return frame[name]


def _frequency_risk(a: pd.Series, b: pd.Series) -> bool:
    # No silent coercion of dates, units, timezones, or frequency.
    def approximate_days(s: pd.Series) -> float | None:
        if not (pd.api.types.is_datetime64_any_dtype(s) or
                any(k in str(s.name).lower() for k in ("date", "time", "timestamp"))):
            return None
        dt = pd.to_datetime(s.dropna(), errors="coerce")
        if dt.isna().any() or len(dt) < 3:
            return None
        distinct = dt.drop_duplicates().sort_values()
        if len(distinct) < 3:
            return None
        deltas = distinct.diff().dropna().dt.total_seconds() / 86400
        return float(deltas.median()) if len(deltas) else None
    av, bv = approximate_days(a), approximate_days(b)
    return av is not None and bv is not None and max(av, bv) > 3 * max(min(av, bv), 1e-9)


def inspect_pair(bundle: DatasetBundle, left_id: str, right_id: str,
                 left_key: str, right_key: str) -> Candidate:
    if left_id == right_id:
        raise ValueError("Select two different datasets.")
    left = bundle.loaded_dataset(left_id).frame
    right = bundle.loaded_dataset(right_id).frame
    a = _key_values(left, left_key)
    b = _key_values(right, right_key)
    left_missing, right_missing = int(a.isna().sum()), int(b.isna().sum())
    left_dupes = int(a.dropna().duplicated().sum())
    right_dupes = int(b.dropna().duplicated().sum())
    if a.dropna().empty or b.dropna().empty:
        return Candidate(left_id, right_id, left_key, right_key, len(a), len(b),
                         left_missing, right_missing, left_dupes, right_dupes,
                         0, "UNKNOWN", False, "No non-null join keys.")
    compatible = (pd.api.types.is_numeric_dtype(a) == pd.api.types.is_numeric_dtype(b))
    if not compatible:
        return Candidate(left_id, right_id, left_key, right_key, len(a), len(b),
                         left_missing, right_missing, left_dupes, right_dupes,
                         0, "INCOMPATIBLE", False, "Key types differ; coercion is not automatic.")
    # Hashed comparison avoids mixed-type ordering assumptions.
    left_values = set(a.dropna().astype(str))
    right_values = set(b.dropna().astype(str))
    overlap = len(left_values & right_values)
    relationship = ("1:1" if not left_dupes and not right_dupes else
                    "1:N" if not left_dupes else
                    "N:1" if not right_dupes else "N:M")
    risky_frequency = _frequency_risk(a, b)
    reason = ("No matching key values." if not overlap else
              "Many-to-many duplication requires aggregation or a different key." if relationship == "N:M" else
              "Different apparent date frequencies; resampling requires explicit approval." if risky_frequency else
              "Candidate only: inspect semantics, units and timezone before trusting the join.")
    safe = overlap > 0 and relationship != "N:M" and not risky_frequency
    return Candidate(left_id, right_id, left_key, right_key, len(a), len(b),
                     left_missing, right_missing, left_dupes, right_dupes,
                     overlap, relationship, safe, reason)


def discover_relationships(bundle: DatasetBundle) -> list[Candidate]:
    results: list[Candidate] = []
    for left_ref, right_ref in combinations(bundle.datasets, 2):
        common = sorted(set(left_ref.column_names) & set(right_ref.column_names))
        for key in common[:20]:
            results.append(inspect_pair(bundle, left_ref.dataset_id,
                                        right_ref.dataset_id, key, key))
    return results


def preview_join(bundle: DatasetBundle, left_id: str, right_id: str,
                 left_key: str, right_key: str, how: str = "inner",
                 max_rows: int = MAX_JOIN_ROWS) -> tuple[Candidate, pd.DataFrame]:
    if how not in ("inner", "left"):
        raise ValueError("Only inner and left preview joins are supported.")
    if max_rows < 1 or max_rows > MAX_JOIN_ROWS:
        raise ValueError("Unsafe preview output row limit.")
    candidate = inspect_pair(bundle, left_id, right_id, left_key, right_key)
    if not candidate.safe_to_preview:
        raise ValueError(candidate.reason)
    a = bundle.loaded_dataset(left_id).frame
    b = bundle.loaded_dataset(right_id).frame
    # Bound the output *before* allocating a potentially explosive pandas merge.
    left_counts = a[left_key].dropna().astype(str).value_counts()
    right_counts = b[right_key].dropna().astype(str).value_counts()
    predicted_inner = sum(int(n) * int(right_counts.get(key, 0))
                          for key, n in left_counts.items())
    predicted = predicted_inner + (len(a) - sum(int(n) for key, n in left_counts.items()
                        if key in right_counts.index)) if how == "left" else predicted_inner
    if predicted > max_rows:
        raise ValueError("Predicted join exceeds safe preview row limit.")
    # Refuse null-key merging: pandas treats null=null as matching, unlike SQL.
    left = a.dropna(subset=[left_key]).copy()
    right = b.dropna(subset=[right_key]).copy()
    if how == "left" and candidate.left_missing:
        raise ValueError("Left join with null keys needs an explicit missing-key policy.")
    expected = {"1:1": "one_to_one", "1:N": "one_to_many", "N:1": "many_to_one"}
    joined = left.merge(right, left_on=left_key, right_on=right_key,
                        how=how, validate=expected[candidate.relationship],
                        suffixes=("_left", "_right"), sort=False)
    if len(joined) > max_rows:
        raise ValueError("Join exceeds row limit.")
    return candidate, joined.head(MAX_PREVIEW_ROWS).copy()
