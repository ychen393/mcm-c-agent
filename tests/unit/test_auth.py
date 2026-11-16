"""Server-side password auth contracts (no Streamlit UI render required)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.auth import (
    AUTH_SESSION_KEY,
    assert_auth_config,
    auth_is_configured,
    clear_authentication,
    is_production_like,
    mark_authenticated,
    resolve_app_password,
    session_is_authenticated,
    verify_password,
)
from core.config import Settings


def _settings(**kwargs) -> Settings:
    base = dict(
        app_env="test",
        llm_provider="deepseek",
        llm_model="test-model",
        llm_base_url="https://api.deepseek.com",
        upload_dir=kwargs.pop("upload_dir", None),
        output_dir=kwargs.pop("output_dir", None),
    )
    # Paths required by normalize_paths — callers should pass tmp paths.
    if base["upload_dir"] is None or base["output_dir"] is None:
        raise AssertionError("tests must pass upload_dir/output_dir")
    base.update(kwargs)
    return Settings(**base)


def test_production_like_detection():
    assert is_production_like("production")
    assert is_production_like("PROD")
    assert is_production_like("railway")
    assert is_production_like("staging")
    assert not is_production_like("development")
    assert not is_production_like("test")


def test_password_never_hardcoded_and_from_settings(tmp_path):
    settings = _settings(
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
        app_password=SecretStr("s3cret-demo"),
    )
    assert resolve_app_password(settings) == "s3cret-demo"
    assert auth_is_configured(settings)
    assert verify_password(settings, "s3cret-demo")
    assert not verify_password(settings, "wrong")
    assert not verify_password(settings, "")


def test_blank_password_treated_as_unset(tmp_path):
    settings = _settings(
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
        app_password=SecretStr("   "),
    )
    assert resolve_app_password(settings) is None
    assert not auth_is_configured(settings)


def test_fail_closed_when_production_password_missing(tmp_path):
    settings = _settings(
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
        app_env="production",
        app_password=None,
    )
    with pytest.raises(RuntimeError, match="APP_PASSWORD"):
        assert_auth_config(settings)


def test_development_allows_missing_password(tmp_path):
    settings = _settings(
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
        app_env="development",
        app_password=None,
    )
    assert_auth_config(settings)  # does not raise


def test_session_auth_helpers():
    state: dict = {}
    assert not session_is_authenticated(state)
    mark_authenticated(state)
    assert state[AUTH_SESSION_KEY] is True
    assert session_is_authenticated(state)
    clear_authentication(state)
    assert not session_is_authenticated(state)
