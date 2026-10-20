# MineOps Copilot — Specification (v1.0, approved 2026-10-20)

## 1. Goal

An AI operations copilot for **Falcon Ridge Mining** (fictional). It:
- answers SOP / safety / maintenance-manual questions with citations, in **English and Arabic**
- answers questions about production KPIs, work orders, and safety incidents through governed tools
- produces executive daily/weekly summaries
- drafts maintenance work orders that a human must approve before they are written

It runs fully locally (docker-compose, no GPU required) and deploys to Kubernetes via Helm, with documented GKE deployment.

## 2. Non-goals

- Real data, real company names or branding
- Production identity provider (local JWT issuer; Keycloak/OIDC swap documented)
- Multi-tenancy
- A polished UI (optional minimal page at the very end, low priority)
- Fine-tuning models

## 3. Users and RBAC

Roles: `operator`, `engineer`, `executive`. JWT claims: `sub`, `role`, `sites[]`, `lang`.

| Capability | operator | engineer | executive |
|---|---|---|---|
| Knowledge Q&A (SOPs) | ✅ | ✅ | ✅ |
| KPIs / work orders / incidents | own `sites[]` only | all sites | all sites |
| Create work-order draft | ✅ | ✅ | ❌ |
| Approve / reject draft (HITL) | ❌ | ✅ | ❌ |
| Executive reports | ❌ | ✅ | ✅ |
| Eval / admin endpoints | ❌ | ✅ | ❌ |

Enforced in the gateway (route guards) **and** in MCP tools (row-level site filters, role checks). The LLM never decides authorization.

## 4. Domain model (synthetic)

- **Sites** (3): open-pit gold, open-pit phosphate, underground copper. Fictional names.
- **Assets** (~120): haul trucks, excavators, crushers, conveyors, pumps, drills. Tag, type, site, criticality, commissioned date, status.
- **PM schedules**: interval-based preventive maintenance per asset.
- **Work orders** (~5k): type (PM/CM/inspection), priority, status, opened/due/closed, asset, assignee role, description.
- **Downtime events**: asset, start/end, reason code.
- **Production daily**: site, date, ore tonnes, target tonnes, grade, availability %, utilization %.
- **Safety incidents** (~300): severity (near-miss → lost-time), category, site, asset (optional), description, date.
- **Work-order drafts**: created by the action agent, state `pending|approved|rejected`, approver, timestamps.

Injected, documented anomalies (written to `data/ground_truth.json`) so reports and tests have real signal:
1. One site under target for the last 14 days
2. One crusher with recurring corrective failures
3. A cluster of overdue PM work orders at one site
4. Incident spike following a shift-pattern change

## 5. Document corpus

~60–100 generated documents: SOPs, safety procedures, maintenance manuals, lockout/tagout, emergency response.
Markdown with YAML frontmatter: `doc_id, title, doc_type, site (or "all"), asset_type, lang (en|ar), version, effective_date, supersedes`.
- ≥25% Arabic-authored documents; some topics exist in both languages.
- Some documents are superseded by newer versions (tests `effective_date` filtering and "latest version" behavior).
- Optional PDF rendering of a subset to exercise PDF ingestion.

## 6. Retrieval

- Chunking: heading-aware, ~400–600 tokens, overlap ~60; chunk inherits doc metadata + `section_path`.
- Keyword: OpenSearch BM25. Mapping has `text` with per-language subfields/analyzers (`english`, `arabic`); query targets the analyzer matching query language (detected), with a fallback multi-match.
- Dense: Qdrant, multilingual embedder, payload indexes on filter fields.
- Filters (both engines): `site`, `asset_type`, `doc_type`, `lang`, `effective_date <= as_of`, `is_latest`.
- Fusion: app-side **RRF** (k=60 default, configurable); weighted fusion implemented as an alternative for the eval.
- Rerank: multilingual cross-encoder on top-N (default 30 → 8).
- Eval: ~60 hand-labeled queries (≥20 Arabic, some cross-lingual) with graded qrels. Compare BM25, dense, hybrid (RRF), hybrid+rerank on recall@5/10, MRR@10, nDCG@10, plus p50/p95 latency. Results committed as a markdown table.

## 7. Agents (LangGraph)

Supervisor routes each turn to one or more agents and composes the final answer.
1. **Knowledge agent** — hybrid retrieval, answers with inline citations `[doc_id §section]`; refuses when evidence is insufficient.
2. **Ops data agent** — calls MCP read tools only; answers with numbers and the tool calls that produced them.
3. **Reporting agent** — composes daily/weekly executive summary: production vs target, incidents, overdue maintenance, top risks; output is structured (Pydantic) + rendered markdown.
4. **Action agent** — prepares a work-order draft, then **interrupts** for human approval; on approval calls `create_work_order_draft` → approval endpoint promotes it; on rejection records reason.

State persists in Postgres (LangGraph checkpointer) so interrupts survive restarts. Answers follow the user's language (`lang` claim or detected).

## 8. MCP server

Python, Streamable HTTP transport, separate service.
- Tools (initial): `get_kpis`, `get_production_vs_target`, `list_work_orders`, `list_overdue_work_orders`, `get_asset`, `get_incidents`, `get_downtime_summary`, `create_work_order_draft`, `search_sops` (thin wrapper over retrieval).
- Resources: `sop://{doc_id}`, `site://{site_id}`.
- Each tool: Pydantic-validated args, parameterized query template, row limit, timeout, site/role enforcement from the caller identity, audit log entry.
- DB roles: `app_ro` (SELECT only on domain tables), `drafts_rw` (INSERT/UPDATE on `work_order_drafts` only).

## 9. Model serving

- Client abstraction speaks OpenAI Chat Completions; `LLM_PROVIDER=vllm|ollama|hosted`, `LLM_BASE_URL`, `LLM_MODEL`.
- Local default: Ollama (CPU) with a small multilingual instruct model.
- vLLM: provider adapter + config in M3; K8s/GKE manifests for a GPU node pool in M9 (documented, cost-gated). Live GPU demo on Colab is deferred to optional M11 after M10.
- Model family: a small instruct model with solid Arabic + tool calling (Qwen-family default; pin exact model at M3).

## 10. Services and APIs

**gateway (NestJS)** — public entrypoint
- `POST /auth/login` (seeded demo users) → RS256 JWT; `GET /.well-known/jwks.json`
- `POST /v1/chat` (SSE passthrough), `GET /v1/runs/:id`, `POST /v1/runs/:id/approve|reject`
- `GET /v1/dashboard/kpis`, `GET /v1/reports/daily|weekly`
- Guards: JWT, RBAC, site scoping; rate limiting; DTO validation; error envelope; request ID propagation.

**agent-service (FastAPI)** — internal
- `POST /chat` (SSE: tokens, tool events, interrupt events), `GET /runs/{id}`, `POST /runs/{id}/resume`
- `POST /reports/{period}`, `POST /eval/retrieval`
- `/healthz`, `/readyz`, `/metrics`

**mcp-server** — internal; `/mcp` Streamable HTTP, `/healthz`, `/metrics`.

## 11. Cross-cutting

- JSON logs with request/trace IDs across all three services
- OpenTelemetry traces gateway → agent-service → mcp-server → DB/LLM
- Prometheus metrics (HTTP, LLM latency/tokens, retrieval latency, tool calls, HITL queue)
- Health/readiness probes; consistent error envelope; input validation at every boundary
- Secrets via env / K8s Secrets; GCP Secret Manager documented

## 12. Deployment

- docker-compose with profiles: `core` (postgres), `search` (opensearch, qdrant), `llm` (ollama), `obs` (otel-collector, jaeger, prometheus, grafana), `app` (services)
- Helm chart(s), tested on kind
- GKE deploy guide with cost warnings and teardown

## 13. Milestones

See `docs/milestones/`. Status in `docs/PROGRESS.md`.

| # | Milestone |
|---|---|
| M1 | Repo skeleton, core package, compose, Postgres schema, synthetic data, CI (lint+test) |
| M2 | Bilingual corpus, ingestion, hybrid retrieval, rerank, retrieval eval |
| M3 | LLM client abstraction, Ollama local, vLLM-ready config |
| M4 | MCP server + tools + resources |
| M5 | LangGraph supervisor + agents + HITL |
| M6 | FastAPI agent-service (SSE, runs, reports, eval) |
| M7 | NestJS gateway (auth, RBAC, validation, proxy) |
| M8 | Observability + security hardening |
| M9 | Helm + kind, GKE docs |
| M10 | CI image builds, README, diagrams, demo script |
| M11 | (optional, deferred) vLLM live on Colab GPU + benchmarks |

## 14. Cost policy

Nothing that costs money happens without explicit approval in chat: Colab paid compute, GCP VMs/GPUs, GKE, hosted LLM APIs.
