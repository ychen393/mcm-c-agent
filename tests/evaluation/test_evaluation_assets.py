import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation"


def test_task_cases_match_schema_and_split_counts():
    schema = json.loads((EVAL / "schemas/evaluation_case.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    cases = [
        json.loads(line)
        for line in (EVAL / "task_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    errors = [(case.get("case_id"), list(validator.iter_errors(case))) for case in cases]
    assert len(cases) == 15
    assert all(not issues for _, issues in errors), errors
    assert Counter(case["split"] for case in cases) == {
        "dev": 8, "holdout": 4, "regression": 3
    }
    assert len({case["case_id"] for case in cases}) == len(cases)


def test_citation_and_recovery_fixture_counts():
    citations = [
        json.loads(line)
        for line in (EVAL / "citation_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    recovery = json.loads((EVAL / "recovery_cases.json").read_text(encoding="utf-8"))
    assert len(citations) == 10
    assert len({case["case_id"] for case in citations}) == 10
    assert len(recovery["cases"]) == 3


def test_eda_golden_statistics_match_fixtures():
    golden = json.loads((EVAL / "fixtures/eda/golden_stats.json").read_text(encoding="utf-8"))

    def read_csv(name):
        with (EVAL / "fixtures/eda" / name).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    missing = read_csv("missingness.csv")
    assert len(missing) == golden["missingness.csv"]["rows"]
    assert len(missing[0]) == golden["missingness.csv"]["columns"]
    for column, expected in golden["missingness.csv"]["missing_by_column"].items():
        assert sum(row[column] == "" for row in missing) == expected

    outliers = read_csv("outliers.csv")
    rentals = [int(row["rentals"]) for row in outliers]
    temps = [int(row["temperature_c"]) for row in outliers]
    assert len(outliers) == golden["outliers.csv"]["rows"]
    assert min(rentals) == golden["outliers.csv"]["rentals_min"]
    assert max(rentals) == golden["outliers.csv"]["rentals_max"]
    assert min(temps) == golden["outliers.csv"]["temperature_min"]
    assert max(temps) == golden["outliers.csv"]["temperature_max"]

    trend = read_csv("time_trend.csv")
    values = [int(row["rentals"]) for row in trend]
    assert len(trend) == golden["time_trend.csv"]["rows"]
    assert min(values) == golden["time_trend.csv"]["rentals_min"]
    assert max(values) == golden["time_trend.csv"]["rentals_max"]
    assert sum(values) / len(values) == golden["time_trend.csv"]["rentals_mean"]
    assert len({row["date"] for row in trend}) == golden["time_trend.csv"]["date_unique"]

    categorical = read_csv("categorical.csv")
    assert len(categorical) == golden["categorical.csv"]["rows"]
    assert len({row["weather"] for row in categorical}) == golden["categorical.csv"]["weather_categories"]
    assert len({row["day_type"] for row in categorical}) == golden["categorical.csv"]["day_type_categories"]

    stations = read_csv("joins_stations.csv")
    daily = read_csv("joins_daily.csv")
    station_ids = {row["station_id"] for row in stations}
    assert len(daily) == golden["joins"]["left_rows"]
    assert len(stations) == golden["joins"]["right_rows"]
    assert sum(row["station_id"] not in station_ids for row in daily) == golden["joins"]["unmatched_station_ids"]
    assert len(daily) == golden["joins"]["expected_join_rows"]


def test_visual_eda_chart_planning_cases_match_schema_and_fixture_hashes():
    schema = json.loads(
        (EVAL / "schemas/evaluation_case.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    cases = [
        json.loads(line)
        for line in (EVAL / "chart_planning_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(cases) == 6
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert all(case["suite"] == "eda" for case in cases)

    for case in cases:
        errors = list(validator.iter_errors(case))
        assert not errors, (case["case_id"], errors)
        for fixture_ref in case.get("fixture_refs", []):
            fixture_path, expected_hash = fixture_ref.split("#sha256=", 1)
            fixture_bytes = (ROOT / fixture_path).read_bytes()
            assert hashlib.sha256(fixture_bytes).hexdigest() == expected_hash, case["case_id"]

    assert {case["split"] for case in cases} == {"dev", "holdout", "regression"}
