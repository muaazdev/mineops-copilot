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

## Notes (implementation, 2026-10-20)

### Decisions agreed at start
- `ground_truth.json` is a generated artefact: `data/generated/ground_truth.json` (gitignored, rebuilt by `make seed`). SPEC §4 wording updated to match.
- **Owner role:** compose `POSTGRES_USER=mineops_owner` (superuser *locally only*) runs migrations and seeding. `deploy/compose/initdb/01-roles.sh` creates the LOGIN roles with passwords from `.env`. Alembic migration `0002` owns every grant and default privilege, and creates any missing role as NOLOGIN, so testcontainers and Cloud SQL get identical privileges.
- **`audit_writer`:** a NOLOGIN group role with INSERT only on `audit.tool_calls`, granted to `app_ro` and `drafts_rw`. It narrows ADR-0009's role list without changing the decision, so there is no superseding ADR. `app_ro` stays read-only on `ops`.

### Other choices
- **Logging:** stdlib `logging` plus a small JSON formatter (`mineops_core/logging.py`), not structlog. It adds no dependency, and OpenTelemetry log instrumentation (M8) hooks into stdlib.
- **Vocabularies:** `varchar(32)` + named CHECK constraints instead of native PG enums, so they evolve through normal transactional migrations.
- **Migration 0001:** autogenerated from the models, then hand-cleaned (duplicate enum CHECKs removed, schema create/drop added). `alembic check` reports no drift.
- **Faker dropped:** all text comes from authored bilingual templates (`texts.py`), so one numpy `Generator` drives everything, UUIDs included. That makes the byte-identical guarantee trivial.
- **Fixed end date:** the generator's window ends on 2026-09-30 by default, so output never depends on today's date. The golden SHA-256 for seed 42 / small is pinned in `tests/test_generator.py`.
- **LLM-facing roles:** `app_ro` and `drafts_rw` get `statement_timeout=5s` and `idle_in_transaction_session_timeout=30s`.
- **CLI:** `mineops-data generate` / `mineops-data load --from` use typer; the load is a single-transaction TRUNCATE + `COPY`.

### Pinned versions (checked on PyPI / Docker Hub, 2026-10-20)
| Dependency | Version |
|---|---|
| uv | 0.11.32 (CI pin) |
| ruff | 0.17.1 (also the pre-commit hook rev) |
| mypy | 2.4.0 |
| pytest | 9.1.1 |
| pytest-cov | 7.1.0 |
| testcontainers[postgres] | 4.15.0 (`testcontainers.community.postgres`) |
| pre-commit | 4.7.0 (pre-commit-hooks v6.0.0) |
| pydantic | 2.14.1 |
| pydantic-settings | 2.16.0 |
| SQLAlchemy | 2.1.5 |
| alembic | 1.20.0 |
| psycopg[binary] | 3.3.6 |
| numpy | 2.5.4 |
| typer | 0.27.3 |
| hatchling | 1.32.4 |
| Image: `postgres` | 16.15 |
| Image: `opensearchproject/opensearch` | 3.9.0 |
| Image: `opensearchproject/opensearch-dashboards` | 3.9.0 (optional `dashboards` profile) |
| Image: `qdrant/qdrant` | v1.19.2 |
| GitHub Action: `actions/checkout` | v7.0.1 |
| GitHub Action: `astral-sh/setup-uv` | v10.3.0 |
