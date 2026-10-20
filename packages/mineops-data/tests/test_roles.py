"""Least-privilege checks. ``SET ROLE`` makes Postgres evaluate privileges as that role."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

pytestmark = pytest.mark.integration

Denied = psycopg.errors.InsufficientPrivilege


def as_role(db: psycopg.Connection[Any], role: str) -> None:
    db.execute(f"SET ROLE {role}")


def first_asset(db: psycopg.Connection[Any]) -> tuple[Any, Any]:
    row = db.execute("SELECT id, site_id FROM ops.assets ORDER BY tag LIMIT 1").fetchone()
    assert row is not None
    return row[0], row[1]


def test_app_ro_can_read_ops(db: psycopg.Connection[Any]) -> None:
    as_role(db, "app_ro")
    row = db.execute("SELECT count(*) FROM ops.work_orders").fetchone()
    assert row is not None and row[0] > 0


@pytest.mark.parametrize(
    "stmt",
    [
        "INSERT INTO ops.sites (code, name_en, name_ar, commodity, mine_type, grade_unit) "
        "VALUES ('XXX', 'x', 'x', 'gold', 'open_pit', 'g/t')",
        "UPDATE ops.work_orders SET status = 'cancelled' WHERE code = 'WO-000001'",
        "DELETE FROM ops.safety_incidents",
        "INSERT INTO ops.work_order_drafts (site_id, asset_id, wo_type, priority, title, "
        "description, lang, requested_by) SELECT site_id, id, 'CM', 'high', 't', 'd', 'en', 'x' "
        "FROM ops.assets LIMIT 1",
        "CREATE TABLE ops.sneaky (id int)",
        "SELECT * FROM audit.tool_calls",
    ],
)
def test_app_ro_cannot_write(db: psycopg.Connection[Any], stmt: str) -> None:
    as_role(db, "app_ro")
    with pytest.raises(Denied):
        db.execute(stmt)


def test_drafts_rw_can_create_and_update_draft(db: psycopg.Connection[Any]) -> None:
    asset_id, site_id = first_asset(db)
    as_role(db, "drafts_rw")
    row = db.execute(
        "INSERT INTO ops.work_order_drafts (site_id, asset_id, wo_type, priority, title, "
        "description, lang, requested_by) VALUES (%s, %s, 'CM', 'high', 'Vibration', "
        "'High vibration on crusher', 'en', 'op-1') RETURNING id",
        (site_id, asset_id),
    ).fetchone()
    assert row is not None
    db.execute(
        "UPDATE ops.work_order_drafts SET state = 'approved', approver = 'eng-1', "
        "decided_at = now() WHERE id = %s",
        (row[0],),
    )


@pytest.mark.parametrize(
    "stmt",
    [
        "SELECT * FROM ops.work_orders",
        "UPDATE ops.work_orders SET status = 'cancelled'",
        "INSERT INTO ops.work_orders (code) VALUES ('WO-999999')",
        "DELETE FROM ops.work_order_drafts",
        "SELECT * FROM ops.safety_incidents",
    ],
)
def test_drafts_rw_cannot_touch_other_tables(db: psycopg.Connection[Any], stmt: str) -> None:
    as_role(db, "drafts_rw")
    with pytest.raises(Denied):
        db.execute(stmt)


@pytest.mark.parametrize("role", ["app_ro", "drafts_rw"])
def test_audit_is_append_only(db: psycopg.Connection[Any], role: str) -> None:
    as_role(db, role)
    db.execute(
        "INSERT INTO audit.tool_calls (caller_sub, caller_role, tool, status) "
        "VALUES ('u1', 'operator', 'get_kpis', 'ok')"
    )
    with pytest.raises(Denied):
        db.execute("UPDATE audit.tool_calls SET status = 'error'")


@pytest.mark.parametrize(
    ("role", "stmt"),
    [
        ("agent_rw", "SELECT * FROM ops.sites"),
        ("gateway_rw", "SELECT * FROM ops.sites"),
        ("app_ro", "CREATE TABLE agent.x (id int)"),
        ("app_ro", "CREATE TABLE public.x (id int)"),
    ],
)
def test_schema_isolation(db: psycopg.Connection[Any], role: str, stmt: str) -> None:
    as_role(db, role)
    with pytest.raises(Denied):
        db.execute(stmt)


def test_agent_rw_can_create_checkpoint_tables(db: psycopg.Connection[Any]) -> None:
    as_role(db, "agent_rw")
    db.execute("CREATE TABLE agent.checkpoints_probe (id int)")
    db.execute("INSERT INTO agent.checkpoints_probe VALUES (1)")


def test_default_privileges_cover_future_tables(db: psycopg.Connection[Any]) -> None:
    db.execute("CREATE TABLE ops.future_table (id int)")
    db.execute("INSERT INTO ops.future_table VALUES (1)")
    as_role(db, "app_ro")
    assert db.execute("SELECT count(*) FROM ops.future_table").fetchone() == (1,)
    db.execute("RESET ROLE")
    as_role(db, "drafts_rw")
    with pytest.raises(Denied):
        db.execute("SELECT * FROM ops.future_table")


def test_llm_roles_have_statement_timeout(db: psycopg.Connection[Any]) -> None:
    rows = db.execute(
        "SELECT r.rolname, s.setconfig FROM pg_db_role_setting s "
        "JOIN pg_roles r ON r.oid = s.setrole WHERE r.rolname IN ('app_ro', 'drafts_rw')"
    ).fetchall()
    assert {r[0] for r in rows} == {"app_ro", "drafts_rw"}
    assert all("statement_timeout=5s" in r[1] for r in rows)
