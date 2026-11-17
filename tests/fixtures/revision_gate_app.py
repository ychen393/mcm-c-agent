"""Minimal Streamlit surface for H2/H3 review acceptance tests, no provider calls on import."""
import streamlit as st

from app.validation_h2_panel import render_validation_h2_panel
from app.paper_h3_panel import render_paper_h3_panel
from core.config import get_settings

recorded = st.session_state.get("last_run") or {}
kwargs={
    "settings":get_settings(),
    "recorded_state":recorded,
    "project_id":recorded.get("project_id"),
    "project_name":recorded.get("project_name"),
    "input_signature":st.session_state.get("foundation_input_signature"),
}
if st.session_state.get("test_review_stage")=="h2":
    render_validation_h2_panel(
        **kwargs,
        problem_specification=recorded.get("problem_specification"),
        upload_payloads=st.session_state.get("test_upload_payloads") or [],
    )
elif st.session_state.get("test_review_stage")=="h3":
    render_paper_h3_panel(
        **kwargs, problem_specification=recorded.get("problem_specification"),
    )
else:
    st.error("Specify test_review_stage in AppTest session.")
