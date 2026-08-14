# Phase 3 tasks

Ordered; each task is one feature branch off `develop` (`feat/p03-<slug>`), squash-merged on green CI. Fill each Evidence section with actual command output. T1 and T2 are independent after Phase 2 and may run in parallel (isolated worktrees).

## T1 — Task store and scheduler

`tasks/models.py` (TaskSpec, TaskTrigger), `tasks/scheduler.py` (TaskScheduler protocol + SQLite implementation), `tasks/repository.py` (reconcile-due-at-sessionStart, duplicate protection, malformed-spec rejection). Controlled-clock tests only.

Verify: `uv run --group test pytest tests/unit tests/dispatch -q -k task`
Evidence:

## T2 — HookEvent model and payload normalizer

Typed HookEvent; normalizer handling both hosts' documented payload shapes for SessionStart/SessionEnd/Stop (fixtures per context.md); reason/exit_reason unified; malformed events rejected deterministically.

Verify: `uv run --group test pytest tests/dispatch -q -k "hook and not test_hook_cli"`
Evidence:

## T3 — Hook entry scripts and dispatch (depends: T1, T2)

`hooks/session_start.py` (restore state, reconcile + dispatch due tasks, expose pending work), `hooks/agent_stop.py` (persist outcome, enqueue evaluate-run TaskSpec), `hooks/session_end.py` (fast enqueue only — ~1.5s Claude budget), all via `dispatch/hooks.py`; never blocking, always exit 0. `storage/` gains hook_invocations/schedule_invocations.

Verify: `uv run --group test pytest tests/dispatch -q`
Evidence:

## T4 — Host manifests (depends: T3)

`.claude/settings.json` hooks block (use the hooksmith skill) and `.github/hooks/credent.json` in Claude-compatible alias mode, both invoking the same entry scripts through `uv run`.

Verify: `uv run credent hook test session-start` (after T6) or direct script invocation with a fixture payload piped to stdin
Evidence:

## T5 — belief-validation skill and validation (depends: T3)

`skills/belief-validation/SKILL.md` per context.md; `dispatch/skills.py` validation logic; skill-hash recording.

Verify: `uv run credent skill validate` (after T6) and `uv run --group test pytest tests/dispatch -q -k skill`
Evidence:

## T6 — CLI: hook test / skill validate / schedule list (depends: T3, T5)

Three subcommands completing the CLI surface; `hook test <hook>` feeds a fixture payload through the real dispatch path.

Verify: `uv run credent hook test agent-stop && uv run credent skill validate && uv run credent schedule list`
Evidence:

## T7 — CopilotCliHost adapter (depends: Phase 2 T7 patterns)

Mirror of ClaudeCodeHost against Copilot's documented invocation contract; contract tests on fixtures only; a skipped-with-reason live test guarded on `copilot` being installed.

Verify: `uv run --group test pytest tests/unit tests/capabilities -q -k copilot`
Evidence:

## T8 — Phoenix/OpenInference export (depends: T3)

Investigate OpenInference conventions first (context.md "Not investigated"), then export the full trigger→dispatch→capability→model-call→state-transition→evaluator path from the Phase 1 span records. CI never starts Phoenix.

Verify: `uv run --group test pytest tests/unit -q -k trace` plus a manual `uv run phoenix serve` render for exit criterion 5
Evidence:

## T9 — Cross-dispatcher contract tests (depends: T6)

Same capability through CLI, hook, and schedule dispatch → semantically equivalent execution and equivalent trace shape; discharges the Phase 1 deferred assertions and the "dispatch mechanism does not change capability semantics" invariant.

Verify: `uv run --group test pytest tests/dispatch tests/capabilities -q`
Evidence:

## T10 — Live Claude Code round-trip and phase exit (depends: T4, T6, T8)

Manifests installed; a real Claude Code session's Stop hook persists a task visible in `credent schedule list`; measure the actual SessionEnd budget and record it. Then all six exit criteria from objectives.md, outputs recorded. Phase completion: PR `develop` → `main`, tag `phase-03` (user-gated).

Verify: `./check.sh` plus objectives.md exit commands
Evidence:
