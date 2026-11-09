import json
from pathlib import Path
from tools.validate_agent_registry import AGENTS, TASKS, validate


def test_registry_contract():
    assert validate() == []


def test_no_extra_cloud_or_auto_merge():
    policy = json.loads(AGENTS.read_text(encoding="utf-8"))["cost_policy"]
    assert policy["extra_billed_usd"] == 50
    assert policy["actual_spend_verified"] is False
    assert policy["auto_top_up_reported_disabled"] is True
    assert policy["autonomous_cloud_dispatch"] is False
    assert policy["auto_merge"] is False


def test_task_inventory_is_explicitly_not_live():
    data = json.loads(TASKS.read_text(encoding="utf-8"))
    assert data["mode"] == "bootstrap-inventory-not-live-sync"
    assert all("next_gate" in entry and "session_verified" in entry for entry in data["entries"])


def test_reject_missing_role_or_fake_session(tmp_path):
    agents = json.loads(AGENTS.read_text(encoding="utf-8"))
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    tasks["entries"][0]["role"] = "invented-agent"
    tasks["entries"][1]["session"] = "https://example.com/fake"
    tasks["entries"][2]["session"] = "https://cursor.com/agents/fake"
    p = tmp_path / "tasks.json"
    p.write_text(json.dumps(tasks), encoding="utf-8")
    errors = validate(AGENTS, p)
    assert any("Unknown role" in e for e in errors)
    assert any("Unrecognized session" in e for e in errors)
    assert any("Not-launched session" in e for e in errors)
