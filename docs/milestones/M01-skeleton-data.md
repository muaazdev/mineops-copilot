# M1 — Repo skeleton, compose, Postgres schema, synthetic data, CI

**Goal:** a clean clone can run `make setup && make up && make migrate && make seed && make test` and end with a populated Postgres containing realistic data and documented anomalies.

**Cost:** none.

## Tasks

### 1. Workspace & tooling
- Root `pyproject.toml` as a `uv` workspace with members: `packages/*`, `services/agent-service`, `services/mcp-server` (services can be empty stubs with a `pyproject.toml` and `src/` package for now).
- Python 3.12 (`.python-version`). Dev deps: ruff, mypy, pytest, pytest-cov, testcontainers[postgres].
- `ruff` config (line length 100, isort, pyupgrade, bugbear, simplify). `mypy --strict` on `packages/`.
- `.pre-commit-config.yaml`: ruff, ruff-format, end-of-file, trailing-whitespace, check-yaml, detect-private-key.
- `.editorconfig`, extend existing `.gitignore` (`.env`, `.venv`, `node_modules`, `data/generated/`, `eval/results/raw/`).
- `LICENSE` (MIT, owner: muaazdev).
- `Makefile` with targets listed in CLAUDE.md (`setup, up, up-all, down, migrate, seed, lint, test, fmt`). `pnpm` steps are no-ops until M7.

### 2. `packages/mineops-core`
- `settings.py`: `pydantic-settings` base `MineOpsSettings` with env prefix `MINEOPS_`; sub-settings for `db`, `log`. Services subclass it later.
- `logging.py`: JSON logging (stdlib `logging` + a JSON formatter, or structlog — pick one, record choice), fields `ts, level, service, request_id, trace_id, msg`; `request_id` via `contextvars`.
- `errors.py`: `ErrorEnvelope` Pydantic model and base `MineOpsError(code, message, http_status, details)`.
- Unit tests for each.

### 3. docker-compose (`deploy/compose/docker-compose.yml`)
- Profiles: `core` (postgres), `search` (opensearch single-node, security plugin disabled **for local only** with a loud comment, opensearch-dashboards optional; qdrant), `obs` placeholder (add in M8).
- Postgres 16 with healthcheck, named volume, init script that creates DB roles (see task 4) using env passwords.
- OpenSearch: `discovery.type=single-node`, JVM heap 1g, `bootstrap.memory_lock`, ulimits; healthcheck on `_cluster/health`.
- Qdrant: healthcheck on `/readyz`.
- `.env.example` with every variable and safe placeholders.
- `make up` = core profile; `make up-all` = core+search.

### 4. `packages/mineops-data` — schema
- SQLAlchemy 2.x typed models + Alembic (migrations live in this package; `alembic.ini` at package root).
- Schemas per ADR-0009: `ops`, `auth`, `agent`, `audit` (create all four now; only `ops` gets tables in M1 besides `audit.tool_calls` stub).
- `ops` tables: `sites`, `assets`, `pm_schedules`, `work_orders`, `downtime_events`, `production_daily`, `safety_incidents`, `work_order_drafts`.
- Use Postgres enums or check constraints for status/priority/severity; `timestamptz` everywhere; FKs with sensible `ON DELETE`.
- Human codes: `work_orders.code` (`WO-000123`), `safety_incidents.code` (`INC-000045`), `assets.tag` (`HT-012`, `CR-03`, ...). Unique constraints.
- Indexes driven by the planned MCP tools (document each index with the tool it serves): e.g. `work_orders (site_id, status, due_at)`, `production_daily (site_id, date)`, `safety_incidents (site_id, occurred_at)`.
- Roles & grants (in a migration or init SQL, idempotent): `app_ro` SELECT on `ops.*` except write on nothing; `drafts_rw` INSERT/UPDATE on `ops.work_order_drafts` + SELECT on `ops.assets`; `agent_rw` on `agent.*`; `gateway_rw` on `auth.*`. Default privileges so future tables are covered.

### 5. Synthetic data generator
- CLI: `uv run mineops-data generate --seed 42 --scale small|medium --out data/generated/` and `uv run mineops-data load --from data/generated/`. `make seed` runs both.
- Deterministic (seeded numpy RNG + Faker with seed). Same seed → byte-identical CSVs.
- Scale `medium`: 3 sites, ~120 assets, 18 months daily production, ~5k work orders, ~300 incidents, downtime events consistent with CM work orders. `small` ≈ 10% for fast tests.
- Realism: production follows seasonality + noise; availability drops when downtime is high; CM WOs follow failures; PM WOs follow `pm_schedules`.
- Bilingual: site and asset display names have `name_en` and `name_ar` (fictional). Incident/WO descriptions mostly English, ~25% Arabic.
- Fictional names only — e.g. sites "Falcon Ridge North Pit", "Wadi Sahm Phosphate", "Jabal Noor Underground" (invent; no real mines).
- Inject the 4 anomalies from SPEC §4 and write `data/generated/ground_truth.json` describing each (site/asset/date range/expected signal).
- Load via `COPY` (psycopg 3) inside one transaction; truncate-and-reload is fine.

### 6. Tests
- Generator determinism (hash of outputs for seed 42 small).
- Referential integrity after load (testcontainers Postgres + run migrations).
- Each injected anomaly is detectable with a plain SQL query (these queries become MCP tool templates later — keep them in `packages/mineops-data/src/mineops_data/queries/` as named, parameterized SQL).
- Role checks: `app_ro` cannot INSERT; `drafts_rw` cannot touch `work_orders`.

### 7. CI (`.github/workflows/ci.yml`)
- On push/PR: setup uv (cache), `uv sync`, ruff, mypy, pytest (Docker available on ubuntu runners for testcontainers).
- Keep under ~5 minutes.

### 8. Docs
- Update `README.md` with a short quickstart (setup → up → migrate → seed → test) and link to SPEC/ARCHITECTURE.
- `docs/data-model.md`: ER diagram (Mermaid `erDiagram`) + anomaly table.

## Done checklist
- [ ] Fresh clone: `make setup && make up && make migrate && make seed && make test` passes
- [ ] `make lint` clean
- [ ] CI green on GitHub
- [ ] `ground_truth.json` anomalies all detected by tests
- [ ] `docs/data-model.md` written
- [ ] `docs/interview/M01.md` written (Postgres roles & least privilege, synthetic data design, uv workspace, testcontainers vs mocks; sovereign note)
- [ ] `docs/PROGRESS.md` updated, commit `feat(m01): ...`
