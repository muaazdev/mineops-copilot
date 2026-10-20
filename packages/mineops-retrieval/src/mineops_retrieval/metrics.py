"""Retrieval metrics over a ranked list of document IDs and graded qrels (0/1/2).

* recall@k — share of documents with rel >= 1 found in the top k.
* MRR@10   — reciprocal rank of the first document carrying the query's *highest* grade
  (normally 2 = "answers the question in the right revision"); 0 if absent from the top 10.
* nDCG@10  — graded gain 2^rel - 1, log2 discount, normalised by the ideal ordering.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from statistics import fmean


def dedupe(ids: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(ids))


def recall_at(ranked: Sequence[str], qrels: Mapping[str, int], k: int) -> float:
    rel = {d for d, r in qrels.items() if r >= 1}
    return len(rel & set(ranked[:k])) / len(rel) if rel else 0.0


def mrr_at(ranked: Sequence[str], qrels: Mapping[str, int], k: int = 10) -> float:
    if not qrels:
        return 0.0
    top = max(qrels.values())
    for i, d in enumerate(ranked[:k], start=1):
        if qrels.get(d, 0) == top:
            return 1.0 / i
    return 0.0


def ndcg_at(ranked: Sequence[str], qrels: Mapping[str, int], k: int = 10) -> float:
    def dcg(gains: Sequence[int]) -> float:
        return float(sum((2.0**g - 1) / math.log2(i + 1) for i, g in enumerate(gains, start=1)))

    ideal = dcg(sorted(qrels.values(), reverse=True)[:k])
    return dcg([qrels.get(d, 0) for d in ranked[:k]]) / ideal if ideal else 0.0


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile (p in 0..100)."""
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, max(0, math.ceil(p / 100 * len(s)) - 1))]


def summarise(
    runs: Mapping[str, Sequence[str]], qrels: Mapping[str, Mapping[str, int]]
) -> dict[str, float]:
    qids = list(runs)
    return {
        "recall@5": fmean(recall_at(runs[q], qrels[q], 5) for q in qids),
        "recall@10": fmean(recall_at(runs[q], qrels[q], 10) for q in qids),
        "mrr@10": fmean(mrr_at(runs[q], qrels[q]) for q in qids),
        "ndcg@10": fmean(ndcg_at(runs[q], qrels[q]) for q in qids),
    }
