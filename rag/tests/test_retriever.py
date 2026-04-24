from __future__ import annotations

from core.config import Settings
from rag.retriever import HybridRetriever
from rag.schemas import RetrievalResult


class _DummyEmbeddingService:
    async def embed_text(self, text: str) -> list[float]:
        return [0.1, 0.2]


class _DummyVectorClient:
    def search_knowledge(self, query_embedding, *, top_k: int, category: str | None, chunk_role: str):
        del query_embedding, top_k, category
        assert chunk_role == "child"
        return [
            {
                "id": "row-1",
                "title": "沟通手册",
                "content": "先观察对方节奏，再决定要不要追问。",
                "source": "builtin",
                "category": "relationship_knowledge",
                "metadata_json": {
                    "chunk_id": "c1",
                    "parent_id": "p1",
                    "doc_id": "doc-1",
                    "heading_path": "沟通 / 节奏",
                    "locator": "a.md | 沟通 / 节奏",
                    "chunk_role": "child",
                },
                "score": 0.62,
            },
            {
                "id": "row-2",
                "title": "沟通手册",
                "content": "情绪高的时候先不要连续发消息。",
                "source": "builtin",
                "category": "relationship_knowledge",
                "metadata_json": {
                    "chunk_id": "c2",
                    "parent_id": "p2",
                    "doc_id": "doc-1",
                    "heading_path": "沟通 / 情绪管理",
                    "locator": "a.md | 沟通 / 情绪管理",
                    "chunk_role": "child",
                },
                "score": 0.58,
            },
        ]

    def get_parent_chunks(self, parent_ids):
        rows = {
            "p1": {
                "title": "沟通手册",
                "source": "builtin",
                "content": "沟通 / 节奏\n\n先观察对方节奏，再决定要不要追问。",
                "metadata_json": {
                    "parent_id": "p1",
                    "doc_id": "doc-1",
                    "heading_path": "沟通 / 节奏",
                    "locator": "a.md | 沟通 / 节奏",
                    "category": "relationship_knowledge",
                    "chunk_role": "parent",
                },
            },
            "p2": {
                "title": "沟通手册",
                "source": "builtin",
                "content": "沟通 / 情绪管理\n\n情绪高的时候先不要连续发消息。",
                "metadata_json": {
                    "parent_id": "p2",
                    "doc_id": "doc-1",
                    "heading_path": "沟通 / 情绪管理",
                    "locator": "a.md | 沟通 / 情绪管理",
                    "category": "relationship_knowledge",
                    "chunk_role": "parent",
                },
            },
        }
        return [rows[item] for item in parent_ids if item in rows]


class _DummyLexicalRetriever:
    async def search(self, query: str, *, top_k: int, category: str | None):
        del query, top_k, category
        return [
            RetrievalResult(
                chunk_id="c2",
                parent_id="p2",
                doc_id="doc-1",
                content="情绪高的时候先不要连续发消息。",
                score=12.0,
                bm25_score=12.0,
                category="relationship_knowledge",
                source="builtin",
                title="沟通手册",
                heading_path="沟通 / 情绪管理",
                locator="a.md | 沟通 / 情绪管理",
            ),
            RetrievalResult(
                chunk_id="c3",
                parent_id="p1",
                doc_id="doc-1",
                content="表达需求时别把问题说成指责。",
                score=8.5,
                bm25_score=8.5,
                category="relationship_knowledge",
                source="builtin",
                title="沟通手册",
                heading_path="沟通 / 节奏",
                locator="a.md | 沟通 / 节奏",
            ),
        ]


class _DummyRerankClient:
    async def rerank(self, query: str, candidates: list[RetrievalResult], *, top_n: int | None = None):
        del query, top_n
        reranked = []
        scores = {"c2": 0.92, "c1": 0.77, "c3": 0.41}
        for candidate in candidates:
            reranked.append(
                candidate.model_copy(
                    update={
                        "rerank_score": scores[candidate.chunk_id],
                        "score": scores[candidate.chunk_id],
                    }
                )
            )
        reranked.sort(key=lambda item: item.rerank_score or 0.0, reverse=True)
        return reranked[:2], True, ""


def test_hybrid_retriever_merges_dense_bm25_and_expands_parent() -> None:
    settings = Settings(
        hybrid_dense_top_k=20,
        hybrid_bm25_top_k=20,
        hybrid_fusion_top_k=12,
        prompt_parent_top_k=4,
        rerank_top_n=5,
    )
    retriever = HybridRetriever(
        embedding_service=_DummyEmbeddingService(),
        vector_client=_DummyVectorClient(),
        lexical_retriever=_DummyLexicalRetriever(),
        rerank_client=_DummyRerankClient(),
        settings=settings,
    )

    import asyncio

    response = asyncio.run(
        retriever.search_with_context(
            ["对方回复变少怎么办", "最近对方回复越来越慢"],
            top_k=2,
            category="relationship_knowledge",
        )
    )

    assert response.rerank_applied is True
    assert [item.chunk_id for item in response.candidates] == ["c2", "c1"]
    assert len(response.parent_contexts) == 2
    assert response.parent_contexts[0].parent_id == "p2"
    assert response.parent_contexts[0].supporting_children[0].chunk_id == "c2"
