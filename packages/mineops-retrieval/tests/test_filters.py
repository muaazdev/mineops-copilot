"""Property test: the OpenSearch and Qdrant translations of a RetrievalFilter select exactly the
same chunks as the reference predicate. The two tiny evaluators below interpret only the query
shapes ``to_opensearch`` / ``to_qdrant`` emit; integration tests repeat the check on real
engines."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from qdrant_client import models as qm

from mineops_retrieval.filters import RetrievalFilter, to_opensearch, to_qdrant
from mineops_retrieval.models import Chunk

SITES = ["FRN", "WSP", "JNU", "all"]
ASSETS = ["crusher", "pump", "haul_truck", "all"]
DOC_TYPES = ["sop", "loto", "maintenance_manual"]
DATES = [date(2024, 1, 1), date(2025, 1, 1), date(2025, 6, 1), date(2026, 1, 1)]


def chunk(i: int, site: str, asset: str, doc_type: str, lang: str, eff: date,
          sup: date | None) -> Chunk:  # fmt: skip
    return Chunk(
        chunk_id=f"D{i}#0", doc_id=f"D{i}", code=f"D{i}", chunk_idx=0, section_path=["1"],
        title="t", text="t", doc_type=doc_type, site=site, asset_type=asset, lang=lang,  # type: ignore[arg-type]
        version=1, effective_date=eff, superseded_on=sup, is_latest=sup is None, n_tokens=1,
    )  # fmt: skip


chunks_st = st.lists(
    st.builds(
        chunk,
        st.integers(0, 10_000),
        st.sampled_from(SITES),
        st.sampled_from(ASSETS),
        st.sampled_from(DOC_TYPES),
        st.sampled_from(["en", "ar"]),
        st.sampled_from(DATES),
        st.one_of(st.none(), st.sampled_from(DATES)),
    ),
    min_size=1,
    max_size=30,
)
filters_st = st.builds(
    RetrievalFilter,
    site=st.one_of(st.none(), st.sampled_from(SITES[:3])),
    asset_type=st.one_of(st.none(), st.sampled_from(ASSETS[:3])),
    doc_type=st.one_of(st.none(), st.sampled_from(DOC_TYPES)),
    lang=st.one_of(st.none(), st.sampled_from(["en", "ar"])),
    as_of=st.one_of(st.none(), st.sampled_from([*DATES, date(2025, 3, 15)])),
    latest_only=st.booleans(),
)


# --- OpenSearch filter-context evaluator ---------------------------------------------------
def os_match(clause: dict[str, Any], doc: dict[str, Any]) -> bool:
    ((kind, body),) = clause.items()
    if kind == "terms":
        ((field, values),) = body.items()
        return doc.get(field) in values
    if kind == "term":
        ((field, value),) = body.items()
        return doc.get(field) == value
    if kind == "range":
        ((field, ops),) = body.items()
        v = doc.get(field)
        if v is None:
            return False
        return all({"lte": v <= x, "gt": v > x}[op] for op, x in ops.items())
    if kind == "exists":
        return doc.get(body["field"]) is not None
    if kind == "bool":
        ok = all(os_match(c, doc) for c in body.get("filter", []))
        ok &= not os_match(body["must_not"], doc) if "must_not" in body else True
        if "should" in body:
            ok &= sum(os_match(c, doc) for c in body["should"]) >= body["minimum_should_match"]
        return ok
    raise AssertionError(f"unexpected clause {kind}")


# --- Qdrant filter evaluator ---------------------------------------------------------------
def _qd_day(v: str | None) -> datetime | None:
    return None if v is None else datetime.fromisoformat(f"{v}T00:00:00+00:00")


def _as_dt(x: Any) -> datetime:
    return x if isinstance(x, datetime) else datetime.fromisoformat(str(x).replace("Z", "+00:00"))


def qd_match(cond: Any, payload: dict[str, Any]) -> bool:
    if isinstance(cond, qm.Filter):
        must = all(qd_match(c, payload) for c in cond.must or [])
        should = any(qd_match(c, payload) for c in cond.should) if cond.should else True
        return must and should
    if isinstance(cond, qm.IsEmptyCondition):
        return payload.get(cond.is_empty.key) in (None, [])
    if isinstance(cond, qm.FieldCondition):
        v = payload.get(cond.key)
        if isinstance(cond.match, qm.MatchAny):
            return v in cond.match.any
        if isinstance(cond.match, qm.MatchValue):
            return v == cond.match.value
        if isinstance(cond.range, qm.DatetimeRange):
            d = _qd_day(v)
            if d is None:
                return False
            r = cond.range
            return (r.lte is None or d <= _as_dt(r.lte)) and (r.gt is None or d > _as_dt(r.gt))
    raise AssertionError(f"unexpected condition {cond!r}")


@settings(max_examples=400, deadline=None)
@given(chunks_st, filters_st)
def test_translators_agree_with_reference(chunks: list[Chunk], f: RetrievalFilter) -> None:
    os_clauses = to_opensearch(f)
    qd_filter = to_qdrant(f)
    for c in chunks:
        p = c.payload()
        expected = f.matches(c)
        assert all(os_match(cl, p) for cl in os_clauses) == expected, (f, p)
        assert (qd_filter is None or qd_match(qd_filter, p)) == expected, (f, p)


def test_site_all_documents_apply_everywhere() -> None:
    c = chunk(1, "all", "all", "sop", "en", date(2025, 1, 1), None)
    assert RetrievalFilter(site="JNU", asset_type="pump").matches(c)


def test_as_of_returns_then_current_revision() -> None:
    old = chunk(1, "all", "all", "sop", "en", date(2024, 1, 1), date(2025, 6, 1))
    new = chunk(2, "all", "all", "sop", "en", date(2025, 6, 1), None)
    f = RetrievalFilter(as_of=date(2025, 1, 1))
    assert [c.doc_id for c in (old, new) if f.matches(c)] == ["D1"]
    assert [c.doc_id for c in (old, new) if RetrievalFilter().matches(c)] == ["D2"]
    no_latest = RetrievalFilter(as_of=date(2025, 7, 1), latest_only=False)
    assert [c.doc_id for c in (old, new) if no_latest.matches(c)] == ["D1", "D2"]
