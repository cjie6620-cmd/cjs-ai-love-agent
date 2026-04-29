from __future__ import annotations

import pytest

from agents.memory import ConversationContextManager, MemoryManager
from contracts.chat import ConversationHistoryMessage, MemoryDecision, SessionSummary


class _FakeEmbeddingService:
    async def embed_text(self, text: str) -> list[float]:
        return [float(len(text))]


class _FakeVectorClient:
    def __init__(self, existing: dict[str, object] | None = None) -> None:
        self.existing = existing
        self.inserted: list[dict[str, object]] = []
        self.updated: list[dict[str, object]] = []
        self.touched: list[dict[str, object]] = []

    def get_active_memory_by_key(self, *, user_id: str, canonical_key: str):
        assert user_id == "user-001"
        assert canonical_key
        return self.existing

    def insert_memory(self, embedding, **kwargs):
        self.inserted.append({"embedding": embedding, **kwargs})
        return "mem-new"

    def update_memory(self, record_id: str, **kwargs):
        self.updated.append({"record_id": record_id, **kwargs})
        return record_id

    def touch_memory(self, record_id: str, *, metadata_json=None):
        self.touched.append({"record_id": record_id, "metadata_json": metadata_json})
        return record_id


class _FakeRedisService:
    def __init__(self, cached_messages: list[dict[str, object]] | None = None) -> None:
        self.cached_messages = cached_messages or []
        self.deleted = False
        self.appended: list[dict[str, object]] = []

    def get_conversation_messages(self, session_id: str, *, limit: int):
        assert session_id == "sess-001"
        return self.cached_messages[-limit:]

    def append_conversation_message(self, session_id: str, message_data, *, max_messages: int, ttl: int):
        assert session_id == "sess-001"
        self.appended.append(message_data)
        return True

    def delete_conversation_messages(self, session_id: str):
        assert session_id == "sess-001"
        self.deleted = True
        return True

    def get_conversation_messages_ttl(self, session_id: str):
        assert session_id == "sess-001"
        return 7200


class _FakeConversationRepository:
    def __init__(self) -> None:
        self.seed_messages = [
            ConversationHistoryMessage(id="m1", role="user", content="第一条"),
            ConversationHistoryMessage(id="m2", role="assistant", content="第二条"),
        ]

    def get_conversation_context_seed(self, user_id: str, session_id: str, *, limit: int):
        assert user_id == "user-001"
        assert session_id == "sess-001"
        return {
            "summary_text": "用户刚分手，需要稳定情绪。",
            "covered_message_count": 8,
            "last_message_id": "m0",
            "updated_at": None,
            "recent_messages": self.seed_messages[-limit:],
        }

    def touch_memory(self, record_id: str, *, metadata_json=None):
        self.touched.append({"record_id": record_id, "metadata_json": metadata_json})
        return record_id


@pytest.mark.asyncio
async def test_save_memory_inserts_structured_memory() -> None:
    """结构化长期记忆应当写入向量库。"""
    vector_client = _FakeVectorClient()
    manager = MemoryManager(embedding_service=_FakeEmbeddingService(), vector_client=vector_client)
    decision = MemoryDecision(
        should_store=True,
        memory_type="profile_summary",
        memory_text="用户的名字是小明，偏好被称呼为小明",
        canonical_key="profile:name",
        importance_score=0.95,
        confidence=0.98,
        merge_strategy="replace",
        reason_code="explicit_identity",
    )

    record_id = await manager.save_memory("user-001", decision, session_id="sess-001")

    assert record_id == "mem-new"
    assert vector_client.inserted[0]["canonical_key"] == "profile:name"
    assert vector_client.inserted[0]["importance_score"] == 0.95


@pytest.mark.asyncio
async def test_save_memory_appends_existing_memory() -> None:
    """append 策略应当在同一治理键上拼接旧内容。"""
    vector_client = _FakeVectorClient(
        existing={"id": "mem-old", "content": "用户在亲密关系冲突中倾向先沉默"}
    )
    manager = MemoryManager(embedding_service=_FakeEmbeddingService(), vector_client=vector_client)
    decision = MemoryDecision(
        should_store=True,
        memory_type="profile_summary",
        memory_text="用户在冲突中不太会马上表达",
        canonical_key="profile:conflict_style",
        importance_score=0.88,
        confidence=0.92,
        merge_strategy="append",
        reason_code="stable_relationship_pattern",
    )

    record_id = await manager.save_memory("user-001", decision, session_id="sess-001")

    assert record_id == "mem-old"
    assert "用户在亲密关系冲突中倾向先沉默" in vector_client.updated[0]["content"]
    assert "用户在冲突中不太会马上表达" in vector_client.updated[0]["content"]


@pytest.mark.asyncio
async def test_save_memory_treats_insert_as_replace_when_key_exists() -> None:
    """模型误返回 insert 时，同一 canonical_key 仍应更新旧 active 记忆。"""
    vector_client = _FakeVectorClient(
        existing={"id": "mem-old", "content": "用户喜欢简短回答"}
    )
    manager = MemoryManager(embedding_service=_FakeEmbeddingService(), vector_client=vector_client)
    decision = MemoryDecision(
        should_store=True,
        memory_type="preference",
        memory_text="用户更喜欢简洁直接的回答",
        canonical_key="preference:reply_length",
        importance_score=0.9,
        confidence=0.95,
        merge_strategy="insert",
        reason_code="stable_preference",
    )

    record_id = await manager.save_memory("user-001", decision, session_id="sess-001")

    assert record_id == "mem-old"
    assert vector_client.inserted == []
    assert vector_client.updated[0]["record_id"] == "mem-old"
    assert vector_client.updated[0]["content"] == "用户更喜欢简洁直接的回答"


@pytest.mark.asyncio
async def test_save_memory_skips_low_value_memory() -> None:
    """低价值长期记忆应当被过滤掉。"""
    vector_client = _FakeVectorClient()
    manager = MemoryManager(embedding_service=_FakeEmbeddingService(), vector_client=vector_client)
    decision = MemoryDecision(
        should_store=True,
        memory_type="event",
        memory_text="用户今天心情有点低落",
        canonical_key="event:temporary_mood",
        importance_score=0.2,
        confidence=0.9,
        merge_strategy="insert",
        reason_code="temporary_mood",
    )

    record_id = await manager.save_memory("user-001", decision, session_id="sess-001")

    assert record_id is None
    assert vector_client.inserted == []
    assert vector_client.updated == []


@pytest.mark.asyncio
async def test_conversation_context_manager_uses_redis_cache_with_token_budget() -> None:
    """Redis 有热缓存时，应按整体 token 预算保留最新消息。"""
    cached = [
        {"id": "m1", "role": "user", "content": "旧消息" * 200},
        {"id": "m2", "role": "assistant", "content": "最近回复"},
        {"id": "m3", "role": "user", "content": "最新问题"},
    ]
    manager = ConversationContextManager(
        redis_service=_FakeRedisService(cached),
        conversation_repository=_FakeConversationRepository(),
    )
    manager._token_budget = 20

    context = await manager.build_context(user_id="user-001", session_id="sess-001")

    assert [item.id for item in context.recent_messages] == ["m2", "m3"]
    assert context.session_summary == SessionSummary(
        summary_text="用户刚分手，需要稳定情绪。",
        covered_message_count=8,
        last_message_id="m0",
        updated_at=None,
    )


@pytest.mark.asyncio
async def test_conversation_context_manager_backfills_redis_when_cache_misses() -> None:
    """Redis 未命中时，应从 DB seed 构造上下文并刷新热缓存。"""
    redis = _FakeRedisService([])
    manager = ConversationContextManager(
        redis_service=redis,
        conversation_repository=_FakeConversationRepository(),
    )

    context = await manager.build_context(user_id="user-001", session_id="sess-001")

    assert [item.content for item in context.recent_messages] == ["第一条", "第二条"]
    assert redis.deleted is True
    assert [item["id"] for item in redis.appended] == ["m1", "m2"]


@pytest.mark.asyncio
async def test_conversation_context_manager_preserves_interrupted_status_from_redis() -> None:
    """Redis 热缓存中的 interrupted 状态应被还原到上下文消息。"""
    cached = [
        {
            "id": "m1",
            "role": "assistant",
            "content": "部分回复",
            "reply_status": "interrupted",
        },
    ]
    manager = ConversationContextManager(
        redis_service=_FakeRedisService(cached),
        conversation_repository=_FakeConversationRepository(),
    )

    context = await manager.build_context(user_id="user-001", session_id="sess-001")

    assert context.recent_messages[0].reply_status == "interrupted"
