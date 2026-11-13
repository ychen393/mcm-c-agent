"""CN/EN presentation strings for Streamlit Research Lab (UX-C).

Schema / field names stay English. User-facing labels go through ``t()``.
Locale persists in ``st.session_state["ui_locale"]`` and optionally ``?lang=``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORTED_LOCALES: tuple[str, ...] = ("en", "zh")
DEFAULT_LOCALE = "en"
LOCALE_KEY = "ui_locale"
QUERY_PARAM = "lang"

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


@lru_cache(maxsize=4)
def _load_locale(locale: str) -> dict[str, str]:
    path = _LOCALES_DIR / f"{locale}.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Locale file must be a JSON object: {path}")
    # Flatten one level of nesting if present; prefer flat string map.
    flat: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, str):
            flat[str(key)] = value
        elif isinstance(value, dict):
            for sub_key, sub_val in value.items():
                if isinstance(sub_val, str):
                    flat[f"{key}.{sub_key}"] = sub_val
    return flat


def clear_locale_cache() -> None:
    """Test helper: drop cached locale JSON."""
    _load_locale.cache_clear()


def _session_locale() -> str | None:
    try:
        import streamlit as st

        raw = st.session_state.get(LOCALE_KEY)
        if isinstance(raw, str) and raw in SUPPORTED_LOCALES:
            return raw
    except Exception:
        return None
    return None


def get_locale() -> str:
    """Active UI locale (defaults to English outside Streamlit / unset)."""
    return _session_locale() or DEFAULT_LOCALE


def set_locale(locale: str) -> str:
    """Force locale into session_state when Streamlit is available."""
    if locale not in SUPPORTED_LOCALES:
        raise ValueError(f"Unsupported locale: {locale}")
    try:
        import streamlit as st

        st.session_state[LOCALE_KEY] = locale
    except Exception:
        pass
    return locale


def t(key: str, **kwargs: Any) -> str:
    """Translate ``key`` for the active locale; fall back to English then key."""
    locale = get_locale()
    catalog = _load_locale(locale)
    text = catalog.get(key)
    if text is None and locale != DEFAULT_LOCALE:
        text = _load_locale(DEFAULT_LOCALE).get(key)
    if text is None:
        text = key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return text
    return text


def locale_display_name(locale: str) -> str:
    if locale == "zh":
        return "中文"
    return "EN"


def init_locale_from_query() -> str:
    """Seed session locale from ``?lang=en|zh`` once, then keep session sticky."""
    import streamlit as st

    if LOCALE_KEY not in st.session_state:
        raw = None
        try:
            raw = st.query_params.get(QUERY_PARAM)
        except Exception:
            raw = None
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if isinstance(raw, str) and raw.lower() in SUPPORTED_LOCALES:
            st.session_state[LOCALE_KEY] = raw.lower()
        else:
            st.session_state[LOCALE_KEY] = DEFAULT_LOCALE
    return get_locale()


def sync_locale_query_param(locale: str | None = None) -> None:
    """Mirror active locale into the URL query string (best-effort)."""
    import streamlit as st

    active = locale or get_locale()
    try:
        current = st.query_params.get(QUERY_PARAM)
        if isinstance(current, list):
            current = current[0] if current else None
        if current != active:
            st.query_params[QUERY_PARAM] = active
    except Exception:
        return


def render_language_toggle(*, location: str = "sidebar") -> str:
    """Render EN | 中文 toggle; persist in session_state and optional query param.

    Must run early on the page so subsequent ``t()`` calls see the choice.
    """
    import streamlit as st

    init_locale_from_query()
    container = st.sidebar if location == "sidebar" else st
    options = list(SUPPORTED_LOCALES)
    # selectbox (not radio) so existing AppTests keep Navigation as radio[0].
    selected = container.selectbox(
        t("lang.toggle"),
        options=options,
        format_func=locale_display_name,
        key=LOCALE_KEY,
        help=t("lang.toggle_help"),
    )
    if selected not in SUPPORTED_LOCALES:
        selected = DEFAULT_LOCALE
        st.session_state[LOCALE_KEY] = selected
    sync_locale_query_param(selected)
    return selected
