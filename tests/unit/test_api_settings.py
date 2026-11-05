"""API Settings UI contracts; no real provider requests or secret persistence."""
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.api_settings import (
    SESSION_SETTINGS_KEY,
    SESSION_REVISION_KEY,
    build_runtime_settings,
    clear_pending_plan,
    sanitize_provider_config,
)
from core.config import Settings
from llm.factory import LLMFactory


@pytest.fixture()
def base(tmp_path):
    return Settings(
        _env_file=None,
        llm_provider="deepseek",
        llm_model="deepseek-chat",
        llm_base_url="https://api.deepseek.com",
        llm_api_key=SecretStr("env-default-key"),
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
    )


@pytest.mark.parametrize("provider", ["deepseek", "openai", "anthropic"])
def test_session_api_configuration_supports_providers(base, provider):
    config = sanitize_provider_config(provider, "test-model", "  sk-session-secret  ")
    runtime = build_runtime_settings(base, config)
    assert runtime.llm_provider == provider
    assert runtime.llm_model == "test-model"
    assert runtime.provider_api_key().get_secret_value() == "sk-session-secret"
    assert base.provider_api_key().get_secret_value() == "env-default-key"
    assert isinstance(config["api_key"], SecretStr)


def test_openai_uses_official_endpoint_not_deepseek_url(base):
    config = sanitize_provider_config("openai", "gpt-4.1-mini", "sk-test")
    runtime = build_runtime_settings(base, config)
    assert runtime.llm_base_url is None
    adapter = LLMFactory.create(runtime)
    assert adapter.provider == "openai"
    assert adapter.base_url is None


def test_anthropic_adapter_can_be_created_without_optional_library(base):
    config = sanitize_provider_config("anthropic", "test-model", "sk-test")
    runtime = build_runtime_settings(base, config)
    adapter = LLMFactory.create(runtime)
    assert adapter.provider == "anthropic"


def test_session_settings_do_not_modify_env_or_write_files(base, tmp_path):
    config = sanitize_provider_config("deepseek", "deepseek-chat", "test-secret-123")
    before = base.model_dump()
    runtime = build_runtime_settings(base, config)
    assert base.model_dump() == before
    assert runtime.llm_api_key.get_secret_value() == "test-secret-123"
    assert not (tmp_path / ".env").exists()
    assert "test-secret-123" not in repr(config)


@pytest.mark.parametrize(
    ("provider", "model", "key"),
    [
        ("unknown", "chat", "sk-valid"),
        ("deepseek", "", "sk-valid"),
        ("openai", "x" * 129, "sk-valid"),
        ("anthropic", "test-model", "  "),
    ],
)
def test_invalid_settings_are_rejected(provider, model, key):
    with pytest.raises(ValueError):
        sanitize_provider_config(provider, model, key)


def test_invalid_session_configuration_is_rejected(base):
    with pytest.raises(ValueError, match="Missing session API key"):
        build_runtime_settings(
            base,
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
                "api_key": SecretStr(""),
            },
        )


def test_pending_chart_approval_is_invalidated_on_key_change():
    state = {
        SESSION_SETTINGS_KEY: {"provider": "deepseek"},
        SESSION_REVISION_KEY: 2,
        "eda_pending_plan": {"charts": []},
        "eda_pending_report": {"project_id": "old"},
        "eda_pending_dataset_sha": "oldhash",
        "eda_pending_problem_statement": "old problem",
        "eda_pending_context_signature": "old-signature",
        "eda_report": {"summary": {}},
    }
    clear_pending_plan(state)
    assert "eda_pending_plan" not in state
    assert "eda_pending_report" not in state
    assert "eda_pending_context_signature" not in state
    assert "eda_report" in state
