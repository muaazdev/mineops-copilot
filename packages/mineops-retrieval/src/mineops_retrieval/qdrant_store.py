"""Qdrant dense index for chunks.

* Cosine distance: BGE-M3 dense vectors are trained for cosine similarity; we also
  L2-normalise at embed time, so cosine == dot product.
* Payload indexes on every filter field. Without them Qdrant must scan payloads during
  filtered HNSW search; with them it can pre-filter and pick a filter-aware search plan.
* Point IDs are UUIDv5 of the chunk ID, so re-ingesting the same chunk overwrites it.
* Re-ingest drops and recreates the collection (65 chunks, seconds); production would write a
  new collection and swap a collection alias, like the OpenSearch side.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client import models as qm

from mineops_retrieval.filters import RetrievalFilter, to_qdrant
from mineops_retrieval.models import Chunk

KEYWORD_FIELDS = ("site", "asset_type", "doc_type", "lang", "doc_id", "code")
DATETIME_FIELDS = ("effective_date", "superseded_on")


def _to_payload(c: Chunk) -> dict[str, Any]:
    p = c.payload()
    for key in DATETIME_FIELDS:
        if p[key] is not None:
            p[key] = f"{p[key]}T00:00:00Z"  # RFC 3339 for the datetime payload index
    return p


def _from_payload(p: dict[str, Any]) -> Chunk:
    q = dict(p)
    for key in DATETIME_FIELDS:
        if q.get(key):
            q[key] = str(q[key])[:10]
    return Chunk.model_validate(q)


class QdrantStore:
    def __init__(self, url: str, collection: str, client: QdrantClient | None = None) -> None:
        self.collection = collection
        self.client = client or QdrantClient(url=url, timeout=30)

    def rebuild(
        self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]], dim: int
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors differ in length")
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        self.client.create_collection(
            self.collection,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
        for key in KEYWORD_FIELDS:
            self.client.create_payload_index(self.collection, key, qm.PayloadSchemaType.KEYWORD)
        for key in DATETIME_FIELDS:
            self.client.create_payload_index(self.collection, key, qm.PayloadSchemaType.DATETIME)
        self.client.create_payload_index(self.collection, "is_latest", qm.PayloadSchemaType.BOOL)
        batch = 64
        for i in range(0, len(chunks), batch):
            self.client.upsert(
                self.collection,
                points=[
                    qm.PointStruct(id=c.point_id, vector=list(v), payload=_to_payload(c))
                    for c, v in zip(chunks[i : i + batch], vectors[i : i + batch], strict=True)
                ],
                wait=True,
            )

    def count(self) -> int:
        return int(self.client.count(self.collection, exact=True).count)

    def search(
        self, vector: Sequence[float], flt: RetrievalFilter, size: int
    ) -> list[tuple[Chunk, float]]:
        resp = self.client.query_points(
            self.collection,
            query=list(vector),
            query_filter=to_qdrant(flt),
            limit=size,
            with_payload=True,
        )
        return [(_from_payload(p.payload or {}), float(p.score)) for p in resp.points]

    def filter_ids(self, flt: RetrievalFilter, size: int = 1000) -> set[str]:
        points, _ = self.client.scroll(
            self.collection, scroll_filter=to_qdrant(flt), limit=size, with_payload=["chunk_id"]
        )
        return {str((p.payload or {})["chunk_id"]) for p in points}
