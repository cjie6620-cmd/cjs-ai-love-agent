"""回答分级缓存服务测试。"""

from __future__ import annotations

import pytest

from agents.response_cache import ResponseCacheService
from contracts.chat import ChatRequest, ChatResponse, ChatTrace, ConversationContext, McpCallInfo
from core.config import Settings


class _FakeRedis:
    def __init__(self) -> None:
        self.payloads: dict[str, dict] = {}
        self.deleted: list[str] = []
        self.locks: set[str] = set()

    def cache_response_payload(self, key: str, payload: dict, *, ttl: int) -> bool:
        del ttl
        self.payloads[key] = payload
        return True

    def get_response_payload(self, key: str) -> dict | None:
        return self.payloads.get(key)

    def delete_response_payload(self, key: str) -> bool:
        self.deleted.append(key)
        self.payloads.pop(key, None)
        return True

    def acquire_lock(self, key: str, *, ttl: int) -> bool:
        del ttl
        if key in self.locks:
            return False
        self.locks.add(key)
        return True


class _FakeEmbedding:
    async def embed_text(self, text: str) -> list[float]:
        del text
        return [0.1, 0.2, 0.3]


class _FakeVector:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.inserted: list[dict] = []

    def search_response_cache(self, embedding, **kwargs):
        del embedding, kwargs
        return self.rows

    def insert_response_cache(self, embedding, **kwargs):
        self.inserted.append({"embedding": embedding, **kwargs})
        return "cache-001"


def _settings() -> Settings:
    return Settings(
        response_cache_enabled=True,
        response_cache_exact_ttl_seconds=60,
        response_cache_semantic_ttl_seconds=60,
        response_cache_semantic_threshold=0.94,
        response_cache_version="test-cache.v1",
    )


def _request(**overrides) -> ChatRequest:
    payload = {
        "user_id": "user-001",
        "session_id": "sess-001",
        "mode": "companion",
        "message": " 最近心情不好 ",
    }
    payload.update(overrides)
    return ChatRequest(**payload)


def _response() -> ChatResponse:
    return ChatResponse(
        reply="我理解你的感受",
        mode="companion",
        trace=ChatTrace(safety_level="low"),
        advisor=None,
    )


@pytest.mark.asyncio
async def test_l1_exact_cache_hit_returns_marked_response() -> None:
    """L1 精确缓存命中时应直接返回带 cache trace 的响应。"""
    redis = _FakeRedis()
    service = ResponseCacheService(
        redis_service=redis,  # type: ignore[arg-type]
        embedding_service=_FakeEmbedding(),  # type: ignore[arg-type]
        vector_client=_FakeVector(),  # type: ignore[arg-type]
        settings=_settings(),
    )
    request = _request()
    context = ConversationContext()
    key = service.build_key(request, context)
    redis.cache_response_payload(key.exact_key, _response().model_dump(mode="json"), ttl=60)

    cached = await service.get_cached_response(request, context)

    assert cached is not None
    assert cached.response.reply == "我理解你的感受"
    assert cached.response.trace.cache_hit is True
    assert cached.response.trace.cache_level == "l1_exact"


@pytest.mark.asyncio
async def test_l2_semantic_cache_hit_returns_similarity() -> None:
    """L2 语义缓存命中时应返回相似度和语义缓存层级。"""
    vector = _FakeVector()
    vector.rows = [
        {
            "id": "cache-001",
            "response_payload": _response().model_dump(mode="json"),
            "score": 0.97,
        }
    ]
    service = ResponseCacheService(
        redis_service=_FakeRedis(),  # type: ignore[arg-type]
        embedding_service=_FakeEmbedding(),  # type: ignore[arg-type]
        vector_client=vector,  # type: ignore[arg-type]
        settings=_settings(),
    )

    cached = await service.get_cached_response(_request(), ConversationContext())

    assert cached is not None
    assert cached.level == "l2_semantic"
    assert cached.response.trace.cache_similarity == 0.97


@pytest.mark.asyncio
async def test_set_response_skips_medium_risk_and_tool_calls() -> None:
    """非 low 风险或存在工具调用时不应写入缓存。"""
    redis = _FakeRedis()
    vector = _FakeVector()
    service = ResponseCacheService(
        redis_service=redis,  # type: ignore[arg-type]
        embedding_service=_FakeEmbedding(),  # type: ignore[arg-type]
        vector_client=vector,  # type: ignore[arg-type]
        settings=_settings(),
    )
    tool_response = _response().model_copy(
        update={
            "trace": ChatTrace(
                safety_level="low",
                mcp_calls=[
                    McpCallInfo(
                        server_label="test",
                        tool_name="search",
                        status="success",
                        duration_ms=1,
                    )
                ],
            )
        }
    )

    await service.set_response(_request(), ConversationContext(), _response(), safety_level="medium")
    await service.set_response(_request(), ConversationContext(), tool_response, safety_level="low")

    assert redis.payloads == {}
    assert vector.inserted == []
