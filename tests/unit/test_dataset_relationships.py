"""Offline MCM MVP relationship and preview safety regression tests."""
import pytest
import pandas as pd

from tools.dataset_bundle import build_dataset_bundle
from tools.dataset_relationships import (
    discover_relationships, inspect_pair, preview_join,
)


def bundle(*files):
    return build_dataset_bundle(list(files), project_id="mvp-demo")


def ids(b):
    return [ref.dataset_id for ref in b.datasets]


def test_sales_weather_safe_one_to_one_preview():
    b = bundle(
        ("sales.csv", b"date,value\n2026-01-01,10\n2026-01-02,20\n2026-01-03,30\n"),
        ("weather.csv", b"date,value\n2026-01-01,5\n2026-01-02,6\n2026-01-03,7\n"),
    )
    a, c = ids(b)
    proposals = discover_relationships(b)
    assert any(x.left_key == "date" and x.relationship == "1:1" for x in proposals)
    inspect, result = preview_join(b, a, c, "date", "date")
    assert inspect.overlap == 3
    assert result.shape[0] == 3
    assert "value_left" in result.columns and "value_right" in result.columns
    assert result["value_left"].tolist() == [10, 20, 30]


def test_many_to_many_does_not_allocate_join():
    b = bundle(
        ("population.csv", b"region,population\nEast,10\nEast,11\nWest,15\n"),
        ("outcome.csv", b"region,outcome\nEast,1\nEast,2\nNorth,3\n"),
    )
    a, c = ids(b)
    found = inspect_pair(b, a, c, "region", "region")
    assert found.relationship == "N:M"
    assert not found.safe_to_preview
    assert found.left_duplicates == found.right_duplicates == 1
    with pytest.raises(ValueError, match="Many-to-many"):
        preview_join(b, a, c, "region", "region")


def test_nonoverlapping_datasets_abstain():
    b = bundle(("sales.csv", b"region,value\nWest,1\n"), ("weather.csv", b"station,temp\nA,2\n"))
    assert discover_relationships(b) == []
    a, c = ids(b)
    with pytest.raises(ValueError, match="No matching"):
        preview_join(b, a, c, "region", "station")


def test_daily_monthly_mismatch_not_silently_aligned():
    b = bundle(
        ("daily.csv", b"date,price\n2026-01-01,10\n2026-01-02,11\n2026-01-03,12\n2026-02-01,15\n"),
        ("monthly.csv", b"date,index\n2026-01-01,100\n2026-02-01,101\n2026-03-01,102\n"),
    )
    a, c = ids(b)
    row = inspect_pair(b, a, c, "date", "date")
    assert not row.safe_to_preview
    assert "frequenc" in row.reason
    with pytest.raises(ValueError, match="frequenc"):
        preview_join(b, a, c, "date", "date")


def test_invalid_strategy_key_limit_and_identity():
    b = bundle(("a.csv", b"id,v\n1,10\n2,20\n"), ("b.csv", b"id,q\n1,100\n2,200\n"))
    a, c = ids(b)
    with pytest.raises(ValueError, match="Only inner"):
        preview_join(b, a, c, "id", "id", how="outer")
    with pytest.raises(ValueError, match="Unknown key"):
        preview_join(b, a, c, "password", "id")
    with pytest.raises(ValueError, match="safe preview"):
        preview_join(b, a, c, "id", "id", max_rows=0)
    with pytest.raises(ValueError, match="exceeds"):
        preview_join(b, a, c, "id", "id", max_rows=1)
    with pytest.raises(ValueError, match="different datasets"):
        inspect_pair(b, a, a, "id", "id")


def test_left_with_null_key_is_rejected():
    b = bundle(
        ("a.csv", b"id,val\n1,10\n,20\n"),
        ("b.csv", b"id,other\n1,100\n2,200\n"),
    )
    a, c = ids(b)
    with pytest.raises(ValueError, match="null keys"):
        preview_join(b, a, c, "id", "id", how="left")


def test_ui_includes_explicit_preview_without_model_call():
    import ast
    from pathlib import Path
    source = Path("app/main.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert "Preview join (no data saved)" in source
    assert "discover_relationships(bundle)" in source
    assert "preview_join(" in source
    assert "No defensible shared key found" in source
