"""Session-scoped API credentials UI.

API keys are kept only in Streamlit's server-side session state. Never persist
them to .env, local files, reports, or git from the web UI.
"""
from __future__ import annotations

from urllib.parse import urlparse

import streamlit as st
from pydantic import SecretStr

from core.config import Settings
from llm.factory import LLMFactory

PROVIDER_DEFAULTS = {
    "deepseek": ("deepseek-chat", "https://api.deepseek.com"),
    "openai": ("gpt-4.1-mini", None),
    "anthropic": ("claude-sonnet-4-5", None),
}
SESSION_SETTINGS_KEY = "llm_session_config"
SESSION_REVISION_KEY = "llm_session_revision"
PENDING_PLAN_KEYS = (
    "eda_pending_plan",
    "eda_pending_report",
    "eda_pending_dataset_sha",
    "eda_pending_problem_statement",
    "eda_pending_context_signature",
)


def build_runtime_settings(base: Settings, session_config: dict | None) -> Settings:
    """Compose runtime settings without mutating cached .env settings."""
    if not session_config:
        return base
    provider = session_config["provider"]
    if provider not in PROVIDER_DEFAULTS:
        raise ValueError("Unsupported model provider")
    key = session_config["api_key"]
    if not isinstance(key, SecretStr) or not key.get_secret_value().strip():
        raise ValueError("Missing session API key")
    return base.model_copy(
        update={
            "llm_provider": provider,
            "llm_model": session_config["model"],
            "llm_base_url": session_config["base_url"],
            # Override any generic key from the environment, for this session only.
            "llm_api_key": key,
        }
    )


def sanitize_provider_config(provider: str, model: str, key: str) -> dict:
    """Reject malformed input; do not accept arbitrary remote API endpoints."""
    if provider not in PROVIDER_DEFAULTS:
        raise ValueError("Select a supported provider")
    model = model.strip()
    if not model or len(model) > 128:
        raise ValueError("Enter a valid model identifier (1–128 characters)")
    if not key.strip():
        raise ValueError("API key cannot be empty")
    default_model, base_url = PROVIDER_DEFAULTS[provider]
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": SecretStr(key.strip()),
    }


def clear_pending_plan(session_state) -> None:
    for key in PENDING_PLAN_KEYS:
        session_state.pop(key, None)


def render_api_settings(base_settings: Settings) -> None:
    st.header("API Settings")
    st.write("Configure the language-model provider used by Visual EDA Planner.")
    st.info(
        "Keys entered here are kept in this browser session on your local "
        "Streamlit server. They are not saved to .env, GitHub, or EDA reports. "
        "You may need to enter them again after restarting the app."
    )
    saved = st.session_state.get(SESSION_SETTINGS_KEY)

    provider_options = list(PROVIDER_DEFAULTS)
    selected_provider = st.selectbox(
        "Provider",
        options=provider_options,
        index=provider_options.index(saved["provider"]) if saved else (
            provider_options.index(base_settings.llm_provider)
        ),
        key="api_provider_selector",
    )
    default_model, base_url = PROVIDER_DEFAULTS[selected_provider]
    with st.form("api_settings_form", clear_on_submit=True):
        model = st.text_input(
            "Model ID",
            value=saved["model"] if saved and saved["provider"] == selected_provider else (
                base_settings.llm_model
                if selected_provider == base_settings.llm_provider
                and base_settings.llm_model != "replace-with-model-id"
                else default_model
            ),
            help="Use the model ID supported by your provider's API account.",
        )
        st.caption(f"API endpoint: {base_url or 'Provider default (official API)'}")
        api_key = st.text_input(
            "API Key",
            type="password",
            placeholder="Paste your key here — hidden while typing",
            help="The key will never be shown again after saving.",
        )
        submitted = st.form_submit_button("Save for this session", type="primary")

    if submitted:
        try:
            config = sanitize_provider_config(selected_provider, model, api_key)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state[SESSION_SETTINGS_KEY] = config
            st.session_state[SESSION_REVISION_KEY] = (
                st.session_state.get(SESSION_REVISION_KEY, 0) + 1
            )
            clear_pending_plan(st.session_state)
            st.success("API configuration saved for this session.")

    current = st.session_state.get(SESSION_SETTINGS_KEY)
    if current:
        st.success(f"Configured: {current['provider']} / {current['model']}")
        st.caption("Credential status: Present in this session (not yet connectivity-verified).")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Test connection", key="test_api_connection"):
                try:
                    runtime = build_runtime_settings(base_settings, current)
                    response = LLMFactory.create(runtime).invoke(
                        [{"role": "user", "content": "Reply exactly OK."}]
                    )
                    if response.content.strip():
                        st.success(
                            f"Connection successful: {response.provider} / {response.model}"
                        )
                    else:
                        st.warning("The request completed but returned no text.")
                except Exception:
                    # Do not expose provider exception bodies; they may contain
                    # headers, URLs or other sensitive configuration.
                    st.error(
                        "Connection failed. Verify API key, model ID, account balance, "
                        "provider access and network connectivity."
                    )
        with col2:
            if st.button("Clear saved key", key="clear_api_key"):
                st.session_state.pop(SESSION_SETTINGS_KEY, None)
                st.session_state[SESSION_REVISION_KEY] = (
                    st.session_state.get(SESSION_REVISION_KEY, 0) + 1
                )
                clear_pending_plan(st.session_state)
                st.success("Session API configuration cleared.")
                st.rerun()
    else:
        st.caption("No session API key is configured. The app may still use a local .env key.")

    st.warning(
        "Only use this API Settings page on your own localhost server. "
        "Do not publish it to the internet without authentication and a secure secret store."
    )
