"""Bilingual text templates for synthetic records.

Arabic strings are authored as Arabic (not machine-translated at runtime). Names are fictional.
"""

from __future__ import annotations

from typing import NamedTuple

from mineops_data.enums import AssetType, DowntimeReason, IncidentCategory


class SiteSpec(NamedTuple):
    code: str
    name_en: str
    name_ar: str
    commodity: str
    mine_type: str
    grade_unit: str
    base_target_t: float
    base_grade: float


SITES: tuple[SiteSpec, ...] = (
    SiteSpec(
        "FRN",
        "Falcon Ridge North Pit",
        "منجم حافة الصقر الشمالي المكشوف",
        "gold",
        "open_pit",
        "g/t Au",
        12000.0,
        1.8,
    ),
    SiteSpec(
        "WSP",
        "Wadi Sahm Phosphate",
        "منجم وادي سهم للفوسفات",
        "phosphate",
        "open_pit",
        "% P2O5",
        18000.0,
        28.0,
    ),
    SiteSpec(
        "JNU",
        "Jabal Noor Underground",
        "منجم جبل نور الجوفي للنحاس",
        "copper",
        "underground",
        "% Cu",
        4500.0,
        1.4,
    ),
)

ASSET_PREFIX: dict[AssetType, str] = {
    AssetType.haul_truck: "HT",
    AssetType.excavator: "EX",
    AssetType.crusher: "CR",
    AssetType.conveyor: "CV",
    AssetType.pump: "PU",
    AssetType.drill: "DR",
}

ASSET_LABEL: dict[AssetType, tuple[str, str]] = {
    AssetType.haul_truck: ("Haul Truck", "شاحنة نقل"),
    AssetType.excavator: ("Excavator", "حفارة"),
    AssetType.crusher: ("Crusher", "كسارة"),
    AssetType.conveyor: ("Conveyor", "ناقل"),
    AssetType.pump: ("Dewatering Pump", "مضخة نزح"),
    AssetType.drill: ("Drill Rig", "جهاز حفر"),
}


class FailureText(NamedTuple):
    reason: DowntimeReason
    en: str
    ar: str


FAILURES: dict[AssetType, tuple[FailureText, ...]] = {
    AssetType.haul_truck: (
        FailureText(
            DowntimeReason.mechanical_failure,
            "Engine overheating alarm on {tag}; truck parked for inspection",
            "إنذار ارتفاع حرارة المحرك في {tag}؛ تم إيقاف الشاحنة للفحص",
        ),
        FailureText(
            DowntimeReason.hydraulic_failure,
            "Hydraulic hose leak on hoist cylinder of {tag}",
            "تسرب في خرطوم الهيدروليك لأسطوانة الرفع في {tag}",
        ),
        FailureText(
            DowntimeReason.mechanical_failure,
            "Tyre damage reported by operator on {tag}",
            "تلف في الإطار أبلغ عنه المشغل في {tag}",
        ),
    ),
    AssetType.excavator: (
        FailureText(
            DowntimeReason.hydraulic_failure,
            "Swing motor fault; {tag} unable to slew",
            "عطل في محرك الدوران؛ {tag} لا يستطيع الدوران",
        ),
        FailureText(
            DowntimeReason.mechanical_failure,
            "Cracked bucket tooth adapter on {tag}",
            "تشقق في محول سن الدلو في {tag}",
        ),
    ),
    AssetType.crusher: (
        FailureText(
            DowntimeReason.mechanical_failure,
            "Crusher {tag} tripped on high vibration",
            "توقف الكسارة {tag} بسبب اهتزاز مرتفع",
        ),
        FailureText(
            DowntimeReason.mechanical_failure,
            "Liner wear beyond limit on {tag}",
            "تآكل البطانة تجاوز الحد المسموح في {tag}",
        ),
        FailureText(
            DowntimeReason.electrical_failure,
            "Main drive motor overload trip on {tag}",
            "فصل محرك التشغيل الرئيسي بسبب الحمل الزائد في {tag}",
        ),
    ),
    AssetType.conveyor: (
        FailureText(
            DowntimeReason.mechanical_failure,
            "Belt misalignment and spillage at tail pulley of {tag}",
            "انحراف السير وانسكاب المواد عند البكرة الخلفية في {tag}",
        ),
        FailureText(
            DowntimeReason.electrical_failure,
            "Conveyor {tag} stopped: pull-wire emergency stop activated",
            "توقف الناقل {tag}: تم تفعيل سلك الإيقاف الطارئ",
        ),
    ),
    AssetType.pump: (
        FailureText(
            DowntimeReason.electrical_failure,
            "Pump {tag} motor tripped on overload",
            "فصل محرك المضخة {tag} بسبب الحمل الزائد",
        ),
        FailureText(
            DowntimeReason.mechanical_failure,
            "Mechanical seal leak on {tag}",
            "تسرب في الختم الميكانيكي للمضخة {tag}",
        ),
    ),
    AssetType.drill: (
        FailureText(
            DowntimeReason.hydraulic_failure,
            "Low hydraulic pressure at rotation head of {tag}",
            "انخفاض الضغط الهيدروليكي لرأس الدوران في {tag}",
        ),
        FailureText(
            DowntimeReason.mechanical_failure,
            "Compressor fault on drill rig {tag}",
            "عطل في الضاغط بجهاز الحفر {tag}",
        ),
    ),
}

# Anomaly 2: one crusher's recurring failure mode.
CRUSHER_BEARING = FailureText(
    DowntimeReason.mechanical_failure,
    "Main bearing overheating on {tag}; crusher stopped (repeat failure)",
    "ارتفاع حرارة المحمل الرئيسي في {tag}؛ تم إيقاف الكسارة (عطل متكرر)",
)

PM_TASKS: dict[int, tuple[str, str]] = {
    30: (
        "Monthly service: lubrication, filters and fluid levels",
        "صيانة شهرية: تشحيم وتغيير الفلاتر وفحص مستويات السوائل",
    ),
    90: (
        "Quarterly major service and component inspection",
        "صيانة ربع سنوية شاملة وفحص المكونات",
    ),
}

INSPECTION = (
    "Statutory safety inspection of {tag}",
    "فحص السلامة النظامي للمعدة {tag}",
)

INCIDENTS: dict[IncidentCategory, tuple[str, str]] = {
    IncidentCategory.vehicle_interaction: (
        "Light vehicle entered haul road without radio call; close interaction with haul truck",
        "دخلت مركبة خفيفة طريق النقل دون اتصال لاسلكي؛ اقتراب خطير من شاحنة نقل",
    ),
    IncidentCategory.slip_trip_fall: (
        "Worker slipped on a wet walkway near the processing plant",
        "انزلق عامل على ممر مبلل قرب محطة المعالجة",
    ),
    IncidentCategory.equipment: (
        "Hand injury while replacing a conveyor idler",
        "إصابة في اليد أثناء تغيير بكرة ناقل",
    ),
    IncidentCategory.ground_control: (
        "Loose rock fell from the face during scaling",
        "سقوط صخرة مفككة من الواجهة أثناء التقشير",
    ),
    IncidentCategory.electrical: (
        "Exposed cable found at a pump station during inspection",
        "تم العثور على كابل مكشوف في محطة الضخ أثناء الفحص",
    ),
    IncidentCategory.fatigue: (
        "Operator reported a microsleep during night shift; equipment stopped safely",
        "أبلغ المشغل عن غفوة قصيرة خلال الوردية الليلية؛ تم إيقاف المعدة بأمان",
    ),
    IncidentCategory.hazardous_substance: (
        "Small diesel spill at the refuelling bay",
        "انسكاب كمية صغيرة من الديزل في محطة التزود بالوقود",
    ),
}
