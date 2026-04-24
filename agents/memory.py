"""记忆管理服务：用户长期记忆和会话短期记忆管理。

目的：提供基于 pgvector 的长期记忆召回、企业化治理写入和 Redis 短期上下文读写。
结果：支持主链路个性化召回，以及后台异步结构化分析后的去重、合并、打分和落库。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from llm import LlmClient
from observability import traceable_chain
from prompt.templates import build_memory_decision_prompt_spec
from rag.embeddings import EmbeddingService
from rag.vector_store import PgVectorClient
from security import RedisService

from contracts.chat import MemoryDecision, MemoryHit, QuestionAdvisorPayload, ShortTermMessage

logger = logging.getLogger(__name__)

_MIN_IMPORTANCE_SCORE = 0.60
_MIN_CONFIDENCE = 0.70


class MemoryManager:
    """长期记忆管理器。

    目的：封装长期记忆召回、结构化分析、价值过滤、去重合并和向量库写入能力。
    结果：上层工作流和 Celery 任务可以通过统一入口完成长期记忆读写治理。
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_client: PgVectorClient | None = None,
    ) -> None:
        """初始化记忆管理器。

        目的：装配 embedding 服务和向量库客户端，支持生产依赖与测试替身注入。
        结果：实例具备长期记忆召回和治理写入能力。
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
        """召回用户长期记忆。

        目的：根据当前检索问题从用户 active 长期记忆中找出语义相关内容。
        结果：返回可注入主 Prompt 的记忆命中列表。
        """
        if not query or not query.strip():
            return []
        try:
            query_embedding = await self.embedding_service.embed_text(query)
            rows = self.vector_client.search_memory(query_embedding, user_id=user_id, top_k=top_k)
            return [
                {"content": str(row.get("content", "")), "score": float(row.get("score", 0.0)), "chunk_id": str(row.get("id", ""))}
                for row in rows
                if row.get("content")
            ]
        except RuntimeError:
            logger.warning("Embedding ?????????????????")
            return []
        except Exception as exc:
            logger.warning("?????????????: %s", exc)
            return []

    @traceable_chain("memory.decide")
    async def decide_memory(self, user_message: str, assistant_reply: str) -> MemoryDecision:
        """使用后台模型分析长期记忆价值。

        目的：通过 DeepSeek with_structured_output 判断本轮对话是否具备长期记忆价值。
        结果：返回包含治理键、重要性、置信度和合并策略的结构化结果。
        """
        try:
            llm = LlmClient.for_memory_analysis()
            prompt_spec = build_memory_decision_prompt_spec(user_message=user_message, assistant_reply=assistant_reply)
            return await llm.decide_memory(prompt_spec)
        except Exception as exc:
            logger.warning("??????????????????: %s", exc)
            return MemoryDecision(should_store=False, memory_type="none", memory_text="", canonical_key="", importance_score=0.0, confidence=0.0, merge_strategy="skip", reason_code="decision_error")

    @traceable_chain("memory.save")
    async def save_memory(
        self,
        user_id: str,
        decision_or_content: MemoryDecision | str,
        *,
        memory_type: str = "event",
        session_id: str | None = None,
        event_id: str = "",
        task_id: str = "",
        trace_id: str = "",
    ) -> str | None:
        """治理写入长期记忆。

        目的：兼容旧调用并优先处理结构化记忆结果，完成价值过滤、去重、合并和向量落库。
        结果：返回新增或更新的记忆 ID，跳过时返回 None。
        """
        decision = self._coerce_decision(decision_or_content, memory_type=memory_type)
        if not self._should_persist(decision):
            logger.info("????????: reason=%s, importance=%.2f, confidence=%.2f", decision.reason_code, decision.importance_score, decision.confidence)
            return None
        try:
            existing = self.vector_client.get_active_memory_by_key(user_id=user_id, canonical_key=decision.canonical_key)
            merged_text = self._build_merged_text(decision, existing)
            embedding = await self.embedding_service.embed_text(merged_text)
            metadata = self._build_metadata(
                decision,
                existing,
                event_id=event_id,
                task_id=task_id,
                trace_id=trace_id,
            )
            if existing and decision.merge_strategy == "skip":
                return self.vector_client.touch_memory(str(existing["id"]), metadata_json=metadata)
            if existing and decision.merge_strategy in {"replace", "append"}:
                return self.vector_client.update_memory(str(existing["id"]), embedding=embedding, content=merged_text, memory_type=decision.memory_type, importance_score=decision.importance_score, confidence=decision.confidence, session_id=session_id, metadata_json=metadata)
            record_id = self.vector_client.insert_memory(embedding, user_id=user_id, memory_type=decision.memory_type, content=merged_text, session_id=session_id, canonical_key=decision.canonical_key, importance_score=decision.importance_score, confidence=decision.confidence, source_session_id=session_id or "", metadata_json=metadata)
            logger.info("??????: user_id=%s, key=%s, type=%s, id=%s", user_id, decision.canonical_key, decision.memory_type, record_id)
            return record_id
        except RuntimeError:
            logger.warning("Embedding ?????????????")
            return None
        except Exception as exc:
            logger.warning("????????: %s", exc)
            return None

    def _coerce_decision(self, decision_or_content: MemoryDecision | str, *, memory_type: str) -> MemoryDecision:
        """兼容旧入参并转换为结构化结果。

        目的：让旧测试或调用方传入字符串时仍能进入统一治理链路。
        结果：返回 MemoryDecision 结构化对象。
        """
        if isinstance(decision_or_content, MemoryDecision):
            return decision_or_content
        content = str(decision_or_content or "").strip()
        return MemoryDecision(should_store=bool(content), memory_type=memory_type, memory_text=content, canonical_key="memory:general", importance_score=1.0 if content else 0.0, confidence=1.0 if content else 0.0, merge_strategy="insert", reason_code="legacy_content")

    def _should_persist(self, decision: MemoryDecision) -> bool:
        """判断结构化结果是否可持久化。

        目的：统一应用长期价值阈值，避免低价值或低置信内容进入长期记忆。
        结果：返回是否允许进入去重合并和写库流程。
        """
        return decision.should_store and bool(decision.memory_text.strip()) and bool(decision.canonical_key.strip()) and decision.importance_score >= _MIN_IMPORTANCE_SCORE and decision.confidence >= _MIN_CONFIDENCE

    def _build_merged_text(self, decision: MemoryDecision, existing: dict[str, Any] | None) -> str:
        """生成最终记忆文本。

        目的：根据模型合并策略产出需要重新向量化和持久化的长期记忆内容。
        结果：返回新增、替换或追加后的规范化记忆文本。
        """
        new_text = decision.memory_text.strip()
        if not existing or decision.merge_strategy != "append":
            return new_text
        old_text = str(existing.get("content") or "").strip()
        if not old_text or new_text in old_text:
            return old_text or new_text
        return f"{old_text}?{new_text}"[:300]

    def _build_metadata(
        self,
        decision: MemoryDecision,
        existing: dict[str, Any] | None,
        *,
        event_id: str = "",
        task_id: str = "",
        trace_id: str = "",
    ) -> dict[str, Any]:
        """构建长期记忆治理元数据。

        目的：记录模型分析结果、合并策略和旧记录引用，便于审计与排障。
        结果：返回可写入 metadata_json 的字典。
        """
        metadata = {
            "reason_code": decision.reason_code,
            "merge_strategy": decision.merge_strategy,
            "canonical_key": decision.canonical_key,
            "previous_memory_id": str(existing.get("id")) if existing else "",
        }
        if event_id:
            metadata["event_id"] = event_id
        if task_id:
            metadata["task_id"] = task_id
        if trace_id:
            metadata["trace_id"] = trace_id
        return metadata


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
