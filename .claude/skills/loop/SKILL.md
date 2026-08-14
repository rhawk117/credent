---
name: loop
description: Resume the credent engineering loop in a fresh session — reads backlog and git state, picks the next unfinished task, and runs the per-task agent cycle. Use at the start of any implementation session, or when asked to continue/resume work on the MVP.
---

# loop

Resume the credent engineering loop exactly as documented in /CLAUDE.md ("Engineering loop"). This skill re-establishes state; it adds no new policy.

## On invocation

1. **Re-establish state** (read, in order):
   - /CLAUDE.md — the loop, agent roster, and model assignments.
   - `docs/.agent-backlog/README.md` — decision log; do not re-open settled decisions.
   - The current phase pack: lowest-numbered `docs/.agent-backlog/phase-0N/` whose tasks.md still has an empty Evidence section. Read its objectives.md, context.md, tasks.md.
   - Git state: `git status -sb`, `git log --oneline -5 develop`, open PRs (`gh pr list`). If a task branch exists with unmerged work, finish or reconcile it before starting anything new.
   - If `docs/.agent-backlog/STAGE-2-PLAN.md` still exists, bootstrap is unfinished — execute that file first and delete it when its verification section has evidence.

2. **Select work**: the first task in the current phase's tasks.md with an empty Evidence section whose dependencies (listed per task) have evidence. Independent tasks may run in parallel — one engineer each, isolated worktrees, per CLAUDE.md.

3. **Run the per-task cycle** from CLAUDE.md with the named agents (scout → code-analyst escalation → plan-critic gate → engineer → git-publisher). Write every dispatch prompt with the **promptlint** skill. Record actual command output in the task's Evidence section before moving on.

4. **Phase exit**: when every task has evidence and the exit-criteria commands in objectives.md pass, present the evidence and ask the user to approve the merge commit `develop` → `main` + tag `phase-0N`. Never perform that merge unprompted.

## Hard rules carried from CLAUDE.md

- `./check.sh` green before any completion claim; evidence is command output, not assertion.
- Commits `kind(scope): summary` through pre-commit; task PRs squash-merge to develop on green CI.
- No live models in `tests/`; live runs only through explicitly-marked paths.
