from __future__ import annotations

import pytest

from agents.memory import MemoryManager
from contracts.chat import MemoryDecision


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


@pytest.mark.asyncio
async def test_save_memory_inserts_structured_memory() -> None:
    """?????????????"""
    vector_client = _FakeVectorClient()
    manager = MemoryManager(embedding_service=_FakeEmbeddingService(), vector_client=vector_client)
    decision = MemoryDecision(
        should_store=True,
        memory_type="profile_summary",
        memory_text="????????",
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
    """append ?????? key ??????????"""
    vector_client = _FakeVectorClient(
        existing={"id": "mem-old", "content": "??????????"}
    )
    manager = MemoryManager(embedding_service=_FakeEmbeddingService(), vector_client=vector_client)
    decision = MemoryDecision(
        should_store=True,
        memory_type="profile_summary",
        memory_text="????????????",
        canonical_key="profile:conflict_style",
        importance_score=0.88,
        confidence=0.92,
        merge_strategy="append",
        reason_code="stable_relationship_pattern",
    )

    record_id = await manager.save_memory("user-001", decision, session_id="sess-001")

    assert record_id == "mem-old"
    assert "????" in vector_client.updated[0]["content"]
    assert "????" in vector_client.updated[0]["content"]


@pytest.mark.asyncio
async def test_save_memory_skips_low_value_memory() -> None:
    """???????????????"""
    vector_client = _FakeVectorClient()
    manager = MemoryManager(embedding_service=_FakeEmbeddingService(), vector_client=vector_client)
    decision = MemoryDecision(
        should_store=True,
        memory_type="event",
        memory_text="???????",
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
