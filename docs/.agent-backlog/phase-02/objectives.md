# Phase 2 — Experiment engine

## Goal

Turn the Phase 1 skeleton into a measuring instrument: synthetic scenarios with deterministic ground truth and controlled perturbations, paired baseline-vs-belief-state evaluation through Pydantic Evals, real statistics, cost/latency accounting, and the first real host adapter. At phase exit the research hypothesis is measurable — deterministically in CI, and with real model economics from one live smoke run.

## Module ownership

- `src/credent/scenarios/` — COMPLETE: `generator.py` (seeded SRE/backend world: teams, services, repos, ownership records, deterministic ground truth), `perturbations.py` (clean, stale, contradictory, missing, duplicated, reordered, false-premise, irrelevant distractors, semantically similar distractors, conflicting authority, changed source revision, long unrelated history), `fixtures.py` extended.
- `src/credent/capabilities/` — adds `validate_claims.py`, `run_evaluation.py`.
- `src/credent/hosts/` — adds `recorded.py` (deterministic replayable subject for CI) and `claude_code.py` (AnyIO subprocess invocation, structured stdin/stdout JSON contract, exit status, timing, usage metadata when exposed).
- `src/credent/evals/` — COMPLETE: `datasets.py` (Pydantic Evals Datasets/Cases; the eval subject calls `harness.run`, never a model directly), `evaluators.py` (deterministic: answer accuracy, state accuracy, contradiction detection, stale-evidence resistance, abstention accuracy, false-premise rejection, provenance accuracy, counterfactual sensitivity, distractor robustness), `statistics.py` (paired deltas; McNemar for paired binary outcomes; bootstrap CIs; permutation tests; pseudo-replication guard — variants of one base scenario are not independent units), `reports.py` (Polars over Parquet exports; every report: absolute result, effect size, CI, cost delta, latency delta — never p-values alone).
- `src/credent/telemetry/usage.py` — input/output tokens, model-call counts, estimated cost, per-stage latency (p50/p95). Lands BEFORE the live smoke run so real runs are metered from the first one.
- `src/credent/storage/` — EXTENSION (stated growth, not scope creep): tables `experiments`, `scenarios`, `scenario_variants`, `evaluation_results`, `model_invocations`, `artifacts`; reproducibility fields (random_seed, evidence hash, prompt hash, code commit, host/model config); the ADR key indexes.
- `src/credent/dispatch/cli.py` — adds `eval`, `compare`, `replay`.
- Data trees: `evals/{datasets,scenarios,expected}/`, `artifacts/{runs,reports,traces}/` (gitignored outputs, committed inputs).
- `tests/integration/`, `tests/evals/`, `tests/regression/` — regression suite seeded with named scenarios (`stale-codeowners-001`, `false-premise-004` naming style).

## Exit criteria

1. `uv run credent eval <experiment>` generates seeded scenario variants and runs baseline and belief-state paired on identical fixed evidence — deterministically through RecordedHost in CI, plus ONE live ClaudeCodeHost smoke run (decision log #7).
2. `uv run credent compare baseline belief-state` emits the Polars report with paired deltas, McNemar/bootstrap statistics, perturbation-specific effects, and cost/latency deltas.
3. Re-running the eval with the same random_seed against RecordedHost reproduces identical results, including identical statistics.
4. `uv run credent replay <run-id>` recreates configuration and inputs.
5. A deliberately-failed case is attributable to a stage (extraction vs reconciliation vs reasoning vs rendering) from the stage-level eval metrics.
6. `./check.sh` green; live-model calls appear only in the explicitly-marked smoke path, never in `tests/`.

## MVP checklist coverage

Completes items 2 (both pipelines against same scenarios), 8 (reproducible deterministic + statistical evals), 9 (quality/cost/latency comparison), 10 (failures inspectable by stage). Item 6 now covers invoke/eval/replay/inspect — hook/skill/schedule legs remain for Phase 3.
