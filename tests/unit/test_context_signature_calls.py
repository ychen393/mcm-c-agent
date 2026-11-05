"""Guard against API Settings revision argument drift in the Streamlit page."""
import ast
from pathlib import Path

from app.api_settings import SESSION_REVISION_KEY


def _is_st_session_state(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "session_state"
        and isinstance(node.value, ast.Name)
        and node.value.id == "st"
    )


def is_revision_lookup(node: ast.AST) -> bool:
    """True for st.session_state.get(SESSION_REVISION_KEY, 0), not an arbitrary get()."""
    if not isinstance(node, ast.Call) or node.keywords or len(node.args) != 2:
        return False
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "get":
        return False
    if not _is_st_session_state(func.value):
        return False
    key, default = node.args
    named_key = isinstance(key, ast.Name) and key.id == "SESSION_REVISION_KEY"
    literal_key = isinstance(key, ast.Constant) and key.value == SESSION_REVISION_KEY
    return (named_key or literal_key) and isinstance(default, ast.Constant) and default.value == 0


def _config_revision_argument(call: ast.Call, parameters: list[str]) -> ast.AST:
    keyword = next((item for item in call.keywords if item.arg == "config_revision"), None)
    if keyword is not None:
        return keyword.value
    revision_index = parameters.index("config_revision")
    assert len(call.args) > revision_index
    return call.args[revision_index]


def test_all_context_signature_calls_supply_config_revision():
    source = Path("app/main.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_context_signature"
    )
    parameters = [arg.arg for arg in function.args.args]
    assert parameters[-1] == "config_revision"
    calls = [
        node for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_context_signature"
    ]
    assert len(calls) == 2
    for call in calls:
        supplied = len(call.args) + len(call.keywords)
        assert supplied == len(parameters), (
            f"_context_signature expected {len(parameters)} arguments, found {supplied} "
            f"at line {call.lineno}"
        )
        revision = _config_revision_argument(call, parameters)
        assert is_revision_lookup(revision), (
            f"_context_signature config_revision at line {call.lineno} "
            "must look up SESSION_REVISION_KEY"
        )


def test_revision_lookup_rejects_wrong_session_key():
    wrong_key = ast.parse("st.session_state.get('other_revision', 0)").body[0]
    assert isinstance(wrong_key, ast.Expr)
    assert not is_revision_lookup(wrong_key.value)
    missing_default = ast.parse("st.session_state.get(SESSION_REVISION_KEY)").body[0]
    assert isinstance(missing_default, ast.Expr)
    assert not is_revision_lookup(missing_default.value)
