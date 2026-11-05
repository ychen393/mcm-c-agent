import ast
from pathlib import Path


def test_streamlit_app_has_valid_python_syntax():
    source = Path("app/main.py").read_text(encoding="utf-8")
    ast.parse(source, filename="app/main.py")
