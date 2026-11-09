"""Verify machine-readable MCM development agent/task inventory contracts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "docs/agents/agent-registry.json"
TASKS = ROOT / "docs/agents/task-registry.json"
ALLOWED = {"PARTIAL","AWAIT_INDEPENDENT_REVIEW","CONFIG_ONLY","LATEST_HEAD_UNVERIFIED","BLOCKED","PROPOSED","OWNER_DECISION_REQUIRED"}


def validate(agent_path=AGENTS, task_path=TASKS):
    agents = json.loads(Path(agent_path).read_text(encoding="utf-8"))
    tasks = json.loads(Path(task_path).read_text(encoding="utf-8"))
    errors = []
    roles = agents.get("roles", [])
    ids = [r.get("id") for r in roles]
    if len(ids) != len(set(ids)) or not ids:
        errors.append("Role ids must be unique and non-empty")
    if agents.get("cost_policy", {}).get("extra_billed_usd") != 50:
        errors.append("Project additional billed spending must remain capped at USD 50")
    if agents.get("cost_policy", {}).get("autonomous_cloud_dispatch") is not False:
        errors.append("Cloud dispatch must remain disabled")
    if agents.get("cost_policy", {}).get("auto_merge") is not False:
        errors.append("Auto-merge must be disabled")
    for role in roles:
        if not role.get("responsibility") or not role.get("config") or not role.get("verification"):
            errors.append(f"Incomplete role {role.get('id')}")
    entries = tasks.get("entries", [])
    tids = [t.get("task_id") for t in entries]
    if not tids or len(tids) != len(set(tids)):
        errors.append("Task ids must be unique and non-empty")
    for t in entries:
        label = t.get("task_id")
        if t.get("role") not in ids or t.get("parent") not in ids:
            errors.append(f"Unknown role/parent in {label}")
        if t.get("status") not in ALLOWED:
            errors.append(f"Unrecognized status in {label}")
        if not t.get("evidence") or not all(
            isinstance(url, str) and url.startswith("https://github.com/")
            for url in t["evidence"]
        ):
            errors.append(f"Missing or non-GitHub evidence in {label}")
        session = t.get("session")
        if session is not None and not session.startswith("https://cursor.com/agents/"):
            errors.append(f"Unrecognized session URL in {label}")
        if t.get("session_verified") == "not-launched" and session is not None:
            errors.append(f"Not-launched session must be null in {label}")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", type=Path, default=AGENTS)
    parser.add_argument("--tasks", type=Path, default=TASKS)
    args = parser.parse_args()
    errors = validate(args.agents, args.tasks)
    if errors:
        print("\n".join(errors))
        return 1
    print("Agent coordination registry contract: PASS (does not prove live execution)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
