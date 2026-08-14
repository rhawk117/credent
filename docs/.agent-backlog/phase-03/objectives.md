# Phase 3 — Delivery surfaces

## Goal

The harness becomes consumable from real agent sessions: lifecycle hooks dispatch capabilities, skills instruct agents, scheduled tasks survive between sessions without any resident daemon, the second host adapter proves the AgentHost contract stays narrow, and tracing exports the complete dispatch-to-result path to Phoenix. This lands last deliberately: divergent Claude/Copilot host semantics are the ADR's self-identified hardest unknown, and by now the CLI, persistence, and eval machinery exist to instrument and debug them.

## Module ownership

- `hooks/` (top level) — `session_start.py`, `session_end.py`, `agent_stop.py`: thin entry scripts (normalize event → ExecutionContext → select capability → `harness.run`). `post_tool.py`/`pre_completion.py` are deferred (decision log #4).
- `src/credent/dispatch/hooks.py` — typed HookEvent; ONE payload normalizer serving both hosts (Copilot manifests run in Claude-compatible payload mode — README hook research); malformed events rejected deterministically; harness failures surfaced without crashing the host session.
- `src/credent/dispatch/skills.py` — skill metadata validation: required fields, referenced capability exists, input schema matches; skill hash recorded per invocation.
- `src/credent/dispatch/tasks.py` — scheduled-task delivery into `harness.run` with trigger="scheduled-task".
- `src/credent/tasks/` — COMPLETE: `models.py` (TaskSpec: capability, input, correlation_id, trigger; TaskTrigger), `scheduler.py` (TaskScheduler protocol + SQLite-persisted implementation), `repository.py` (durable task store, reconciled opportunistically at sessionStart — NO resident daemon, NO wall-clock polling).
- `skills/belief-validation/SKILL.md` — the only MVP skill (docs-query deferred, decision log #3): when to invoke validate-claims, required inputs, UNKNOWN handling, contradiction surfacing.
- `src/credent/hosts/copilot_cli.py` — real adapter, contract-tested on documented payload fixtures; live validation deferred until Copilot CLI is installed (decision log #6).
- `src/credent/telemetry/tracing.py` — COMPLETE: Phoenix + OpenInference export of trigger → dispatch → capability → model call → state transition → evaluator, for hook-, schedule-, and CLI-triggered runs.
- `src/credent/storage/` — EXTENSION: `hook_invocations`, `schedule_invocations` tables; reproducibility record gains skill hash / hook revision / task trigger fields.
- `src/credent/dispatch/cli.py` — adds `hook test`, `skill validate`, `schedule list`.
- Host manifests: `.claude/settings.json` hooks block (SessionStart, SessionEnd, Stop) and `.github/hooks/credent.json` (Copilot, Claude-compatible event aliases) — both dispatch into the same `hooks/` entry scripts.
- `tests/dispatch/` — hook mapping, malformed-event rejection, failure surfacing; lifecycle/scheduling tests with controlled clocks and fake scheduler adapters (no sleeping, no daemon); cross-dispatcher contract tests proving CLI, hook, and schedule dispatch produce semantically equivalent capability execution (the deferred Phase 1 trace-shape assertions land here too).

## Exit criteria

1. `uv run credent hook test agent-stop` dispatches the mapped capability with trigger `hook:agent_stop` and correct correlation IDs.
2. Controlled-clock round-trip: a task scheduled at simulated sessionEnd is persisted, then reconciled and dispatched at a simulated sessionStart, correlation IDs preserved — proven in `tests/dispatch/` with a fake clock.
3. `uv run credent skill validate` passes against `skills/`.
4. One live Claude Code round-trip: with the manifests installed, a real session's Stop hook persists an observation/task that `credent schedule list` then shows.
5. Phoenix renders the complete dispatch-to-result trace for a hook-triggered and a CLI-triggered run of the same capability.
6. Cross-dispatcher contract tests green; `./check.sh` green.

## MVP checklist coverage

Completes items 3 (hooks dispatch capabilities), 4 (skills instruct agents), 5 (lifecycle-created scheduled tasks without a daemon), and finishes 6 (hook test / skill validate / schedule list) and 7 (all runs persisted and traceable incl. hook/schedule triggers). With Phase 2, all 10 items are done.
