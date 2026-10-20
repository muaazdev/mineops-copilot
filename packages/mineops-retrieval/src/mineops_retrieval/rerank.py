"""Rerankers behind one protocol.

* ``CrossEncoderReranker`` — bge-reranker-v2-m3 (multilingual, XLM-R based), pinned revision.
  Scores (query, passage) pairs jointly, so it can use word order and cross-attention that
  bi-encoders and BM25 cannot; it is too slow to run over the whole corpus, hence top-N only.
* ``OverlapReranker`` — deterministic token-overlap scorer for integration tests.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Protocol

_WORD = re.compile(r"\w+", re.UNICODE)


class Reranker(Protocol):
    name: str

    def score(self, query: str, passages: Sequence[str]) -> list[float]: ...


class OverlapReranker:
    name = "overlap"

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        q = {w.lower() for w in _WORD.findall(query)}
        out: list[float] = []
        for p in passages:
            words = {w.lower() for w in _WORD.findall(p)}
            out.append(len(q & words) / (len(q) or 1))
        return out


class CrossEncoderReranker:
    def __init__(
        self, model: str, revision: str, device: str = "cpu", batch_size: int = 8,
        max_length: int = 512,
    ) -> None:  # fmt: skip
        from sentence_transformers import CrossEncoder  # heavy import: torch

        self._model: Any = CrossEncoder(
            model, revision=revision, device=device, max_length=max_length
        )
        self.batch_size = batch_size
        self.name = f"{model}@{revision[:7]}"

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        scores = self._model.predict(
            [(query, p) for p in passages], batch_size=self.batch_size, show_progress_bar=False
        )
        return [float(s) for s in scores]
