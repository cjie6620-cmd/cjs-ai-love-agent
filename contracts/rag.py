"""RAG API 相关契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeIndexTextRequest(BaseModel):
    """纯文本直接索引请求。
    
    目的：描述纯文本直接索引请求的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    text: str = Field(..., min_length=1, max_length=100_000, description="待索引的文本内容")
    title: str = Field(default="", max_length=255, description="知识标题")
    category: str = Field(
        default="relationship_knowledge",
        max_length=64,
        description="知识分类",
    )
    source: str = Field(default="手工录入", max_length=255, description="来源标识")


class KnowledgeIndexResponse(BaseModel):
    """索引操作统一响应。
    
    目的：描述索引操作统一响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    success: bool = Field(description="是否成功")
    filename: str = Field(default="", description="文件名")
    chunks_written: int = Field(default=0, description="成功写入的 chunk 数量")
    message: str = Field(default="", description="补充信息")


class KnowledgeBatchIndexResponse(BaseModel):
    """批量索引响应。
    
    目的：描述批量索引响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    success: bool = Field(description="是否整体成功")
    total_files: int = Field(default=0, description="处理文件总数")
    total_chunks: int = Field(default=0, description="成功写入 chunk 总数")
    results: list[KnowledgeIndexResponse] = Field(default_factory=list, description="逐文件结果")
    message: str = Field(default="", description="补充信息")


class KnowledgeSearchRequest(BaseModel):
    """知识检索请求。
    
    目的：描述知识检索请求的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    query: str = Field(..., min_length=1, max_length=2000, description="检索查询文本")
    top_k: int = Field(default=5, ge=1, le=50, description="返回最大结果数")
    category: str | None = Field(default=None, description="分类过滤")


class KnowledgeSearchResultItem(BaseModel):
    """单条知识检索结果。
    
    目的：描述单条知识检索结果的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    chunk_id: str = Field(description="知识块 ID")
    content: str = Field(description="命中的文本内容")
    score: float = Field(description="相似度得分")
    category: str = Field(description="知识分类")
    source: str = Field(description="来源")
    parent_id: str = Field(default="", description="父块 ID")
    title: str = Field(default="", description="标题")
    heading_path: str = Field(default="", description="章节路径")
    locator: str = Field(default="", description="定位信息")
    dense_score: float | None = Field(default=None, description="向量召回得分")
    bm25_score: float | None = Field(default=None, description="BM25 召回得分")
    fusion_score: float | None = Field(default=None, description="融合得分")
    rerank_score: float | None = Field(default=None, description="重排得分")


class KnowledgeSearchResponse(BaseModel):
    """知识检索响应。
    
    目的：描述知识检索响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    query: str = Field(description="原始查询文本")
    results: list[KnowledgeSearchResultItem] = Field(default_factory=list, description="检索结果")
    total: int = Field(default=0, description="结果总数")
