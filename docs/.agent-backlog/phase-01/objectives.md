# Phase 1 — Walking skeleton

## Goal

One capability runs end-to-end through every load-bearing seam the ADR defines: CLI dispatch → `harness.run` → capability → pipeline → host adapter → deterministic domain reconciliation → SQLite persistence → inspection. No live models — FakeHost makes the whole slice runnable and testable from day one. At phase exit the project's core loop (same evidence, two reasoning architectures, inspectable belief state) is demonstrable, which is the reason this system exists.

## Module ownership

This phase creates and owns:

- `src/credent/harness/` — COMPLETE in this phase: `context.py` (ExecutionContext: invocation_id, trigger, actor, correlation_id, parent_run_id, metadata), `registry.py` (named capability registration), `runtime.py` (`Harness.run(capability, input, context)`), `dispatch.py`. The Capability protocol: `async def execute(self, input, context) -> output`.
- `src/credent/domain/` — minimal but real: `beliefs.py` (BeliefStatus StrEnum: OBSERVED, RETRIEVED, INFERRED, ASSUMED, CONTRADICTED, UNKNOWN; Belief model), `observations.py` (Observation model), `transitions.py` (deterministic reconciliation: supersession, contradiction, UNKNOWN), `provenance.py` (lineage resolution).
- `src/credent/storage/` — the run-graph subset ONLY: tables `capabilities`, `runs`, `invocations`, `sources`, `observations`, `beliefs`, `belief_support`, `belief_contradictions`, `state_transitions`. Phase 2 extends this schema; do not build experiment/eval tables now.
- `src/credent/hosts/` — `base.py` (AgentHost protocol: `name`, `async invoke(AgentInvocation) -> AgentResult`) and `fake.py`. Real hosts come in Phase 2.
- `src/credent/pipelines/` — thin `baseline.py` (one host call) and `belief_state.py` (extract → reconcile → reason → render).
- `src/credent/capabilities/` — `reason_from_evidence.py`, `reconcile_beliefs.py`, `inspect_belief_state.py` (this third file is an intentional addition beyond the ADR Source Layout — decision log #5).
- `src/credent/dispatch/cli.py` — Typer app with exactly `capability list`, `run`, `inspect`. Phase 2 adds eval/compare/replay; Phase 3 adds hook/skill/schedule commands. Repoint `[project.scripts] credent` here.
- `src/credent/scenarios/fixtures.py` — one hand-authored stale-owner scenario (old README says platform-team owns payments-api; current CODEOWNERS says payments-team) with deterministic ground truth. The full generator is Phase 2.
- `src/credent/telemetry/tracing.py` — minimal local span capture persisted with the run. Phoenix/OpenInference export is Phase 3; design span data so export is an addition, not a rewrite.
- `tests/unit/`, `tests/capabilities/` — including Hypothesis property tests.

## Exit criteria

All commands run from a clean checkout and their output is recorded as evidence:

1. `uv run credent capability list` shows the three registered capabilities.
2. `uv run credent run reason-from-evidence` (no arguments — the stale-owner fixture is the default input) executes BOTH pipelines through FakeHost, validates structured host output with Pydantic before any state mutation, and persists runs, observations, beliefs, and state transitions to SQLite.
3. `uv run credent inspect <run-id>` renders the belief state showing the superseded belief and its provenance.
4. `./check.sh` green (ruff, ty, pytest — no live models anywhere in tests).

## MVP checklist coverage

Completes item 1 (generic capability execution interface). Seeds items 2 (both pipelines exist, FakeHost-only), 6 (CLI invoke + inspect), 7 (runs persisted), 10 (stage-shaped spans persisted). Those items finish in Phases 2–3.
