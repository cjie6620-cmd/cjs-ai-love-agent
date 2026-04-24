from rag.fusion import (
    reciprocal_rank_fusion,
    rrf_rank_only,
    weighted_reciprocal_rank_fusion,
    weighted_rrf_rank_only,
)


def test_rrf_fusion_orders_by_sum_of_reciprocal_ranks() -> None:
    """验证 rrf fusion orders by sum of reciprocal ranks。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    dense = ["b", "a", "c"]
    sparse = ["b", "d", "e"]
    merged = reciprocal_rank_fusion([dense, sparse], k=60)
    ids = [x[0] for x in merged]
    assert ids[0] == "b"
    assert set(ids) == {"a", "b", "c", "d", "e"}


def test_rrf_rank_only_matches_scores_order() -> None:
    """验证 rrf rank only matches scores order。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    out = rrf_rank_only([["x", "y"], ["y", "z"]], k=60)
    assert len(out) == 3
    assert out[0] == "y"


def test_weighted_rrf_gives_priority_to_higher_weight_query() -> None:
    """高权重列表应更明显地影响最终排序。"""
    ranked = weighted_reciprocal_rank_fusion(
        [
            (["a", "b", "c"], 1.0),
            (["b", "c", "d"], 0.3),
        ],
        k=60,
    )

    ids = [item[0] for item in ranked]
    assert ids[0] == "b"
    assert ids.index("a") < ids.index("d")
    assert weighted_rrf_rank_only([(["x", "y"], 1.0), (["y", "z"], 0.5)], k=60)[0] == "y"
