"""Guard against API Settings revision argument drift in the Streamlit page."""
import ast
from pathlib import Path


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
        revision = call.args[-1]
        assert isinstance(revision, ast.Call)
        assert isinstance(revision.func, ast.Attribute)
        assert revision.func.attr == "get"
