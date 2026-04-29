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
    """目的：融合多个有序检索列表，计算每个文档的 RRF 综合得分并返回降序排列的结果，
    结果：返回文档 ID 和对应 RRF 得分的元组列表，按得分降序排列。
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
    """目的：在融合多路召回结果时按来源或 query 重要性调整得分贡献。
    结果：返回文档 ID 与加权 RRF 分数的降序列表。
    """
    scores: dict[str, float] = {}
    for ranks, weight in ranked_lists:
        if not ranks or weight <= 0:
            continue
        for rank, doc_id in enumerate(ranks, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + float(weight) * (1.0 / (k + rank))
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


def rrf_rank_only(ranked_lists: list[list[str]], *, k: int = 60) -> list[str]:
    """目的：提供轻量级接口，直接返回融合排序后的文档 ID 列表，
    结果：返回文档 ID 列表，按 RRF 融合得分降序排列。
    """
    return [doc_id for doc_id, _ in reciprocal_rank_fusion(ranked_lists, k=k)]


def weighted_rrf_rank_only(
    ranked_lists: list[tuple[list[str], float]],
    *,
    k: int = 60,
) -> list[str]:
    """目的：为只关心排序 ID 的调用方隐藏得分细节。
    结果：返回按加权 RRF 得分降序排列的文档 ID 列表。
    """
    return [doc_id for doc_id, _ in weighted_reciprocal_rank_fusion(ranked_lists, k=k)]
