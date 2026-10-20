"""Referential and domain integrity after a real migrate + COPY load."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

pytestmark = pytest.mark.integration


def scalar(db: psycopg.Connection[Any], q: str) -> Any:
    row = db.execute(q).fetchone()  # type: ignore[arg-type]
    assert row is not None
    return row[0]


def test_row_counts_match_csv(db: psycopg.Connection[Any], loaded: dict[str, int]) -> None:
    for table, n in loaded.items():
        assert scalar(db, f"SELECT count(*) FROM ops.{table}") == n
    assert loaded["work_orders"] > 0


@pytest.mark.parametrize(
    ("name", "violations_sql"),
    [
        (
            "work order site matches asset site",
            "SELECT count(*) FROM ops.work_orders w JOIN ops.assets a ON a.id = w.asset_id "
            "WHERE a.site_id <> w.site_id",
        ),
        (
            "downtime site matches asset site",
            "SELECT count(*) FROM ops.downtime_events d JOIN ops.assets a ON a.id = d.asset_id "
            "WHERE a.site_id <> d.site_id",
        ),
        (
            "every CM work order has exactly one unplanned downtime event",
            "SELECT count(*) FROM ops.work_orders w WHERE w.wo_type = 'CM' AND (SELECT count(*) "
            "FROM ops.downtime_events d WHERE d.work_order_id = w.id "
            "AND d.reason_code <> 'planned_maintenance') <> 1",
        ),
        (
            "every unplanned downtime event belongs to a CM work order",
            "SELECT count(*) FROM ops.downtime_events d LEFT JOIN ops.work_orders w "
            "ON w.id = d.work_order_id WHERE d.reason_code <> 'planned_maintenance' "
            "AND (w.id IS NULL OR w.wo_type <> 'CM')",
        ),
        (
            "planned downtime comes from a completed PM",
            "SELECT count(*) FROM ops.downtime_events d JOIN ops.work_orders w "
            "ON w.id = d.work_order_id WHERE d.reason_code = 'planned_maintenance' "
            "AND (w.wo_type <> 'PM' OR w.status <> 'completed')",
        ),
        (
            "PM work orders reference a schedule of the same asset",
            "SELECT count(*) FROM ops.work_orders w LEFT JOIN ops.pm_schedules p "
            "ON p.id = w.pm_schedule_id WHERE w.wo_type = 'PM' "
            "AND (p.id IS NULL OR p.asset_id <> w.asset_id)",
        ),
        (
            "assets with an open CM are marked down",
            "SELECT count(*) FROM ops.assets a WHERE a.status <> 'down' AND EXISTS (SELECT 1 "
            "FROM ops.work_orders w WHERE w.asset_id = a.id AND w.wo_type = 'CM' "
            "AND w.status = 'in_progress')",
        ),
        (
            "one production row per site per day, no gaps",
            "SELECT count(*) FROM (SELECT site_id FROM ops.production_daily GROUP BY site_id "
            "HAVING count(*) <> max(date) - min(date) + 1) g",
        ),
        (
            "nothing happens after as_of",
            "SELECT (SELECT count(*) FROM ops.work_orders WHERE opened_at > "
            "(SELECT max(date) + 1 FROM ops.production_daily)) + (SELECT count(*) FROM "
            "ops.safety_incidents WHERE occurred_at > (SELECT max(date) + 1 FROM "
            "ops.production_daily))",
        ),
    ],
)
def test_invariant(db: psycopg.Connection[Any], name: str, violations_sql: str) -> None:
    assert scalar(db, violations_sql) == 0, name


def test_human_codes(db: psycopg.Connection[Any]) -> None:
    assert scalar(db, "SELECT min(code) FROM ops.work_orders") == "WO-000001"
    assert scalar(db, "SELECT min(code) FROM ops.safety_incidents") == "INC-000001"
    assert scalar(db, r"SELECT count(*) FROM ops.assets WHERE tag !~ '^[A-Z]{2}-[0-9]{2,3}$'") == 0


def test_fk_rejects_orphans(db: psycopg.Connection[Any]) -> None:
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute(
            "INSERT INTO ops.downtime_events (site_id, asset_id, started_at, ended_at, "
            "reason_code) SELECT id, gen_random_uuid(), now(), now() + interval '1h', "
            "'mechanical_failure' FROM ops.sites LIMIT 1"
        )


def test_check_constraints_reject_bad_vocab(db: psycopg.Connection[Any]) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE ops.work_orders SET status = 'done' WHERE code = 'WO-000001'")


def test_reload_is_idempotent(conninfo: str, generated: Any, loaded: dict[str, int]) -> None:
    from mineops_data.loader import load

    assert load(conninfo, generated) == loaded
