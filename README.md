# MineOps Copilot

An AI operations copilot for **Falcon Ridge Mining**, a fictional mining company. It answers SOP questions with citations in Arabic and English, queries production, maintenance, and safety data through governed MCP tools, writes executive reports, and drafts work orders behind human approval.

> All data is synthetic. Status: spec approved, Milestone 1 in progress. See [`docs/PROGRESS.md`](docs/PROGRESS.md).

**Stack:** Python · FastAPI · LangGraph/LangChain · hybrid RAG (OpenSearch BM25 + Qdrant + RRF + cross-encoder) · MCP · vLLM / Ollama · NestJS/TypeScript · PostgreSQL · Docker · Helm/Kubernetes · GCP (docs) · OpenTelemetry · Prometheus

## Docs
- [Specification](docs/SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Architecture decision records](docs/adr/)
- [Milestones](docs/milestones/)
- [Interview notes](docs/interview/)

## Building with Claude Code
This repo is built milestone by milestone with Claude Code. [`CLAUDE.md`](CLAUDE.md) holds the working rules.
- `/start-milestone M01` — restate scope, surface questions, then build
- `/finish-milestone M01` — verify, write interview notes, update progress
- `/interview-notes M02` — regenerate notes for a milestone

## Quickstart

Needs Docker, [uv](https://docs.astral.sh/uv/) and GNU make. Python 3.12 is installed by uv.

```bash
make setup     # uv sync, pre-commit hooks, creates .env from .env.example
make up        # Postgres 16 (compose profile "core"); make up-all adds OpenSearch + Qdrant
make migrate   # alembic upgrade head: schemas, tables, least-privilege roles/grants
make seed      # deterministic synthetic data (SEED=42 SCALE=medium; SCALE=small is faster)
make test      # pytest; integration tests start their own Postgres via testcontainers
make lint      # ruff + mypy --strict
make down
```

Data model, roles and the injected anomalies: [`docs/data-model.md`](docs/data-model.md).

### Retrieval (M2)

```bash
make up-all            # + OpenSearch 3.9 and Qdrant 1.19 (RESTRICTED=1 on constrained hosts)
make corpus            # re-render data/corpus/ from the authored YAML (already committed)
make ingest            # chunk -> BGE-M3 embeddings -> OpenSearch (BM25 en/ar) + Qdrant
uv run mineops-retrieval search "crusher bearing temperature trip" --site FRN
make eval-retrieval    # BM25 / dense / hybrid / hybrid+rerank -> eval/results/retrieval.md
```

First use downloads `BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3` (~4.4 GB, pinned revisions).
Results and analysis: [`eval/results/retrieval.md`](eval/results/retrieval.md).
