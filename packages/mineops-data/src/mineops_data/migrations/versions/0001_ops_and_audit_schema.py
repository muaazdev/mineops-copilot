"""ops and audit schema

Revision ID: 0001
Revises:
Create Date: 2026-10-20

Creates the four schemas (ADR-0009) and the M1 tables. Vocab columns are varchar(32) with
CHECK constraints named ck_<table>_<vocab> (see models.py).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = ("ops", "auth", "agent", "audit")


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("caller_sub", sa.Text(), nullable=False),
        sa.Column("caller_role", sa.Text(), nullable=False),
        sa.Column("tool", sa.Text(), nullable=False),
        sa.Column(
            "args",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_calls")),
        schema="audit",
    )
    op.create_index(
        "ix_tool_calls_caller_ts", "tool_calls", ["caller_sub", "ts"], unique=False, schema="audit"
    )
    op.create_index("ix_tool_calls_ts", "tool_calls", ["ts"], unique=False, schema="audit")
    op.create_table(
        "sites",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column("name_ar", sa.Text(), nullable=False),
        sa.Column("commodity", sa.String(length=32), nullable=False),
        sa.Column("mine_type", sa.String(length=32), nullable=False),
        sa.Column("grade_unit", sa.String(length=16), nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default=sa.text("'Asia/Riyadh'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "commodity IN ('gold', 'phosphate', 'copper')", name=op.f("ck_sites_commodity")
        ),
        sa.CheckConstraint(
            "mine_type IN ('open_pit', 'underground')", name=op.f("ck_sites_mine_type")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sites")),
        sa.UniqueConstraint("code", name=op.f("uq_sites_code")),
        schema="ops",
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tag", sa.String(length=16), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column("name_ar", sa.Text(), nullable=False),
        sa.Column("criticality", sa.SmallInteger(), nullable=False),
        sa.Column("commissioned_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "asset_type IN ('haul_truck', 'excavator', 'crusher', 'conveyor', 'pump', 'drill')",
            name=op.f("ck_assets_asset_type"),
        ),
        sa.CheckConstraint(
            "status IN ('operational', 'down', 'maintenance', 'retired')",
            name=op.f("ck_assets_asset_status"),
        ),
        sa.CheckConstraint("criticality BETWEEN 1 AND 3", name=op.f("ck_assets_criticality_range")),
        sa.ForeignKeyConstraint(
            ["site_id"], ["ops.sites.id"], name=op.f("fk_assets_site_id_sites"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint("tag", name=op.f("uq_assets_tag")),
        schema="ops",
    )
    op.create_index(
        "ix_assets_site_type", "assets", ["site_id", "asset_type"], unique=False, schema="ops"
    )
    op.create_table(
        "production_daily",
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("ore_tonnes", sa.Numeric(precision=12, scale=1), nullable=False),
        sa.Column("target_tonnes", sa.Numeric(precision=12, scale=1), nullable=False),
        sa.Column("grade", sa.Numeric(precision=8, scale=3), nullable=False),
        sa.Column("availability_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("utilization_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.CheckConstraint(
            "availability_pct BETWEEN 0 AND 100",
            name=op.f("ck_production_daily_availability_range"),
        ),
        sa.CheckConstraint(
            "ore_tonnes >= 0 AND target_tonnes > 0", name=op.f("ck_production_daily_tonnes_valid")
        ),
        sa.CheckConstraint(
            "utilization_pct BETWEEN 0 AND 100", name=op.f("ck_production_daily_utilization_range")
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["ops.sites.id"],
            name=op.f("fk_production_daily_site_id_sites"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("site_id", "date", name=op.f("pk_production_daily")),
        schema="ops",
    )
    op.create_table(
        "pm_schedules",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("task_en", sa.Text(), nullable=False),
        sa.Column("task_ar", sa.Text(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("last_done_on", sa.Date(), nullable=True),
        sa.Column("next_due_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("interval_days > 0", name=op.f("ck_pm_schedules_interval_positive")),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["ops.assets.id"],
            name=op.f("fk_pm_schedules_asset_id_assets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pm_schedules")),
        schema="ops",
    )
    op.create_index(
        op.f("ix_ops_pm_schedules_asset_id"),
        "pm_schedules",
        ["asset_id"],
        unique=False,
        schema="ops",
    )
    op.create_table(
        "safety_incidents",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shift", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("lang", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('vehicle_interaction', 'slip_trip_fall', 'equipment', 'ground_control', 'electrical', 'fatigue', 'hazardous_substance')",
            name=op.f("ck_safety_incidents_category"),
        ),
        sa.CheckConstraint("code ~ '^INC-[0-9]{6}$'", name=op.f("ck_safety_incidents_code_format")),
        sa.CheckConstraint("lang IN ('en', 'ar')", name=op.f("ck_safety_incidents_lang")),
        sa.CheckConstraint(
            "severity IN ('near_miss', 'first_aid', 'medical_treatment', 'lost_time')",
            name=op.f("ck_safety_incidents_severity"),
        ),
        sa.CheckConstraint("shift IN ('day', 'night')", name=op.f("ck_safety_incidents_shift")),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["ops.assets.id"],
            name=op.f("fk_safety_incidents_asset_id_assets"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["ops.sites.id"],
            name=op.f("fk_safety_incidents_site_id_sites"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_safety_incidents")),
        sa.UniqueConstraint("code", name=op.f("uq_safety_incidents_code")),
        schema="ops",
    )
    op.create_index(
        "ix_incidents_site_occurred",
        "safety_incidents",
        ["site_id", "occurred_at"],
        unique=False,
        schema="ops",
    )
    op.create_table(
        "work_orders",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("pm_schedule_id", sa.UUID(), nullable=True),
        sa.Column("wo_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignee_role", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("lang", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status IN ('completed','cancelled')) = (closed_at IS NOT NULL)",
            name=op.f("ck_work_orders_closed_iff_terminal"),
        ),
        sa.CheckConstraint(
            "assignee_role IN ('mechanic', 'electrician', 'hydraulics_tech', 'inspector')",
            name=op.f("ck_work_orders_assignee_role"),
        ),
        sa.CheckConstraint("code ~ '^WO-[0-9]{6}$'", name=op.f("ck_work_orders_code_format")),
        sa.CheckConstraint("lang IN ('en', 'ar')", name=op.f("ck_work_orders_lang")),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name=op.f("ck_work_orders_priority"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'on_hold', 'completed', 'cancelled')",
            name=op.f("ck_work_orders_wo_status"),
        ),
        sa.CheckConstraint(
            "wo_type IN ('PM', 'CM', 'inspection')", name=op.f("ck_work_orders_wo_type")
        ),
        sa.CheckConstraint(
            "closed_at IS NULL OR closed_at >= opened_at",
            name=op.f("ck_work_orders_closed_after_open"),
        ),
        sa.CheckConstraint("due_at >= opened_at", name=op.f("ck_work_orders_due_after_open")),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["ops.assets.id"],
            name=op.f("fk_work_orders_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pm_schedule_id"],
            ["ops.pm_schedules.id"],
            name=op.f("fk_work_orders_pm_schedule_id_pm_schedules"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["ops.sites.id"],
            name=op.f("fk_work_orders_site_id_sites"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_orders")),
        sa.UniqueConstraint("code", name=op.f("uq_work_orders_code")),
        schema="ops",
    )
    op.create_index(
        "ix_work_orders_asset_type_opened",
        "work_orders",
        ["asset_id", "wo_type", "opened_at"],
        unique=False,
        schema="ops",
    )
    op.create_index(
        "ix_work_orders_site_status_due",
        "work_orders",
        ["site_id", "status", "due_at"],
        unique=False,
        schema="ops",
    )
    op.create_table(
        "downtime_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("work_order_id", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reason_code IN ('mechanical_failure', 'electrical_failure', 'hydraulic_failure', 'planned_maintenance', 'operational_delay')",
            name=op.f("ck_downtime_events_reason_code"),
        ),
        sa.CheckConstraint(
            "ended_at > started_at", name=op.f("ck_downtime_events_end_after_start")
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["ops.assets.id"],
            name=op.f("fk_downtime_events_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["ops.sites.id"],
            name=op.f("fk_downtime_events_site_id_sites"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["ops.work_orders.id"],
            name=op.f("fk_downtime_events_work_order_id_work_orders"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_downtime_events")),
        schema="ops",
    )
    op.create_index(
        "ix_downtime_asset_started",
        "downtime_events",
        ["asset_id", "started_at"],
        unique=False,
        schema="ops",
    )
    op.create_index(
        "ix_downtime_site_started",
        "downtime_events",
        ["site_id", "started_at"],
        unique=False,
        schema="ops",
    )
    op.create_index(
        op.f("ix_ops_downtime_events_work_order_id"),
        "downtime_events",
        ["work_order_id"],
        unique=False,
        schema="ops",
    )
    op.create_table(
        "work_order_drafts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("wo_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("lang", sa.String(length=32), nullable=False),
        sa.Column(
            "state", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("approver", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("promoted_work_order_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(state = 'pending') = (decided_at IS NULL)",
            name=op.f("ck_work_order_drafts_decided_iff_not_pending"),
        ),
        sa.CheckConstraint("lang IN ('en', 'ar')", name=op.f("ck_work_order_drafts_lang")),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name=op.f("ck_work_order_drafts_priority"),
        ),
        sa.CheckConstraint(
            "state <> 'rejected' OR reject_reason IS NOT NULL",
            name=op.f("ck_work_order_drafts_reject_needs_reason"),
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'approved', 'rejected')",
            name=op.f("ck_work_order_drafts_draft_state"),
        ),
        sa.CheckConstraint(
            "wo_type IN ('PM', 'CM', 'inspection')", name=op.f("ck_work_order_drafts_wo_type")
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["ops.assets.id"],
            name=op.f("fk_work_order_drafts_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["promoted_work_order_id"],
            ["ops.work_orders.id"],
            name=op.f("fk_work_order_drafts_promoted_work_order_id_work_orders"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["ops.sites.id"],
            name=op.f("fk_work_order_drafts_site_id_sites"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_order_drafts")),
        schema="ops",
    )
    op.create_index(
        "ix_drafts_site_state_created",
        "work_order_drafts",
        ["site_id", "state", "created_at"],
        unique=False,
        schema="ops",
    )


def downgrade() -> None:
    op.drop_index("ix_drafts_site_state_created", table_name="work_order_drafts", schema="ops")
    op.drop_table("work_order_drafts", schema="ops")
    op.drop_index(
        op.f("ix_ops_downtime_events_work_order_id"), table_name="downtime_events", schema="ops"
    )
    op.drop_index("ix_downtime_site_started", table_name="downtime_events", schema="ops")
    op.drop_index("ix_downtime_asset_started", table_name="downtime_events", schema="ops")
    op.drop_table("downtime_events", schema="ops")
    op.drop_index("ix_work_orders_site_status_due", table_name="work_orders", schema="ops")
    op.drop_index("ix_work_orders_asset_type_opened", table_name="work_orders", schema="ops")
    op.drop_table("work_orders", schema="ops")
    op.drop_index("ix_incidents_site_occurred", table_name="safety_incidents", schema="ops")
    op.drop_table("safety_incidents", schema="ops")
    op.drop_index(op.f("ix_ops_pm_schedules_asset_id"), table_name="pm_schedules", schema="ops")
    op.drop_table("pm_schedules", schema="ops")
    op.drop_table("production_daily", schema="ops")
    op.drop_index("ix_assets_site_type", table_name="assets", schema="ops")
    op.drop_table("assets", schema="ops")
    op.drop_table("sites", schema="ops")
    op.drop_index("ix_tool_calls_ts", table_name="tool_calls", schema="audit")
    op.drop_index("ix_tool_calls_caller_ts", table_name="tool_calls", schema="audit")
    op.drop_table("tool_calls", schema="audit")
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema}")
