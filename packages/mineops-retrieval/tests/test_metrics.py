import math

import pytest

from mineops_retrieval.metrics import dedupe, mrr_at, ndcg_at, percentile, recall_at

QRELS = {"a": 2, "b": 1, "c": 1}


def test_recall() -> None:
    assert recall_at(["a", "x", "b"], QRELS, 5) == pytest.approx(2 / 3)
    assert recall_at(["x"] * 5 + ["a"], QRELS, 5) == 0.0


def test_mrr_uses_highest_grade() -> None:
    assert mrr_at(["b", "a"], QRELS) == 0.5  # "b" is only grade 1
    assert mrr_at(["b"], {"b": 1, "c": 1}) == 1.0  # no grade 2 -> top grade is 1
    assert mrr_at(["x"], QRELS) == 0.0


def test_ndcg() -> None:
    assert ndcg_at(["a", "b", "c"], QRELS) == pytest.approx(1.0)
    worst = ndcg_at(["c", "b", "a"], QRELS)
    ideal = 3 + 1 / math.log2(3) + 1 / 2
    assert worst == pytest.approx((1 + 1 / math.log2(3) + 3 / 2) / ideal)
    assert ndcg_at(["x"], {}) == 0.0


def test_dedupe_and_percentile() -> None:
    assert dedupe(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
    assert percentile([5, 1, 3, 2, 4], 50) == 3
    assert percentile([float(i) for i in range(1, 101)], 95) == 95.0
    assert percentile([], 95) == 0.0
