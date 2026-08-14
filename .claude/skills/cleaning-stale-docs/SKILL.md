---
name: cleaning-stale-docs
description: Use when cleaning up stale or outdated documentation references after a process, policy, file, or name changed — workflow changes, renames, file deletions, infrastructure changes — including cleanup that looks like simple search-and-replace.
---

# Cleaning Stale Docs

## Overview

Bring every live document in line with a changed fact without rewriting history or losing meaning. Coverage comes from search, not memory.

## Procedure

1. Write each changed fact as old → new (e.g. "phase merge: local merge commit → PR with review").
2. For each fact, grep the entire repository for the old terms and their synonyms — all Markdown, skills, templates, and comments. The file list comes from search output, never from guessing which files matter.
3. Classify every hit:
   - **Live reference** — states current process or facts → edit it, minimal diff.
   - **Historical record** — decision-log entries, changelogs, dated research notes → leave the entry as written; if the decision changed, append a new dated entry recording the change. Never rewrite what was decided.
   - **Canonical-but-superseded** — in this repo, `docs/ADR.md` and `docs/MVP.md` → never edit; the backlog records supersessions.
4. Preserve every adjacent fact in each line you edit. One sentence often carries two facts (e.g. "merge via PR" and "gated on the user") when the change updates only one; dropping the other is a silent policy change. A mechanism fact (branch protection requires review) does not replace a process fact (the agent asks the user first).
5. Verify: re-run the step 2 greps. Old terms must have zero hits outside files classified historical or canonical.
6. Report: edits made (file:line, old → new), hits deliberately left with their classification, and the greps run with their final output.

## Sanity checks

- If a file you were told to fix is missing from your working tree, or the tree looks older than the description of the change: stop and report the mismatch. Do not reconstruct files from copies found elsewhere.
- Edits must land in the working tree of the branch under work — an edit stranded in a scratch copy fixes nothing.

## Common mistakes

| Mistake | Fix |
|---|---|
| Editing the files you remember instead of the files search finds | Grep first; work from hits |
| Rewriting a decision-log entry in place | Append a new dated entry |
| Updating one fact in a sentence and dropping its neighbor | Change only the stale words |
| Reporting success without re-searching | The re-grep is the done check |
