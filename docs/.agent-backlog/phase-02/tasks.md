# Phase 2 tasks

Ordered; each task is one feature branch off `develop` (`feat/p02-<slug>`), squash-merged on green CI. Fill each Evidence section with actual command output. T1–T3 are independent after Phase 1 and may run in parallel (isolated worktrees).

## T1 — Scenario generator and perturbations

Seeded SRE-world generator with deterministic ground truth; all perturbation variants from objectives.md; counterfactual triplets (control / counterfactual / missing → UNKNOWN) emitted per scenario. Property test: same seed → identical world.

Verify: `uv run --group test pytest tests/unit -q -k "scenario or perturb"`
Evidence:

## T2 — Storage extension and usage accounting

Experiment/scenario/evaluation_results/model_invocations/artifacts tables, reproducibility fields, ADR key indexes; `telemetry/usage.py` (tokens, model calls, estimated cost, per-stage latency). No migration tooling: local SQLite files under `artifacts/` are disposable — schema changes mean deleting them (documented policy, see phase-01 context.md).

Verify: `uv run --group test pytest tests/unit -q -k "storage or usage"`
Evidence:

## T3 — Evals API investigation and dataset layer

Scout/code-analyst pass over pydantic-evals docs (API not yet investigated — see context.md), then `evals/datasets.py`: Datasets/Cases whose subject calls `harness.run` with trigger="eval". Findings from the investigation recorded at the top of the module or in this Evidence section.

Verify: `uv run --group test pytest tests/evals -q -k dataset`
Evidence:

## T4 — Deterministic evaluators (depends: T1, T3)

All nine evaluator families from objectives.md, driven by scenario ground truth.

Verify: `uv run --group test pytest tests/evals -q -k evaluator`
Evidence:

## T5 — Statistics and reports (depends: T2, T4)

`statistics.py` (paired deltas, McNemar, bootstrap CIs, permutation tests, pseudo-replication grouping) and `reports.py` (Polars over Parquet; absolute result + effect size + CI + cost delta + latency delta). Unit-test statistics against hand-computed small cases.

Verify: `uv run --group test pytest tests/unit tests/evals -q -k "stat or report"`
Evidence:

## T6 — RecordedHost and capability additions (depends: T2)

`recorded.py` replaying AgentResult fixtures; `validate_claims.py`; `run_evaluation.py` orchestrating dataset → paired runs → evaluators → persisted evaluation_results.

Verify: `uv run --group test pytest tests/capabilities -q`
Evidence:

## T7 — ClaudeCodeHost adapter (depends: T6)

Verify installed `claude` CLI headless/structured-output flags first (context.md "Not investigated"); AnyIO subprocess adapter with Pydantic-validated boundary, timing, usage metadata capture (or documented estimation). Contract tests on recorded transcripts only.

Verify: `uv run --group test pytest tests/unit tests/capabilities -q -k claude`
Evidence:

## T8 — CLI eval / compare / replay (depends: T5, T6)

`credent eval <experiment>` (RecordedHost default, `--host claude-code` for live), `credent compare baseline belief-state`, `credent replay <run-id>`. Data trees `evals/{datasets,scenarios,expected}/` committed (`artifacts/` is already gitignored since bootstrap).

Verify: `uv run credent eval <experiment>` (recorded) then `uv run credent compare baseline belief-state`
Evidence:

## T9 — Regression seeds and integration suite (depends: T8)

`tests/regression/` with named scenarios (`stale-codeowners-001`, `false-premise-004`, `missing-evidence-012` style) running through RecordedHost; `tests/integration/` covering eval → persist → compare → replay round-trip; same-seed determinism test.

Verify: `uv run --group test pytest tests/regression tests/integration -q`
Evidence:

## T10 — Live smoke run and phase exit (depends: T7, T8, T9)

ONE small live ClaudeCodeHost experiment; record its transcript as a RecordedHost fixture; capture cost/latency into the compare report. Then all six exit criteria from objectives.md with outputs recorded.

Verify: `./check.sh` plus objectives.md exit commands 1–5
Evidence:
