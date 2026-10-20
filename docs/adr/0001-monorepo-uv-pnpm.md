# ADR-0001: Monorepo with uv workspace (Python) and pnpm (gateway)

- Status: Accepted
- Date: 2026-10-20

## Context
Three services and three shared Python packages must evolve together; reviewers should see the whole system in one repo.

## Decision
Single repo. Python packages and services are members of one `uv` workspace (one lockfile). The NestJS gateway is a standalone pnpm project under `services/gateway`. A root Makefile is the single entrypoint.

## Alternatives considered
- Polyrepo — realistic for large orgs but bad for a portfolio and for atomic cross-service changes.
- Poetry — slower, weaker workspace support than uv.
- Nx/Turborepo across both languages — overkill for one TS project.

## Consequences
- Shared code (logging, errors, LLM client) is imported, not copied.
- Docker builds must copy the workspace root + the relevant members; use multi-stage builds with `uv sync --package`.

## Revisit when
A service needs an independent release cadence or team ownership.
