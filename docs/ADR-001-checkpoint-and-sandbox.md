# ADR-001: Durable Workflow Checkpointing and Isolated Python Execution

- Status: Accepted direction; implementation spike required before M2
- Decision date: 2026-11-04
- Related PRD: v1.1, sections 21, 22, 24 and 26

## Context
MCM C research runs are long-lived and may include parallel LLM calls, data processing, human approval pauses, and expensive experiments. A process restart or provider timeout must not erase completed work. Agent-generated Python is untrusted and must never execute inside the Streamlit or orchestration process.

The M0 scaffold uses LangGraph, PostgreSQL/pgvector, Streamlit and local artifact storage. Its current acceptance checklist explicitly says persistent LangGraph checkpointing is not active.

## Decision A — Workflow persistence

Adopt LangGraph PostgreSQL checkpointer using the supported langgraph-checkpoint-postgres integration (PostgresSaver or its async equivalent, selected according to the app execution model).

### Identity and state contract
- thread_id = project_id for the durable project workflow thread.
- Each workflow invocation receives a unique application-level run_id.
- Store workflow type, run status, initiating action, timestamps and idempotency metadata in application tables. Checkpoint rows are not the only job registry.
- Use a stable checkpoint namespace for the research workflow; separate workflow families with explicit namespaces.
- Permit one active mutating research run per project in the first demo release; reject or queue conflicting concurrent runs.
- Store compact structured state and artifact references in checkpoints. Large files, dataframes, plots, LaTeX bundles and PDFs live in artifact storage and are referenced by URI, SHA-256, size and schema/version metadata.

### Recovery contract
- Persist after each meaningful node boundary and before/after human approval interrupts.
- On restart, show interrupted/runnable runs and allow explicit resume from the last durable checkpoint.
- A recovery scan reconciles application run records with checkpoint metadata; PostgreSQL checkpoint persistence alone is not a background job scheduler.
- Every side-effecting node declares an idempotency policy. Use stable idempotency keys for artifact writes and exports; verify existing artifact hashes before redoing work.
- Record state_schema_version and artifact_schema_version; provide migration or explicit incompatibility handling.
- Configure database backups and a documented local restore procedure.

### Security and operations
- Run the checkpointer with a least-privilege database role, not the database superuser.
- Initialize checkpointer tables through its documented setup/migration step.
- Enable strict/safe MessagePack deserialization or an explicit allowlist of permitted types; never enable unrestricted deserialization.
- Keep secrets out of checkpoint payloads and logs.
- Pin compatible package versions after the implementation spike.

### Consequences
Benefits: durable human-in-the-loop pauses, restart recovery, visible run history, and a natural fit with existing PostgreSQL.
Costs: schema lifecycle, connection management, serialization compatibility, and recovery/idempotency logic become application responsibilities.

## Decision B — Python execution isolation

Adopt one short-lived isolated container per untrusted code execution. Docker is the initial local execution backend.

- On Linux hosts, prefer Docker Engine rootless mode where supported.
- On Windows development machines, use Docker Desktop with its WSL2/Linux VM boundary; do not assume the Windows host itself runs a rootless Linux daemon. Validate the actual engine mode in the spike.
- Run as a non-root container user; never use privileged mode.
- Set read-only root filesystem, drop Linux capabilities, enable no-new-privileges, and apply CPU, memory, PID, wall-clock, disk and output-size limits.
- Default to network=none. Network access, if ever required, must go through a separately authorized fetch tool.
- Mount only task-specific input directories read-only and a dedicated output directory writable. Never mount the home directory, Docker socket, source repository, credentials, or broad host paths.
- Do not pass LLM API keys, database credentials, or host secrets into the sandbox.
- Use a pinned image digest and controlled dependency set. Record code hash, image digest, dependency versions, arguments, random seed, exit code, stdout/stderr and produced artifact hashes.
- Always remove containers and temporary workspaces after completion, including failure and timeout paths.

### Execution API
The orchestrator submits an immutable request containing run_id, task_id, code artifact reference, input artifact references, resource profile and deterministic seed. The worker returns typed status, exit code, logs, resource usage and output artifact references. The orchestrator validates output paths and sizes before registering artifacts.

### Consequences
Benefits: clear trust boundary, reproducible environments, resource caps and reduced host exposure.
Costs: Docker availability is a runtime prerequisite; container startup and dependency images add latency. Windows/WSL2 file-mount and permission behavior needs a real integration test.

## Required implementation spike before M2
1. Start PostgreSQL and create the least-privilege checkpoint role.
2. Run a tiny LangGraph graph with PostgresSaver; verify checkpoint writes and reads.
3. Pause at an interrupt, kill the app process, restart it, and resume from the same thread_id.
4. Inject an LLM timeout and a tool exception; verify recovery and no duplicate side effects.
5. Run a sandbox smoke test with network disabled, read-only input, bounded writable output, non-root identity, timeout and memory/CPU limits.
6. Run the sandbox test in the actual Windows + Docker Desktop/WSL2 environment.
7. Document package versions, startup commands, limitations and measured overhead.

Exit criteria: all recovery and sandbox tests pass; no credentials are exposed; no code executes in the application process. If rootless mode is unavailable in the target Windows setup, retain container isolation controls and document the Docker Desktop VM boundary rather than claiming rootless operation.

## References
- LangGraph PostgreSQL checkpoint integration: https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-postgres
- Docker Rootless mode: https://docs.docker.com/engine/security/rootless/
- COMAP 2027 rules and AI guidance: https://contest.comap.org/undergraduate/contests/mcm/instructions.php
