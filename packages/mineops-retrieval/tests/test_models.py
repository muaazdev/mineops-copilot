"""Opt-in checks with the real pinned models (``uv run pytest -m models``).

Excluded from the default run and CI: they load ~4.4 GB of weights on CPU. They pin down the
two properties the hashing stand-ins cannot show: cross-lingual dense similarity and
cross-encoder relevance ordering.
"""

from __future__ import annotations

import math

import pytest

from mineops_core.settings import get_settings
from mineops_retrieval.embedders import SentenceTransformerEmbedder
from mineops_retrieval.rerank import CrossEncoderReranker

pytestmark = pytest.mark.models


def cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    )


@pytest.fixture(scope="module")
def embedder() -> SentenceTransformerEmbedder:
    s = get_settings().search
    return SentenceTransformerEmbedder(s.embed_model, s.embed_revision)


def test_bge_m3_is_cross_lingual(embedder: SentenceTransformerEmbedder) -> None:
    en = embedder.embed_query("minimum brake lining thickness on haul trucks")
    ar, unrelated = embedder.embed_documents(
        [
            "استبدل بطانات الفرامل إذا قلت السماكة المتبقية عن 6 مم في شاحنات النقل.",
            "Water carts spray haul roads every two hours to control phosphate dust.",
        ]
    )
    assert embedder.dim == 1024
    assert cos(en, ar) > cos(en, unrelated) + 0.1


def test_cross_encoder_orders_by_relevance() -> None:
    s = get_settings().search
    rr = CrossEncoderReranker(s.rerank_model, s.rerank_revision)
    good, bad = rr.score(
        "how long does the fire watch stay after hot work",
        [
            "A fire watch stays at the work area during hot work and for 30 minutes after.",
            "Check tyre pressures cold; the target cold pressure is 700 kPa.",
        ],
    )
    assert good > bad
