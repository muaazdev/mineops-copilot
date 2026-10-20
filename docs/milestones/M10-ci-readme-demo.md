# M10 — CI images, README, diagrams, demo

**Goal:** a reviewer can understand, run, and evaluate the project in 10 minutes.

**Cost:** none (GHCR is free for public repos — confirm before pushing images).

## Tasks
1. CI: matrix for Python + Node; build images for all services (buildx, cache); push to GHCR on main/tags only (ask owner first); trivy scan; gitleaks.
2. README: one-paragraph pitch, architecture Mermaid, feature list mapped to the JD stack, quickstart, demo GIF/screens, eval results table, links to ADRs and interview notes, "what I'd do in production" section.
3. `scripts/demo.sh`: scripted walkthrough via gateway — login as each role, EN + AR knowledge Q with citations, ops question with tool trace, executive report, operator drafts WO → engineer approves; prints trace IDs.
4. Optional minimal UI (only if time permits; owner decides).
5. Final pass on all `docs/interview/*.md` → `docs/interview/CHEATSHEET.md` (top 25 questions).

## Done checklist
- [ ] Clean-clone run-through by following README only
- [ ] `docs/interview/M10.md` + `CHEATSHEET.md`
