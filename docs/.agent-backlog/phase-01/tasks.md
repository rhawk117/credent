# Phase 1 tasks

Ordered; each task is one feature branch off `develop` (`feat/p01-<slug>`), squash-merged on green CI. The executing agent fills each Evidence section with actual command output before the task is considered done. Tasks 2–3 are independent after task 1 and may run in parallel (isolated worktrees); task 4 depends on task 2; tasks 5+ depend on their predecessors as noted.

## T1 — Package skeleton and tooling wiring

Create the `src/credent/` subpackage layout for this phase (harness, domain, storage, hosts, pipelines, capabilities, dispatch, scenarios, telemetry — empty `__init__.py`s), `tests/`, `tests/unit/`, `tests/capabilities/` (each with `__init__.py` — see context.md on INP001), pytest/pytest-asyncio configuration in pyproject, and one real smoke test (e.g. `credent` imports and exposes `__version__`) — check.sh runs pytest once `tests/` exists, and pytest fails on an empty suite (exit 5).

Verify: `./check.sh`
Evidence:

## T2 — Domain models and reconciliation (depends: T1)

BeliefStatus, Observation, Belief, deterministic reconciliation (supersession, contradiction, UNKNOWN-carries-no-value), provenance lineage resolution, state transitions. Unit tests plus the Hypothesis invariants from context.md.

Verify: `uv run --group test pytest tests/unit -q -k "domain or belief or reconcil or provenance"`
Evidence:

## T3 — Harness core (depends: T1)

ExecutionContext, capability registry, `Harness.run`, dispatch plumbing. Unit tests: registration, lookup failure, context propagation.

Verify: `uv run --group test pytest tests/unit -q -k harness`
Evidence:

## T4 — Storage: run-graph subset (depends: T2)

SQLAlchemy models + repositories for capabilities, runs, invocations, sources, observations, beliefs, belief_support, belief_contradictions, state_transitions. T2 owns all domain types (including BeliefStatus) — storage maps them to rows and never redefines them. Round-trip tests against a temp SQLite file.

Verify: `uv run --group test pytest tests/unit -q -k storage`
Evidence:

## T5 — Host protocol and FakeHost (depends: T2)

AgentHost protocol, AgentInvocation/AgentResult models, FakeHost returning canned structured JSON; Pydantic boundary validation including the malformed-output rejection path.

Verify: `uv run --group test pytest tests/unit -q -k host`
Evidence:

## T6 — Pipelines (depends: T2, T5)

`baseline.py` and `belief_state.py` as ordinary async composition. Tests exercise both through FakeHost.

Verify: `uv run --group test pytest tests/unit -q -k pipeline`
Evidence:

## T7 — Capabilities and contract tests (depends: T3, T4, T6)

`reason-from-evidence`, `reconcile-beliefs`, `inspect-belief-state` registered and executable via `harness.run`. This task also lands the minimal stale-owner fixture in `scenarios/fixtures.py` (old README: platform-team; current CODEOWNERS: payments-team; deterministic ground truth) — the contract tests and T9's CLI default both consume it. Contract tests per capability: input → expected structured output → expected side effects (persisted rows). Expected-trace-shape assertions are deferred to Phase 3 (dispatch equivalence needs hook/schedule dispatchers) — note this in the test file.

Verify: `uv run --group test pytest tests/capabilities -q`
Evidence:

## T8 — Minimal span capture (depends: T7)

Local span records (capability → pipeline stage → host call) persisted with the run. No Phoenix. Shape must be exportable later without rework.

Verify: `uv run --group test pytest tests/unit -q -k "span or trace"`
Evidence:

## T9 — CLI: capability list / run / inspect (depends: T7)

Typer app in `dispatch/cli.py`, `[project.scripts]` repointed. `run` reads evidence/input from an optional `--input` JSON file, defaulting to the T7 stale-owner fixture so the exit-criteria command runs verbatim with no arguments; `inspect` renders belief state + spans for a run-id via Rich.

Verify: `uv run credent capability list && uv run credent run reason-from-evidence && uv run credent inspect <run-id>`
Evidence:

## T10 — Walking-skeleton exit (depends: T8, T9)

End-to-end test on the T7 stale-owner fixture: both pipelines on identical fixture evidence; belief-state output shows payments-team with the superseded platform-team belief in lineage.

Verify: `./check.sh` plus the three exit commands from objectives.md, outputs recorded
Evidence:
