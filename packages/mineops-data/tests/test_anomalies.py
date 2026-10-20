"""Every anomaly in ground_truth.json is detectable with its named, parameterized query.

These are the same templates the M4 MCP tools will execute, so this also proves the tool
queries can surface the signal the reporting agent must find.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import psycopg
import pytest

from mineops_data.queries import QUERY_NAMES, load_query

pytestmark = pytest.mark.integration


def anomaly(gt: dict[str, Any], prefix: str) -> dict[str, Any]:
    found: dict[str, Any] = next(a for a in gt["anomalies"] if a["id"].startswith(prefix))
    return found


def run(db: psycopg.Connection[Any], name: str, **params: Any) -> list[dict[str, Any]]:
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(load_query(name), params)
        return cur.fetchall()


def test_every_anomaly_names_a_known_query(ground_truth: dict[str, Any]) -> None:
    assert {a["query"] for a in ground_truth["anomalies"]} <= set(QUERY_NAMES)


def test_a1_site_under_target(db: psycopg.Connection[Any], ground_truth: dict[str, Any]) -> None:
    a = anomaly(ground_truth, "A1")
    rows = run(db, a["query"], date_from=a["date_from"], date_to=a["date_to"], site_codes=None)
    by_site = {r["site_code"]: r for r in rows}
    exp = a["expected_signal"]
    assert by_site[a["site_code"]]["attainment"] <= exp["attainment_max"]
    assert by_site[a["site_code"]]["days_under_target"] == by_site[a["site_code"]]["days"]
    for code, r in by_site.items():
        if code != a["site_code"]:
            assert r["attainment"] >= exp["others_attainment_min"], code


def test_a2_crusher_recurring_failures(
    db: psycopg.Connection[Any], ground_truth: dict[str, Any]
) -> None:
    a = anomaly(ground_truth, "A2")
    rows = run(
        db,
        a["query"],
        date_from=a["date_from"],
        date_to=a["date_to"],
        asset_type="crusher",
        site_codes=None,
        row_limit=10,
    )
    exp = a["expected_signal"]
    top, nxt = rows[0], rows[1]
    assert top["asset_tag"] == a["asset_tag"]
    assert top["cm_count"] >= exp["cm_count_min"]
    assert top["cm_count"] >= exp["ratio_to_next_crusher_min"] * nxt["cm_count"]


def test_a3_overdue_pm_cluster(db: psycopg.Connection[Any], ground_truth: dict[str, Any]) -> None:
    a = anomaly(ground_truth, "A3")
    rows = run(db, a["query"], as_of=ground_truth["as_of"], wo_type="PM", site_codes=None)
    counts = {r["site_code"]: r["overdue_count"] for r in rows}
    others = max(c for s, c in counts.items() if s != a["site_code"])
    assert rows[0]["site_code"] == a["site_code"]
    assert counts[a["site_code"]] >= a["expected_signal"]["ratio_to_other_sites_min"] * max(
        others, 1
    )


def test_a4_incident_spike_after_shift_change(
    db: psycopg.Connection[Any], ground_truth: dict[str, Any]
) -> None:
    a = anomaly(ground_truth, "A4")
    exp = a["expected_signal"]
    change = date.fromisoformat(a["change_date"])
    change_week = change - timedelta(days=change.weekday())
    rows = run(
        db,
        a["query"],
        date_from=change_week - timedelta(weeks=exp["baseline_weeks"]),
        date_to=date.fromisoformat(a["date_to"]),
        site_codes=[a["site_code"]],
    )
    # Exclude the partial week containing the change date from both sides.
    before = [r["incidents"] for r in rows if r["week_start"] < change_week]
    after = [r["incidents"] for r in rows if r["week_start"] > change_week]
    assert len(before) == exp["baseline_weeks"]
    rate_before = max(sum(before) / len(before), 0.5)
    rate_after = sum(after) / len(after)
    assert rate_after >= exp["weekly_rate_ratio_min"] * rate_before


def test_site_scoping_filters_rows(
    db: psycopg.Connection[Any], ground_truth: dict[str, Any]
) -> None:
    a = anomaly(ground_truth, "A1")
    rows = run(db, a["query"], date_from=a["date_from"], date_to=a["date_to"], site_codes=["JNU"])
    assert [r["site_code"] for r in rows] == ["JNU"]


def test_unknown_query_rejected() -> None:
    with pytest.raises(KeyError):
        load_query("drop_everything")
