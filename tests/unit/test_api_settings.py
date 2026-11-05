"""API Settings UI contracts; no real provider requests or secret persistence."""
import ast
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.api_settings import (
    SESSION_REVISION_KEY,
    SESSION_SETTINGS_KEY,
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
    for key in (
        "eda_pending_plan",
        "eda_pending_report",
        "eda_pending_dataset_sha",
        "eda_pending_problem_statement",
        "eda_pending_context_signature",
    ):
        assert key not in state
    assert "eda_report" in state


def _is_st_session_state(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "session_state"
        and isinstance(node.value, ast.Name)
        and node.value.id == "st"
    )


def _is_revision_lookup(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or node.keywords or len(node.args) != 2:
        return False
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "get":
        return False
    if not _is_st_session_state(func.value):
        return False
    key, default = node.args
    key_ok = isinstance(key, ast.Name) and key.id == "SESSION_REVISION_KEY"
    return key_ok and isinstance(default, ast.Constant) and default.value == 0


def _is_revision_increment(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return False
    target = stmt.targets[0]
    if not (
        isinstance(target, ast.Subscript)
        and _is_st_session_state(target.value)
        and isinstance(target.slice, ast.Name)
        and target.slice.id == "SESSION_REVISION_KEY"
    ):
        return False
    value = stmt.value
    return (
        isinstance(value, ast.BinOp)
        and isinstance(value.op, ast.Add)
        and isinstance(value.right, ast.Constant)
        and value.right.value == 1
        and _is_revision_lookup(value.left)
    )


def _is_clear_pending_call(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
        return False
    call = stmt.value
    if node_name(call.func) != "clear_pending_plan" or call.keywords or len(call.args) != 1:
        return False
    return _is_st_session_state(call.args[0])


def node_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _is_clear_saved_key_button(test: ast.AST) -> bool:
    if not isinstance(test, ast.Call):
        return False
    func = test.func
    if not isinstance(func, ast.Attribute) or func.attr != "button":
        return False
    if not isinstance(func.value, ast.Name) or func.value.id != "st":
        return False
    label = any(
        isinstance(arg, ast.Constant) and arg.value == "Clear saved key" for arg in test.args
    )
    button_key = any(
        keyword.arg == "key"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value == "clear_api_key"
        for keyword in test.keywords
    )
    return label and button_key


def _statement_lists(function: ast.FunctionDef) -> list[tuple[ast.AST, str, list[ast.stmt]]]:
    found: list[tuple[ast.AST, str, list[ast.stmt]]] = []
    for node in ast.walk(function):
        for field in ("body", "orelse", "finalbody"):
            value = getattr(node, field, None)
            if isinstance(value, list) and all(isinstance(item, ast.stmt) for item in value):
                found.append((node, field, value))
    return found


def assert_save_and_clear_invalidate_pending_plan(source: str) -> None:
    """Require both UI mutation paths to bump SESSION_REVISION_KEY and clear the plan."""
    module = ast.parse(source)
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "render_api_settings"
    )
    save_try: ast.Try | None = None
    saw_clear = False
    for node, field, body in _statement_lists(function):
        has_increment = any(_is_revision_increment(stmt) for stmt in body)
        has_clear = any(_is_clear_pending_call(stmt) for stmt in body)
        if not has_increment and not has_clear:
            continue
        if has_increment != has_clear:
            raise AssertionError(
                "SESSION_REVISION_KEY increment and clear_pending_plan must occur together "
                f"at line {getattr(node, 'lineno', '?')}"
            )
        if isinstance(node, ast.Try) and field == "orelse":
            if save_try is not None:
                raise AssertionError("multiple successful API Settings save paths")
            save_try = node
        elif isinstance(node, ast.If) and field == "body" and _is_clear_saved_key_button(node.test):
            if saw_clear:
                raise AssertionError("multiple Clear saved key paths")
            saw_clear = True
        else:
            raise AssertionError(
                f"unexpected revision mutation at line {getattr(node, 'lineno', '?')}"
            )
    if save_try is None:
        raise AssertionError("successful save path does not bump the revision and clear the plan")
    if not saw_clear:
        raise AssertionError("Clear saved key path does not bump the revision and clear the plan")
    for handler in save_try.handlers:
        invalidates = any(
            _is_revision_increment(stmt) or _is_clear_pending_call(stmt) for stmt in handler.body
        )
        if invalidates:
            raise AssertionError("rejected API Settings input must not invalidate a pending plan")


_REVISION_INCREMENT = (
    "st.session_state[SESSION_REVISION_KEY] = "
    "st.session_state.get(SESSION_REVISION_KEY, 0) + 1"
)
_WRONG_REVISION_INCREMENT = (
    "st.session_state[SESSION_REVISION_KEY] = "
    "st.session_state.get('other_revision', 0) + 1"
)
_CLEAR_PENDING = "clear_pending_plan(st.session_state)"


def _mutation_snippet(save_clear: str, clear_revision: str, clear_call: str) -> str:
    return f"""
def render_api_settings(base_settings):
    if submitted:
        try:
            sanitize_provider_config(selected_provider, model, api_key)
        except ValueError as exc:
            st.error(str(exc))
        else:
            {_REVISION_INCREMENT}
            {save_clear}
    if st.button("Clear saved key", key="clear_api_key"):
        {clear_revision}
        {clear_call}
"""


def test_render_api_settings_save_and_clear_invalidate_pending_plan():
    source = Path("app/api_settings.py").read_text(encoding="utf-8")
    assert_save_and_clear_invalidate_pending_plan(source)


def test_removed_clear_or_wrong_revision_key_fails_contract():
    missing_clear = _mutation_snippet("pass", _REVISION_INCREMENT, _CLEAR_PENDING)
    wrong_key = _mutation_snippet(_CLEAR_PENDING, _WRONG_REVISION_INCREMENT, _CLEAR_PENDING)
    with pytest.raises(AssertionError, match="must occur together"):
        assert_save_and_clear_invalidate_pending_plan(missing_clear)
    with pytest.raises(AssertionError, match="must occur together"):
        assert_save_and_clear_invalidate_pending_plan(wrong_key)
