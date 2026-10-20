---
description: Verify and close a milestone (e.g. /finish-milestone M01)
argument-hint: MXX
---

Finish milestone $ARGUMENTS.

1. Re-read the milestone file and run every item in its "Done checklist". Actually run the commands (`make lint`, `make test`, the milestone demo) — do not assume.
2. Report any failing item and fix it before continuing. If something can't be fixed in scope, list it and ask the owner.
3. Write `docs/interview/$ARGUMENTS.md` following `docs/interview/README.md`. Answers must cite real file paths and measured numbers from this milestone.
4. Update `docs/PROGRESS.md`: mark $ARGUMENTS DONE, add a dated log line with key decisions/versions. Do NOT mark the next milestone ACTIVE — ask the owner.
5. Show `git status` and a proposed commit message `feat(<mXX lowercase>): <summary>`. Commit only after the owner says so.
