# ADR-0003: LLM never writes SQL; data access only via parameterized MCP tools

- Status: Accepted
- Date: 2026-10-20

## Context
Ops data lives in Postgres. Text-to-SQL is flexible but hard to secure (injection through prompts, data exfiltration across sites, expensive queries) — unacceptable for a government deployment.

## Decision
Every data access the LLM can trigger is an MCP tool backed by a fixed, parameterized query template. Arguments are Pydantic-validated (enums, date ranges, limits). Tools run under least-privilege DB roles: `app_ro` (SELECT on domain tables) and `drafts_rw` (INSERT/UPDATE on `work_order_drafts` only). Each tool enforces caller role and site scope, applies row limits and statement timeouts, and writes an audit record.

## Alternatives considered
- Text-to-SQL with validation/allow-listing — flexible but the attack surface is the whole schema.
- Text-to-SQL against read-only views — better, still allows expensive or cross-scope queries.

## Consequences
- New questions sometimes need a new tool; that is the intended control point.
- Tool catalog doubles as the documented "what the AI can see" for auditors.

## Revisit when
Analysts need ad-hoc exploration — then add a separate, sandboxed text-to-SQL tool over a curated semantic layer, behind its own role.
