---
description: Start a milestone (e.g. /start-milestone M01)
argument-hint: MXX
---

Start milestone $ARGUMENTS.

1. Read `CLAUDE.md`, `docs/SPEC.md`, `docs/ARCHITECTURE.md`, all ADRs in `docs/adr/`, `docs/PROGRESS.md`, and the file in `docs/milestones/` whose name starts with $ARGUMENTS.
2. Check `docs/PROGRESS.md`. If $ARGUMENTS is not ACTIVE, stop and ask the owner whether to activate it (and confirm the previous milestone is DONE).
3. Reply with:
   - a 5-line restatement of the milestone goal and done criteria
   - any conflicts between the milestone file and SPEC/ADRs
   - anything that could cost money or needs Colab/cloud access (these need explicit approval)
   - open questions (max 3)
   - the dependency versions you plan to pin, after checking current stable releases
4. Wait for the owner's confirmation. Then create a task list from the milestone's tasks and begin.
