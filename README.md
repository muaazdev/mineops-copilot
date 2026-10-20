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

Quickstart arrives with Milestone 1.
