"""RAG API 相关契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeIndexTextRequest(BaseModel):
    """目的：描述纯文本直接索引请求的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 text 字段，用于 KnowledgeIndexTextRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 text 值。
    text: str = Field(..., min_length=1, max_length=100_000, description="待索引的文本内容")
    # 目的：保存 title 字段，用于 KnowledgeIndexTextRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: str = Field(default="", max_length=255, description="知识标题")
    # 目的：保存 category 字段，用于 KnowledgeIndexTextRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 category 值。
    category: str = Field(
        default="relationship_knowledge",
        max_length=64,
        description="知识分类",
    )
    # 目的：保存 source 字段，用于 KnowledgeIndexTextRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source 值。
    source: str = Field(default="手工录入", max_length=255, description="来源标识")


class KnowledgeIndexResponse(BaseModel):
    """目的：描述索引操作统一响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 success 字段，用于 KnowledgeIndexResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 success 值。
    success: bool = Field(description="是否成功")
    # 目的：保存 filename 字段，用于 KnowledgeIndexResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 filename 值。
    filename: str = Field(default="", description="文件名")
    # 目的：保存 chunks_written 字段，用于 KnowledgeIndexResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 chunks_written 值。
    chunks_written: int = Field(default=0, description="成功写入的 chunk 数量")
    # 目的：保存 message 字段，用于 KnowledgeIndexResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 message 值。
    message: str = Field(default="", description="补充信息")


class KnowledgeBatchIndexResponse(BaseModel):
    """目的：描述批量索引响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 success 字段，用于 KnowledgeBatchIndexResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 success 值。
    success: bool = Field(description="是否整体成功")
    # 目的：保存 total_files 字段，用于 KnowledgeBatchIndexResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 total_files 值。
    total_files: int = Field(default=0, description="处理文件总数")
    # 目的：保存 total_chunks 字段，用于 KnowledgeBatchIndexResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 total_chunks 值。
    total_chunks: int = Field(default=0, description="成功写入 chunk 总数")
    # 目的：保存 results 字段，用于 KnowledgeBatchIndexResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 results 值。
    results: list[KnowledgeIndexResponse] = Field(default_factory=list, description="逐文件结果")
    # 目的：保存 message 字段，用于 KnowledgeBatchIndexResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 message 值。
    message: str = Field(default="", description="补充信息")


class KnowledgeSearchRequest(BaseModel):
    """目的：描述知识检索请求的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 query 字段，用于 KnowledgeSearchRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 query 值。
    query: str = Field(..., min_length=1, max_length=2000, description="检索查询文本")
    # 目的：保存 top_k 字段，用于 KnowledgeSearchRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 top_k 值。
    top_k: int = Field(default=5, ge=1, le=50, description="返回最大结果数")
    # 目的：保存 category 字段，用于 KnowledgeSearchRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 category 值。
    category: str | None = Field(default=None, description="分类过滤")


class KnowledgeSearchResultItem(BaseModel):
    """目的：描述单条知识检索结果的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 chunk_id 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 chunk_id 值。
    chunk_id: str = Field(description="知识块 ID")
    # 目的：保存 content 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 content 值。
    content: str = Field(description="命中的文本内容")
    # 目的：保存 score 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 score 值。
    score: float = Field(description="相似度得分")
    # 目的：保存 category 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 category 值。
    category: str = Field(description="知识分类")
    # 目的：保存 source 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source 值。
    source: str = Field(description="来源")
    # 目的：保存 parent_id 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 parent_id 值。
    parent_id: str = Field(default="", description="父块 ID")
    # 目的：保存 title 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: str = Field(default="", description="标题")
    # 目的：保存 heading_path 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 heading_path 值。
    heading_path: str = Field(default="", description="章节路径")
    # 目的：保存 locator 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 locator 值。
    locator: str = Field(default="", description="定位信息")
    # 目的：保存 dense_score 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 dense_score 值。
    dense_score: float | None = Field(default=None, description="向量召回得分")
    # 目的：保存 bm25_score 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 bm25_score 值。
    bm25_score: float | None = Field(default=None, description="BM25 召回得分")
    # 目的：保存 fusion_score 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 fusion_score 值。
    fusion_score: float | None = Field(default=None, description="融合得分")
    # 目的：保存 rerank_score 字段，用于 KnowledgeSearchResultItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 rerank_score 值。
    rerank_score: float | None = Field(default=None, description="重排得分")


class KnowledgeSearchResponse(BaseModel):
    """目的：描述知识检索响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 query 字段，用于 KnowledgeSearchResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 query 值。
    query: str = Field(description="原始查询文本")
    # 目的：保存 results 字段，用于 KnowledgeSearchResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 results 值。
    results: list[KnowledgeSearchResultItem] = Field(default_factory=list, description="检索结果")
    # 目的：保存 total 字段，用于 KnowledgeSearchResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 total 值。
    total: int = Field(default=0, description="结果总数")
