# Phase 3 context

Read `docs/.agent-backlog/README.md` first — its "Host hook research" section is the factual basis for this phase (lifecycle event mapping, payload compatibility, config locations, exit-code semantics, source URLs). Phases 1–2 must be complete.

## Hook payload contracts (researched 2026-08-13, official docs)

Common stdin fields both hosts deliver in Claude-compatible mode: `hook_event_name`, `session_id`, `cwd`, plus event-specific fields. Key per-event facts:

- SessionStart: Claude adds `transcript_path`, matcher on how started (startup/resume/clear/compact/fork); Copilot adds `source` (startup/resume/new) and is the only Copilot event supporting auto-submitted prompt hooks.
- SessionEnd: Claude has `exit_reason` (clear/resume/logout/prompt_input_exit/other); Copilot has `reason` (complete/error/abort/timeout/user_exit) — normalize these to one enum in HookEvent; keep the raw value in payload.
- Stop/agentStop: fires when the main agent finishes a turn. Both support block-to-continue (Claude: exit 2; Copilot: `{"decision": "block"}` with an 8-consecutive-block runaway guard). The credent hooks must NEVER block — they observe, persist, and schedule only (ADR: hooks avoid extending the critical path).
- Exit-code discipline: exit 0 always; report harness failures inside the hook script (log + persist) rather than via exit codes, because Copilot treats non-zero as fail-open warning and Claude shows stderr — neither should ever see a crash from us.
- Timeouts: Copilot default 30s fail-open; Claude command default 600s but SessionEnd hooks get a ~1.5s shared budget — sessionEnd work must be a fast enqueue (persist TaskSpec rows), never actual computation.

Fixtures for `tests/dispatch/` encode both hosts' documented payload shapes for all three lifecycle events; the normalizer is tested against both.

## Scheduling semantics (ADR "Task Scheduling Contract" + "Lifecycle Hook and Task Scheduling Tests")

- A scheduled task is data: task_id, capability, input, created_by, run_at/trigger, correlation_id, status.
- No resident process. If no wall-clock scheduler exists, due tasks persist in SQLite and sessionStart reconciles opportunistically.
- Tests use controlled clocks and fake scheduler adapters; no test may sleep for wall-clock time or require a daemon. Duplicate-scheduling protection and malformed-TaskSpec rejection are required test cases.
- Capability logic must not know how it was delivered — the cross-dispatcher contract tests enforce this (same capability through CLI, hook, and schedule dispatch → semantically equivalent execution; this also discharges the trace-shape and dispatch-equivalence assertions deferred from Phase 1's contract tests and the Hypothesis invariant "dispatch mechanism does not change capability semantics").

## Skills (ADR "Skills" + "Skill Tests")

`skills/belief-validation/SKILL.md` must specify: triggering conditions, capability name (`validate-claims`), required inputs, interpretation rules (UNKNOWN is a valid result; surface unresolved contradictions), expected failure behavior. `credent skill validate` checks metadata, capability existence, and input-schema match. The harness records the skill hash per invocation when known.

## Constraints and ruled-out approaches

- Hooks contain zero business logic — no reconciliation, no prompts, no retrieval, no evaluation (ADR "Hooks"). Belief logic is never tested through hook modules.
- docs-query skill and capability: deferred (decision log #3). post_tool/pre_completion hooks: deferred (decision log #4).
- Copilot live validation: deferred until the CLI is installed (decision log #6); the adapter and manifests are still built and fixture-tested now.
- Phoenix runs on demand (`uv run phoenix serve` or the library launcher) for exit criterion 5 — it is not a test dependency and CI never starts it.
- The `hooksmith` skill is available in this environment for authoring the `.claude/settings.json` hooks block — use it for the Claude manifest task.

## Not investigated

- OpenInference span-attribute conventions for non-LLM spans — investigate before writing the exporter (scout pass over openinference-instrumentation docs).
- Whether the installed `claude` version's SessionEnd hook budget matches the documented ~1.5s — measure during the live round-trip task and record the number in Evidence.
