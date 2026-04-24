"""RAG 检索链路内部数据模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievalResult(BaseModel):
    """单条召回结果。"""

    chunk_id: str = Field(default="", description="知识块 ID")
    parent_id: str = Field(default="", description="父块 ID")
    doc_id: str = Field(default="", description="文档 ID")
    content: str = Field(default="", description="命中的文本内容")
    score: float = Field(default=0.0, description="兼容字段，默认等于 rerank/fusion/dense 的最佳分值")
    category: str = Field(default="", description="知识分类")
    source: str = Field(default="", description="来源")
    title: str = Field(default="", description="文档标题")
    heading_path: str = Field(default="", description="章节路径")
    locator: str = Field(default="", description="定位信息")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    dense_score: float | None = Field(default=None, description="向量召回分数")
    bm25_score: float | None = Field(default=None, description="BM25 召回分数")
    fusion_score: float | None = Field(default=None, description="加权 RRF 融合分数")
    rerank_score: float | None = Field(default=None, description="重排分数")
    rank: int = Field(default=0, description="最终排序名次")


class RetrievedParentContext(BaseModel):
    """用于最终 prompt 的父块上下文。"""

    parent_id: str = Field(default="", description="父块 ID")
    doc_id: str = Field(default="", description="文档 ID")
    title: str = Field(default="", description="文档标题")
    source: str = Field(default="", description="来源")
    heading_path: str = Field(default="", description="章节路径")
    locator: str = Field(default="", description="定位信息")
    content: str = Field(default="", description="父块完整内容")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    supporting_children: list[RetrievalResult] = Field(
        default_factory=list,
        description="支撑该父块的子块召回结果",
    )


class RetrievalRequest(BaseModel):
    """检索请求参数。"""

    query: str = Field(..., min_length=1, description="检索查询文本")
    knowledge_types: list[str] = Field(
        default_factory=list,
        description="要检索的知识库类型列表，为空时检索所有类型",
    )
    top_k: int = Field(default=5, ge=1, le=50, description="返回的最大结果数")
    user_id: str = Field(default="", description="用户 ID（用于记忆/风格样本检索）")


class HybridRetrievalResponse(BaseModel):
    """混合召回后的上下文结果。"""

    query: str = Field(default="", description="主检索查询")
    candidates: list[RetrievalResult] = Field(default_factory=list, description="最终候选 child")
    parent_contexts: list[RetrievedParentContext] = Field(
        default_factory=list,
        description="最终进入 prompt 的父块上下文",
    )
    rerank_applied: bool = Field(default=False, description="是否成功应用 rerank")
    rerank_error: str = Field(default="", description="rerank 失败原因")
