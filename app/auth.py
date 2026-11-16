"""Server-side single-user password gate for Streamlit.

v1 auth is a shared app password from the environment / Railway Secret.
UI hide-only is not enough: unauthenticated sessions must not render Research Lab,
API Settings, or other sensitive content. Fail closed when APP_ENV is production-like
and APP_PASSWORD is unset.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import Settings

AUTH_SESSION_KEY = "mcm_authenticated"
AUTH_FORM_KEY = "mcm_auth_password_input"
PRODUCTION_LIKE_ENVS = frozenset({"production", "prod", "staging", "railway"})


def is_production_like(app_env: str) -> bool:
    return str(app_env or "").strip().lower() in PRODUCTION_LIKE_ENVS


def resolve_app_password(settings: Settings) -> str | None:
    """Return the configured password string, or None when unset/blank."""
    secret = getattr(settings, "app_password", None)
    if secret is None:
        return None
    value = secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)
    value = (value or "").strip()
    return value or None


def auth_is_configured(settings: Settings) -> bool:
    return resolve_app_password(settings) is not None


def assert_auth_config(settings: Settings) -> None:
    """Raise when a production-like deploy would otherwise ship with open access."""
    if is_production_like(settings.app_env) and not auth_is_configured(settings):
        raise RuntimeError(
            "APP_PASSWORD is required when APP_ENV is production-like "
            f"({settings.app_env!r}). Set a Railway Secret / env var; never hardcode."
        )


def verify_password(settings: Settings, candidate: str) -> bool:
    expected = resolve_app_password(settings)
    if expected is None:
        return False
    # compare_digest requires equal-length strings of the same type; pad via hmac pattern
    # by hashing both sides so length differences do not leak via exception.
    left = secrets.compare_digest(
        _digest(candidate),
        _digest(expected),
    )
    return left


def _digest(value: str) -> bytes:
    # Fixed-length comparison material; not a password KDF (v1 shared password).
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).digest()


def session_is_authenticated(session_state: dict | None = None) -> bool:
    state = session_state
    if state is None:
        import streamlit as st

        state = st.session_state
    return bool(state.get(AUTH_SESSION_KEY))


def mark_authenticated(session_state: dict | None = None) -> None:
    state = session_state
    if state is None:
        import streamlit as st

        state = st.session_state
    state[AUTH_SESSION_KEY] = True


def clear_authentication(session_state: dict | None = None) -> None:
    state = session_state
    if state is None:
        import streamlit as st

        state = st.session_state
    state.pop(AUTH_SESSION_KEY, None)


def require_streamlit_auth(settings: Settings) -> None:
    """Block all Streamlit content until the shared password is accepted.

    Call immediately after ``st.set_page_config``. On failure, renders a login
    form (or a hard error) and ``st.stop()`` so later panels never execute.
    """
    import streamlit as st

    try:
        assert_auth_config(settings)
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    if not auth_is_configured(settings):
        # Local/dev with no password: open access (do not use for public URLs).
        return

    if session_is_authenticated():
        with st.sidebar:
            if st.button("Log out", key="mcm_auth_logout"):
                clear_authentication()
                st.rerun()
        return

    st.title("Sign in")
    st.caption("This Research Lab requires a shared access password.")
    with st.form("mcm_auth_login", clear_on_submit=False):
        candidate = st.text_input(
            "Password",
            type="password",
            key=AUTH_FORM_KEY,
            autocomplete="current-password",
        )
        submitted = st.form_submit_button("Unlock", type="primary")
    if submitted:
        if verify_password(settings, candidate or ""):
            mark_authenticated()
            st.rerun()
        st.error("Incorrect password.")
    st.stop()
