"""检索结果融合模块：提供多路召回结果的重排序融合算法。

目的：作为 fusion 子包的入口，统一导出 Reciprocal Rank Fusion (RRF) 融合算法，
使 RAG 系统可以将多个检索来源的结果进行智能融合排序，
提高最终检索结果的质量和多样性。
结果：导出 rrf_rank_only 函数。
"""

from .rrf import (
    reciprocal_rank_fusion,
    rrf_rank_only,
    weighted_reciprocal_rank_fusion,
    weighted_rrf_rank_only,
)

__all__ = [
    "reciprocal_rank_fusion",
    "rrf_rank_only",
    "weighted_reciprocal_rank_fusion",
    "weighted_rrf_rank_only",
]
