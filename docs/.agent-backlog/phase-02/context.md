# Phase 2 context

Read `docs/.agent-backlog/README.md` first. Phase 1 must be complete (its exit evidence filled) before this phase starts — everything here builds on the walking skeleton.

## Experimental design rules (from docs/MVP.md, binding)

- Both pipelines receive the same question, the same fixed evidence, the same host, the same selected model where controllable, equivalent inference settings, equivalent output requirements. Retrieval is excluded — fixed evidence isolates the state architecture from retrieval quality.
- Counterfactuals are mandatory (ADR "Counterfactual Evaluation"): control → expected owner; counterfactual (one fact changed) → changed owner; missing → UNKNOWN. The generator must emit these triplets per scenario.
- Runs are paired by scenario and variant. Statistics must treat them as paired observations; McNemar-style analysis for paired binary outcomes, bootstrap CIs / permutation tests for continuous deltas. Never report p-values without effect size and CI.
- Pseudo-replication guard: many variants from one base scenario are not independent experimental units — statistics.py must support grouping by base scenario.

## Reproducibility record (ADR "Experiment Reproducibility")

Persist per run: run_id, experiment_id, capability, pipeline, scenario_id, variant_id, random_seed, trigger, host agent, selected model where exposed, host/model configuration, evidence hash, prompt hash, code commit, start/end time, input/output tokens, estimated cost, result, metrics. (skill hash / hook revision / task trigger fields are added in Phase 3 — leave columns nullable or add then.)

## ClaudeCodeHost facts

- Invoke the `claude` CLI headless (`claude -p`) via AnyIO subprocess; request structured JSON output and validate with Pydantic at the boundary. `claude` is installed and on PATH (verified 2026-08-13).
- The live smoke run is ONE small experiment for cost/latency ground truth (decision log #7) — it must be an explicitly-invoked CLI path, marked clearly, and never triggered from `tests/`.
- RecordedHost is the CI subject: it replays captured AgentResult fixtures deterministically. Record the smoke run's transcript as the first recorded fixture so CI thereafter exercises the real shape.
- CopilotCliHost is Phase 3; do not build it here.

## Constraints and ruled-out approaches

- Eval subjects call `harness.run(...)` with trigger="eval" — never a model provider, never a host adapter directly from a dataset case (ADR "Pydantic Evals").
- Prefer deterministic evaluators; an LLM-judge evaluator is out of scope for the MVP.
- Parquet for exported analytical datasets; SQLite remains the transactional store. Pandas is ruled out — Polars only.
- Do not introduce retrieval, Qdrant, embeddings, or ragas — deferred with RAG.
- `tests/` stay model-free: integration tests run through RecordedHost/FakeHost.

## Established facts

- pydantic-evals is installed (resolved 2026-08-13) but its API surface was NOT investigated during bootstrap — the first eval task should start with a scout/code-analyst pass over its docs (Dataset, Case, evaluators, experiment execution) before code is written.
- numpy/scipy/polars/pyarrow all import cleanly on 3.14.6.
- The stale-owner fixture from Phase 1 becomes the first generator template and the first regression scenario (`stale-codeowners-001`).

## Not investigated

- pydantic-evals experiment-execution API details (see above).
- Claude CLI structured-output flags and their stability across versions — verify against the installed `claude --help` before writing the adapter contract.
- Token/cost metadata availability from headless Claude runs — if unavailable, estimate from transcript lengths and record the estimation method in usage.py.
