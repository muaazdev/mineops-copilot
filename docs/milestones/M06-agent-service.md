# M6 — FastAPI agent-service

**Goal:** the graph is served over HTTP with SSE streaming, run status, HITL resume, reports, and eval endpoints; runs in compose (`app` profile).

**Cost:** none.

## Tasks
1. App factory, lifespan (DB pools, MCP client session, retriever warmup), settings subclass.
2. JWT verification dependency via JWKS (test keypair until M7); `CallerContext` injected.
3. `POST /chat` — SSE event types: `token`, `tool_start`, `tool_end`, `citation`, `interrupt`, `final`, `error`; heartbeat comments; client disconnect handling; run_id returned in first event.
4. `GET /runs/{id}` (status: running|interrupted|completed|failed, timestamps, route, pending draft), `POST /runs/{id}/resume`.
5. `POST /reports/{daily|weekly}` (sync for now; note async/job trade-off), `POST /eval/retrieval` (engineer only).
6. Middleware: request ID, structured access log, error envelope handlers (validation, domain, unexpected), body size limit.
7. `/healthz` (process), `/readyz` (DB, MCP, OpenSearch, Qdrant, LLM reachable).
8. Dockerfile (multi-stage, uv, non-root, slim). Compose `app` profile.
9. Tests: httpx AsyncClient + fake LLM; SSE parsing test; resume flow; error envelope shape.

## Done checklist
- [ ] `curl -N` demo for chat and HITL in `docs/demo/m06-curl.md`
- [ ] `docs/interview/M06.md` (SSE vs WebSocket, backpressure/disconnects, async FastAPI pitfalls, long-running jobs; sovereign note)
