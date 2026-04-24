"""记忆管理服务：用户长期记忆和会话短期记忆管理。

目的：提供基于 pgvector 的语义召回能力和 Redis List 的快速读写。
结果：支持记忆写入、语义检索和会话上下文缓存，提升对话体验。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from llm import LlmClient
from observability import traceable_chain
from prompt.templates import build_memory_decision_prompt_spec
from rag.embeddings import EmbeddingService
from rag.vector_store import PgVectorClient
from security import RedisService

from contracts.chat import MemoryDecision, MemoryHit, QuestionAdvisorPayload, ShortTermMessage

logger = logging.getLogger(__name__)


class MemoryManager:
    """用户长期记忆管理器，支持记忆写入和基于语义相似度的召回。

    目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_client: PgVectorClient | None = None,
    ) -> None:
        """初始化记忆管理器实例。

        目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_client = vector_client or PgVectorClient()

    @traceable_chain("memory.recall")
    async def recall(
        self,
        user_id: str,
        *,
        query: str | None = None,
        top_k: int = 3,
    ) -> list[MemoryHit]:
        """召回与当前查询语义相关的用户长期记忆。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        if not query or not query.strip():
            return []

        try:
            query_embedding = await self.embedding_service.embed_text(query)
            rows = self.vector_client.search_memory(
                query_embedding,
                user_id=user_id,
                top_k=top_k,
            )
            # 返回结构化结果而非纯字符串，保留 score 和 chunk_id
            return [
                {
                    "content": str(row.get("content", "")),
                    "score": float(row.get("score", 0.0)),
                    "chunk_id": str(row.get("id", "")),
                }
                for row in rows
                if row.get("content")
            ]
        except RuntimeError:
            # API Key 未配置，降级返回空结果
            logger.warning("Embedding 服务未配置，记忆召回降级为空结果。")
            return []
        except Exception as exc:
            logger.warning("记忆召回异常，降级为空结果: %s", exc)
            return []

    @traceable_chain("memory.decide")
    async def decide_memory(
        self,
        user_message: str,
        assistant_reply: str,
    ) -> MemoryDecision:
        """基于结构化输出决定是否写入长期记忆。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        try:
            llm = LlmClient()
            prompt_spec = build_memory_decision_prompt_spec(
                user_message=user_message,
                assistant_reply=assistant_reply,
            )
            return await llm.decide_memory(prompt_spec)
        except Exception as exc:
            logger.warning("长期记忆决策失败，默认跳过保存: %s", exc)
            return MemoryDecision(
                should_store=False,
                memory_type="none",
                memory_text="",
                confidence=0.0,
                reason_code="decision_error",
            )

    @traceable_chain("memory.save")
    async def save_memory(
        self,
        user_id: str,
        content: str,
        *,
        memory_type: str = "event",
        session_id: str | None = None,
    ) -> str | None:
        """将一条记忆写入向量库。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        if not content or not content.strip():
            return None

        try:
            embedding = await self.embedding_service.embed_text(content)
            record_id = self.vector_client.insert_memory(
                embedding,
                user_id=user_id,
                memory_type=memory_type,
                content=content,
                session_id=session_id,
            )
            logger.info("记忆写入成功: user_id=%s, type=%s, id=%s", user_id, memory_type, record_id)
            return record_id
        except RuntimeError:
            logger.warning("Embedding 服务未配置，记忆写入跳过。")
            return None
        except Exception as exc:
            logger.warning("记忆写入异常: %s", exc)
            return None


class SessionMemoryManager:
    """会话短期记忆管理器：基于 Redis List 的快速读写。

    目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    def __init__(self, redis_service: RedisService | None = None) -> None:
        """初始化短期记忆管理器。

        目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self._redis = redis_service or RedisService()
        self._default_ttl = 1800  # 30 分钟
        self._max_messages = 20  # 最多保留 20 条（10 轮对话）

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        advisor: QuestionAdvisorPayload | None = None,
        ttl: int = 1800,
    ) -> bool:
        """追加一条消息到会话短期记忆。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        message_dict: dict[str, object] = {
            "role": role,
            "content": content,
            "created_at": datetime.now(UTC).isoformat(),
        }
        if advisor is not None:
            message_dict["advisor"] = advisor.model_dump()

        return self._redis.append_message(
            session_id,
            message_dict,
            max_messages=self._max_messages,
            ttl=ttl,
        )

    def get_recent(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[ShortTermMessage]:
        """读取会话短期记忆最近若干条消息。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        raw_list = self._redis.get_recent_messages(session_id, limit=limit)
        if not raw_list:
            return []

        results: list[ShortTermMessage] = []
        for item in raw_list:
            advisor_obj: QuestionAdvisorPayload | None = None
            advisor_raw = item.get("advisor")
            if isinstance(advisor_raw, dict):
                advisor_obj = QuestionAdvisorPayload.model_validate(advisor_raw)

            created_at: datetime | None = None
            created_at_raw = item.get("created_at")
            if isinstance(created_at_raw, str):
                try:
                    created_at = datetime.fromisoformat(created_at_raw)
                except ValueError:
                    pass

            results.append(
                ShortTermMessage(
                    role=item.get("role", "user"),  # type: ignore[arg-type]
                    content=str(item.get("content", "")),
                    created_at=created_at,
                    advisor=advisor_obj,
                )
            )

        return results

    def delete_session(self, session_id: str) -> bool:
        """删除会话短期记忆。

        目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        return self._redis.delete_session(session_id)

    def get_ttl(self, session_id: str) -> int:
        """获取会话短期记忆剩余 TTL。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        return self._redis.get_ttl(session_id)
