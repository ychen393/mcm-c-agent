"""Streamlit AppTest: password gate blocks content until authenticated."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from core.config import get_settings

APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_login_form_shown_when_password_configured(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_PASSWORD", "gate-secret")
    monkeypatch.setenv("PROJECT_STORE_BACKEND", "local")
    get_settings.cache_clear()

    at = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    titles = [t.value for t in at.title]
    assert any("Sign in" in str(v) for v in titles)
    # Research Lab chrome must not render while locked.
    assert not any("Research" in str(v) and "Lab" in str(v) for v in titles)


def test_dev_without_password_reaches_lab(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setenv("PROJECT_STORE_BACKEND", "local")
    get_settings.cache_clear()

    at = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    # Should not be stuck on the Sign in page.
    titles = [str(t.value) for t in at.title]
    assert not any(v == "Sign in" for v in titles)
