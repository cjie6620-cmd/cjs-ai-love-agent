"""RagService 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from contracts.rag import KnowledgeIndexTextRequest, KnowledgeSearchRequest
from core.config import get_settings
from rag import RagService
from rag.schemas import HybridRetrievalResponse, RetrievalResult, RetrievedParentContext


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_index_text_success() -> None:
    service = RagService()
    service._replace_existing_document = AsyncMock(return_value=2)
    service._pipeline.ingest_text = AsyncMock(return_value=4)

    request = KnowledgeIndexTextRequest(
        text="当对方回复变少时，不要立刻追问。",
        title="沟通技巧",
        category="relationship_knowledge",
        source="手工录入",
    )
    result = await service.index_text(request)

    assert result.success is True
    assert result.chunks_written == 4
    service._replace_existing_document.assert_called_once()
    service._pipeline.ingest_text.assert_called_once_with(
        request.text,
        title=request.title,
        category=request.category,
        source=request.source,
    )


@pytest.mark.asyncio
async def test_index_file_replaces_existing_document_before_ingest() -> None:
    service = RagService()
    service._replace_existing_document = AsyncMock(return_value=3)
    service._pipeline.ingest_file = AsyncMock(return_value=6)

    result = await service.index_file(
        b"# Title\n\nBody",
        "playbook.md",
        category="relationship_knowledge",
        source="builtin:knowledge_base",
    )

    assert result.success is True
    assert result.chunks_written == 6
    service._replace_existing_document.assert_called_once()
    service._pipeline.ingest_file.assert_called_once()


@pytest.mark.asyncio
async def test_index_directory_not_exist() -> None:
    service = RagService()
    result = await service.index_knowledge_directory("/nonexistent/path")

    assert result.success is False
    assert "不存在" in result.message


@pytest.mark.asyncio
async def test_search_returns_hybrid_scores() -> None:
    response = HybridRetrievalResponse(
        query="如何和对象沟通",
        candidates=[
            RetrievalResult(
                chunk_id="c-1",
                parent_id="p-1",
                content="主动倾听是沟通的第一步",
                score=0.92,
                category="relationship_knowledge",
                source="knowledge_base",
                title="沟通策略",
                heading_path="沟通 / 倾听",
                locator="沟通策略.md | 沟通 / 倾听",
                dense_score=0.61,
                bm25_score=8.2,
                fusion_score=0.42,
                rerank_score=0.92,
            )
        ],
        parent_contexts=[
            RetrievedParentContext(
                parent_id="p-1",
                doc_id="doc-1",
                title="沟通策略",
                source="knowledge_base",
                heading_path="沟通 / 倾听",
                locator="沟通策略.md | 沟通 / 倾听",
                content="主动倾听是沟通的第一步",
            )
        ],
        rerank_applied=True,
    )

    service = RagService()
    service._retriever.search_with_context = AsyncMock(return_value=response)

    request = KnowledgeSearchRequest(query="如何和对象沟通")
    result = await service.search(request)

    assert result.total == 1
    assert result.results[0].chunk_id == "c-1"
    assert result.results[0].rerank_score == 0.92
    assert result.results[0].heading_path == "沟通 / 倾听"


@pytest.mark.asyncio
async def test_replace_existing_document_deletes_vector_and_es() -> None:
    service = RagService()
    service._vector_client.delete_knowledge = MagicMock(return_value=5)
    service._delete_lexical_document = AsyncMock(return_value=5)

    deleted = await service._replace_existing_document(
        filename="guide.md",
        category="relationship_knowledge",
        source="builtin:knowledge_base",
        doc_id="doc-1",
    )

    assert deleted == 5
    service._vector_client.delete_knowledge.assert_called_once_with(
        source="builtin:knowledge_base",
        category="relationship_knowledge",
        filename="guide.md",
        doc_id="doc-1",
    )
    service._delete_lexical_document.assert_called_once()
