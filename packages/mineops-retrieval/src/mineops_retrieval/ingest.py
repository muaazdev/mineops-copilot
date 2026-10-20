"""Wire settings -> components, and run corpus -> chunks -> OpenSearch + Qdrant."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from mineops_core.settings import SearchSettings
from mineops_retrieval.chunking import chunk_corpus
from mineops_retrieval.embedders import Embedder, HashingEmbedder, SentenceTransformerEmbedder
from mineops_retrieval.models import Chunk
from mineops_retrieval.opensearch_store import OpenSearchStore
from mineops_retrieval.qdrant_store import QdrantStore
from mineops_retrieval.rerank import CrossEncoderReranker, OverlapReranker, Reranker
from mineops_retrieval.retriever import HybridRetriever
from mineops_retrieval.tokens import hf_token_counter

log = logging.getLogger(__name__)


def make_embedder(s: SearchSettings) -> Embedder:
    if s.embedder == "hashing":
        return HashingEmbedder()
    return SentenceTransformerEmbedder(s.embed_model, s.embed_revision, s.device)


def make_reranker(s: SearchSettings) -> Reranker:
    if s.embedder == "hashing":
        return OverlapReranker()
    return CrossEncoderReranker(s.rerank_model, s.rerank_revision, s.device)


def make_stores(s: SearchSettings) -> tuple[OpenSearchStore, QdrantStore]:
    return (
        OpenSearchStore(s.opensearch_url, s.opensearch_index),
        QdrantStore(s.qdrant_url, s.qdrant_collection),
    )


def make_retriever(s: SearchSettings, *, with_reranker: bool = True) -> HybridRetriever:
    os_store, qd_store = make_stores(s)
    return HybridRetriever(
        os_store,
        qd_store,
        make_embedder(s),
        make_reranker(s) if with_reranker else None,
        rrf_k=s.rrf_k,
        candidates=s.candidates,
    )


@dataclass(frozen=True)
class IngestReport:
    documents: int
    chunks: int
    opensearch_index: str
    embedder: str
    seconds: dict[str, float]


def ingest(
    corpus_dir: Path,
    s: SearchSettings,
    embedder: Embedder | None = None,
    stores: tuple[OpenSearchStore, QdrantStore] | None = None,
) -> IngestReport:
    t = {"start": time.perf_counter()}
    chunks: list[Chunk] = chunk_corpus(
        corpus_dir,
        hf_token_counter(s.embed_model, s.embed_revision),
        s.chunk_max_tokens,
        s.chunk_overlap_tokens,
    )
    t["chunked"] = time.perf_counter()
    embedder = embedder or make_embedder(s)
    vectors = embedder.embed_documents([c.text for c in chunks])
    t["embedded"] = time.perf_counter()
    os_store, qd_store = stores or make_stores(s)
    index = os_store.rebuild(chunks)
    qd_store.rebuild(chunks, vectors, embedder.dim)
    t["indexed"] = time.perf_counter()
    report = IngestReport(
        documents=len({c.doc_id for c in chunks}),
        chunks=len(chunks),
        opensearch_index=index,
        embedder=embedder.name,
        seconds={
            "chunk": round(t["chunked"] - t["start"], 2),
            "embed": round(t["embedded"] - t["chunked"], 2),
            "index": round(t["indexed"] - t["embedded"], 2),
        },
    )
    log.info("ingest complete", extra={"chunks": report.chunks, "index": index})
    return report
