# CLAUDE.md — MineOps Copilot

Read this file fully at the start of every session. It is the contract for how work happens in this repo.

## What this is

MineOps Copilot is an AI operations assistant for **Falcon Ridge Mining**, a fictional mining company.
It is a portfolio project that mirrors a government AI Engineer job description, and the build itself is interview prep.
All data is synthetic. Never use real company names, logos, people, or locations of real mines.

Source of truth, in this order:
1. `docs/SPEC.md` — what we build and why
2. `docs/ARCHITECTURE.md` — how the pieces fit
3. `docs/adr/` — decisions already made (do not silently reverse one; propose a new ADR that supersedes it)
4. `docs/milestones/MXX-*.md` — the task list for the current milestone
5. `docs/PROGRESS.md` — which milestone is active and what is done

## The owner

Senior ML engineer. Strong in Python, RAG, LangGraph, MLOps. **Weaker in NestJS/TypeScript, OpenSearch, vLLM internals, and GCP/GKE** — when working in those areas, explain the *why* in code comments and in the milestone notes, more than you would elsewhere. Skip basics everywhere else. Keep chat explanations short.

## Working rules (non-negotiable)

1. **One milestone at a time.** Only work on the milestone marked `ACTIVE` in `docs/PROGRESS.md`. Do not start the next milestone without the owner's explicit go-ahead.
2. **Spec first.** If a task is ambiguous or the milestone file conflicts with SPEC/ADRs, stop and ask. Do not invent scope.
3. **Cost gate.** Before doing anything that can cost money — GPU VMs, Colab paid compute, GKE clusters, any cloud resource, hosted LLM API calls — STOP and ask the owner. State what it is, the rough cost driver, and the teardown step. Never create cloud resources without a "yes" in chat.
4. **Colab gate.** The owner has no local GPU. Colab/GPU work is **deferred to M11 (after M10)** — do not use Colab before then. When M11 starts, use Google Colab through the VS Code Colab extension and **ask before every Colab step**. Respect Colab's usage rules: no tunnels/proxies exposing a Colab runtime as a web service to the local stack. See `docs/gpu/colab-vllm.md`.
5. **Every milestone ends runnable.** `make up`, `make test`, and that milestone's demo command must work from a clean clone. Commit at the end with message `feat(mXX): <summary>`; smaller commits along the way are fine (conventional commits).
6. **Pin versions when you add a dependency.** Check the current stable release at that moment (don't trust memory for library versions/APIs — LangGraph, LangChain, MCP SDK, vLLM, NestJS, OpenSearch clients change fast). Record notable version choices in the milestone file.
7. **Never commit secrets.** Only `.env.example` with placeholders. Real values come from `.env` (gitignored), K8s Secrets, or GCP Secret Manager.
8. **No raw SQL from the LLM. Ever.** LLM-facing data access goes only through MCP tools backed by parameterized query templates (see ADR-0003).
9. **Authorization lives in code, not prompts.** Role and site scoping are enforced in the gateway and again in MCP tools.
10. **Tests with every feature.** pytest for Python, Jest for TypeScript. Prefer testcontainers for Postgres/OpenSearch/Qdrant integration tests.

## Milestone protocol

Use the slash commands in `.claude/commands/`:
- `/start-milestone MXX` — reads the milestone file, restates scope, lists open questions, waits for confirmation, then creates a task list.
- `/finish-milestone MXX` — runs the done-checklist, updates `docs/PROGRESS.md`, writes `docs/interview/MXX.md`, proposes the commit.
- `/interview-notes MXX` — (re)generates the interview notes for a milestone.

At the end of **every** milestone, write `docs/interview/MXX.md` containing:
- 3–5 interview questions this milestone prepares for, each with a crisp model answer (≤120 words)
- Key trade-offs to defend (2–4, each: options, choice, why, when you'd choose differently)
- One "sovereign / on-prem government deployment" note: what changes and why

## Stack (fixed — see ADRs)

| Area | Choice |
|---|---|
| Python | 3.12, `uv` workspace, ruff, mypy (strict on packages), pytest |
| Python services | FastAPI (agent-service), MCP Python SDK over Streamable HTTP (mcp-server) |
| Agents | LangGraph (supervisor + 4 agents), LangChain for model/tool glue, Postgres checkpointer |
| Retrieval | OpenSearch (BM25, `english` + `arabic` analyzers), Qdrant (dense), app-side RRF, cross-encoder rerank |
| Embeddings / rerank | Multilingual (Arabic + English): BGE-M3 class embedder, multilingual cross-encoder reranker. CPU locally. |
| LLM | OpenAI-compatible client; providers `vllm` / `ollama` / `hosted` selected by `LLM_PROVIDER` |
| Gateway | Node LTS, NestJS, TypeScript strict, pnpm, class-validator, Jest |
| DB | PostgreSQL 16, SQLAlchemy 2.x, Alembic |
| Ops | JSON logs, OpenTelemetry, Prometheus, Docker Compose, Helm on kind, GKE docs |
| CI | GitHub Actions |

## Repo layout

```
services/agent-service   FastAPI + LangGraph
services/mcp-server      Python MCP server
services/gateway         NestJS
packages/mineops-core    settings, logging, errors, LLM client, telemetry
packages/mineops-data    models, migrations, synthetic generator
packages/mineops-retrieval  ingestion, BM25/dense/hybrid, rerank
data/corpus              generated SOP/manual markdown (EN + AR)
data/eval                retrieval eval queries + qrels
eval/                    eval harness + result tables
deploy/compose           docker-compose + profiles
deploy/helm              Helm chart(s)
deploy/gcp               GKE + Secret Manager docs
docs/                    SPEC, ARCHITECTURE, adr/, milestones/, interview/, gpu/
scripts/                 demo + helper scripts
```

## Commands (target — implement in M1, keep working after)

```
make setup      # uv sync + pnpm install + pre-commit install
make up         # docker compose up (core profile)
make up-all     # core + search + obs profiles
make down
make migrate    # alembic upgrade head
make seed       # synthetic data -> Postgres (SEED=42 SCALE=medium)
make lint       # ruff + mypy + eslint
make test       # pytest (+ jest once gateway exists)
make fmt
```

## Running in a Claude Code cloud session

- Docker and `docker compose` are available, but nothing runs at session start: run `make up` (or `make up-all`) yourself each session before integration tests.
- Python 3.12 is installed by the environment setup script; always run Python through `uv run`.
- Network is allowlisted. Model downloads use Hugging Face and Ollama hosts; if a download or image pull is blocked, stop and tell the owner which domain to add — don't try workarounds.
- Resources are limited: prefer `SCALE=small` and the small Ollama model for local runs; OpenSearch heap stays at 1g.
- Long downloads (models, images) can exceed the default command timeout; run them with a longer timeout or in the background.

## Code conventions

- Python: type hints everywhere, Pydantic v2 models at every boundary, no bare `except`, raise domain errors that map to the error envelope.
- Error envelope (all services, all languages):
  `{"error": {"code": "STRING_CODE", "message": "human readable", "request_id": "...", "details": {}}}`
- Logs: one JSON object per line with `ts, level, service, request_id, trace_id, msg` + context. Never log tokens, secrets, or full prompts at INFO.
- Config: `pydantic-settings`, env prefix `MINEOPS_`. No config read outside the settings module.
- IDs: UUIDv4 for entities except human-facing codes (`WO-000123`, `INC-000045`, asset tags like `HT-012`).
- Time: store UTC `timestamptz`; site timezone is `Asia/Riyadh` for display/reporting.
- Bilingual text: documents carry `lang: en|ar`. Never machine-translate silently; Arabic docs are authored as Arabic.

## Things to avoid

- Adding services, frameworks, or UIs not in the SPEC.
- Mocking away the thing being tested (e.g., don't mock OpenSearch in retrieval tests — use testcontainers).
- Large refactors outside the active milestone.
- Writing to `docs/adr/` an accepted ADR's decision change without a new superseding ADR.
