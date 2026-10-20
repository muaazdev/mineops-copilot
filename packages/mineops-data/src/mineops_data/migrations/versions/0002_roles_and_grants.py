"""Least-privilege roles and grants (ADR-0003, ADR-0009).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20

Roles are cluster-wide, so they are created only if missing (NOLOGIN). In compose the init
script has already created them with LOGIN + password; on Cloud SQL an operator does the same
from Secret Manager. Either way this migration owns *what each role may do*:

    app_ro        SELECT on ops.*                         (MCP read tools)
    drafts_rw     SELECT ops.assets, SELECT/INSERT/UPDATE ops.work_order_drafts
    agent_rw      full DML + CREATE in schema agent       (LangGraph checkpointer creates tables)
    gateway_rw    full DML on auth.*
    audit_writer  INSERT only on audit.tool_calls; NOLOGIN group role granted to app_ro and
                  drafts_rw so every MCP tool can write its audit row, but none can read or
                  rewrite the trail.

Default privileges make tables added by later migrations (run by the same owner) inherit the
schema-level grants. Every statement is idempotent: re-running upgrade is safe.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ("app_ro", "drafts_rw", "agent_rw", "gateway_rw", "audit_writer")

# All identifiers below are constants from this file, never user input.
GRANTS = """
-- Lock down: no implicit access for PUBLIC to our schemas.
REVOKE ALL ON SCHEMA ops, auth, agent, audit FROM PUBLIC;

-- app_ro: read-only on the domain schema.
GRANT USAGE ON SCHEMA ops TO app_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA ops TO app_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA ops GRANT SELECT ON TABLES TO app_ro;

-- drafts_rw: only what create_work_order_draft / approve need. Explicit table list, no
-- default privileges, so a new ops table never becomes writable by accident.
GRANT USAGE ON SCHEMA ops TO drafts_rw;
GRANT SELECT ON ops.assets, ops.sites TO drafts_rw;
GRANT SELECT, INSERT, UPDATE ON ops.work_order_drafts TO drafts_rw;

-- agent_rw: owns its own schema's data; may create checkpoint tables.
GRANT USAGE, CREATE ON SCHEMA agent TO agent_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA agent TO agent_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA agent TO agent_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA agent
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agent_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA agent GRANT USAGE, SELECT ON SEQUENCES TO agent_rw;

-- gateway_rw: users + gateway audit.
GRANT USAGE ON SCHEMA auth TO gateway_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA auth TO gateway_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA auth TO gateway_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gateway_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth GRANT USAGE, SELECT ON SEQUENCES TO gateway_rw;

-- audit_writer: append-only audit trail.
GRANT USAGE ON SCHEMA audit TO audit_writer;
GRANT INSERT ON audit.tool_calls TO audit_writer;
GRANT audit_writer TO app_ro, drafts_rw;

-- Guard rails on the LLM-facing roles: bounded statements, no idle-in-transaction holders.
ALTER ROLE app_ro SET statement_timeout = '5s';
ALTER ROLE drafts_rw SET statement_timeout = '5s';
ALTER ROLE app_ro SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE drafts_rw SET idle_in_transaction_session_timeout = '30s';
"""

REVOKES = """
REVOKE audit_writer FROM app_ro, drafts_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA ops REVOKE SELECT ON TABLES FROM app_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA agent
    REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM agent_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA agent REVOKE USAGE, SELECT ON SEQUENCES FROM agent_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth
    REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM gateway_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA auth REVOKE USAGE, SELECT ON SEQUENCES FROM gateway_rw;
REVOKE ALL ON ALL TABLES IN SCHEMA ops, auth, agent, audit
    FROM app_ro, drafts_rw, agent_rw, gateway_rw, audit_writer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA auth, agent FROM agent_rw, gateway_rw;
REVOKE ALL ON SCHEMA ops, auth, agent, audit
    FROM app_ro, drafts_rw, agent_rw, gateway_rw, audit_writer;
"""


def upgrade() -> None:
    for role in ROLES:
        op.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
            f"THEN CREATE ROLE {role} NOLOGIN; END IF; END $$"
        )
    op.execute(GRANTS)


def downgrade() -> None:
    # Roles are left in place: they are cluster-wide and may hold LOGIN/passwords set outside
    # Alembic. Only the privileges this migration granted are removed.
    op.execute(REVOKES)
