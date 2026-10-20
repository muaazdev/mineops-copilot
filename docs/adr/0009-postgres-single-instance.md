# ADR-0009: One PostgreSQL instance, separate schemas and roles

- Status: Accepted
- Date: 2026-10-20

## Context
Domain data, gateway users/audit, and LangGraph checkpoints all need durable storage.

## Decision
One Postgres 16 instance. Schemas: `ops` (domain), `auth` (users, gateway audit), `agent` (LangGraph checkpoints, run metadata), `audit` (MCP tool calls). Roles: `owner` (migrations), `app_ro`, `drafts_rw`, `agent_rw`, `gateway_rw` — each with grants only on its schema/tables.

## Alternatives considered
- Separate databases per service — purer isolation, more ops overhead for a demo.
- Redis for checkpoints — fast but not durable by default; HITL approvals must survive restarts.

## Consequences
- Simple local ops; role grants provide the isolation that matters.
- In production, split to separate instances (Cloud SQL) per service if blast radius warrants it.

## Revisit when
Checkpoint write volume competes with domain queries.
