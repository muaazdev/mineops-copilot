"""Domain vocabularies. Stored as text + CHECK constraint (see models.py for why not PG enums)."""

from __future__ import annotations

from enum import StrEnum


class Commodity(StrEnum):
    gold = "gold"
    phosphate = "phosphate"
    copper = "copper"


class MineType(StrEnum):
    open_pit = "open_pit"
    underground = "underground"


class AssetType(StrEnum):
    haul_truck = "haul_truck"
    excavator = "excavator"
    crusher = "crusher"
    conveyor = "conveyor"
    pump = "pump"
    drill = "drill"


class AssetStatus(StrEnum):
    operational = "operational"
    down = "down"
    maintenance = "maintenance"
    retired = "retired"


class WorkOrderType(StrEnum):
    PM = "PM"
    CM = "CM"
    inspection = "inspection"


class Priority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class WorkOrderStatus(StrEnum):
    open = "open"
    in_progress = "in_progress"
    on_hold = "on_hold"
    completed = "completed"
    cancelled = "cancelled"


class AssigneeRole(StrEnum):
    mechanic = "mechanic"
    electrician = "electrician"
    hydraulics_tech = "hydraulics_tech"
    inspector = "inspector"


class DowntimeReason(StrEnum):
    mechanical_failure = "mechanical_failure"
    electrical_failure = "electrical_failure"
    hydraulic_failure = "hydraulic_failure"
    planned_maintenance = "planned_maintenance"
    operational_delay = "operational_delay"


class Severity(StrEnum):
    near_miss = "near_miss"
    first_aid = "first_aid"
    medical_treatment = "medical_treatment"
    lost_time = "lost_time"


class IncidentCategory(StrEnum):
    vehicle_interaction = "vehicle_interaction"
    slip_trip_fall = "slip_trip_fall"
    equipment = "equipment"
    ground_control = "ground_control"
    electrical = "electrical"
    fatigue = "fatigue"
    hazardous_substance = "hazardous_substance"


class Shift(StrEnum):
    day = "day"
    night = "night"


class DraftState(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Lang(StrEnum):
    en = "en"
    ar = "ar"
