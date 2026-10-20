# Progress

Only the milestone marked **ACTIVE** may be worked on. Change status only with the owner's go-ahead.

| # | Milestone | Status | Notes |
|---|---|---|---|
| M1 | Skeleton, compose, schema, synthetic data, CI | DONE | 56 tests, CI green; see docs/interview/M01.md |
| M2 | Corpus, ingestion, hybrid retrieval, eval | ACTIVE | |
| M3 | LLM client, Ollama, vLLM on Colab (gated) | TODO | |
| M4 | MCP server + tools | TODO | |
| M5 | LangGraph agents + HITL | TODO | |
| M6 | agent-service API | TODO | |
| M7 | NestJS gateway | TODO | |
| M8 | Observability + security hardening | TODO | |
| M9 | Helm + kind, GKE docs | TODO | |
| M10 | CI images, README, demo | TODO | |
| M11 | vLLM on Colab (deferred, optional) | DEFERRED | Only after M10, owner go-ahead required |

Statuses: TODO → ACTIVE → DONE.

## Log

- 2026-10-20 — Spec approved. Decisions: Arabic support yes, Helm, no local GPU (Colab via VS Code, ask first), name "Falcon Ridge Mining".
- 2026-10-20 — Colab/vLLM GPU work deferred until after M10 (new optional M11). M3 is Ollama + vLLM-ready config/docs only.
- 2026-10-20 — M1 DONE. Postgres 16.15, SQLAlchemy 2.1.5, Alembic 1.20.0, psycopg 3.3.6, pydantic 2.14.1 / pydantic-settings 2.16.0, numpy 2.5.4, ruff 0.17.1, mypy 2.4.0, pytest 9.1.1, testcontainers 4.15.0; OpenSearch 3.9.0, Qdrant v1.19.2. Decisions: ground_truth.json is generated (data/generated/); grants owned by Alembic, login roles by compose init; new NOLOGIN `audit_writer` (INSERT-only audit) granted to app_ro/drafts_rw; stdlib JSON logging; Faker dropped (single numpy RNG); vocab as varchar+CHECK; `RESTRICTED=1` compose override for hosts that block rlimits.
