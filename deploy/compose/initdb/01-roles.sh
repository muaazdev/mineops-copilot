#!/usr/bin/env bash
# Runs once, when the Postgres data volume is first initialised (docker-entrypoint-initdb.d).
# Creates the LOGIN roles with passwords from env. Grants are NOT here: they live in the
# Alembic migration (mineops_data/migrations) so every environment (compose, testcontainers,
# Cloud SQL) gets identical privileges. The migration also creates these roles as NOLOGIN if
# they are missing, so this script only adds the ability to log in.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_ro_pw="$MINEOPS_APP_RO_PASSWORD" \
  -v drafts_rw_pw="$MINEOPS_DRAFTS_RW_PASSWORD" \
  -v agent_rw_pw="$MINEOPS_AGENT_RW_PASSWORD" \
  -v gateway_rw_pw="$MINEOPS_GATEWAY_RW_PASSWORD" <<'SQL'
-- format(%I, %L) quotes identifiers/literals; \gexec runs each generated statement.
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', r.name, r.pw)
FROM (VALUES ('app_ro', :'app_ro_pw'),
             ('drafts_rw', :'drafts_rw_pw'),
             ('agent_rw', :'agent_rw_pw'),
             ('gateway_rw', :'gateway_rw_pw')) AS r(name, pw)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.name)
\gexec
-- Nobody gets to create objects in public.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
SQL
