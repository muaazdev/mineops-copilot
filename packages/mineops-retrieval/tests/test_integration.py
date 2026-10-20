"""Integration tests on real OpenSearch 3.9 + Qdrant 1.19 (testcontainers), full corpus.

The embedder is the model-free HashingEmbedder: these tests check engines, mappings,
analyzers, filters and fusion plumbing — not semantic quality (that is the eval's job)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from mineops_core.settings import SearchSettings
from mineops_retrieval.embedders import HashingEmbedder
from mineops_retrieval.filters import RetrievalFilter
from mineops_retrieval.ingest import IngestReport, ingest
from mineops_retrieval.models import Chunk, Mode
from mineops_retrieval.opensearch_store import OpenSearchStore
from mineops_retrieval.qdrant_store import QdrantStore
from mineops_retrieval.retriever import HybridRetriever

pytestmark = pytest.mark.integration

FILTERS = [
    RetrievalFilter(),
    RetrievalFilter(latest_only=False),
    RetrievalFilter(lang="ar"),
    RetrievalFilter(site="JNU"),
    RetrievalFilter(site="FRN", asset_type="crusher"),
    RetrievalFilter(doc_type="maintenance_manual", lang="en"),
    RetrievalFilter(as_of=date(2025, 1, 1)),
    RetrievalFilter(as_of=date(2025, 12, 15), doc_type="safety_procedure"),
    RetrievalFilter(as_of=date(2024, 6, 1), latest_only=False),
    RetrievalFilter(site="WSP", asset_type="pump", lang="en", as_of=date(2026, 9, 1)),
]


def test_ingest_counts(ingested: IngestReport, stores: tuple[OpenSearchStore, QdrantStore]) -> None:
    assert (ingested.documents, ingested.chunks) == (64, 65)
    assert stores[0].count() == stores[1].count() == 65


@pytest.mark.parametrize("flt", FILTERS, ids=lambda f: f.model_dump_json(exclude_defaults=True))
def test_engines_and_reference_agree_on_filters(
    flt: RetrievalFilter, stores: tuple[OpenSearchStore, QdrantStore], chunks: list[Chunk],
    ingested: IngestReport,
) -> None:  # fmt: skip
    expected = {c.chunk_id for c in chunks if flt.matches(c)}
    assert stores[0].filter_ids(flt) == expected
    assert stores[1].filter_ids(flt) == expected
    assert expected  # every fixture filter selects something


def test_arabic_analyzer_normalises_hamza_and_strips_prefixes(
    stores: tuple[OpenSearchStore, QdrantStore],
) -> None:
    os_store = stores[0]
    # إجراء / اجراء and the definite article ال normalise to the same token.
    assert os_store.analyze("arabic", "الإجراء") == os_store.analyze("arabic", "اجراء")
    assert os_store.analyze("english", "inspections") == os_store.analyze("english", "inspect")


def test_arabic_query_without_hamza_finds_arabic_doc(retriever: HybridRetriever) -> None:
    res = retriever.search("اجراء العزل والاقفال", mode=Mode.bm25, k=3)
    assert res.query_lang == "ar"
    assert res.hits[0].chunk.doc_id == "LOTO-001-AR-R2"


def test_as_of_returns_then_current_revision(retriever: HybridRetriever) -> None:
    q = "how many workers may share a single danger lock on an isolation point"
    now = retriever.search(q, mode=Mode.bm25, k=5)
    then = retriever.search(q, RetrievalFilter(as_of=date(2025, 1, 1)), Mode.bm25, k=5)
    assert now.hits[0].chunk.doc_id == "LOTO-001-EN-R2"
    assert then.hits[0].chunk.doc_id == "LOTO-001-EN-R1"
    for res in (now, then):
        loto = [h.chunk.doc_id for h in res.hits if h.chunk.code == "LOTO-001"]
        assert len({d.split("-R")[1] for d in loto}) <= 1  # never both revisions


def test_site_filter_excludes_other_sites(retriever: HybridRetriever) -> None:
    res = retriever.search("underground ventilation gas monitoring", RetrievalFilter(site="WSP"))
    assert res.hits
    assert {h.chunk.site for h in res.hits} <= {"WSP", "all"}


@pytest.mark.parametrize("mode", list(Mode))
def test_every_mode_returns_stage_scores(retriever: HybridRetriever, mode: Mode) -> None:
    res = retriever.search("crusher main bearing temperature trip", mode=mode, k=5)
    assert len(res.hits) == 5
    assert res.hits[0].chunk.code == "MM-CR-002"
    top = res.hits[0]
    expected = {
        Mode.bm25: {"bm25"},
        Mode.dense: {"dense"},
        Mode.hybrid: {"fused"},
        Mode.hybrid_weighted: {"fused"},
        Mode.hybrid_rerank: {"fused", "rerank"},
    }[mode]
    assert expected <= top.scores.keys()
    assert [h.score for h in res.hits] == sorted((h.score for h in res.hits), reverse=True)
    assert "total" in res.timings_ms


def test_reingest_swaps_alias(
    ingested: IngestReport,
    stores: tuple[OpenSearchStore, QdrantStore],
    corpus_dir: Path,
    search_settings: SearchSettings,
) -> None:
    again = ingest(corpus_dir, search_settings, HashingEmbedder(), stores)
    assert again.opensearch_index != ingested.opensearch_index
    names = set(stores[0].client.indices.get(index=f"{stores[0].alias}-v*"))
    assert names == {again.opensearch_index}
    assert stores[0].count() == 65
