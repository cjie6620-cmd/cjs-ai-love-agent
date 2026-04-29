"""RAG 检索链路内部数据模型。

目的：定义召回候选、父块上下文、请求和响应等内部结构。
结果：向量召回、BM25、RRF、rerank 和 prompt 组装可以共享稳定契约。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievalResult(BaseModel):
    """目的：承载某个 child chunk 的内容、来源、分数和排序信息。
    结果：融合、重排和 API 转换阶段可以复用同一候选结构。
    """

    # 目的：保存 chunk_id 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 chunk_id 值。
    chunk_id: str = Field(default="", description="知识块 ID")
    # 目的：保存 parent_id 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 parent_id 值。
    parent_id: str = Field(default="", description="父块 ID")
    # 目的：保存 doc_id 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 doc_id 值。
    doc_id: str = Field(default="", description="文档 ID")
    # 目的：保存 content 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 content 值。
    content: str = Field(default="", description="命中的文本内容")
    # 目的：保存 score 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 score 值。
    score: float = Field(default=0.0, description="兼容字段，默认等于 rerank/fusion/dense 的最佳分值")
    # 目的：保存 category 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 category 值。
    category: str = Field(default="", description="知识分类")
    # 目的：保存 source 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source 值。
    source: str = Field(default="", description="来源")
    # 目的：保存 title 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: str = Field(default="", description="文档标题")
    # 目的：保存 heading_path 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 heading_path 值。
    heading_path: str = Field(default="", description="章节路径")
    # 目的：保存 locator 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 locator 值。
    locator: str = Field(default="", description="定位信息")
    # 目的：保存 metadata 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 metadata 值。
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    # 目的：保存 dense_score 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 dense_score 值。
    dense_score: float | None = Field(default=None, description="向量召回分数")
    # 目的：保存 bm25_score 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 bm25_score 值。
    bm25_score: float | None = Field(default=None, description="BM25 召回分数")
    # 目的：保存 fusion_score 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 fusion_score 值。
    fusion_score: float | None = Field(default=None, description="加权 RRF 融合分数")
    # 目的：保存 rerank_score 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_score 值。
    rerank_score: float | None = Field(default=None, description="重排分数")
    # 目的：保存 rank 字段，用于 RetrievalResult 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rank 值。
    rank: int = Field(default=0, description="最终排序名次")


class RetrievedParentContext(BaseModel):
    """目的：把被选中 child 所属的完整 parent 内容和支撑证据聚合在一起。
    结果：回复生成可以获得更完整的上下文，而不是只看到零散片段。
    """

    # 目的：保存 parent_id 字段，用于 RetrievedParentContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 parent_id 值。
    parent_id: str = Field(default="", description="父块 ID")
    # 目的：保存 doc_id 字段，用于 RetrievedParentContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 doc_id 值。
    doc_id: str = Field(default="", description="文档 ID")
    # 目的：保存 title 字段，用于 RetrievedParentContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: str = Field(default="", description="文档标题")
    # 目的：保存 source 字段，用于 RetrievedParentContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source 值。
    source: str = Field(default="", description="来源")
    # 目的：保存 heading_path 字段，用于 RetrievedParentContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 heading_path 值。
    heading_path: str = Field(default="", description="章节路径")
    # 目的：保存 locator 字段，用于 RetrievedParentContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 locator 值。
    locator: str = Field(default="", description="定位信息")
    # 目的：保存 content 字段，用于 RetrievedParentContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 content 值。
    content: str = Field(default="", description="父块完整内容")
    # 目的：保存 metadata 字段，用于 RetrievedParentContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 metadata 值。
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    # 目的：保存 supporting_children 字段，用于 RetrievedParentContext 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 supporting_children 值。
    supporting_children: list[RetrievalResult] = Field(
        default_factory=list,
        description="支撑该父块的子块召回结果",
    )


class RetrievalRequest(BaseModel):
    """目的：描述内部检索调用需要的 query、知识类型、数量和用户信息。
    结果：检索入口可以用统一参数对象接收请求。
    """

    # 目的：保存 query 字段，用于 RetrievalRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 query 值。
    query: str = Field(..., min_length=1, description="检索查询文本")
    # 目的：保存 knowledge_types 字段，用于 RetrievalRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_types 值。
    knowledge_types: list[str] = Field(
        default_factory=list,
        description="要检索的知识库类型列表，为空时检索所有类型",
    )
    # 目的：保存 top_k 字段，用于 RetrievalRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 top_k 值。
    top_k: int = Field(default=5, ge=1, le=50, description="返回的最大结果数")
    # 目的：保存 user_id 字段，用于 RetrievalRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: str = Field(default="", description="用户 ID（用于记忆/风格样本检索）")


class HybridRetrievalResponse(BaseModel):
    """目的：承载最终候选、父块上下文和 rerank 应用状态。
    结果：调用方可以同时使用证据列表、prompt 上下文和降级诊断。
    """

    # 目的：保存 query 字段，用于 HybridRetrievalResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 query 值。
    query: str = Field(default="", description="主检索查询")
    # 目的：保存 candidates 字段，用于 HybridRetrievalResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 candidates 值。
    candidates: list[RetrievalResult] = Field(default_factory=list, description="最终候选 child")
    # 目的：保存 parent_contexts 字段，用于 HybridRetrievalResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 parent_contexts 值。
    parent_contexts: list[RetrievedParentContext] = Field(
        default_factory=list,
        description="最终进入 prompt 的父块上下文",
    )
    # 目的：保存 rerank_applied 字段，用于 HybridRetrievalResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_applied 值。
    rerank_applied: bool = Field(default=False, description="是否成功应用 rerank")
    # 目的：保存 rerank_error 字段，用于 HybridRetrievalResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_error 值。
    rerank_error: str = Field(default="", description="rerank 失败原因")
