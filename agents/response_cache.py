"""聊天回答分级缓存服务。

目的：统一封装 L1 Redis 精确缓存、L2 pgvector 语义缓存和缓存击穿保护。
结果：AgentService 主链路可以用一个稳定入口完成读写缓存，不污染工作流节点。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from contracts.chat import CacheLevel, ChatRequest, ChatResponse, ConversationContext
from core.config import Settings, get_settings
from rag.embeddings import EmbeddingService
from rag.vector_store import PgVectorClient
from security import RedisService

logger = logging.getLogger(__name__)

_LOCK_TTL_SECONDS = 15
_WAIT_RETRY_COUNT = 8
_WAIT_INTERVAL_SECONDS = 0.08


@dataclass(frozen=True)
class ResponseCacheKey:
    """目的：承载一次缓存查找需要的稳定键。
    结果：L1、L2 和锁可以共用相同归一化结果。
    """

    exact_key: str
    normalized_message: str
    context_fingerprint: str


@dataclass(frozen=True)
class CachedResponse:
    """目的：描述一次缓存命中结果。
    结果：调用方可以直接获得响应、命中层级和语义相似度。
    """

    response: ChatResponse
    level: CacheLevel
    similarity: float | None = None


class ResponseCacheService:
    """目的：提供回答缓存的读、写和击穿保护能力。
    结果：主链路在缓存不可用时自动降级，不影响正常 LLM 调用。
    """

    def __init__(
        self,
        redis_service: RedisService | None = None,
        *,
        embedding_service: EmbeddingService | None = None,
        vector_client: PgVectorClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.redis = redis_service or RedisService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_client = vector_client or PgVectorClient()

    def build_key(
        self,
        request: ChatRequest,
        conversation_context: ConversationContext,
    ) -> ResponseCacheKey:
        """目的：生成 L1/L2 共用的缓存键材料。
        结果：相同用户、会话、模式、消息和上下文会得到相同缓存键。
        """
        normalized_message = self.normalize_message(request.message)
        context_fingerprint = self.build_context_fingerprint(conversation_context)
        raw = "|".join(
            [
                self.settings.response_cache_version,
                request.user_id,
                request.session_id,
                request.mode,
                normalized_message,
                context_fingerprint,
            ]
        )
        exact_key = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return ResponseCacheKey(
            exact_key=exact_key,
            normalized_message=normalized_message,
            context_fingerprint=context_fingerprint,
        )

    async def get_cached_response(
        self,
        request: ChatRequest,
        conversation_context: ConversationContext,
    ) -> CachedResponse | None:
        """目的：按 L1 精确缓存 -> L2 语义缓存顺序查找回答。
        结果：命中时返回带 trace 标记的 ChatResponse，未命中或异常时返回 None。
        """
        if not self.settings.response_cache_enabled:
            return None

        key = self.build_key(request, conversation_context)
        exact = self.get_exact_response(key)
        if exact is not None:
            return CachedResponse(
                response=self._mark_cache_trace(exact, level="l1_exact", similarity=None),
                level="l1_exact",
            )

        semantic = await self.get_semantic_response(request, key)
        if semantic is not None:
            return semantic
        return None

    def get_exact_response(self, key: ResponseCacheKey) -> ChatResponse | None:
        """目的：读取 Redis L1 精确缓存。
        结果：命中且结构合法时返回 ChatResponse，否则返回 None。
        """
        try:
            payload = self.redis.get_response_payload(key.exact_key)
            if not isinstance(payload, dict):
                return None
            return ChatResponse.model_validate(payload)
        except Exception as exc:
            logger.warning("L1 回答缓存读取失败，已降级: key=%s, error=%s", key.exact_key, exc)
            try:
                self.redis.delete_response_payload(key.exact_key)
            except Exception:
                pass
            return None

    async def get_semantic_response(
        self,
        request: ChatRequest,
        key: ResponseCacheKey,
    ) -> CachedResponse | None:
        """目的：读取 pgvector L2 语义缓存。
        结果：命中相似度阈值时返回 ChatResponse，否则返回 None。
        """
        try:
            embedding = await self.embedding_service.embed_text(key.normalized_message)
            rows = self.vector_client.search_response_cache(
                embedding,
                user_id=request.user_id,
                session_id=request.session_id,
                mode=request.mode,
                context_fingerprint=key.context_fingerprint,
                threshold=self.settings.response_cache_semantic_threshold,
                top_k=1,
            )
        except RuntimeError:
            logger.warning("Embedding 服务暂不可用，跳过 L2 回答缓存")
            return None
        except Exception as exc:
            logger.warning("L2 回答缓存读取失败，已降级: %s", exc)
            return None

        if not rows:
            return None
        row = rows[0]
        payload = row.get("response_payload")
        if not isinstance(payload, dict):
            return None
        try:
            similarity = float(row.get("score", 0.0))
            response = ChatResponse.model_validate(payload)
            marked = self._mark_cache_trace(
                response,
                level="l2_semantic",
                similarity=similarity,
            )
            return CachedResponse(
                response=marked,
                level="l2_semantic",
                similarity=similarity,
            )
        except Exception as exc:
            logger.warning("L2 回答缓存反序列化失败，已降级: %s", exc)
            return None

    async def set_response(
        self,
        request: ChatRequest,
        conversation_context: ConversationContext,
        response: ChatResponse,
        *,
        safety_level: str,
    ) -> None:
        """目的：按策略写入 L1 精确缓存和 L2 语义缓存。
        结果：低风险、无工具调用的回答可以被后续请求复用。
        """
        if not self._can_store(response, safety_level=safety_level):
            return

        key = self.build_key(request, conversation_context)
        payload = self._response_payload(response)

        try:
            self.redis.cache_response_payload(
                key.exact_key,
                payload,
                ttl=self.settings.response_cache_exact_ttl_seconds,
            )
        except Exception as exc:
            logger.warning("L1 回答缓存写入失败，已跳过: key=%s, error=%s", key.exact_key, exc)

        try:
            embedding = await self.embedding_service.embed_text(key.normalized_message)
            expires_at = datetime.now(UTC) + timedelta(
                seconds=self.settings.response_cache_semantic_ttl_seconds
            )
            self.vector_client.insert_response_cache(
                embedding,
                user_id=request.user_id,
                session_id=request.session_id,
                mode=request.mode,
                context_fingerprint=key.context_fingerprint,
                normalized_message=key.normalized_message,
                response_payload=payload,
                expires_at=expires_at,
            )
        except RuntimeError:
            logger.warning("Embedding 服务暂不可用，跳过 L2 回答缓存写入")
        except Exception as exc:
            logger.warning("L2 回答缓存写入失败，已跳过: %s", exc)

    def acquire_generation_lock(
        self,
        request: ChatRequest,
        conversation_context: ConversationContext,
    ) -> bool | None:
        """目的：在 L1 未命中后获取短锁，降低同一问题并发击穿概率。
        结果：True 表示当前请求负责生成，False 表示可等待缓存回填，None 表示 Redis 不可用。
        """
        if not self.settings.response_cache_enabled:
            return None
        key = self.build_key(request, conversation_context)
        try:
            return self.redis.acquire_lock(
                f"response_cache:lock:{key.exact_key}",
                ttl=_LOCK_TTL_SECONDS,
            )
        except Exception as exc:
            logger.debug("回答缓存击穿锁获取失败，继续走 L3: %s", exc)
            return None

    async def wait_for_exact_response(
        self,
        request: ChatRequest,
        conversation_context: ConversationContext,
    ) -> CachedResponse | None:
        """目的：短暂等待其他并发请求回填 L1 缓存。
        结果：等待期间命中则复用缓存，超时后调用方继续走 L3。
        """
        key = self.build_key(request, conversation_context)
        for _ in range(_WAIT_RETRY_COUNT):
            await asyncio.sleep(_WAIT_INTERVAL_SECONDS)
            exact = self.get_exact_response(key)
            if exact is not None:
                return CachedResponse(
                    response=self._mark_cache_trace(exact, level="l1_exact", similarity=None),
                    level="l1_exact",
                )
        return None

    @staticmethod
    def normalize_message(message: str) -> str:
        """目的：归一化用户输入，减少空白、大小写差异导致的缓存错失。
        结果：返回适合作为缓存键和 embedding 输入的文本。
        """
        return re.sub(r"\s+", " ", str(message or "").strip()).lower()

    def build_context_fingerprint(self, conversation_context: ConversationContext) -> str:
        """目的：根据会话摘要和最近消息生成上下文指纹。
        结果：上下文变化时缓存自动隔离，避免复用过期回答。
        """
        summary = conversation_context.session_summary
        parts: list[str] = [
            self.settings.response_cache_version,
            conversation_context.context_version,
            summary.last_message_id,
            str(summary.covered_message_count),
            hashlib.sha256(summary.summary_text.encode("utf-8")).hexdigest(),
        ]
        for msg in conversation_context.recent_messages:
            msg_hash = hashlib.sha256(msg.content.encode("utf-8")).hexdigest()
            parts.extend([msg.id, msg.role, msg.reply_status, msg_hash])
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    def _can_store(self, response: ChatResponse, *, safety_level: str) -> bool:
        """目的：统一回答缓存写入条件。
        结果：风险输入、工具调用和非低风险输出不会进入缓存。
        """
        if not self.settings.response_cache_enabled:
            return False
        if safety_level != "low" or response.trace.safety_level != "low":
            return False
        return not response.trace.mcp_calls

    @staticmethod
    def _response_payload(response: ChatResponse) -> dict[str, Any]:
        """目的：只保存可返回给前端的 ChatResponse JSON。
        结果：缓存中不包含 prompt、历史上下文、密钥等内部数据。
        """
        clean_trace = response.trace.model_copy(
            update={
                "cache_hit": False,
                "cache_level": "none",
                "cache_similarity": None,
            }
        )
        clean_response = response.model_copy(
            deep=True,
            update={"trace": clean_trace, "guest_quota_remaining": None},
        )
        return clean_response.model_dump(mode="json")

    @staticmethod
    def _mark_cache_trace(
        response: ChatResponse,
        *,
        level: CacheLevel,
        similarity: float | None,
    ) -> ChatResponse:
        """目的：给缓存响应补充 trace 标记。
        结果：调用方可以明确看到命中层级和语义相似度。
        """
        trace = response.trace.model_copy(
            update={
                "cache_hit": True,
                "cache_level": level,
                "cache_similarity": similarity,
            }
        )
        return response.model_copy(deep=True, update={"trace": trace})
