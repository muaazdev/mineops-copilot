# M8 — Observability + security hardening

**Goal:** one trace spans gateway → agent-service → mcp-server → Postgres/LLM; metrics dashboards exist; a security checklist is satisfied and documented.

**Cost:** none.

## Tasks
1. OpenTelemetry: Python (FastAPI, httpx, SQLAlchemy/psycopg, custom spans for retrieval stages, LLM calls, tool calls) and Node (Nest/HTTP) → OTel Collector → Jaeger (compose `obs` profile). W3C `traceparent` propagated; `trace_id` in logs.
2. Prometheus metrics: HTTP RED, LLM latency/tokens/errors by provider, retrieval latency by stage, tool calls by tool/outcome, HITL pending count. Grafana dashboard JSON committed.
3. GenAI-specific telemetry: prompt/response sizes, model, route — without logging content at INFO; optional DEBUG content logging behind a flag.
4. Security hardening checklist (document in `docs/security.md`):
   - secrets only via env/secret mounts; `.env` never committed; gitleaks in CI
   - CORS policy, security headers (helmet), body size limits, timeouts everywhere
   - prompt-injection mitigations: tool allow-list per agent, retrieved text treated as data, no tool can be called with LLM-chosen identity
   - output validation before tool calls; max tool calls per run
   - dependency scanning (pip-audit, pnpm audit), container scanning (trivy) in CI
   - DB: least-privilege roles verified by tests; statement timeouts
   - audit log coverage for every data access and approval
5. Threat model table (STRIDE-lite) for the trust boundaries in ARCHITECTURE.md.

## Done checklist
- [ ] Screenshot/export of one end-to-end trace in `docs/demo/`
- [ ] `docs/security.md` complete
- [ ] `docs/interview/M08.md` (OTel concepts, sampling, cardinality, LLM observability, prompt injection defenses, audit; sovereign note: data residency of telemetry, on-prem collectors)
