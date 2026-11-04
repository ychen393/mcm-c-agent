from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import numpy as np
import pandas as pd
from schemas.eda import ColumnProfile, DatasetMetadata, EDAReport
from tools.data_loader import LoadedDataset

def _json_scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)

def _numeric_summary(series: pd.Series) -> tuple[dict[str, float | None], int]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {key: None for key in ("mean", "median", "std", "min", "q1", "q3", "max")}, 0
    q1, q3 = float(numeric.quantile(0.25)), float(numeric.quantile(0.75))
    iqr = q3 - q1
    outliers = int(((numeric < q1 - 1.5 * iqr) | (numeric > q3 + 1.5 * iqr)).sum())
    return {"mean": float(numeric.mean()), "median": float(numeric.median()),
            "std": float(numeric.std()) if len(numeric) > 1 else 0.0,
            "min": float(numeric.min()), "q1": q1, "q3": q3, "max": float(numeric.max())}, outliers

def build_eda_report(dataset: LoadedDataset, project_id: str) -> EDAReport:
    frame = dataset.frame
    row_count, column_count = frame.shape
    profiles: list[ColumnProfile] = []
    warnings: list[str] = []
    duplicate_rows = int(frame.duplicated().sum())
    if duplicate_rows:
        warnings.append(f"Found {duplicate_rows} fully duplicated rows. Review before modeling.")
    for column in frame.columns:
        series = frame[column]
        missing_count = int(series.isna().sum())
        sample_values = [_json_scalar(value) for value in series.dropna().head(5).tolist()]
        profile = ColumnProfile(name=str(column), dtype=str(series.dtype), missing_count=missing_count,
            missing_rate=missing_count / row_count if row_count else 0.0,
            unique_count=int(series.nunique(dropna=True)), sample_values=sample_values)
        if pd.api.types.is_numeric_dtype(series):
            summary, outlier_count = _numeric_summary(series)
            profile.numeric_summary, profile.outlier_count_iqr = summary, outlier_count
            if outlier_count:
                warnings.append(f"Column '{column}' has {outlier_count} IQR-flagged values; this is a review signal, not proof of bad data.")
        elif pd.api.types.is_datetime64_any_dtype(series) or any(
            token in str(column).lower() for token in ("date", "time", "timestamp")
        ):
            values = pd.to_datetime(series, errors="coerce").dropna()
            if not values.empty and len(values) / max(len(non_null), 1) >= 0.8:
                profile.dtype = "datetime (inferred)"
                profile.datetime_min, profile.datetime_max = values.min().isoformat(), values.max().isoformat()
            else:
                counts = series.astype("string").value_counts(dropna=True).head(10)
                profile.top_values = [{"value": str(value), "count": int(count)} for value, count in counts.items()]
        else:
            counts = series.astype("string").value_counts(dropna=True).head(10)
            profile.top_values = [{"value": str(value), "count": int(count)} for value, count in counts.items()]
        if missing_count:
            warnings.append(f"Column '{column}' has {missing_count} missing values ({missing_count / row_count:.1%}).")
        profiles.append(profile)
    numeric_frame = frame.select_dtypes(include=["number"])
    correlations: dict[str, dict[str, float | None]] = {}
    if numeric_frame.shape[1] >= 2:
        corr = numeric_frame.corr(numeric_only=True)
        correlations = {str(row): {str(col): (None if pd.isna(val) else float(val))
            for col, val in corr.loc[row].items()} for row in corr.index}
    metadata = DatasetMetadata(file_name=dataset.file_name, file_extension=dataset.file_extension,
        file_size_bytes=dataset.file_size_bytes, sha256=dataset.sha256,
        loaded_at_utc=datetime.now(timezone.utc), row_count=row_count, column_count=column_count,
        duplicate_row_count=duplicate_rows, columns=profiles)
    return EDAReport(project_id=project_id, dataset=metadata, numeric_correlations=correlations,
        warnings=warnings, generated_at_utc=datetime.now(timezone.utc),
        summary={"row_count": row_count, "column_count": column_count,
            "numeric_column_count": int(numeric_frame.shape[1]),
            "columns_with_missing_values": sum(item.missing_count > 0 for item in profiles),
            "duplicate_row_count": duplicate_rows,
            "datetime_columns": [item.name for item in profiles if item.datetime_min is not None]})
