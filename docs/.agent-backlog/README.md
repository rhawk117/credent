# Agent Backlog

Implementation backlog for the credent MVP, split into three phases. Each phase directory holds:

- `objectives.md` — the phase goal, module ownership, and exit criteria (which MVP-deliverable points it satisfies).
- `context.md` — decisions, constraints, and ADR/MVP facts the phase depends on, including approaches that are ruled out.
- `tasks.md` — ordered tasks, each with a verification command and an Evidence section the executing agent fills with actual command output.

Phases execute in order. A phase is complete when every task's Evidence section is filled, its exit-criteria commands pass, and `develop` is merge-committed into `main` with tag `phase-0N` (user-gated). The per-task engineering loop is documented in /CLAUDE.md.

Source of truth for architecture: `docs/ADR.md`. Research scope: `docs/MVP.md`. Both are settled. Where this backlog contradicts them, the backlog wins — it encodes later, user-approved decisions recorded below.

## Decision log (user-settled 2026-08-13)

1. **Naming: everything is `credent`.** Project, package (`src/credent`), and CLI (`credent`) keep the scaffold name. ADR references to `belief_lab`/`belief-lab` are stale names for the same system. Alternative (renaming to match the ADR) was offered and declined.
2. **Walking-skeleton phase split.** Phases are ordered by integration risk and time-to-evidence, not by architectural layer. The bottom-up layered alternative (core+domain+storage → hosts+pipelines+evals → dispatch+tasks+telemetry+CLI) was drafted first and rejected after adversarial review found: no runnable state until late; paid model runs would execute before usage accounting exists; the full schema would be committed with zero consumers; and dispatch+tasks+telemetry+CLI would stack into one wide final phase on top of the hardest external unknown. Accepted cost of the chosen split: `storage/`, `capabilities/`, and the CLI grow across phases — each phase's objectives.md states that growth explicitly, so no phase silently edits outside its scope.
3. **docs-query is deferred with RAG.** No docs-query capability or skill in the MVP. `skills/` ships `belief-validation` only, so `credent skill validate` (which requires a skill's referenced capability to exist) stays green. The MVP.md capability diagram listing docs-query as core is superseded by the ADR's "Initial capabilities" list.
4. **post_tool / pre_completion hooks are deferred.** The ADR's `post_tool.py` example dispatches `observe-tool-result`, a capability that exists in no capability list. The ADR names sessionStart/sessionEnd/agentStop as the primary hooks and the others as optional; the MVP ships only the primary three.
5. **inspect-belief-state gets `capabilities/inspect_belief_state.py`.** The ADR lists it as an initial capability but omits it from the Source Layout's capabilities/ file list — an internal ADR inconsistency resolved by adding the file.
6. **CopilotCliHost: real adapter, fixture-tested, live validation deferred.** Copilot CLI is not installed on this machine. The adapter and its hook manifests are built against the officially documented payload contracts (see hook research below) with contract tests on fixtures; live end-to-end validation waits until the CLI is installed. MVP gates on Claude Code end-to-end.
7. **One live ClaudeCodeHost smoke run is part of the Phase 2 exit.** The full evaluation program (MVP.md "Evaluation Progression") is post-MVP activity; the MVP proves the machinery with RecordedHost/FakeHost determinism plus one small real run for cost/latency ground truth.
8. **Merge policy: auto squash-merge on green CI** for task PRs into `develop`; `develop` → `main` phase merges are gated on the user.
9. **Engineering loop** (documented in /CLAUDE.md): scout (haiku) triage → code-analyst escalation for judgment calls → plan-critic gate on non-trivial tasks → one engineer (fable-5) per task committing through pre-commit → git-publisher PR + CI watch + squash-merge. Conventional commits `kind(scope): summary`.

## Host hook research (verified 2026-08-13, official docs)

Both host agents expose lifecycle hooks, and they are wire-compatible:

| Harness concept | Claude Code event | Copilot CLI event |
|---|---|---|
| sessionStart | `SessionStart` | `sessionStart` (alias `SessionStart`) |
| sessionEnd | `SessionEnd` | `sessionEnd` (alias `SessionEnd`) |
| agentStop | `Stop` | `agentStop` (alias `Stop`) |

- Copilot CLI accepts Claude-style PascalCase event names and then delivers Claude's snake_case stdin fields (`hook_event_name`, `session_id`, `cwd`, `tool_name`, `tool_input`) — configure the Copilot manifests in this compatible mode so `dispatch/hooks.py` normalizes one payload shape.
- Config locations: Claude Code `.claude/settings.json` hooks blocks; Copilot CLI `.github/hooks/*.json` (repo) or `~/.copilot/hooks/` (user), JSON `{"version": 1, "hooks": {...}}`, loaded at CLI startup.
- Semantics differences to encode in fixtures: Copilot timeouts are always fail-open (default 30s); Copilot exit-2 denies only on `preToolUse`/`permissionRequest`; Copilot's `agentStop` supports block-to-continue with an 8-consecutive-block runaway guard; Claude Code `Stop` blocks via exit 2.
- Sources: docs.github.com/en/copilot/reference/hooks-reference, docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-hooks, code.claude.com/docs/en/hooks.md.

## Environment facts (verified 2026-08-13)

- Python 3.14.6 via uv (`.python-version` pins 3.14); uv 0.11.29.
- `claude` CLI installed; `copilot` CLI **not** installed; `gh` installed.
- All ADR runtime deps resolve and import on 3.14 (arize-phoenix emits one harmless SyntaxWarning from its own code on import).
- Verification gate: `./check.sh` (ruff check, ruff format --check, ty check, pytest via the `test` group). CI runs the same script.
