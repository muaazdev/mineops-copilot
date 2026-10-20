"""SQLAlchemy 2.x typed models for the ``ops`` and ``audit`` schemas (ADR-0009).

Design notes:
- Vocabularies are ``text`` + CHECK constraints rather than native PG enums: adding a value is a
  one-line constraint swap instead of ``ALTER TYPE`` (which cannot run inside a transaction on
  older PG and is awkward to downgrade in Alembic).
- Every timestamp is ``timestamptz`` (UTC). Site display timezone is a column on ``sites``.
- ``site_id`` is denormalised onto work orders, downtime and incidents: every MCP tool filters
  by the caller's ``sites[]`` first, so the site predicate must be index-leading without a join.
- Each index comment names the planned MCP tool it serves.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from mineops_data.enums import (
    AssetStatus,
    AssetType,
    AssigneeRole,
    Commodity,
    DowntimeReason,
    DraftState,
    IncidentCategory,
    Lang,
    MineType,
    Priority,
    Severity,
    Shift,
    WorkOrderStatus,
    WorkOrderType,
)

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

SCHEMAS = ("ops", "auth", "agent", "audit")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def vocab(enum_cls: type[enum.StrEnum], name: str) -> SAEnum:
    """text column constrained to the enum's values."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


def pk_uuid() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = ({"schema": "ops"},)

    id: Mapped[uuid.UUID] = pk_uuid()
    code: Mapped[str] = mapped_column(String(8), unique=True)
    name_en: Mapped[str] = mapped_column(Text)
    name_ar: Mapped[str] = mapped_column(Text)
    commodity: Mapped[Commodity] = mapped_column(vocab(Commodity, "commodity"))
    mine_type: Mapped[MineType] = mapped_column(vocab(MineType, "mine_type"))
    grade_unit: Mapped[str] = mapped_column(String(16))
    timezone: Mapped[str] = mapped_column(String(64), server_default=text("'Asia/Riyadh'"))
    created_at: Mapped[datetime] = created_at()


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("criticality BETWEEN 1 AND 3", name="criticality_range"),
        # get_asset / list by site+type
        Index("ix_assets_site_type", "site_id", "asset_type"),
        {"schema": "ops"},
    )

    id: Mapped[uuid.UUID] = pk_uuid()
    tag: Mapped[str] = mapped_column(String(16), unique=True)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ops.sites.id", ondelete="RESTRICT"))
    asset_type: Mapped[AssetType] = mapped_column(vocab(AssetType, "asset_type"))
    name_en: Mapped[str] = mapped_column(Text)
    name_ar: Mapped[str] = mapped_column(Text)
    criticality: Mapped[int] = mapped_column(SmallInteger)  # 1 = most critical
    commissioned_on: Mapped[date] = mapped_column(Date)
    status: Mapped[AssetStatus] = mapped_column(vocab(AssetStatus, "asset_status"))
    created_at: Mapped[datetime] = created_at()


class PmSchedule(Base):
    __tablename__ = "pm_schedules"
    __table_args__ = (
        CheckConstraint("interval_days > 0", name="interval_positive"),
        {"schema": "ops"},
    )

    id: Mapped[uuid.UUID] = pk_uuid()
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ops.assets.id", ondelete="CASCADE"), index=True
    )
    task_en: Mapped[str] = mapped_column(Text)
    task_ar: Mapped[str] = mapped_column(Text)
    interval_days: Mapped[int] = mapped_column(Integer)
    last_done_on: Mapped[date | None] = mapped_column(Date)
    next_due_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = created_at()


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        CheckConstraint(r"code ~ '^WO-[0-9]{6}$'", name="code_format"),
        CheckConstraint("due_at >= opened_at", name="due_after_open"),
        CheckConstraint(
            "(status IN ('completed','cancelled')) = (closed_at IS NOT NULL)",
            name="closed_iff_terminal",
        ),
        CheckConstraint("closed_at IS NULL OR closed_at >= opened_at", name="closed_after_open"),
        # list_work_orders, list_overdue_work_orders: site scope -> status -> due date range
        Index("ix_work_orders_site_status_due", "site_id", "status", "due_at"),
        # get_asset (recent WOs), CM failure history per asset
        Index("ix_work_orders_asset_type_opened", "asset_id", "wo_type", "opened_at"),
        {"schema": "ops"},
    )

    id: Mapped[uuid.UUID] = pk_uuid()
    code: Mapped[str] = mapped_column(String(16), unique=True)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ops.sites.id", ondelete="RESTRICT"))
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ops.assets.id", ondelete="RESTRICT"))
    pm_schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ops.pm_schedules.id", ondelete="SET NULL")
    )
    wo_type: Mapped[WorkOrderType] = mapped_column(vocab(WorkOrderType, "wo_type"))
    priority: Mapped[Priority] = mapped_column(vocab(Priority, "priority"))
    status: Mapped[WorkOrderStatus] = mapped_column(vocab(WorkOrderStatus, "wo_status"))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignee_role: Mapped[AssigneeRole] = mapped_column(vocab(AssigneeRole, "assignee_role"))
    description: Mapped[str] = mapped_column(Text)
    lang: Mapped[Lang] = mapped_column(vocab(Lang, "lang"))
    created_at: Mapped[datetime] = created_at()


class DowntimeEvent(Base):
    __tablename__ = "downtime_events"
    __table_args__ = (
        CheckConstraint("ended_at > started_at", name="end_after_start"),
        # get_downtime_summary: site scope + time window
        Index("ix_downtime_site_started", "site_id", "started_at"),
        Index("ix_downtime_asset_started", "asset_id", "started_at"),
        {"schema": "ops"},
    )

    id: Mapped[uuid.UUID] = pk_uuid()
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ops.sites.id", ondelete="RESTRICT"))
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ops.assets.id", ondelete="RESTRICT"))
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ops.work_orders.id", ondelete="SET NULL"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[DowntimeReason] = mapped_column(vocab(DowntimeReason, "reason_code"))
    created_at: Mapped[datetime] = created_at()


class ProductionDaily(Base):
    __tablename__ = "production_daily"
    __table_args__ = (
        CheckConstraint("ore_tonnes >= 0 AND target_tonnes > 0", name="tonnes_valid"),
        CheckConstraint("availability_pct BETWEEN 0 AND 100", name="availability_range"),
        CheckConstraint("utilization_pct BETWEEN 0 AND 100", name="utilization_range"),
        {"schema": "ops"},
    )

    # get_kpis, get_production_vs_target: (site_id, date) PK is the serving index.
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ops.sites.id", ondelete="RESTRICT"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    ore_tonnes: Mapped[Decimal] = mapped_column(Numeric(12, 1))
    target_tonnes: Mapped[Decimal] = mapped_column(Numeric(12, 1))
    grade: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    availability_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    utilization_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))


class SafetyIncident(Base):
    __tablename__ = "safety_incidents"
    __table_args__ = (
        CheckConstraint(r"code ~ '^INC-[0-9]{6}$'", name="code_format"),
        # get_incidents: site scope + time window
        Index("ix_incidents_site_occurred", "site_id", "occurred_at"),
        {"schema": "ops"},
    )

    id: Mapped[uuid.UUID] = pk_uuid()
    code: Mapped[str] = mapped_column(String(16), unique=True)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ops.sites.id", ondelete="RESTRICT"))
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ops.assets.id", ondelete="SET NULL")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    shift: Mapped[Shift] = mapped_column(vocab(Shift, "shift"))
    severity: Mapped[Severity] = mapped_column(vocab(Severity, "severity"))
    category: Mapped[IncidentCategory] = mapped_column(vocab(IncidentCategory, "category"))
    description: Mapped[str] = mapped_column(Text)
    lang: Mapped[Lang] = mapped_column(vocab(Lang, "lang"))
    created_at: Mapped[datetime] = created_at()


class WorkOrderDraft(Base):
    """Written only by the action agent via MCP ``create_work_order_draft`` (role drafts_rw)."""

    __tablename__ = "work_order_drafts"
    __table_args__ = (
        CheckConstraint(
            "(state = 'pending') = (decided_at IS NULL)", name="decided_iff_not_pending"
        ),
        CheckConstraint(
            "state <> 'rejected' OR reject_reason IS NOT NULL", name="reject_needs_reason"
        ),
        # HITL queue: pending drafts per site, oldest first
        Index("ix_drafts_site_state_created", "site_id", "state", "created_at"),
        {"schema": "ops"},
    )

    id: Mapped[uuid.UUID] = pk_uuid()
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ops.sites.id", ondelete="RESTRICT"))
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ops.assets.id", ondelete="RESTRICT"))
    wo_type: Mapped[WorkOrderType] = mapped_column(vocab(WorkOrderType, "wo_type"))
    priority: Mapped[Priority] = mapped_column(vocab(Priority, "priority"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    lang: Mapped[Lang] = mapped_column(vocab(Lang, "lang"))
    state: Mapped[DraftState] = mapped_column(
        vocab(DraftState, "draft_state"), server_default=text("'pending'")
    )
    requested_by: Mapped[str] = mapped_column(Text)  # JWT sub
    run_id: Mapped[str | None] = mapped_column(Text)  # LangGraph thread/run
    approver: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)
    promoted_work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ops.work_orders.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ToolCall(Base):
    """MCP audit trail (stub in M1; written by mcp-server from M4 via role audit_writer)."""

    __tablename__ = "tool_calls"
    __table_args__ = (
        Index("ix_tool_calls_ts", "ts"),
        Index("ix_tool_calls_caller_ts", "caller_sub", "ts"),
        {"schema": "audit"},
    )

    id: Mapped[uuid.UUID] = pk_uuid()
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    request_id: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(Text)
    caller_sub: Mapped[str] = mapped_column(Text)
    caller_role: Mapped[str] = mapped_column(Text)
    tool: Mapped[str] = mapped_column(Text)
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(16))  # ok | denied | error
    error_code: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
