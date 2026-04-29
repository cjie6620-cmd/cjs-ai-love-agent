"""pgvector 向量数据访问层。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from core.config import get_settings
from .base import get_vector_session_factory
from .models import (
    KnowledgeEmbedding,
    MemoryEmbedding,
    ResponseSemanticCacheEntry,
    StyleSampleEmbedding,
)

logger = logging.getLogger(__name__)


class PgVectorClient:
    """目的：封装知识库、记忆库、风格样本三类向量数据的写入、删除和检索操作。
    结果：上层 RAG 流程可以通过统一客户端访问 pgvector，而不需要直接处理底层 SQL 和会话管理。
    """

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        """目的：接收外部注入的会话工厂，便于在生产环境复用默认配置、在测试环境替换数据库依赖。
        结果：客户端持有可延迟初始化的会话工厂，并具备后续执行向量读写操作的基础能力。
        """
        self.settings = get_settings()
        self._session_factory = session_factory

    @property
    def session_factory(self) -> sessionmaker[Session]:
        """目的：在首次访问时延迟装配默认 `sessionmaker`，避免构造阶段立即创建数据库连接。
        结果：返回一个可直接创建 `Session` 的会话工厂，供当前客户端内部所有数据库操作复用。
        """
        if self._session_factory is None:
            self._session_factory = get_vector_session_factory()
        return self._session_factory

    # ------------------------------------------------------------------ #
    # 知识库写入与检索
    # ------------------------------------------------------------------ #

    def insert_knowledge(
        self,
        embedding: list[float],
        *,
        knowledge_id: str = "",
        record_id: str = "",
        category: str = "relationship_knowledge",
        title: str = "",
        content: str = "",
        source: str = "",
        tenant_id: str = "default",
        created_by: str = "",
        metadata_json: dict[str, Any] | None = None,
    ) -> str:
        """目的：将单条知识分块及其向量、标题、来源和元数据持久化到知识库表。
        结果：数据库新增一条知识向量记录，并返回可用于后续追踪或删除的记录 ID。
        """
        resolved_id = record_id or str(uuid4())
        record = KnowledgeEmbedding(
            id=resolved_id,
            tenant_id=tenant_id,
            knowledge_id=knowledge_id or resolved_id,
            category=category,
            title=title,
            content=content,
            source=source,
            created_by=created_by,
            metadata_json=metadata_json or {},
            embedding=embedding,
        )
        with self.session_factory() as session:
            session.add(record)
            session.commit()
        return resolved_id

    def insert_knowledge_batch(self, records: Iterable[dict[str, Any]]) -> list[str]:
        """目的：将一批知识分块一次性写入数据库，降低多次提交带来的性能损耗和半成功风险。
        结果：所有待写入记录会在同一批次提交成功后落库，并返回对应的记录 ID 列表。
        """
        resolved_ids: list[str] = []
        orm_records: list[KnowledgeEmbedding] = []
        for payload in records:
            resolved_id = str(payload.get("record_id") or uuid4())
            resolved_ids.append(resolved_id)
            orm_records.append(
                KnowledgeEmbedding(
                    id=resolved_id,
                    tenant_id=str(payload.get("tenant_id") or "default"),
                    knowledge_id=str(payload.get("knowledge_id") or resolved_id),
                    category=str(payload.get("category") or "relationship_knowledge"),
                    title=str(payload.get("title") or ""),
                    content=str(payload.get("content") or ""),
                    source=str(payload.get("source") or ""),
                    created_by=str(payload.get("created_by") or ""),
                    metadata_json=payload.get("metadata_json") or {},
                    embedding=payload.get("embedding") or [],
                )
            )

        if not orm_records:
            return []

        with self.session_factory() as session:
            session.add_all(orm_records)
            session.commit()
        return resolved_ids

    def delete_knowledge(
        self,
        *,
        source: str,
        category: str | None = None,
        filename: str | None = None,
        doc_id: str | None = None,
        tenant_id: str = "default",
    ) -> int:
        """目的：在知识重建、文件重新导入或文档更新时，按来源和元数据条件清理旧向量数据。
        结果：符合条件的知识向量记录会被删除，并返回实际删除的记录数量。
        """
        with self.session_factory() as session:
            statement = delete(KnowledgeEmbedding).where(KnowledgeEmbedding.tenant_id == tenant_id)
            if source:
                statement = statement.where(KnowledgeEmbedding.source == source)
            if category:
                statement = statement.where(KnowledgeEmbedding.category == category)
            if filename:
                statement = statement.where(
                    KnowledgeEmbedding.metadata_json["filename"].as_string() == filename
                )
            if doc_id:
                statement = statement.where(
                    KnowledgeEmbedding.metadata_json["doc_id"].as_string() == doc_id
                )
            result = session.execute(statement)
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def search_knowledge(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        category: str | None = None,
        chunk_role: str = "child",
        tenant_id: str = "default",
    ) -> list[dict[str, Any]]:
        """目的：根据查询向量在知识库中检索最相近的内容片段，并支持按分类和分块角色过滤。
        结果：返回按相似度排序的知识记录列表，列表中包含正文、来源、元数据和匹配分数。
        """
        with self.session_factory() as session:
            filters = ["COALESCE(metadata_json->>'chunk_role', '') = :chunk_role"]
            params: dict[str, Any] = {
                "embedding": str(query_embedding),
                "top_k": top_k,
                "chunk_role": chunk_role,
                "tenant_id": tenant_id,
            }
            filters.append("tenant_id = :tenant_id")
            if category:
                filters.append("category = :category")
                params["category"] = category

            sql = text(
                f"""
                SELECT id, tenant_id, knowledge_id, category, title, content, source,
                       metadata_json,
                       1 - (embedding <=> CAST(:embedding AS vector)) AS score
                FROM knowledge_embeddings
                WHERE {' AND '.join(filters)}
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
                """
            )
            rows = session.execute(sql, params).mappings().all()
            return [dict(row) for row in rows]

    def get_parent_chunks(
        self,
        parent_ids: Iterable[str],
        *,
        tenant_id: str = "default",
    ) -> list[dict[str, Any]]:
        """目的：在命中子分块后，根据父块 ID 批量补全更完整的上下文内容。
        结果：返回所有匹配到的父块记录，供上层拼接更适合模型阅读的原始上下文。
        """
        parent_id_list = [item for item in parent_ids if item]
        if not parent_id_list:
            return []
        with self.session_factory() as session:
            statement = (
                select(KnowledgeEmbedding)
                .where(KnowledgeEmbedding.tenant_id == tenant_id)
                .where(KnowledgeEmbedding.metadata_json["chunk_role"].as_string() == "parent")
                .where(KnowledgeEmbedding.metadata_json["parent_id"].as_string().in_(parent_id_list))
            )
            rows = session.execute(statement).scalars().all()
            return [
                {
                    "id": row.id,
                    "knowledge_id": row.knowledge_id,
                    "category": row.category,
                    "title": row.title,
                    "content": row.content,
                    "source": row.source,
                    "metadata_json": row.metadata_json,
                }
                for row in rows
            ]

    # ------------------------------------------------------------------ #
    # 记忆库写入与检索
    # ------------------------------------------------------------------ #

    def insert_memory(
        self,
        embedding: list[float],
        *,
        user_id: str,
        memory_type: str = "event",
        content: str = "",
        session_id: str | None = None,
        canonical_key: str = "",
        importance_score: float = 0.0,
        confidence: float = 0.0,
        status: str = "active",
        source_session_id: str = "",
        merged_into_id: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> str:
        """目的：保存经过结构化分析和治理后的长期记忆及其向量表示。
        结果：数据库新增一条 active 记忆记录，并返回该条记忆的唯一 ID。
        """
        if status == "active" and canonical_key:
            existing = self.get_active_memory_by_key(user_id=user_id, canonical_key=canonical_key)
            if existing is not None:
                updated_id = self.update_memory(
                    str(existing["id"]),
                    embedding=embedding,
                    content=content,
                    memory_type=memory_type,
                    importance_score=importance_score,
                    confidence=confidence,
                    session_id=session_id,
                    metadata_json=metadata_json,
                )
                return updated_id or str(existing["id"])

        record_id = str(uuid4())
        record = MemoryEmbedding(
            id=record_id,
            user_id=user_id,
            session_id=session_id,
            memory_type=memory_type,
            canonical_key=canonical_key,
            content=content,
            importance_score=importance_score,
            confidence=confidence,
            status=status,
            source_session_id=source_session_id or session_id or "",
            merged_into_id=merged_into_id,
            metadata_json=metadata_json or {},
            embedding=embedding,
        )
        with self.session_factory() as session:
            session.add(record)
            session.commit()
        return record_id

    def get_active_memory_by_key(self, *, user_id: str, canonical_key: str) -> dict[str, Any] | None:
        """目的：在写入长期记忆前定位同类记忆，支撑去重、替换和合并策略。
        结果：返回匹配的 active 记忆字典，未命中时返回 None。
        """
        if not canonical_key:
            return None
        with self.session_factory() as session:
            statement = (
                select(MemoryEmbedding)
                .where(MemoryEmbedding.user_id == user_id)
                .where(MemoryEmbedding.canonical_key == canonical_key)
                .where(MemoryEmbedding.status == "active")
                .order_by(MemoryEmbedding.updated_at.desc())
                .limit(1)
            )
            row = session.execute(statement).scalar_one_or_none()
            if row is None:
                return None
            return self._serialize_memory(row)

    def update_memory(
        self,
        record_id: str,
        *,
        embedding: list[float],
        content: str,
        memory_type: str,
        importance_score: float,
        confidence: float,
        session_id: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> str | None:
        """目的：对同一 canonical_key 下的旧记忆执行替换或合并后的持久化更新。
        结果：目标记忆内容、向量、评分和最近出现时间被刷新。
        """
        with self.session_factory() as session:
            record = session.get(MemoryEmbedding, record_id)
            if record is None:
                return None
            record.content = content
            record.memory_type = memory_type
            record.embedding = embedding
            record.importance_score = importance_score
            record.confidence = confidence
            record.session_id = session_id or record.session_id
            record.source_session_id = session_id or record.source_session_id
            record.metadata_json = metadata_json or record.metadata_json or {}
            record.last_seen_at = func.now()
            record.updated_at = func.now()
            session.commit()
            return record.id

    def touch_memory(self, record_id: str, *, metadata_json: dict[str, Any] | None = None) -> str | None:
        """目的：在模型判断同类信息无需改写时记录该记忆再次出现，避免重复写入。
        结果：目标记忆的 last_seen_at 和可选元数据被更新。
        """
        with self.session_factory() as session:
            record = session.get(MemoryEmbedding, record_id)
            if record is None:
                return None
            if metadata_json:
                record.metadata_json = metadata_json
            record.last_seen_at = func.now()
            record.updated_at = func.now()
            session.commit()
            return record.id

    def list_user_memories(
        self,
        *,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """目的：按用户列出可管理的 active 长期记忆。
        结果：返回给个人记忆管理页展示的数据列表。
        """
        normalized_limit = max(1, min(int(limit), 100))
        normalized_offset = max(0, int(offset))
        with self.session_factory() as session:
            statement = (
                select(MemoryEmbedding)
                .where(MemoryEmbedding.user_id == user_id)
                .where(MemoryEmbedding.status == "active")
                .order_by(MemoryEmbedding.updated_at.desc(), MemoryEmbedding.created_at.desc())
                .offset(normalized_offset)
                .limit(normalized_limit)
            )
            rows = session.execute(statement).scalars().all()
            return [self._serialize_memory(row) for row in rows]

    def count_user_memories(self, *, user_id: str) -> int:
        """目的：统计用户 active 长期记忆数量。
        结果：分页接口可以返回总数。
        """
        with self.session_factory() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(MemoryEmbedding)
                    .where(MemoryEmbedding.user_id == user_id)
                    .where(MemoryEmbedding.status == "active")
                )
                or 0
            )

    def soft_delete_memory(self, *, user_id: str, record_id: str) -> int:
        """目的：软删除当前用户的一条长期记忆。
        结果：命中的 active 记录状态变为 deleted，后续召回不再命中。
        """
        with self.session_factory() as session:
            record = session.get(MemoryEmbedding, record_id)
            if record is None or record.user_id != user_id or record.status != "active":
                return 0
            record.status = "deleted"
            record.updated_at = func.now()
            session.commit()
            return 1

    def soft_delete_user_memories(self, *, user_id: str) -> int:
        """目的：软删除当前用户全部 active 长期记忆。
        结果：返回实际删除数量，召回链路只保留非 deleted 数据。
        """
        with self.session_factory() as session:
            rows = session.scalars(
                select(MemoryEmbedding)
                .where(MemoryEmbedding.user_id == user_id)
                .where(MemoryEmbedding.status == "active")
            ).all()
            for row in rows:
                row.status = "deleted"
                row.updated_at = func.now()
            session.commit()
            return len(rows)

    def search_memory(
        self,
        query_embedding: list[float],
        *,
        user_id: str,
        top_k: int = 3,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """目的：根据查询向量在指定用户的长期记忆中召回最相关的历史内容，并支持按记忆类型过滤。
        结果：返回按相似度排序的记忆列表，供对话生成阶段补充个性化上下文。
        """
        with self.session_factory() as session:
            filters = "AND user_id = :user_id"
            params: dict[str, Any] = {
                "embedding": str(query_embedding),
                "top_k": top_k,
                "user_id": user_id,
            }
            if memory_type:
                filters += " AND memory_type = :memory_type"
                params["memory_type"] = memory_type

            sql = text(
                f"""
                SELECT id, user_id, session_id, memory_type, canonical_key, content,
                       importance_score, confidence, status, metadata_json,
                       1 - (embedding <=> CAST(:embedding AS vector)) AS score
                FROM memory_embeddings
                WHERE status = 'active' {filters}
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
                """
            )
            rows = session.execute(sql, params).mappings().all()
            return [dict(row) for row in rows]

    def _serialize_memory(self, row: MemoryEmbedding) -> dict[str, Any]:
        """目的：统一向量存储层对外返回的记忆字段，避免上层依赖 ORM 实例。
        结果：返回可用于治理、合并和测试断言的字典结构。
        """
        return {
            "id": row.id,
            "user_id": row.user_id,
            "session_id": row.session_id,
            "memory_type": row.memory_type,
            "canonical_key": row.canonical_key,
            "content": row.content,
            "importance_score": row.importance_score,
            "confidence": row.confidence,
            "status": row.status,
            "metadata_json": row.metadata_json,
            "created_at": row.created_at,
            "last_seen_at": row.last_seen_at,
            "updated_at": row.updated_at,
        }

    # ------------------------------------------------------------------ #
    # 回答语义缓存写入与检索
    # ------------------------------------------------------------------ #

    def insert_response_cache(
        self,
        embedding: list[float],
        *,
        user_id: str,
        session_id: str,
        mode: str,
        context_fingerprint: str,
        normalized_message: str,
        response_payload: dict[str, Any],
        expires_at: datetime,
    ) -> str:
        """目的：写入一条可语义复用的聊天回答缓存。
        结果：后续同用户、同会话、同上下文的相似问题可以通过向量召回命中。
        """
        record_id = str(uuid4())
        record = ResponseSemanticCacheEntry(
            id=record_id,
            user_id=user_id,
            session_id=session_id,
            mode=mode,
            context_fingerprint=context_fingerprint,
            normalized_message=normalized_message,
            response_payload=response_payload,
            embedding=embedding,
            expires_at=expires_at,
        )
        with self.session_factory() as session:
            session.add(record)
            session.commit()
        return record_id

    def search_response_cache(
        self,
        query_embedding: list[float],
        *,
        user_id: str,
        session_id: str,
        mode: str,
        context_fingerprint: str,
        threshold: float,
        top_k: int = 1,
    ) -> list[dict[str, Any]]:
        """目的：按用户、会话、模式和上下文过滤后召回相似回答缓存。
        结果：只返回未过期且相似度达到阈值的缓存记录。
        """
        with self.session_factory() as session:
            params: dict[str, Any] = {
                "embedding": str(query_embedding),
                "user_id": user_id,
                "session_id": session_id,
                "mode": mode,
                "context_fingerprint": context_fingerprint,
                "threshold": threshold,
                "top_k": top_k,
            }
            sql = text(
                """
                SELECT id, user_id, session_id, mode, context_fingerprint,
                       normalized_message, response_payload, hit_count, expires_at,
                       1 - (embedding <=> CAST(:embedding AS vector)) AS score
                FROM response_semantic_cache_entries
                WHERE user_id = :user_id
                  AND session_id = :session_id
                  AND mode = :mode
                  AND context_fingerprint = :context_fingerprint
                  AND expires_at > NOW()
                  AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :threshold
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
                """
            )
            rows = [dict(row) for row in session.execute(sql, params).mappings().all()]
            if rows:
                session.execute(
                    text(
                        """
                        UPDATE response_semantic_cache_entries
                        SET hit_count = hit_count + 1,
                            updated_at = NOW()
                        WHERE id = :id
                        """
                    ),
                    {"id": rows[0]["id"]},
                )
                session.commit()
            return rows

    # ------------------------------------------------------------------ #
    # 风格样本写入与检索
    # ------------------------------------------------------------------ #

    def insert_style_sample(
        self,
        embedding: list[float],
        *,
        user_id: str,
        profile_id: str,
        source_message: str = "",
        normalized_text: str = "",
        style_tags: dict[str, Any] | None = None,
    ) -> str:
        """目的：保存原始表达、规范化文本和风格标签，形成可检索的语气样本库。
        结果：数据库新增一条风格样本记录，并返回该样本的唯一 ID。
        """
        record_id = str(uuid4())
        record = StyleSampleEmbedding(
            id=record_id,
            user_id=user_id,
            profile_id=profile_id,
            source_message=source_message,
            normalized_text=normalized_text,
            style_tags=style_tags or {},
            embedding=embedding,
        )
        with self.session_factory() as session:
            session.add(record)
            session.commit()
        return record_id

    def search_style_samples(
        self,
        query_embedding: list[float],
        *,
        user_id: str,
        top_k: int = 4,
        profile_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """目的：根据查询向量查找语义或表达风格接近的样本，并可按画像进一步缩小范围。
        结果：返回按相似度排序的风格样本列表，供文案生成或语气模仿流程参考。
        """
        with self.session_factory() as session:
            filters = "AND user_id = :user_id"
            params: dict[str, Any] = {
                "embedding": str(query_embedding),
                "top_k": top_k,
                "user_id": user_id,
            }
            if profile_id:
                filters += " AND profile_id = :profile_id"
                params["profile_id"] = profile_id

            sql = text(
                f"""
                SELECT id, user_id, profile_id, source_message,
                       normalized_text, style_tags,
                       1 - (embedding <=> CAST(:embedding AS vector)) AS score
                FROM style_sample_embeddings
                WHERE 1=1 {filters}
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
                """
            )
            rows = session.execute(sql, params).mappings().all()
            return [dict(row) for row in rows]
