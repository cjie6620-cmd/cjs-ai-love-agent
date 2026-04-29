from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.config import get_settings
from .base import VectorBase

settings = get_settings()


def generate_uuid() -> str:
    """目的：为向量表生成统一格式的字符串主键，降低与业务主键体系对接的转换成本。
    结果：返回一个新的 UUID 字符串，可直接作为 ORM 记录主键写入数据库。
    """
    return str(uuid4())


class MemoryEmbedding(VectorBase):
    """目的：存储用户长期记忆内容及其向量表示，支撑多轮对话中的个性化检索与上下文延续。
    结果：系统可以按用户、会话和记忆类型快速召回相似历史记忆，用于生成更连贯的回答。
    """

    # 目的：保存 __tablename__ 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "memory_embeddings"

    # 目的：保存 id 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 user_id 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    # 目的：保存 session_id 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 session_id 值。
    session_id: Mapped[str | None] = mapped_column(String(36), index=True)
    # 目的：保存 memory_type 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 memory_type 值。
    memory_type: Mapped[str] = mapped_column(String(32), index=True)
    # 目的：保存 canonical_key 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 canonical_key 值。
    canonical_key: Mapped[str] = mapped_column(String(96), default="", index=True)
    # 目的：保存 content 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 content 值。
    content: Mapped[str] = mapped_column(Text)
    # 目的：保存 importance_score 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 importance_score 值。
    importance_score: Mapped[float] = mapped_column(Float, default=0.0)
    # 目的：保存 confidence 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 confidence 值。
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # 目的：保存 status 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    # 目的：保存 source_session_id 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source_session_id 值。
    source_session_id: Mapped[str] = mapped_column(String(36), default="", index=True)
    # 目的：保存 merged_into_id 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 merged_into_id 值。
    merged_into_id: Mapped[str | None] = mapped_column(String(36), index=True)
    # 目的：保存 metadata_json 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 metadata_json 值。
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    # 目的：保存 embedding 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 embedding 值。
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.vector_dimension))
    # 目的：保存 created_at 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 目的：保存 last_seen_at 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 last_seen_at 值。
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 目的：保存 updated_at 字段，用于 MemoryEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class KnowledgeEmbedding(VectorBase):
    """目的：存储知识文档分块及其向量表示，支撑 RAG 场景下的语义检索和元数据过滤。
    结果：系统可以基于相似度从知识库中召回最相关的内容片段，为回答生成提供事实依据。
    """

    # 目的：保存 __tablename__ 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "knowledge_embeddings"

    # 目的：保存 id 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 tenant_id 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant_id 值。
    tenant_id: Mapped[str] = mapped_column(String(36), default="default", index=True)
    # 目的：保存 knowledge_id 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 knowledge_id 值。
    knowledge_id: Mapped[str] = mapped_column(String(64), index=True)
    # 目的：保存 category 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 category 值。
    category: Mapped[str] = mapped_column(String(32), index=True)
    # 目的：保存 title 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: Mapped[str] = mapped_column(String(255))
    # 目的：保存 content 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 content 值。
    content: Mapped[str] = mapped_column(Text)
    # 目的：保存 source 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source 值。
    source: Mapped[str] = mapped_column(String(255), default="")
    # 目的：保存 created_by 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_by 值。
    created_by: Mapped[str] = mapped_column(String(36), default="", index=True)
    # 目的：保存 metadata_json 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 metadata_json 值。
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    # 目的：保存 embedding 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 embedding 值。
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.vector_dimension))
    # 目的：保存 created_at 字段，用于 KnowledgeEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StyleSampleEmbedding(VectorBase):
    """目的：存储用户或人设的表达样本及其向量表示，用于识别和复用相近的语言风格。
    结果：系统可以按用户和画像检索相似表达样本，辅助生成更贴近目标语气的文案。
    """

    # 目的：保存 __tablename__ 字段，用于 StyleSampleEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "style_sample_embeddings"

    # 目的：保存 id 字段，用于 StyleSampleEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 user_id 字段，用于 StyleSampleEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    # 目的：保存 profile_id 字段，用于 StyleSampleEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 profile_id 值。
    profile_id: Mapped[str] = mapped_column(String(36), index=True)
    # 目的：保存 source_message 字段，用于 StyleSampleEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source_message 值。
    source_message: Mapped[str] = mapped_column(Text)
    # 目的：保存 normalized_text 字段，用于 StyleSampleEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 normalized_text 值。
    normalized_text: Mapped[str] = mapped_column(Text)
    # 目的：保存 style_tags 字段，用于 StyleSampleEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 style_tags 值。
    style_tags: Mapped[dict] = mapped_column(JSONB, default=dict)
    # 目的：保存 embedding 字段，用于 StyleSampleEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 embedding 值。
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.vector_dimension))
    # 目的：保存 created_at 字段，用于 StyleSampleEmbedding 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResponseSemanticCacheEntry(VectorBase):
    """目的：保存同一用户会话上下文下可复用的语义回答缓存。
    结果：相似问题可以通过 pgvector 召回历史 ChatResponse，降低重复 LLM 调用。
    """

    __tablename__ = "response_semantic_cache_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    mode: Mapped[str] = mapped_column(String(32), index=True)
    context_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    normalized_message: Mapped[str] = mapped_column(Text)
    response_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.vector_dimension))
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
