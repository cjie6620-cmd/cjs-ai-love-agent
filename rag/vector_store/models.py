from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.config import get_settings
from .base import VectorBase

settings = get_settings()


def generate_uuid() -> str:
    """向量表同样使用字符串主键，便于和业务表主键统一。

    目的：为向量表生成统一格式的字符串主键，降低与业务主键体系对接的转换成本。
    结果：返回一个新的 UUID 字符串，可直接作为 ORM 记录主键写入数据库。
    """
    return str(uuid4())


class MemoryEmbedding(VectorBase):
    """长期记忆向量表，服务关系连续性和个性化召回。

    目的：存储用户长期记忆内容及其向量表示，支撑多轮对话中的个性化检索与上下文延续。
    结果：系统可以按用户、会话和记忆类型快速召回相似历史记忆，用于生成更连贯的回答。
    """

    __tablename__ = "memory_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), index=True)
    memory_type: Mapped[str] = mapped_column(String(32), index=True)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.vector_dimension))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class KnowledgeEmbedding(VectorBase):
    """知识库向量表，服务恋爱建议和安全知识检索。

    目的：存储知识文档分块及其向量表示，支撑 RAG 场景下的语义检索和元数据过滤。
    结果：系统可以基于相似度从知识库中召回最相关的内容片段，为回答生成提供事实依据。
    """

    __tablename__ = "knowledge_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    knowledge_id: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(255), default="")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.vector_dimension))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StyleSampleEmbedding(VectorBase):
    """风格样本向量表，服务语气复刻和相似表达召回。

    目的：存储用户或人设的表达样本及其向量表示，用于识别和复用相近的语言风格。
    结果：系统可以按用户和画像检索相似表达样本，辅助生成更贴近目标语气的文案。
    """

    __tablename__ = "style_sample_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    profile_id: Mapped[str] = mapped_column(String(36), index=True)
    source_message: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    style_tags: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.vector_dimension))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
