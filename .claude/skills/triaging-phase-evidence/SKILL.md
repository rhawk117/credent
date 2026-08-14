---
name: triaging-phase-evidence
description: Use when a backlog phase is about to begin and needs pre-implementation research, or when dispatched to triage evidence, verify environment facts, or close open unknowns for an upcoming phase.
---

# Triaging Phase Evidence

## Overview

Close the evidence gaps a phase pack still has. The pack (`docs/.agent-backlog/phase-0N/`) is the only document the implementing agent reads; triage adds missing facts to it. It never restates what the pack already pins.

## Output contract

Triage produces exactly one artifact: edits to the phase pack in the repository working tree.

1. Read `docs/.agent-backlog/README.md` (decision log, environment facts), then the phase's `objectives.md`, `context.md`, `tasks.md`.
2. Collect the open unknowns: every "Not investigated" item, every fact marked unverified, every environment fact dated from an earlier session.
3. For each unknown, gather evidence: run the command, inspect the installed package, fetch the official doc. Record exactly what you ran and what it returned.
4. Write findings into the pack: a resolved unknown moves out of "Not investigated" into the phase `context.md` with its evidence and date; corrected environment facts go to the backlog README.
5. Report three lists: unknowns resolved (with evidence), unknowns still open (with what blocks each), pack files edited.

## Rules

- New facts only. If the ADR, MVP, CLAUDE.md, or the pack already states something, cite the path. A transcribed copy drifts, and its transcription errors carry no authority.
- Every fact added to the pack carries its evidence: command plus output, or source URL plus date. A fact you could not verify stays in "Not investigated" with a note on what you tried.
- The scratchpad and /tmp are ephemeral. The next agent sees only the repository — findings that are not written into the pack do not exist.
- Proposals (test layout, coverage targets, config values not settled in the pack) belong in the report, labeled as proposals — never written into the pack as facts.
- Do not write implementation guides, plans, or code. `tasks.md` scopes the work; plan-critic and engineer own the how. Do not begin implementing.

## Common mistakes

| Mistake | Fix |
|---|---|
| Summarizing the ADR or pack into new documents | Cite paths; add only what is new |
| Saving research to /tmp or a scratchpad | Edit the pack files in the working tree |
| Presenting invented targets or config as settled | Label them proposals, in the report only |
| Declaring research complete with zero unknowns resolved | The unknown list is the work: resolve each or explain what blocks it |
