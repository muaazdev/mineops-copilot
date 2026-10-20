"""Boundary models for retrieval: chunks and search results."""

from __future__ import annotations

import uuid
from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

Lang = Literal["en", "ar"]

# Stable namespace so a chunk always maps to the same Qdrant point ID (idempotent re-ingest).
CHUNK_NAMESPACE = uuid.UUID("6f1c3c1e-6b0e-4c55-9a59-4a0f3b7d2e10")


class Chunk(BaseModel):
    chunk_id: str  # "<doc_id>#<chunk_idx>"
    doc_id: str
    code: str
    chunk_idx: int
    section_path: list[str]
    title: str
    text: str  # embedded / indexed text, starts with a "title > section" header line
    doc_type: str
    site: str
    asset_type: str
    lang: Lang
    version: int
    effective_date: date
    supersedes: str | None = None
    superseded_on: date | None = None  # effective date of the newer revision, if any
    is_latest: bool = True
    n_tokens: int

    @property
    def point_id(self) -> str:
        return str(uuid.uuid5(CHUNK_NAMESPACE, self.chunk_id))

    def payload(self) -> dict[str, Any]:
        """JSON-safe payload shared by OpenSearch documents and Qdrant points."""
        return self.model_dump(mode="json")


class Mode(StrEnum):
    bm25 = "bm25"
    dense = "dense"
    hybrid = "hybrid"
    hybrid_weighted = "hybrid_weighted"
    hybrid_rerank = "hybrid_rerank"


class Hit(BaseModel):
    chunk: Chunk
    score: float  # final score for the requested mode
    scores: dict[str, float] = Field(default_factory=dict)  # per stage: bm25, dense, fused, rerank
    ranks: dict[str, int] = Field(default_factory=dict)  # 1-based rank per stage


class SearchResult(BaseModel):
    query: str
    query_lang: Lang
    mode: Mode
    hits: list[Hit]
    timings_ms: dict[str, float] = Field(default_factory=dict)
