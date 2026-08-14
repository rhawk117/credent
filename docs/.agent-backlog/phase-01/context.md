# Phase 1 context

Read `docs/.agent-backlog/README.md` first (decision log, environment facts). This file adds only what Phase 1 depends on.

## Contracts to implement exactly (from docs/ADR.md)

These are copied from the ADR so you do not have to re-derive them; if the ADR text differs, the ADR wins for signatures, this file wins for scope.

- Capability protocol (ADR "Runtime Abstractions"): generic over input/output, single method `async def execute(self, input, context: ExecutionContext) -> output`.
- `Harness.run(self, capability: str, input: object, context: ExecutionContext) -> object`. The public contract exposes no Claude Code-, Copilot-, or model-provider-specific concepts.
- `ExecutionContext(BaseModel)`: `invocation_id: str`, `trigger: str`, `actor: str | None = None`, `correlation_id: str | None = None`, `parent_run_id: str | None = None`, `metadata: dict[str, object] = {}`. Trigger values in Phase 1: `"cli"`, `"eval"` reserved for Phase 2, hook/schedule triggers for Phase 3.
- `Observation`: id, subject, predicate, value, source_id, source_revision (optional), confidence (0.0–1.0).
- `Belief`: id, subject, predicate, value (`str | None`), status, confidence, plus `supporting_observation_ids`, `contradicting_observation_ids`, `derived_from_belief_ids` as tuples.
- `AgentHost` protocol: `name: str`, `async def invoke(self, request: AgentInvocation) -> AgentResult`. Adapters normalize only: process invocation, stdin/stdout, exit status, session/run ids, structured output, timing, usage metadata, trace correlation.
- `AgentInvocation` and `AgentResult` are named but not field-specified in the ADR — pin them here so Phase 2's real adapters inherit a stable shape. AgentInvocation: `id`, `prompt: str | None`, `payload: dict[str, object]`, `timeout_s: float | None`, `correlation_id: str | None`, `metadata: dict[str, object]`. AgentResult: `invocation_id`, `exit_code: int`, `structured_output: dict[str, object] | None`, `raw_stdout: str`, `session_id: str | None`, `run_id: str | None`, `started_at`, `ended_at`, `usage: Usage | None` (input_tokens, output_tokens, model_calls — all optional). T5 may refine field types, but Phase 2 must not break names.

## Reconciliation semantics (deterministic, no model calls)

- Newer or more authoritative evidence supersedes stale evidence; the superseded belief keeps its lineage.
- Incompatible observations of equal authority produce `CONTRADICTED` — an unresolved state, not a coin flip.
- Missing required evidence produces `UNKNOWN`, and `UNKNOWN` never carries a committed value (enforce in the model: invalid states unrepresentable where possible).
- Removing/changing a supporting observation invalidates dependent derived beliefs.

Hypothesis invariants that MUST hold (ADR "Property-Based Tests"): reconciliation is order-independent over input permutations; irrelevant evidence does not mutate state; superseded evidence invalidates dependent beliefs; provenance references always resolve; UNKNOWN carries no value. (The sixth ADR invariant — dispatch mechanism does not change capability semantics — lands in Phase 3 when multiple dispatchers exist.)

## Structured host boundary

FakeHost returns canned structured JSON of the ADR "Structured Agent Contracts" shape: `{"observations": [...], "unknowns": [...], "contradictions": [...]}`. Pydantic validates this before any state mutation — the validation failure path is a Phase 1 test case, not an afterthought.

## Constraints and ruled-out approaches

- No LangGraph/DSPy/Pydantic AI — pipelines are ordinary Python composition (ADR "Pipeline Orchestration").
- No resident daemon, no scheduler work at all in this phase.
- `domain/` imports nothing host-specific — no hosts, CLI, storage, telemetry, or Phoenix imports.
- SQLite via SQLAlchemy; database path comes from the `CREDENT_DB` env var, default `artifacts/credent.sqlite` (`artifacts/` is gitignored). No migration tooling in the MVP: local SQLite files are disposable — delete them when the schema changes. Parquet/Polars are Phase 2 concerns.
- Test packages need `__init__.py` files (`tests/`, `tests/unit/`, `tests/capabilities/`): the ruff config enforces INP001 (no implicit namespace packages) and has no per-file ignore for tests.
- Do not build eval/compare/replay CLI commands, real host adapters, scenario generation, or usage accounting — all Phase 2. Do not build hook or task modules — Phase 3.
- CLI stays a thin dispatcher (ADR "CLI"): construct ExecutionContext with trigger="cli", call `harness.run` via `anyio.run`.

## Established facts

- The venv resolves and all runtime deps import on Python 3.14.6 (verified 2026-08-13; arize-phoenix emits a harmless SyntaxWarning on import — ignore it). Re-verified 2026-08-14: `uv run python -c "import sys; print(sys.version)"` → `3.14.6`; installed versions pydantic 2.13.4, sqlalchemy 2.0.52, typer 0.27.1, rich 15.0.0, anyio 4.14.2, arize-phoenix 20.2.0, openinference-instrumentation 0.1.57, hypothesis 6.165.6, pytest-asyncio 1.4.0.
- Ruff config is strict (see `.ruff.toml`: 90-col, single quotes, many rule families); ty runs with `error-on-warning`. Run `./format.sh` before committing to avoid lint churn; pre-commit runs ruff+ty on commit.
- INP001 detail confirmed (2026-08-14, read `.ruff.toml`): `"INP"` is in `[lint] select` and `[lint.per-file-ignores]` is empty — tests need `__init__.py` as context above states. `S101` is in the global `ignore` list, so bare `assert` in tests is fine without per-file exemptions.
- `[project.scripts]` currently points at a stub `credent:main` (re-verified 2026-08-14 in `pyproject.toml`); repointing it to the Typer app is part of the CLI task.
- pytest-asyncio is installed; configure `asyncio_mode = "auto"` (or explicit markers) in pyproject when the first async test lands. As of 2026-08-14 `pyproject.toml` has no `[tool.pytest.ini_options]` section at all — T1 creates it.
- `src/credent/` contains only `__init__.py` and `tests/` does not exist yet (verified 2026-08-14, `ls`); `check.sh` skips pytest until `tests/` exists, and `./check.sh` passes green on the current clean checkout.
- T8 span-shape anchors (verified 2026-08-14 against the installed packages, so "exportable later without rework" has a concrete target): OpenInference marks a span's kind via the attribute key `openinference.span.kind` with enum values TOOL, CHAIN, LLM, RETRIEVER, EMBEDDING, AGENT, RERANKER, UNKNOWN, GUARDRAIL, EVALUATOR, PROMPT (`openinference.semconv.trace.OpenInferenceSpanKindValues`, openinference-semantic-conventions 0.1.32). The underlying OTel `ReadableSpan` (opentelemetry-sdk 1.44.0, already in the venv via phoenix) carries `name`, `context` (trace/span ids), `parent`, `start_time`, `end_time`, `attributes`, `status`, `kind`. A local span record with name, ids, parent id, start/end, status, and a string kind plus free-form attributes maps onto this without rework.

## Not investigated

- pydantic-evals API surface (Phase 2 will need it; nothing in Phase 1 imports it). Left open 2026-08-14: not a Phase 1 dependency.
- Exact Phoenix span *ingestion/export* path (OTLP endpoint, project naming, exporter wiring) — Phase 3. The span *shape* facts Phase 1 needs are now in Established facts above.
