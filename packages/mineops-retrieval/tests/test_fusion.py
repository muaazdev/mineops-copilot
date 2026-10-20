import pytest

from mineops_retrieval.fusion import min_max, rrf, weighted


def test_rrf_scores_and_order() -> None:
    fused = dict(rrf([["a", "b", "c"], ["b", "d"]], k=60))
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert fused["a"] == pytest.approx(1 / 61)
    assert rrf([["a", "b", "c"], ["b", "d"]], k=60)[0][0] == "b"


def test_rrf_agreement_beats_single_top_hit() -> None:
    # "x" is rank 1 in one engine only; "y" is rank 2 in both -> y wins with k=60.
    order = [d for d, _ in rrf([["x", "y"], ["z", "y"]], k=60)]
    assert order[0] == "y"


def test_k_controls_head_dominance() -> None:
    # "y" is rank 4 in both engines; "x" is rank 1 in one engine only.
    runs = [["x", "a", "b", "y"], ["c", "d", "e", "y"]]
    assert rrf(runs, k=60)[0][0] == "y"  # 2/64 > 1/61: agreement wins
    assert rrf(runs, k=1)[0][0] in {"x", "c"}  # 1/2 > 2/5: head wins


def test_rrf_ties_are_deterministic_and_k_validated() -> None:
    assert rrf([["b"], ["a"]]) == rrf([["b"], ["a"]])
    assert [d for d, _ in rrf([["b"], ["a"]])] == ["a", "b"]
    with pytest.raises(ValueError):
        rrf([["a"]], k=0)


def test_min_max_and_weighted() -> None:
    assert min_max({"a": 10.0, "b": 0.0, "c": 5.0}) == {"a": 1.0, "b": 0.0, "c": 0.5}
    assert min_max({"a": 3.0}) == {"a": 1.0}
    assert min_max({}) == {}
    fused = dict(weighted([{"a": 12.0, "b": 2.0}, {"b": 0.9, "c": 0.1}], [0.5, 0.5]))
    assert fused == {"a": 0.5, "b": 0.5, "c": 0.0}
    with pytest.raises(ValueError):
        weighted([{"a": 1.0}], [0.5, 0.5])
