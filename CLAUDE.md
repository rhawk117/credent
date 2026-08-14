# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

credent is an AI execution and evaluation harness for experimenting with explicit belief-state reasoning in local coding agents (Claude Code, GitHub Copilot CLI). The architecture is specified in docs/ADR.md and the research scope in docs/MVP.md — both are settled; do not re-litigate their technology decisions or Explicit Non-Decisions.

Naming: the project, package, and CLI are all `credent`. ADR references to `belief_lab` / `belief-lab` are stale names for the same thing.

Implementation is organized into three phases under docs/.agent-backlog/. Before starting any work, read the current phase's objectives.md, context.md, and tasks.md — they carry the decisions, constraints, and per-task verification commands for that phase.

## Commands

uv only — never pip, never bare python.

- `./check.sh` — the full verification gate: ruff check, ruff format --check, ty check, pytest. This is what CI runs; it must pass before any completion claim.
- `./format.sh` — auto-fix lint violations and reformat.
- `uv run --group test pytest tests/unit/test_foo.py::test_name` — run a single test.
- `uv sync --all-groups` — install/refresh the environment.
- `uv run pre-commit install` — once per clone; commits then run ruff (fix + format) and ty automatically.

Dependency groups: runtime deps live in `[project.dependencies]`; `lint` and `test` are dependency-groups (`dev` includes `lint`). The `rag` extra (qdrant, sentence-transformers, ragas) is deferred — do not add it.

## Architecture

Four layers; dependencies point downward only:

Delivery/Dispatch (hooks | skills | scheduled tasks | CLI) → Capabilities → Harness runtime → Infrastructure (SQLite, filesystem)

Dispatchers determine *when* work runs. Capabilities define *what* runs. The harness runtime defines *how* AI work executes.

Rules that gate PRs:

- `dispatch/` and `hooks/` stay thin: normalize event → build ExecutionContext → select capability → `harness.run`. No belief logic, prompts, or evaluation logic in a hook.
- `domain/` is pure: it imports nothing host-specific — no Claude Code, Copilot, Phoenix, CLI, hooks, or scheduler adapters.
- `hosts/` adapters own process/invocation details only, never belief-state semantics or capability policy.
- No second agent loop and no resident scheduler daemon: scheduled tasks are data in SQLite, reconciled opportunistically at sessionStart.
- Host agents own model execution; the harness never calls model-provider APIs directly in the MVP.
- Structured host output is validated by Pydantic at the boundary before any state mutation.
- Do not introduce: Pydantic AI, LangGraph, DSPy, FastAPI, Redis, Celery, Pandas, MLflow (ADR Explicit Non-Decisions).

Host hooks are wire-compatible: Copilot CLI accepts Claude-style PascalCase event names and delivers Claude's snake_case payload fields. Hook logic is written once against the normalized HookEvent in `dispatch/hooks.py`; per-host differences live only in config manifests (`.claude/settings.json` vs `.github/hooks/*.json`) and documented exit-code semantics.

## Tests vs evals

`tests/` holds deterministic software tests — no live models, ever: unit, Hypothesis property tests, capability contract tests, dispatch tests, regression scenarios. `evals/` (data) and `src/credent/evals/` (code) hold probabilistic experiment evaluation via Pydantic Evals, which may invoke real hosts. Never test belief logic through hook modules. Lifecycle/scheduling tests use controlled clocks and fake scheduler adapters — no wall-clock sleeping, no daemon.

## Engineering loop

Branch model: task branches `feat/p0N-<slug>` (or `fix/`, `chore/`, …) off `develop`; squash-merge to `develop` via PR once CI is green (auto-merge is approved policy); phase completion is a merge commit `develop` → `main` tagged `phase-0N`, gated on the user.

Commits: `kind(scope): summary` — kinds: feat, fix, chore, docs, test, refactor, ci. PRs fill `.github/PULL_REQUEST_TEMPLATE.md`; CI runs `./check.sh`.

Agent roster and models — always dispatch these agents by name:

| Agent | Model | Role |
|---|---|---|
| scout | haiku 4.5 | task triage and mechanical retrieval (files, references, constraints) |
| code-analyst | session default | escalation target when a question needs judgment, not retrieval |
| plan-critic | session default | adversarial review of plans before implementation |
| engineer | fable-5 | one per task; implements, verifies, commits through pre-commit |
| git-publisher | haiku 4.5 | opens PRs from the template, watches CI, squash-merges on green |
| ci-watcher | session default | standalone CI verdicts when no publish is in flight |

When dispatching any subagent, the primary agent writes the dispatch prompt with the **promptlint** skill so every agent receives clear, verifiable instructions.

Per-task cycle:

1. Primary agent takes the next task from `docs/.agent-backlog/phase-0N/tasks.md`.
2. **scout** retrieves files, references, and constraints; escalates to **code-analyst** when the question needs judgment rather than retrieval.
3. For non-trivial tasks the primary drafts a plan and **plan-critic** reviews it before implementation.
4. **engineer**, one per task, implements on the task branch — in an isolated worktree when tasks run in parallel — runs the task's verification command, and commits through pre-commit.
5. **git-publisher** opens the PR from the template, watches CI, squash-merges on green, and reports back.
6. The primary records actual command output in the task's Evidence section in tasks.md before moving on.

To resume the loop in a fresh session, invoke the project `loop` skill (`.claude/skills/loop/`) — it reads the backlog state and git state, then picks up the next unfinished task.
