"""Rank fusion. Pure functions over ``id -> score`` / ranked id lists.

RRF (Cormack et al. 2009): score(d) = sum_i 1 / (k + rank_i(d)). Uses ranks only, so BM25
scores (unbounded, query-dependent) and cosine similarities (bounded, compressed) need no
calibration. k=60 damps the head: rank 1 vs rank 2 differ by ~1.6%, so one engine's top hit
cannot dominate when the other engine disagrees.

Weighted fusion: min-max normalise each engine's scores within the candidate list, then take a
weighted sum (missing = 0). Sensitive to score distributions and outliers, so it is kept only
as the eval baseline (ADR-0002).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def rrf(rankings: Sequence[Sequence[str]], k: int = 60) -> list[tuple[str, float]]:
    if k < 1:
        raise ValueError("k must be >= 1")
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def min_max(scores: Mapping[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    if hi == lo:
        return {d: 1.0 for d in scores}
    return {d: (s - lo) / (hi - lo) for d, s in scores.items()}


def weighted(
    runs: Sequence[Mapping[str, float]], weights: Sequence[float]
) -> list[tuple[str, float]]:
    if len(runs) != len(weights):
        raise ValueError("one weight per run")
    fused: dict[str, float] = {}
    for run, w in zip(runs, weights, strict=True):
        for d, s in min_max(run).items():
            fused[d] = fused.get(d, 0.0) + w * s
    return sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
