"""``HybridRetriever``: one entry point for BM25, dense, hybrid (RRF / weighted), and
hybrid + cross-encoder rerank. Every hit carries per-stage scores and ranks, so the eval and
the knowledge agent can explain *why* a chunk was returned."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from mineops_retrieval.embedders import Embedder
from mineops_retrieval.filters import RetrievalFilter
from mineops_retrieval.fusion import rrf, weighted
from mineops_retrieval.lang import detect_lang
from mineops_retrieval.models import Chunk, Hit, Lang, Mode, SearchResult
from mineops_retrieval.opensearch_store import OpenSearchStore
from mineops_retrieval.qdrant_store import QdrantStore
from mineops_retrieval.rerank import Reranker


class HybridRetriever:
    def __init__(
        self,
        os_store: OpenSearchStore,
        qd_store: QdrantStore,
        embedder: Embedder,
        reranker: Reranker | None = None,
        *,
        rrf_k: int = 60,
        candidates: int = 30,
        weights: tuple[float, float] = (0.5, 0.5),
    ) -> None:
        self.os = os_store
        self.qd = qd_store
        self.embedder = embedder
        self.reranker = reranker
        self.rrf_k = rrf_k
        self.candidates = candidates
        self.weights = weights
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="retrieval")

    def _bm25(
        self, q: str, lang: Lang, f: RetrievalFilter, n: int
    ) -> tuple[list[tuple[Chunk, float]], float]:
        t = time.perf_counter()
        hits = self.os.search(q, lang, f, n)
        return hits, (time.perf_counter() - t) * 1000

    def _dense(self, q: str, f: RetrievalFilter, n: int) -> tuple[list[tuple[Chunk, float]], float]:
        t = time.perf_counter()
        hits = self.qd.search(self.embedder.embed_query(q), f, n)
        return hits, (time.perf_counter() - t) * 1000

    def search(
        self,
        query: str,
        flt: RetrievalFilter | None = None,
        mode: Mode = Mode.hybrid_rerank,
        k: int = 8,
    ) -> SearchResult:
        flt = flt or RetrievalFilter()
        lang = detect_lang(query)
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        n = max(self.candidates, k)

        bm25: list[tuple[Chunk, float]] = []
        dense: list[tuple[Chunk, float]] = []
        if mode == Mode.bm25:
            bm25, timings["bm25"] = self._bm25(query, lang, flt, n)
        elif mode == Mode.dense:
            dense, timings["dense"] = self._dense(query, flt, n)
        else:
            # ADR-0002: both engines queried in parallel with identical filters.
            fb = self._pool.submit(self._bm25, query, lang, flt, n)
            fd = self._pool.submit(self._dense, query, flt, n)
            (bm25, timings["bm25"]), (dense, timings["dense"]) = fb.result(), fd.result()

        chunks: dict[str, Chunk] = {}
        scores: dict[str, dict[str, float]] = {}
        ranks: dict[str, dict[str, int]] = {}
        for stage, run in (("bm25", bm25), ("dense", dense)):
            for r, (c, s) in enumerate(run, start=1):
                chunks[c.chunk_id] = c
                scores.setdefault(c.chunk_id, {})[stage] = s
                ranks.setdefault(c.chunk_id, {})[stage] = r

        if mode in (Mode.bm25, Mode.dense):
            order = [(c.chunk_id, s) for c, s in (bm25 or dense)]
        elif mode == Mode.hybrid_weighted:
            order = weighted(
                [{c.chunk_id: s for c, s in bm25}, {c.chunk_id: s for c, s in dense}],
                self.weights,
            )
        else:
            order = rrf([[c.chunk_id for c, _ in bm25], [c.chunk_id for c, _ in dense]], self.rrf_k)
        if mode not in (Mode.bm25, Mode.dense):
            for r, (cid, s) in enumerate(order, start=1):
                scores[cid]["fused"] = s
                ranks[cid]["fused"] = r

        if mode == Mode.hybrid_rerank:
            if self.reranker is None:
                raise ValueError("hybrid_rerank requires a reranker")
            pool = [cid for cid, _ in order[: self.candidates]]
            t = time.perf_counter()
            rs = self.reranker.score(query, [chunks[cid].text for cid in pool])
            timings["rerank"] = (time.perf_counter() - t) * 1000
            order = sorted(zip(pool, rs, strict=True), key=lambda kv: (-kv[1], kv[0]))
            for r, (cid, s) in enumerate(order, start=1):
                scores[cid]["rerank"] = s
                ranks[cid]["rerank"] = r

        hits = [
            Hit(chunk=chunks[cid], score=s, scores=scores[cid], ranks=ranks[cid])
            for cid, s in order[:k]
        ]
        timings["total"] = (time.perf_counter() - t0) * 1000
        return SearchResult(query=query, query_lang=lang, mode=mode, hits=hits, timings_ms=timings)

    def close(self) -> None:
        self._pool.shutdown(wait=False)
