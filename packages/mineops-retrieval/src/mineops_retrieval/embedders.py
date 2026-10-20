"""Embedders behind one protocol.

* ``SentenceTransformerEmbedder`` — BGE-M3 (dense head only, 1024-d), pinned revision, CPU.
  BGE-M3 needs no query instruction prefix, unlike BGE v1.5 / E5.
* ``HashingEmbedder`` — deterministic feature hashing of word unigrams + bigrams. No model
  download; integration tests use it so CI exercises real Qdrant search and filtering without
  pulling 2 GB of weights. It is lexical, so it says nothing about semantic quality — that is
  what the eval with the real model is for.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from itertools import pairwise
from typing import Any, Protocol

_WORD = re.compile(r"\w+", re.UNICODE)


class Embedder(Protocol):
    dim: int
    name: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashingEmbedder:
    def __init__(self, dim: int = 512) -> None:
        self.dim = dim
        self.name = f"hashing-{dim}"

    def _vec(self, text: str) -> list[float]:
        words = [w.lower() for w in _WORD.findall(text)]
        feats = words + [f"{a}_{b}" for a, b in pairwise(words)]
        v = [0.0] * self.dim
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class SentenceTransformerEmbedder:
    def __init__(self, model: str, revision: str, device: str = "cpu", batch_size: int = 8) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import: torch

        self._model: Any = SentenceTransformer(model, revision=revision, device=device)
        self._model.max_seq_length = 1024  # chunks are <= ~660 tokens; keep headroom
        self.batch_size = batch_size
        dim = self._model.get_embedding_dimension()
        if dim is None:
            raise ValueError(f"{model} does not report an embedding dimension")
        self.dim = int(dim)
        self.name = f"{model}@{revision[:7]}"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        out = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [list(map(float, row)) for row in out]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
