"""Reciprocal Rank Fusion：多路有序列表融合为单一得分排序。

目的：提供 RRF 算法实现，用于将多路检索结果融合为统一的排序列表，
通过计算每个文档在所有检索列表中的综合得分来生成最终排序，
提高检索结果的多样性和准确性。
结果：导出 reciprocal_rank_fusion 和 rrf_rank_only 函数。
"""

from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    """对多路检索结果（每路为文档 id 的有序列表，名次从 1 起）计算 RRF 得分并降序排序。

    目的：融合多个有序检索列表，计算每个文档的 RRF 综合得分并返回降序排列的结果，
    使来自不同检索来源的结果能够公平地竞争排序位置。
    结果：返回文档 ID 和对应 RRF 得分的元组列表，按得分降序排列。

    算法说明：score(d) = sum_i 1 / (k + rank_i(d))；未出现在某路则该路贡献为 0。
    k 参数控制平滑因子，较大的 k 值会使不同排名位置的差异减小。
    """
    scores: dict[str, float] = {}
    for ranks in ranked_lists:
        for rank, doc_id in enumerate(ranks, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


def weighted_reciprocal_rank_fusion(
    ranked_lists: list[tuple[list[str], float]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    """支持每一路列表不同权重的 RRF。"""
    scores: dict[str, float] = {}
    for ranks, weight in ranked_lists:
        if not ranks or weight <= 0:
            continue
        for rank, doc_id in enumerate(ranks, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + float(weight) * (1.0 / (k + rank))
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


def rrf_rank_only(ranked_lists: list[list[str]], *, k: int = 60) -> list[str]:
    """仅返回融合后的 id 序列。

    目的：提供轻量级接口，直接返回融合排序后的文档 ID 列表，
    忽略得分信息，适用于只需要排序结果而不需要得分的场景。
    结果：返回文档 ID 列表，按 RRF 融合得分降序排列。
    """
    return [doc_id for doc_id, _ in reciprocal_rank_fusion(ranked_lists, k=k)]


def weighted_rrf_rank_only(
    ranked_lists: list[tuple[list[str], float]],
    *,
    k: int = 60,
) -> list[str]:
    """仅返回加权 RRF 的排序结果。"""
    return [doc_id for doc_id, _ in weighted_reciprocal_rank_fusion(ranked_lists, k=k)]
