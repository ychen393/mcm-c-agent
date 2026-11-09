"""Multi-dataset relationship table and an explicit join preview.

The panel never starts a preview on its own and never stores the preview as a
dataset, chart plan, or file.
"""

from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

from tools.dataset_bundle import DatasetBundle
from tools.relationship_profiler import (
    preview_join,
    profile_relationships,
    relationship_table_rows,
)

_JOIN_LABELS = ("Inner", "Left", "Right", "Outer")


def render_relationship_panel(
    bundle: DatasetBundle,
    *,
    column_units_by_dataset: Mapping[str, Mapping[str, str]] | None = None,
    temporal_frequency_by_dataset: Mapping[str, str | None] | None = None,
) -> None:
    """Show evidence for the current bundle and preview only after a click."""
    units = {
        dataset_id: {name: unit for name, unit in mapping.items()}
        for dataset_id, mapping in (column_units_by_dataset or {}).items()
    }
    frequencies = {
        dataset_id: value for dataset_id, value in (temporal_frequency_by_dataset or {}).items()
    }
    report = profile_relationships(
        bundle,
        column_units_by_dataset=units,
        temporal_frequency_by_dataset=frequencies,
    )
    st.subheader("Relationship evidence")
    st.caption(
        "Candidates are exact column names or exact ISO dates. "
        "Nothing is joined until you preview, and a preview is not saved."
    )
    for note in report.limitations:
        st.caption(note)
    for pair in report.pairs:
        if pair.state == "cannot safely join":
            detail = pair.caveats[0] if pair.caveats else ""
            st.error(
                f"{pair.left_display_name} and {pair.right_display_name}: "
                f"cannot safely join. {detail}".strip()
            )
        elif pair.state == "ambiguous":
            st.info(
                f"{pair.left_display_name} and {pair.right_display_name}: UNKNOWN. "
                "Choose the keys yourself. Nothing is joined automatically."
            )
    st.dataframe(relationship_table_rows(report), use_container_width=True)

    names = [ref.display_name for ref in bundle.datasets]
    id_by_name = {ref.display_name: ref.dataset_id for ref in bundle.datasets}
    _prefer("rel_left_dataset", names, names[0])
    _prefer("rel_right_dataset", names, names[1] if len(names) > 1 else names[0])
    left_name = st.selectbox("Left dataset", names, key="rel_left_dataset")
    right_name = st.selectbox("Right dataset", names, key="rel_right_dataset")
    left_ref = next(ref for ref in bundle.datasets if ref.display_name == left_name)
    right_ref = next(ref for ref in bundle.datasets if ref.display_name == right_name)
    preferred_left, preferred_right = _preferred_keys(
        report, left_ref.dataset_id, right_ref.dataset_id
    )
    _prefer("rel_left_key", left_ref.column_names, preferred_left)
    _prefer("rel_right_key", right_ref.column_names, preferred_right)
    _prefer("rel_join_type", list(_JOIN_LABELS), _JOIN_LABELS[0])
    left_key = st.selectbox("Left key", left_ref.column_names, key="rel_left_key")
    right_key = st.selectbox("Right key", right_ref.column_names, key="rel_right_key")
    join_label = st.selectbox("Join type", list(_JOIN_LABELS), key="rel_join_type")
    st.caption(
        "Preview join does not save a merged dataset and does not change the uploaded files."
    )
    if st.button("Preview join", key="relationship_preview_join"):
        result = preview_join(
            bundle,
            left_dataset_id=id_by_name[left_name],
            right_dataset_id=id_by_name[right_name],
            left_key=left_key,
            right_key=right_key,
            join_type=join_label.lower(),
            column_units_by_dataset=units,
            temporal_frequency_by_dataset=frequencies,
        )
        if result.status == "blocked":
            st.error(result.message)
            return
        for warning in result.warnings:
            st.warning(warning)
        st.dataframe(result.preview_rows, use_container_width=True)
        lineage = result.lineage
        if lineage is not None:
            st.caption(
                "Lineage: "
                f"{lineage.left_file_name} `{lineage.left_qualified_key}` "
                f"{lineage.join_type} {lineage.right_file_name} "
                f"`{lineage.right_qualified_key}`. "
                f"SHA-256 {lineage.left_sha256} and {lineage.right_sha256}. "
                "Not saved, not resampled, and units were not converted."
            )
        st.caption(
            f"Overlap keys: {result.overlap_key_count}. "
            f"Unmatched rows: left {result.unmatched_left_rows}, "
            f"right {result.unmatched_right_rows}. "
            f"Cardinality: {result.cardinality}."
        )


def _prefer(key: str, options: list[str], preferred: str) -> None:
    if st.session_state.get(key) not in options:
        st.session_state[key] = preferred if preferred in options else options[0]


def _preferred_keys(report, left_id: str, right_id: str) -> tuple[str, str]:
    for pair in report.pairs:
        forward = pair.left_dataset_id == left_id and pair.right_dataset_id == right_id
        reverse = pair.left_dataset_id == right_id and pair.right_dataset_id == left_id
        if not forward and not reverse:
            continue
        for candidate in pair.candidates:
            if not candidate.safe_to_preview:
                continue
            if forward:
                return candidate.left_column, candidate.right_column
            return candidate.right_column, candidate.left_column
        if pair.candidates:
            candidate = pair.candidates[0]
            if forward:
                return candidate.left_column, candidate.right_column
            return candidate.right_column, candidate.left_column
    return "", ""
