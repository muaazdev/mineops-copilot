"""Deterministic synthetic data for Falcon Ridge Mining.

One seeded ``numpy.random.Generator`` drives everything (UUIDs included), and the window is
anchored to a fixed ``end_date`` rather than "today", so the same seed + scale + end date
produce byte-identical CSVs on any machine.

Causal story, so downstream signals are real rather than painted on:
- Failures are a per-asset renewal process -> each failure is one unplanned downtime event and
  one CM work order (linked by ``work_order_id``).
- PM work orders are released from ``pm_schedules`` every ``interval_days``; completing one
  causes a short planned-maintenance downtime event.
- Daily availability is driven by that day's downtime hours at the site; ore tonnes follow
  target x seasonality x availability x noise.
- Four anomalies (SPEC §4) are injected on top and described in ``ground_truth.json``.

All timestamps are UTC. Production ``date`` is the UTC calendar day (simplification; the
reporting layer converts to Asia/Riyadh for display).
"""

from __future__ import annotations

import csv
import json
import math
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np

from mineops_data.enums import (
    AssetStatus,
    AssetType,
    AssigneeRole,
    DowntimeReason,
    IncidentCategory,
    Lang,
    Priority,
    Severity,
    Shift,
    WorkOrderStatus,
    WorkOrderType,
)
from mineops_data.texts import (
    ASSET_LABEL,
    ASSET_PREFIX,
    CRUSHER_BEARING,
    FAILURES,
    INCIDENTS,
    INSPECTION,
    PM_TASKS,
    SITES,
    FailureText,
)

Scale = Literal["small", "medium"]
DEFAULT_END_DATE = date(2026, 9, 30)

# Load order == FK order. Column order is the CSV header and the COPY column list.
TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "sites": (
        "id", "code", "name_en", "name_ar", "commodity", "mine_type", "grade_unit", "timezone",
    ),
    "assets": (
        "id", "tag", "site_id", "asset_type", "name_en", "name_ar", "criticality",
        "commissioned_on", "status",
    ),
    "pm_schedules": (
        "id", "asset_id", "task_en", "task_ar", "interval_days", "last_done_on", "next_due_on",
    ),
    "work_orders": (
        "id", "code", "site_id", "asset_id", "pm_schedule_id", "wo_type", "priority", "status",
        "opened_at", "due_at", "closed_at", "assignee_role", "description", "lang",
    ),
    "downtime_events": (
        "id", "site_id", "asset_id", "work_order_id", "started_at", "ended_at", "reason_code",
    ),
    "production_daily": (
        "site_id", "date", "ore_tonnes", "target_tonnes", "grade", "availability_pct",
        "utilization_pct",
    ),
    "safety_incidents": (
        "id", "code", "site_id", "asset_id", "occurred_at", "shift", "severity", "category",
        "description", "lang",
    ),
}  # fmt: skip


@dataclass(frozen=True)
class ScaleSpec:
    days: int
    asset_mix: tuple[tuple[AssetType, int], ...]  # per site


SCALES: dict[str, ScaleSpec] = {
    # 3 sites x 40 assets = 120 assets, 18 months.
    "medium": ScaleSpec(
        days=548,
        asset_mix=(
            (AssetType.haul_truck, 14),
            (AssetType.excavator, 4),
            (AssetType.crusher, 4),
            (AssetType.conveyor, 6),
            (AssetType.pump, 6),
            (AssetType.drill, 6),
        ),
    ),
    # ~15% of medium: 18 assets, 6 months. Big enough for every anomaly to stay detectable.
    "small": ScaleSpec(
        days=183,
        asset_mix=(
            (AssetType.haul_truck, 2),
            (AssetType.excavator, 1),
            (AssetType.crusher, 1),
            (AssetType.conveyor, 1),
            (AssetType.pump, 1),
        ),
    ),
}

# Mean failures per asset-day (renewal process); keeps medium at ~5k work orders total.
FAILURE_RATE: dict[AssetType, float] = {
    AssetType.haul_truck: 0.040,
    AssetType.excavator: 0.035,
    AssetType.crusher: 0.030,
    AssetType.conveyor: 0.030,
    AssetType.pump: 0.035,
    AssetType.drill: 0.040,
}
CRITICALITY: dict[AssetType, int] = {
    AssetType.crusher: 1,
    AssetType.conveyor: 1,
    AssetType.excavator: 2,
    AssetType.haul_truck: 2,
    AssetType.pump: 2,
    AssetType.drill: 3,
}
INSPECTION_RATE = 0.008  # per asset-day
INCIDENT_RATE = 0.17  # per site-day
ARABIC_SHARE = 0.25
DUE_BY_PRIORITY = {
    Priority.critical: timedelta(days=1),
    Priority.high: timedelta(days=2),
    Priority.medium: timedelta(days=5),
    Priority.low: timedelta(days=10),
}
ROLE_BY_REASON = {
    DowntimeReason.mechanical_failure: AssigneeRole.mechanic,
    DowntimeReason.hydraulic_failure: AssigneeRole.hydraulics_tech,
    DowntimeReason.electrical_failure: AssigneeRole.electrician,
}
OPEN_STATES = (WorkOrderStatus.open, WorkOrderStatus.in_progress, WorkOrderStatus.on_hold)

# --- Anomaly parameters (offsets are days before end_date) ---------------------------------
A1_SITE, A1_DAYS, A1_FACTOR = "WSP", 14, 0.72
A2_SITE, A2_WINDOW_DAYS = "FRN", 90
A3_SITE, A3_DUE_FROM, A3_DUE_TO = "JNU", 35, 5
A4_SITE, A4_CHANGE_OFFSET, A4_SPIKE_DAYS, A4_MULT = "FRN", 56, 28, 3.5


Row = dict[str, Any]


@dataclass
class Dataset:
    tables: dict[str, list[Row]] = field(default_factory=lambda: defaultdict(list))
    ground_truth: dict[str, Any] = field(default_factory=dict)


class _Gen:
    def __init__(self, seed: int, scale: Scale, end_date: date) -> None:
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.scale = scale
        self.spec = SCALES[scale]
        self.end_date = end_date
        self.start_date = end_date - timedelta(days=self.spec.days - 1)
        self.t0 = datetime.combine(self.start_date, time(), tzinfo=UTC)
        self.as_of = datetime.combine(end_date + timedelta(days=1), time(), tzinfo=UTC)
        self.ds = Dataset()
        self.site_by_code: dict[str, Row] = {}
        self.assets_by_site: dict[str, list[Row]] = defaultdict(list)
        self.work_orders: list[Row] = []
        self.downtime: list[Row] = []

    # --- primitives -----------------------------------------------------------------------
    def uid(self) -> str:
        return str(uuid.UUID(bytes=self.rng.bytes(16), version=4))

    def u(self, lo: float = 0.0, hi: float = 1.0) -> float:
        return float(self.rng.uniform(lo, hi))

    def choice[T](self, items: Sequence[T], p: Sequence[float] | None = None) -> T:
        return items[int(self.rng.choice(len(items), p=p))]

    def day_offset(self, d: date) -> datetime:
        return datetime.combine(d, time(), tzinfo=UTC)

    def pick_lang(self) -> Lang:
        return Lang.ar if self.u() < ARABIC_SHARE else Lang.en

    # --- entities -------------------------------------------------------------------------
    def sites(self) -> None:
        for s in SITES:
            row: Row = {
                "id": self.uid(),
                "code": s.code,
                "name_en": s.name_en,
                "name_ar": s.name_ar,
                "commodity": s.commodity,
                "mine_type": s.mine_type,
                "grade_unit": s.grade_unit,
                "timezone": "Asia/Riyadh",
            }
            self.site_by_code[s.code] = row
            self.ds.tables["sites"].append(row)

    def assets(self) -> None:
        counters: dict[AssetType, int] = defaultdict(int)
        for s in SITES:
            for atype, n in self.spec.asset_mix:
                for _ in range(n):
                    counters[atype] += 1
                    num = counters[atype]
                    width = 3 if atype == AssetType.haul_truck else 2
                    tag = f"{ASSET_PREFIX[atype]}-{num:0{width}d}"
                    en, ar = ASSET_LABEL[atype]
                    row: Row = {
                        "id": self.uid(),
                        "tag": tag,
                        "site_id": self.site_by_code[s.code]["id"],
                        "asset_type": atype.value,
                        "name_en": f"{en} {num}",
                        "name_ar": f"{ar} {num}",
                        "criticality": CRITICALITY[atype],
                        "commissioned_on": self.start_date
                        - timedelta(days=int(self.rng.integers(365, 365 * 9))),
                        "status": AssetStatus.operational.value,
                        "_site": s.code,
                        "_type": atype,
                    }
                    self.assets_by_site[s.code].append(row)
                    self.ds.tables["assets"].append(row)

    def anomalous_crusher(self) -> Row:
        return next(a for a in self.assets_by_site[A2_SITE] if a["_type"] == AssetType.crusher)

    # --- work orders + downtime ------------------------------------------------------------
    def add_wo(self, asset: Row, **fields: Any) -> Row:
        lang = self.pick_lang()
        text_en, text_ar = fields.pop("text")
        row: Row = {
            "id": self.uid(),
            "code": "",  # assigned after sorting by opened_at
            "site_id": asset["site_id"],
            "asset_id": asset["id"],
            "pm_schedule_id": None,
            "description": (text_ar if lang == Lang.ar else text_en).format(tag=asset["tag"]),
            "lang": lang.value,
            **fields,
        }
        self.work_orders.append(row)
        return row

    def add_downtime(
        self,
        asset: Row,
        start: datetime,
        end: datetime,
        reason: DowntimeReason,
        wo: Row | None,
    ) -> None:
        self.downtime.append(
            {
                "id": self.uid(),
                "site_id": asset["site_id"],
                "asset_id": asset["id"],
                "work_order_id": wo["id"] if wo else None,
                "started_at": start,
                "ended_at": min(end, self.as_of),
                "reason_code": reason.value,
            }
        )

    def failure(self, asset: Row, start: datetime, ft: FailureText, hours: float) -> datetime:
        end = start + timedelta(hours=hours)
        crit = asset["criticality"]
        priority = self.choice(
            [Priority.critical, Priority.high, Priority.medium],
            p=[0.3, 0.5, 0.2] if crit == 1 else [0.05, 0.45, 0.5],
        )
        opened = start + timedelta(minutes=self.u(2, 30))
        closed = end + timedelta(hours=self.u(0.5, 3))
        done = closed <= self.as_of
        if not done:
            asset["status"] = AssetStatus.down.value
        wo = self.add_wo(
            asset,
            wo_type=WorkOrderType.CM.value,
            priority=priority.value,
            status=(WorkOrderStatus.completed if done else WorkOrderStatus.in_progress).value,
            opened_at=opened,
            due_at=opened + DUE_BY_PRIORITY[priority],
            closed_at=closed if done else None,
            assignee_role=ROLE_BY_REASON[ft.reason].value,
            text=(ft.en, ft.ar),
        )
        self.add_downtime(asset, start, end, ft.reason, wo)
        return end

    def failures(self) -> None:
        crusher = self.anomalous_crusher()
        a2_start = self.as_of - timedelta(days=A2_WINDOW_DAYS)
        for site in SITES:
            for asset in self.assets_by_site[site.code]:
                atype: AssetType = asset["_type"]
                rate = FAILURE_RATE[atype]
                is_anom = asset is crusher
                t = self.t0
                while True:
                    in_a2 = is_anom and t >= a2_start
                    gap_days = self.u(3.0, 6.0) if in_a2 else float(self.rng.exponential(1 / rate))
                    t = t + timedelta(days=gap_days)
                    if t >= self.as_of:
                        break
                    if is_anom and t >= a2_start:
                        ft, hours = CRUSHER_BEARING, self.u(6, 14)
                    else:
                        ft = self.choice(FAILURES[atype])
                        hours = float(np.clip(self.rng.lognormal(math.log(6), 0.7), 1, 72))
                    t = self.failure(asset, t, ft, hours)

    def pm(self) -> None:
        a3_from = self.as_of - timedelta(days=A3_DUE_FROM)
        a3_to = self.as_of - timedelta(days=A3_DUE_TO)
        for site in SITES:
            for asset in self.assets_by_site[site.code]:
                intervals = [30] + ([90] if self.u() < 0.5 else [])
                for interval in intervals:
                    task_en, task_ar = PM_TASKS[interval]
                    sched: Row = {
                        "id": self.uid(),
                        "asset_id": asset["id"],
                        "task_en": task_en,
                        "task_ar": task_ar,
                        "interval_days": interval,
                        "last_done_on": None,
                        "next_due_on": None,
                    }
                    self.ds.tables["pm_schedules"].append(sched)
                    due = self.t0 + timedelta(days=self.u(3, interval), hours=8)
                    while True:
                        opened = due - timedelta(days=7)
                        if opened >= self.as_of:
                            sched["next_due_on"] = due.date()
                            break
                        self._pm_wo(asset, sched, opened, due, in_a3=a3_from <= due < a3_to)
                        due += timedelta(days=interval)

    def _pm_wo(self, asset: Row, sched: Row, opened: datetime, due: datetime, in_a3: bool) -> None:
        if in_a3 and asset["_site"] == A3_SITE:
            # Anomaly 3: backlog — PMs due in the window were never done.
            status = self.choice([WorkOrderStatus.open, WorkOrderStatus.on_hold], p=[0.7, 0.3])
            closed = None
        elif self.u() < 0.02:
            status, closed = WorkOrderStatus.cancelled, opened + timedelta(days=self.u(0, 5))
        else:
            late = self.u(1, 5) if self.u() < 0.1 else 0.0
            done_at = due - timedelta(days=self.u(0, 3)) + timedelta(days=late)
            done_at = max(done_at, opened + timedelta(hours=4))
            if done_at <= self.as_of:
                status, closed = WorkOrderStatus.completed, done_at
            else:
                status, closed = WorkOrderStatus.open, None
        closed = min(closed, self.as_of) if closed else None
        wo = self.add_wo(
            asset,
            wo_type=WorkOrderType.PM.value,
            pm_schedule_id=sched["id"],
            priority=Priority.medium.value if asset["criticality"] == 1 else Priority.low.value,
            status=status.value,
            opened_at=opened,
            due_at=due,
            closed_at=closed,
            assignee_role=AssigneeRole.mechanic.value,
            text=(f"{sched['task_en']} for {{tag}}", f"{sched['task_ar']} للمعدة {{tag}}"),
        )
        if status == WorkOrderStatus.completed and closed is not None:
            sched["last_done_on"] = closed.date()
            dur = timedelta(hours=self.u(2, 6))
            self.add_downtime(asset, closed - dur, closed, DowntimeReason.planned_maintenance, wo)

    def inspections(self) -> None:
        for site in SITES:
            for asset in self.assets_by_site[site.code]:
                n = int(self.rng.poisson(INSPECTION_RATE * self.spec.days))
                for _ in range(n):
                    opened = self.t0 + timedelta(days=self.u(0, self.spec.days))
                    closed = opened + timedelta(days=self.u(0.5, 5))
                    done = closed <= self.as_of
                    self.add_wo(
                        asset,
                        wo_type=WorkOrderType.inspection.value,
                        priority=self.choice([Priority.low, Priority.medium]).value,
                        status=(WorkOrderStatus.completed if done else WorkOrderStatus.open).value,
                        opened_at=opened,
                        due_at=opened + timedelta(days=7),
                        closed_at=closed if done else None,
                        assignee_role=AssigneeRole.inspector.value,
                        text=INSPECTION,
                    )

    # --- production ------------------------------------------------------------------------
    def production(self) -> None:
        unplanned_hours: dict[tuple[str, date], float] = defaultdict(float)
        site_code_by_id = {s["id"]: c for c, s in self.site_by_code.items()}
        for ev in self.downtime:
            if ev["reason_code"] == DowntimeReason.planned_maintenance.value:
                continue
            code = site_code_by_id[ev["site_id"]]
            for d, hours in _split_by_day(ev["started_at"], ev["ended_at"]):
                unplanned_hours[(code, d)] += hours
        a1_from = self.end_date - timedelta(days=A1_DAYS - 1)
        for s in SITES:
            site_id = self.site_by_code[s.code]["id"]
            fleet_hours = 24.0 * len(self.assets_by_site[s.code])
            for i in range(self.spec.days):
                d = self.start_date + timedelta(days=i)
                doy = d.timetuple().tm_yday
                season = 1.0 - 0.05 * math.sin(2 * math.pi * (doy - 110) / 365.0)  # July low
                dt_frac = unplanned_hours[(s.code, d)] / fleet_hours
                avail = float(np.clip(91.0 - 300.0 * dt_frac + self.rng.normal(0, 1.2), 55, 99))
                util = float(np.clip(self.rng.normal(78, 3), 60, 95))
                factor = 1.03 * season * (avail / 90.0) * math.sqrt(util / 78.0)
                if s.code == A1_SITE and d >= a1_from:
                    factor *= A1_FACTOR  # Anomaly 1
                    util = float(np.clip(util - 12, 40, 95))
                ore = s.base_target_t * factor * float(self.rng.lognormal(0, 0.05))
                grade = s.base_grade * (1 + float(self.rng.normal(0, 0.04)))
                self.ds.tables["production_daily"].append(
                    {
                        "site_id": site_id,
                        "date": d,
                        "ore_tonnes": round(ore, 1),
                        "target_tonnes": s.base_target_t,
                        "grade": round(grade, 3),
                        "availability_pct": round(avail, 2),
                        "utilization_pct": round(util, 2),
                    }
                )

    # --- incidents -------------------------------------------------------------------------
    def incidents(self) -> list[Row]:
        change = self.end_date - timedelta(days=A4_CHANGE_OFFSET)
        spike_end = change + timedelta(days=A4_SPIKE_DAYS)
        cats = list(IncidentCategory)
        base_p = [0.20, 0.18, 0.20, 0.12, 0.08, 0.10, 0.12]
        spike_p = [0.30, 0.10, 0.12, 0.08, 0.05, 0.30, 0.05]
        sev = list(Severity)
        sev_p = [0.55, 0.25, 0.14, 0.06]
        rows: list[Row] = []
        for s in SITES:
            site = self.site_by_code[s.code]
            for i in range(self.spec.days):
                d = self.start_date + timedelta(days=i)
                spike = s.code == A4_SITE and change <= d < spike_end
                lam = INCIDENT_RATE * (A4_MULT if spike else 1.0)
                for _ in range(int(self.rng.poisson(lam))):
                    night = self.u() < (0.75 if spike else 0.45)
                    # Night shift 18:00-06:00: fold the post-midnight part onto the same day.
                    hour = (self.u(18, 30) % 24) if night else self.u(6, 18)
                    cat = self.choice(cats, p=spike_p if spike else base_p)
                    asset_id = None
                    with_asset = (IncidentCategory.vehicle_interaction, IncidentCategory.equipment)
                    if cat in with_asset and self.u() < 0.6:
                        asset_id = self.choice(self.assets_by_site[s.code])["id"]
                    lang = self.pick_lang()
                    en, ar = INCIDENTS[cat]
                    rows.append(
                        {
                            "id": self.uid(),
                            "code": "",
                            "site_id": site["id"],
                            "asset_id": asset_id,
                            "occurred_at": self.day_offset(d) + timedelta(hours=hour),
                            "shift": (Shift.night if night else Shift.day).value,
                            "severity": self.choice(sev, p=sev_p).value,
                            "category": cat.value,
                            "description": ar if lang == Lang.ar else en,
                            "lang": lang.value,
                        }
                    )
        return rows

    # --- assemble --------------------------------------------------------------------------
    def run(self) -> Dataset:
        self.sites()
        self.assets()
        self.failures()
        self.pm()
        self.inspections()
        self.production()
        incidents = self.incidents()

        self.work_orders.sort(key=lambda r: (r["opened_at"], r["id"]))
        for n, wo in enumerate(self.work_orders, start=1):
            wo["code"] = f"WO-{n:06d}"
        incidents.sort(key=lambda r: (r["occurred_at"], r["id"]))
        for n, inc in enumerate(incidents, start=1):
            inc["code"] = f"INC-{n:06d}"
        self.downtime.sort(key=lambda r: (r["started_at"], r["id"]))

        self.ds.tables["work_orders"] = self.work_orders
        self.ds.tables["downtime_events"] = self.downtime
        self.ds.tables["safety_incidents"] = incidents
        self.ds.ground_truth = self.ground_truth()
        return self.ds

    def ground_truth(self) -> dict[str, Any]:
        e = self.end_date
        change = e - timedelta(days=A4_CHANGE_OFFSET)
        crusher = self.anomalous_crusher()
        return {
            "seed": self.seed,
            "scale": self.scale,
            "start_date": self.start_date.isoformat(),
            "end_date": e.isoformat(),
            "as_of": self.as_of.isoformat(),
            "anomalies": [
                {
                    "id": "A1_site_under_target",
                    "description": f"{A1_SITE} ore output ~{int(A1_FACTOR * 100)}% of target "
                    f"for the last {A1_DAYS} days",
                    "site_code": A1_SITE,
                    "date_from": (e - timedelta(days=A1_DAYS - 1)).isoformat(),
                    "date_to": e.isoformat(),
                    "query": "production_vs_target",
                    "expected_signal": {"attainment_max": 0.85, "others_attainment_min": 0.90},
                },
                {
                    "id": "A2_crusher_recurring_failures",
                    "description": f"{crusher['tag']} at {A2_SITE}: repeat main-bearing CM "
                    f"failures every 3-6 days over the last {A2_WINDOW_DAYS} days",
                    "site_code": A2_SITE,
                    "asset_tag": crusher["tag"],
                    "date_from": (self.as_of - timedelta(days=A2_WINDOW_DAYS)).isoformat(),
                    "date_to": self.as_of.isoformat(),
                    "query": "cm_failures_by_asset",
                    "expected_signal": {"cm_count_min": 10, "ratio_to_next_crusher_min": 2.0},
                },
                {
                    "id": "A3_overdue_pm_cluster",
                    "description": f"{A3_SITE}: every PM due {A3_DUE_FROM}-{A3_DUE_TO} days "
                    "before as_of left open/on hold",
                    "site_code": A3_SITE,
                    "date_from": (self.as_of - timedelta(days=A3_DUE_FROM)).isoformat(),
                    "date_to": (self.as_of - timedelta(days=A3_DUE_TO)).isoformat(),
                    "query": "overdue_work_orders_by_site",
                    "expected_signal": {"ratio_to_other_sites_min": 3.0},
                },
                {
                    "id": "A4_incident_spike_after_shift_change",
                    "description": f"{A4_SITE} moved to a new night-shift roster on "
                    f"{change.isoformat()}; incident rate x{A4_MULT} for {A4_SPIKE_DAYS} "
                    "days, mostly night shift (fatigue, vehicle interaction)",
                    "site_code": A4_SITE,
                    "change_date": change.isoformat(),
                    "date_from": change.isoformat(),
                    "date_to": (change + timedelta(days=A4_SPIKE_DAYS - 1)).isoformat(),
                    "query": "incidents_by_week",
                    "expected_signal": {"weekly_rate_ratio_min": 2.0, "baseline_weeks": 12},
                },
            ],
        }


def _split_by_day(start: datetime, end: datetime) -> Iterable[tuple[date, float]]:
    cur = start
    while cur < end:
        nxt = min(end, datetime.combine(cur.date() + timedelta(days=1), time(), tzinfo=UTC))
        yield cur.date(), (nxt - cur).total_seconds() / 3600.0
        cur = nxt


def generate(seed: int, scale: Scale, end_date: date = DEFAULT_END_DATE) -> Dataset:
    return _Gen(seed, scale, end_date).run()


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.astimezone(UTC).isoformat(timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        return repr(v)
    return str(v)


def write_dataset(ds: Dataset, out: Path) -> dict[str, int]:
    """Write one CSV per table + ground_truth.json. Returns row counts."""
    out.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for table, cols in TABLE_COLUMNS.items():
        rows = ds.tables[table]
        with (out / f"{table}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(cols)
            for r in rows:
                w.writerow([_fmt(r[c]) for c in cols])
        counts[table] = len(rows)
    gt = {**ds.ground_truth, "row_counts": counts}
    (out / "ground_truth.json").write_text(
        json.dumps(gt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return counts
