"""记忆管理服务：用户长期记忆和会话短期记忆管理。

目的：提供基于 pgvector 的长期记忆召回、企业化治理写入和 Redis 短期上下文读写。
结果：支持主链路个性化召回，以及后台异步结构化分析后的去重、合并、打分和落库。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, cast

from core.config import get_settings
from llm import LlmClient
from observability import traceable_chain
from persistence import ConversationRepository, MemorySettingsRepository
from prompt.templates import build_memory_decision_prompt_spec
from rag.embeddings import EmbeddingService
from rag.vector_store import PgVectorClient
from security import RedisService

from contracts.chat import (
    ConversationContext,
    ConversationHistoryMessage,
    MemoryDecision,
    MemoryDecisionBatch,
    MemoryHit,
    MemoryType,
    QuestionAdvisorPayload,
    SessionSummary,
)

logger = logging.getLogger(__name__)

_MIN_IMPORTANCE_SCORE = 0.60
_MIN_CONFIDENCE = 0.70


class MemoryManager:
    """目的：封装长期记忆召回、结构化分析、价值过滤、去重合并和向量库写入能力。
    结果：上层工作流和 Celery 任务可以通过统一入口完成长期记忆读写治理。
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_client: PgVectorClient | None = None,
        memory_settings_repository: MemorySettingsRepository | None = None,
    ) -> None:
        """目的：装配 embedding 服务和向量库客户端，支持生产依赖与测试替身注入。
        结果：实例具备长期记忆召回和治理写入能力。
        """
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_client = vector_client or PgVectorClient()
        self.memory_settings_repository = memory_settings_repository or MemorySettingsRepository()

    @traceable_chain("memory.recall")
    async def recall(
        self,
        user_id: str,
        *,
        query: str | None = None,
        top_k: int = 3,
    ) -> list[MemoryHit]:
        """目的：根据当前检索问题从用户 active 长期记忆中找出语义相关内容。
        结果：返回可注入主 Prompt 的记忆命中列表。
        """
        if not query or not query.strip():
            return []
        if not self.memory_settings_repository.is_enabled(user_id):
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
            logger.warning("Embedding 服务暂不可用，跳过长期记忆召回")
            return []
        except Exception as exc:
            logger.warning("长期记忆召回失败: %s", exc)
            return []

    @traceable_chain("memory.decide")
    async def decide_memory(self, user_message: str, assistant_reply: str) -> MemoryDecisionBatch:
        """目的：通过结构化输出判断本轮对话中哪些信息具备长期记忆价值。
        结果：返回包含 0 到多条治理项的批量结构化结果。
        """
        try:
            llm = LlmClient.for_memory_analysis()
            prompt_spec = build_memory_decision_prompt_spec(user_message=user_message, assistant_reply=assistant_reply)
            return await llm.decide_memory(prompt_spec)
        except Exception as exc:
            logger.warning("长期记忆价值判断失败，按不保存处理: %s", exc)
            return MemoryDecisionBatch(items=[])

    def deduplicate_decisions(self, decisions: list[MemoryDecision]) -> list[MemoryDecision]:
        """目的：按 canonical_key 对同轮输出做批内去重。
        结果：完成当前实例行为并返回约定结果。
        """
        selected: dict[str, MemoryDecision] = {}
        passthrough: list[MemoryDecision] = []

        for decision in decisions:
            key = decision.canonical_key.strip()
            if not key:
                passthrough.append(decision)
                continue
            current = selected.get(key)
            if current is None or self._decision_rank(decision) > self._decision_rank(current):
                selected[key] = decision

        return [*passthrough, *selected.values()]

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
        """目的：兼容旧调用并优先处理结构化记忆结果，完成价值过滤、去重、合并和向量落库。
        结果：返回新增或更新的记忆 ID，跳过时返回 None。
        """
        decision = self._coerce_decision(decision_or_content, memory_type=memory_type)
        if not self._should_persist(decision):
            logger.info("长期记忆被过滤: reason=%s, importance=%.2f, confidence=%.2f", decision.reason_code, decision.importance_score, decision.confidence)
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
            if existing and decision.merge_strategy in {"replace", "append", "insert"}:
                return self.vector_client.update_memory(str(existing["id"]), embedding=embedding, content=merged_text, memory_type=decision.memory_type, importance_score=decision.importance_score, confidence=decision.confidence, session_id=session_id, metadata_json=metadata)
            record_id = self.vector_client.insert_memory(embedding, user_id=user_id, memory_type=decision.memory_type, content=merged_text, session_id=session_id, canonical_key=decision.canonical_key, importance_score=decision.importance_score, confidence=decision.confidence, source_session_id=session_id or "", metadata_json=metadata)
            logger.info("长期记忆已保存: user_id=%s, key=%s, type=%s, id=%s", user_id, decision.canonical_key, decision.memory_type, record_id)
            return record_id
        except RuntimeError:
            logger.warning("Embedding 服务暂不可用，跳过长期记忆写入")
            return None
        except Exception as exc:
            logger.warning("长期记忆写入失败: %s", exc)
            return None

    def _coerce_decision(self, decision_or_content: MemoryDecision | str, *, memory_type: str) -> MemoryDecision:
        """目的：让旧测试或调用方传入字符串时仍能进入统一治理链路。
        结果：返回 MemoryDecision 结构化对象。
        """
        if isinstance(decision_or_content, MemoryDecision):
            return decision_or_content
        content = str(decision_or_content or "").strip()
        allowed_types = {"event", "preference", "profile_summary", "none"}
        normalized_type: MemoryType = cast(
            MemoryType,
            memory_type if memory_type in allowed_types else "event",
        )
        return MemoryDecision(should_store=bool(content), memory_type=normalized_type, memory_text=content, canonical_key="memory:general", importance_score=1.0 if content else 0.0, confidence=1.0 if content else 0.0, merge_strategy="insert", reason_code="legacy_content")

    def _should_persist(self, decision: MemoryDecision) -> bool:
        """目的：统一应用长期价值阈值，避免低价值或低置信内容进入长期记忆。
        结果：返回是否允许进入去重合并和写库流程。
        """
        return decision.should_store and bool(decision.memory_text.strip()) and bool(decision.canonical_key.strip()) and decision.importance_score >= _MIN_IMPORTANCE_SCORE and decision.confidence >= _MIN_CONFIDENCE

    def _decision_rank(self, decision: MemoryDecision) -> tuple[float, float, int]:
        """目的：返回批内去重排序权重。
        结果：完成当前实例行为并返回约定结果。
        """
        return (
            decision.importance_score,
            decision.confidence,
            len(decision.memory_text.strip()),
        )

    def _build_merged_text(self, decision: MemoryDecision, existing: dict[str, Any] | None) -> str:
        """目的：根据模型合并策略产出需要重新向量化和持久化的长期记忆内容。
        结果：返回新增、替换或追加后的规范化记忆文本。
        """
        new_text = decision.memory_text.strip()
        if not existing or decision.merge_strategy != "append":
            return new_text
        old_text = str(existing.get("content") or "").strip()
        if not old_text or new_text in old_text:
            return old_text or new_text
        return f"{old_text}；{new_text}"[:300]

    def _build_metadata(
        self,
        decision: MemoryDecision,
        existing: dict[str, Any] | None,
        *,
        event_id: str = "",
        task_id: str = "",
        trace_id: str = "",
    ) -> dict[str, Any]:
        """目的：记录模型分析结果、合并策略和旧记录引用，便于审计与排障。
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


def estimate_text_tokens(text: str) -> int:
    """目的：用轻量规则估算 token，避免主链路依赖外部 tokenizer。
    结果：完成当前业务处理并返回约定结果。
    """
    normalized = str(text or "").strip()
    if not normalized:
        return 0
    return max(1, len(normalized) // 2)


class ConversationContextManager:
    """目的：会话上下文管理器：统一构建滚动摘要 + 最近原文窗口。
    结果：提供 ConversationContextManager 的结构化能力，供业务流程复用。
    """

    def __init__(
        self,
        redis_service: RedisService | None = None,
        conversation_repository: ConversationRepository | None = None,
    ) -> None:
        """目的：初始化会话上下文管理器。
        结果：完成实例初始化，得到可用对象。
        """
        self._settings = get_settings()
        self._redis = redis_service or RedisService()
        self._repository = conversation_repository or ConversationRepository()
        self._cache_max_messages = self._settings.conversation_cache_max_messages
        self._cache_ttl = self._settings.conversation_cache_ttl_seconds
        self._token_budget = self._settings.conversation_context_token_budget

    async def build_context(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> ConversationContext:
        """目的：构建本轮对话上下文，Redis 只做热缓存，DB 作为事实源。
        结果：返回构建完成的业务对象。
        """
        seed = self._repository.get_conversation_context_seed(
            user_id,
            session_id,
            limit=self._cache_max_messages,
        )
        covered_count_raw = seed.get("covered_message_count", 0)
        covered_count = int(covered_count_raw) if isinstance(covered_count_raw, int | str) else 0
        updated_at_raw = seed.get("updated_at")
        summary = SessionSummary(
            summary_text=str(seed.get("summary_text", "")),
            covered_message_count=covered_count,
            last_message_id=str(seed.get("last_message_id", "")),
            updated_at=updated_at_raw if isinstance(updated_at_raw, datetime) else None,
        )

        messages = self._read_cached_messages(session_id)
        if not messages:
            seed_messages = seed.get("recent_messages", [])
            messages = cast(
                list[ConversationHistoryMessage],
                seed_messages if isinstance(seed_messages, list) else [],
            )
            self.refresh_cache(session_id, messages)

        return ConversationContext(
            session_summary=summary,
            recent_messages=self._fit_messages_to_budget(messages),
            token_budget=self._token_budget,
            context_version="conversation_context.v1",
        )

    def append_message(
        self,
        session_id: str,
        message_id: str,
        role: str,
        content: str,
        *,
        advisor: QuestionAdvisorPayload | None = None,
        created_at: datetime | None = None,
        reply_status: str = "completed",
    ) -> bool:
        """目的：追加一条消息到会话热缓存。
        结果：完成当前实例行为并返回约定结果。
        """
        message_dict: dict[str, object] = {
            "id": message_id,
            "role": role,
            "content": content,
            "created_at": (created_at or datetime.now(UTC)).isoformat(),
            "reply_status": reply_status,
        }
        if advisor is not None:
            message_dict["advisor"] = advisor.model_dump()

        return self._redis.append_conversation_message(
            session_id,
            message_dict,
            max_messages=self._cache_max_messages,
            ttl=self._cache_ttl,
        )

    def refresh_cache(
        self,
        session_id: str,
        messages: list[ConversationHistoryMessage],
    ) -> None:
        """目的：用 DB 最近消息刷新 Redis 热缓存。
        结果：刷新登录凭证并返回新的登录态信息。
        """
        self._redis.delete_conversation_messages(session_id)
        for msg in messages[-self._cache_max_messages:]:
            self.append_message(
                session_id,
                msg.id,
                msg.role,
                msg.content,
                advisor=msg.advisor,
                created_at=msg.created_at,
                reply_status=msg.reply_status,
            )

    def _read_cached_messages(self, session_id: str) -> list[ConversationHistoryMessage]:
        """目的：读取并解析 Redis 热缓存消息。
        结果：完成当前实例行为并返回约定结果。
        """
        raw_list = self._redis.get_conversation_messages(
            session_id,
            limit=self._cache_max_messages,
        )
        if not raw_list:
            return []

        results: list[ConversationHistoryMessage] = []
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
                ConversationHistoryMessage(
                    id=str(item.get("id", "")),
                    role=item.get("role", "user"),  # type: ignore[arg-type]
                    content=str(item.get("content", "")),
                    created_at=created_at,
                    advisor=advisor_obj,
                    reply_status=(
                        "interrupted"
                        if item.get("reply_status") == "interrupted"
                        else "completed"
                    ),
                )
            )

        return results

    def _fit_messages_to_budget(
        self,
        messages: list[ConversationHistoryMessage],
    ) -> list[ConversationHistoryMessage]:
        """目的：按整体 token 预算保留最新消息，并恢复时间正序。
        结果：完成当前实例行为并返回约定结果。
        """
        selected: list[ConversationHistoryMessage] = []
        used_tokens = 0
        for msg in reversed(messages):
            message_tokens = estimate_text_tokens(msg.content) + 6
            if selected and used_tokens + message_tokens > self._token_budget:
                break
            if message_tokens > self._token_budget:
                selected.append(
                    msg.model_copy(
                        update={"content": self._clip_to_budget(msg.content, self._token_budget - 6)}
                    )
                )
                break
            selected.append(msg)
            used_tokens += message_tokens
        selected.reverse()
        return selected

    @staticmethod
    def _clip_to_budget(content: str, token_budget: int) -> str:
        """目的：按估算 token 预算裁剪单条超长消息。
        结果：完成当前实例行为并返回约定结果。
        """
        if token_budget <= 0:
            return ""
        return content[-max(1, token_budget * 2):]

    def delete_session(self, session_id: str) -> bool:
        """目的：删除会话热缓存。
        结果：删除或标记删除业务资源并返回处理结果。
        """
        return self._redis.delete_conversation_messages(session_id)

    def get_ttl(self, session_id: str) -> int:
        """目的：获取会话热缓存剩余 TTL。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        return self._redis.get_conversation_messages_ttl(session_id)
