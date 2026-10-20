# Progress

Only the milestone marked **ACTIVE** may be worked on. Change status only with the owner's go-ahead.

| # | Milestone | Status | Notes |
|---|---|---|---|
| M1 | Skeleton, compose, schema, synthetic data, CI | ACTIVE | |
| M2 | Corpus, ingestion, hybrid retrieval, eval | TODO | |
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
