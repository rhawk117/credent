# Stage 2 completion plan

Self-contained execution prompt for finishing the credent bootstrap. Written for an agent with zero memory of the session that produced it. Delete this file once every item in `<verification>` has evidence and the PR is merged.

<objective>
Finish bootstrapping the credent repo so Phase 1 implementation can begin. Stage 1 (understanding, clarification, phase-split approval) is DONE — all decisions are recorded in docs/.agent-backlog/README.md ("Decision log" + "Host hook research" + "Environment facts"). Read that file first; do not re-open settled decisions. This stage produces setup artifacts only — no MVP feature code.
</objective>

<context>
Already completed (verified this session):
- Runtime deps added per ADR Dependency Shape (no rag extra): `uv add pydantic pydantic-evals anyio arize-phoenix openinference-instrumentation sqlalchemy numpy scipy polars pyarrow typer rich`; `pytest-asyncio` added to the `test` group. `uv sync --all-groups` clean; all imports verified on Python 3.14.6.
- /CLAUDE.md written (project overview, commands, architecture rules, tests-vs-evals, engineering loop). Still needs the update listed below.
- docs/.agent-backlog/README.md written (decision log, hook research, environment facts).

User directives added mid-session (must be reflected in CLAUDE.md's loop section):
- Reference agents by exact name: scout, code-analyst, plan-critic, engineer, git-publisher, ci-watcher.
- Model assignments: scout = haiku 4.5, git-publisher = haiku 4.5, engineer = fable-5; code-analyst and plan-critic use the session default.
- When the primary agent dispatches any subagent, it writes the dispatch prompt using the promptlint skill so agents always receive clear instructions.
- A project skill for starting a new session/loop iteration is created at the VERY END of this stage (after everything else): .claude/skills/loop/SKILL.md — on invocation it reads CLAUDE.md's loop, docs/.agent-backlog/ state (current phase, next unfinished task in tasks.md), and git state (branch, develop/main positions), then resumes the per-task cycle.
</context>

<remaining_work>
In order:

1. Update /CLAUDE.md loop section with the four user directives above.
2. Write the three phase packs (objectives.md, context.md, tasks.md each — content outline below). Every task in tasks.md carries a verification command and an empty "Evidence:" section.
3. Write .github/workflows/ci.yml: on pull_request and on push to develop/main; steps: checkout, install uv (astral-sh/setup-uv), `uv sync --all-groups`, `./check.sh`.
4. Create the loop skill (very end of file-writing).
5. Dispatch one fresh-context completeness-critic subagent: "Could a fresh agent execute Phase 1 correctly using only CLAUDE.md + the phase-01 pack + docs/ADR.md + docs/MVP.md? Name concrete gaps." Fix real gaps it finds.
6. Run the verification gate (below), record actual output.
7. Commit everything on chore/agent-harness as `chore(setup): bootstrap dependencies, backlog, CI, and agent loop` (pre-commit hooks will run; `uv run pre-commit install` first if hooks aren't installed).
8. Dispatch git-publisher (haiku 4.5): PR chore/agent-harness → develop using .github/PULL_REQUEST_TEMPLATE.md, watch CI, squash-merge on green (approved policy), report. develop → main phase merges stay user-gated.

Phase pack content outlines (the approved walking-skeleton split — expand each into the three files):

PHASE 1 — Walking skeleton: one capability end-to-end through CLI, FakeHost, SQLite.
Modules: harness/ COMPLETE (Capability protocol with async execute(input, context); Harness.run(capability, input, context); ExecutionContext BaseModel: invocation_id, trigger, actor, correlation_id, parent_run_id, metadata; registry). domain/ minimal-but-real (BeliefStatus StrEnum: OBSERVED RETRIEVED INFERRED ASSUMED CONTRADICTED UNKNOWN; Observation; Belief with supporting/contradicting/derived id-tuples; deterministic reconciliation covering supersession, contradiction, UNKNOWN-carries-no-value; provenance lineage). storage/ run-graph subset ONLY (capabilities, runs, invocations, sources, observations, beliefs, belief_support, belief_contradictions, state_transitions). hosts/ base.py (AgentHost protocol: name, async invoke(AgentInvocation)->AgentResult) + fake.py. pipelines/ thin baseline (one host call) + belief_state (extract→reconcile→reason→render). capabilities/ reason_from_evidence.py, reconcile_beliefs.py, inspect_belief_state.py (file is an intentional addition — decision log #5). dispatch/cli.py Typer app: `capability list`, `run`, `inspect`; repoint [project.scripts] credent to it. scenarios/fixtures.py: one hand-authored stale-owner scenario with ground truth. telemetry/tracing.py minimal local span capture (Phoenix export deferred to Phase 3). tests/unit + tests/capabilities incl. Hypothesis invariants (reconciliation order-independence; UNKNOWN carries no value).
Exit: `uv run credent capability list`; `uv run credent run reason-from-evidence` on the fixture runs BOTH pipelines via FakeHost, validates structured host output with Pydantic before state mutation, persists run graph to SQLite; `uv run credent inspect <run-id>` shows the superseded belief with provenance; `./check.sh` green. MVP checklist #1 done; #2/#6/#7/#10 seeded.

PHASE 2 — Experiment engine: scenarios, evals, statistics, first real host.
Modules: scenarios/ COMPLETE (seeded SRE-world generator with deterministic ground truth; perturbations: clean, stale, contradictory, missing, duplicated, reordered, false-premise, irrelevant + semantically-similar distractors, conflicting authority, changed revision, long history). capabilities/ validate_claims.py, run_evaluation.py. hosts/ recorded.py (deterministic replay for CI), claude_code.py (AnyIO subprocess, structured stdin/stdout JSON contract, timing, usage metadata). evals/ COMPLETE (datasets: Pydantic Evals, subject calls harness.run; evaluators: deterministic answer/state/contradiction/abstention/false-premise/provenance/counterfactual/distractor accuracy; statistics: paired deltas, McNemar for paired binary outcomes, bootstrap CIs, permutation tests, pseudo-replication guard; reports: Polars over Parquet in artifacts/ — absolute result, effect size, CI, cost delta, latency delta — never p-values alone). telemetry/usage.py (input/output tokens, model calls, estimated cost, per-stage latency p50/p95) — lands BEFORE any paid run. storage/ EXTENSION (experiments, scenarios, scenario_variants, evaluation_results, model_invocations, artifacts; reproducibility fields: random_seed, evidence hash, prompt hash, code commit, host/model config; ADR key indexes). dispatch/cli.py adds `eval`, `compare`, `replay`. Data trees: evals/{datasets,scenarios,expected}/, artifacts/{runs,reports,traces}/. tests/integration, tests/evals, tests/regression seeded with named scenarios (stale-codeowners-001, false-premise-004 style).
Exit: `credent eval` runs paired baseline-vs-belief-state on identical fixed evidence deterministically via RecordedHost in CI plus ONE live ClaudeCodeHost smoke run (decision log #7); `credent compare` emits the stats report incl. cost/latency deltas; same-seed re-run reproduces identical results; `credent replay <run-id>` works; failures attributable per stage via stage-level eval metrics. Checklist #2 #8 #9 #10 done, #6 mostly.

PHASE 3 — Delivery surfaces: hooks, skills, daemon-free scheduled tasks, full tracing.
Modules: hooks/ session_start.py, session_end.py, agent_stop.py (thin: normalize → ExecutionContext → select capability → harness.run; post_tool/pre_completion deferred, decision log #4). dispatch/hooks.py (typed HookEvent; ONE normalizer for both hosts — Copilot manifests configured in Claude-compatible payload mode, see README hook research). dispatch/skills.py (metadata validation, referenced capability exists, input schema match, skill hash recorded). dispatch/tasks.py (scheduled delivery, trigger="scheduled-task"). tasks/ COMPLETE (TaskSpec/TaskTrigger models; TaskScheduler protocol; SQLite-persisted task store reconciled opportunistically at sessionStart — NO resident daemon). skills/belief-validation/SKILL.md only (docs-query deferred, decision log #3). hosts/copilot_cli.py (fixture-tested; live validation deferred, decision log #6). telemetry/tracing.py COMPLETE (Phoenix + OpenInference export of trigger→dispatch→capability→model call→state transition→evaluator). storage/ EXTENSION (hook_invocations, schedule_invocations). dispatch/cli.py adds `hook test`, `skill validate`, `schedule list`. Host manifests: .claude/settings.json hooks block + .github/hooks/credent.json. tests/dispatch (event→capability mapping, malformed events rejected, harness failure surfaced; controlled clocks + fake scheduler, no wall-clock sleeps; cross-dispatcher contract tests: CLI vs hook vs schedule dispatch semantically equivalent).
Exit: `credent hook test agent-stop` passes; a task scheduled at sessionEnd is reconciled and dispatched at a simulated sessionStart with correlation IDs preserved under a controlled clock; `credent skill validate` green; one live Claude Code hook round-trip; Phoenix renders the full trace; `./check.sh` green. Checklist #3 #4 #5 done; #6 #7 completed.
</remaining_work>

<constraints>
- No implementation: nothing under src/, tests/, hooks/ — the only skill file created is .claude/skills/loop/SKILL.md. Every other new file is CLAUDE.md content, a backlog artifact, or ci.yml.
- uv only; never pip or bare python.
- Do not modify docs/ADR.md or docs/MVP.md; contradictions are already resolved in the decision log.
- develop → main merges are user-gated; do not perform one.
</constraints>

<verification>
Run and record actual output:
- `uv sync --all-groups` — clean.
- `uv run python -c "import pydantic, pydantic_evals, anyio, sqlalchemy, polars, numpy, scipy, typer, rich"` — OK.
- `ls docs/.agent-backlog/*/` — three phase dirs, each with objectives.md, context.md, tasks.md.
- CLAUDE.md contains the gate commands, the loop with named agents + models, and the promptlint-dispatch rule.
- `./check.sh` — green.
- After PR: CI green on the PR, squash-merged into develop.
</verification>

<output>
Final report: approved phase split (one paragraph per phase), files created, verification evidence (actual command output), PR link + CI verdict, and anything discovered that contradicts this plan.
</output>
