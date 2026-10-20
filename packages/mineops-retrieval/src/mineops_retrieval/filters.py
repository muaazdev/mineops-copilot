"""One filter model, two translators (ADR-0002: filters must mean the same in both engines).

Semantics (``RetrievalFilter.matches`` is the reference implementation the translators are
property-tested against):
- ``site`` / ``asset_type``: a document scoped to ``"all"`` applies everywhere, so filtering on
  site FRN matches documents with site FRN *or* all.
- ``doc_type`` / ``lang``: exact match.
- ``as_of``: only documents already in effect (``effective_date <= as_of``).
- ``latest_only``: without ``as_of``, the current revision (``is_latest``). With ``as_of``, the
  revision that was current on that date: not yet superseded (``superseded_on`` missing or
  ``> as_of``). A static ``is_latest`` flag alone would wrongly hide the then-current revision.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict
from qdrant_client import models as qm

from mineops_retrieval.models import Chunk, Lang

SCOPE_ALL = "all"


class RetrievalFilter(BaseModel):
    model_config = ConfigDict(frozen=True)

    site: str | None = None
    asset_type: str | None = None
    doc_type: str | None = None
    lang: Lang | None = None
    as_of: date | None = None
    latest_only: bool = True

    def matches(self, c: Chunk) -> bool:
        if self.site is not None and c.site not in (self.site, SCOPE_ALL):
            return False
        if self.asset_type is not None and c.asset_type not in (self.asset_type, SCOPE_ALL):
            return False
        if self.doc_type is not None and c.doc_type != self.doc_type:
            return False
        if self.lang is not None and c.lang != self.lang:
            return False
        if self.as_of is not None and c.effective_date > self.as_of:
            return False
        if self.latest_only:
            if self.as_of is None:
                return c.is_latest
            return c.superseded_on is None or c.superseded_on > self.as_of
        return True


def to_opensearch(f: RetrievalFilter) -> list[dict[str, Any]]:
    """Clauses for a ``bool.filter`` (filter context: cached, no effect on BM25 scores)."""
    clauses: list[dict[str, Any]] = []
    if f.site is not None:
        clauses.append({"terms": {"site": [f.site, SCOPE_ALL]}})
    if f.asset_type is not None:
        clauses.append({"terms": {"asset_type": [f.asset_type, SCOPE_ALL]}})
    if f.doc_type is not None:
        clauses.append({"term": {"doc_type": f.doc_type}})
    if f.lang is not None:
        clauses.append({"term": {"lang": f.lang}})
    if f.as_of is not None:
        clauses.append({"range": {"effective_date": {"lte": f.as_of.isoformat()}}})
    if f.latest_only:
        if f.as_of is None:
            clauses.append({"term": {"is_latest": True}})
        else:
            # null values are not indexed in OpenSearch, so "not superseded" == field missing.
            clauses.append(
                {
                    "bool": {
                        "should": [
                            {"bool": {"must_not": {"exists": {"field": "superseded_on"}}}},
                            {"range": {"superseded_on": {"gt": f.as_of.isoformat()}}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )
    return clauses


def _day(d: date) -> str:
    # Qdrant datetime payloads are RFC 3339; dates are stored as midnight UTC.
    return f"{d.isoformat()}T00:00:00Z"


def to_qdrant(f: RetrievalFilter) -> qm.Filter | None:
    must: list[qm.Condition] = []
    if f.site is not None:
        must.append(qm.FieldCondition(key="site", match=qm.MatchAny(any=[f.site, SCOPE_ALL])))
    if f.asset_type is not None:
        must.append(
            qm.FieldCondition(key="asset_type", match=qm.MatchAny(any=[f.asset_type, SCOPE_ALL]))
        )
    if f.doc_type is not None:
        must.append(qm.FieldCondition(key="doc_type", match=qm.MatchValue(value=f.doc_type)))
    if f.lang is not None:
        must.append(qm.FieldCondition(key="lang", match=qm.MatchValue(value=f.lang)))
    if f.as_of is not None:
        must.append(
            qm.FieldCondition(key="effective_date", range=qm.DatetimeRange(lte=_day(f.as_of)))
        )
    if f.latest_only:
        if f.as_of is None:
            must.append(qm.FieldCondition(key="is_latest", match=qm.MatchValue(value=True)))
        else:
            must.append(
                qm.Filter(
                    should=[
                        qm.IsEmptyCondition(is_empty=qm.PayloadField(key="superseded_on")),
                        qm.FieldCondition(
                            key="superseded_on", range=qm.DatetimeRange(gt=_day(f.as_of))
                        ),
                    ]
                )
            )
    return qm.Filter(must=must) if must else None
