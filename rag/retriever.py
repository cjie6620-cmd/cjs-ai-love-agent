"""知识检索服务：混合召回 + 加权 RRF + 独立 rerank。

目的：把向量召回、BM25 召回、RRF 融合、rerank 和父块上下文组装成完整检索链路。
结果：回复生成可以获得排序后的证据 child 和可注入 prompt 的 parent 上下文。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

from observability import traceable_chain

from core.config import Settings, get_settings
from .embeddings import EmbeddingService
from .fusion import weighted_reciprocal_rank_fusion
from .lexical_retriever import LexicalRetriever
from .rerank_client import RerankClient
from .schemas import HybridRetrievalResponse, RetrievalResult, RetrievedParentContext
from .vector_store import PgVectorClient

logger = logging.getLogger(__name__)


class HybridRetriever:
    """目的：同时负责稠密召回、BM25 召回、RRF 融合和重排。
    结果：对外返回最终候选证据和父块上下文。
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_client: PgVectorClient | None = None,
        lexical_retriever: LexicalRetriever | None = None,
        rerank_client: RerankClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """目的：装配 embedding、向量库、关键词召回、rerank 和检索配置。
        结果：实例可执行完整 RAG 检索流程。
        """
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_client = vector_client or PgVectorClient()
        self.lexical_retriever = lexical_retriever or LexicalRetriever(self.settings)
        self.rerank_client = rerank_client or RerankClient(self.settings)

    @traceable_chain("rag.search")
    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
        tenant_id: str = "default",
    ) -> list[RetrievalResult]:
        """目的：兼容旧调用方只需要内容列表或简单 RetrievalResult 的场景。
        结果：返回由父块上下文转换出的 RetrievalResult 列表。
        """
        response = await self.search_with_context(
            [query],
            top_k=top_k,
            category=category,
            tenant_id=tenant_id,
        )
        return [
            RetrievalResult(
                chunk_id=context.parent_id,
                parent_id=context.parent_id,
                doc_id=context.doc_id,
                content=context.content,
                score=max(
                    (child.rerank_score or child.fusion_score or child.dense_score or 0.0)
                    for child in context.supporting_children
                )
                if context.supporting_children
                else 0.0,
                category=str(context.metadata.get("category", category or "")),
                source=context.source,
                title=context.title,
                heading_path=context.heading_path,
                locator=context.locator,
                metadata=context.metadata,
            )
            for context in response.parent_contexts
        ]

    @traceable_chain("rag.search_with_context")
    async def search_with_context(
        self,
        queries: list[str],
        *,
        top_k: int = 5,
        category: str | None = None,
        tenant_id: str = "default",
    ) -> HybridRetrievalResponse:
        """目的：对一个或多个 query 执行向量召回、BM25、RRF、rerank 和父块扩展。
        结果：返回完整 HybridRetrievalResponse，供 prompt 组装使用。
        """
        valid_queries = [query.strip() for query in queries if query and query.strip()]
        if not valid_queries:
            return HybridRetrievalResponse()

        candidate_map: dict[str, RetrievalResult] = {}
        weighted_ranked_lists: list[tuple[list[str], float]] = []
        dense_top_k = max(self.settings.hybrid_dense_top_k, top_k)
        bm25_top_k = max(self.settings.hybrid_bm25_top_k, top_k)

        for index, query in enumerate(valid_queries):
            dense_results, lexical_results = await asyncio.gather(
                self._dense_search(
                    query,
                    top_k=dense_top_k,
                    category=category,
                    tenant_id=tenant_id,
                ),
                self.lexical_retriever.search(
                    query,
                    top_k=bm25_top_k,
                    category=category,
                    tenant_id=tenant_id,
                ),
            )
            weight = 1.0 if index == 0 else 0.7
            if dense_results:
                weighted_ranked_lists.append(([item.chunk_id for item in dense_results], weight))
            if lexical_results:
                weighted_ranked_lists.append(([item.chunk_id for item in lexical_results], weight))

            for item in dense_results:
                self._merge_candidate(candidate_map, item, source_type="dense")
            for item in lexical_results:
                self._merge_candidate(candidate_map, item, source_type="bm25")

        fused = weighted_reciprocal_rank_fusion(weighted_ranked_lists, k=60)
        fused_candidates: list[RetrievalResult] = []
        for rank, (chunk_id, fusion_score) in enumerate(
            fused[: self.settings.hybrid_fusion_top_k],
            start=1,
        ):
            candidate = candidate_map.get(chunk_id)
            if candidate is None:
                continue
            updated = candidate.model_copy(
                update={
                    "fusion_score": fusion_score,
                    "score": fusion_score,
                    "rank": rank,
                }
            )
            fused_candidates.append(updated)

        reranked, rerank_applied, rerank_error = await self.rerank_client.rerank(
            valid_queries[0],
            fused_candidates,
            top_n=min(top_k, self.settings.rerank_top_n),
        )

        final_candidates = reranked if rerank_applied else fused_candidates[: min(top_k, len(fused_candidates))]
        if not rerank_applied:
            for rank, item in enumerate(final_candidates, start=1):
                item.rank = rank
                item.score = item.fusion_score or item.dense_score or item.bm25_score or 0.0

        parent_contexts = self._build_parent_contexts(final_candidates, tenant_id=tenant_id)
        return HybridRetrievalResponse(
            query=valid_queries[0],
            candidates=final_candidates,
            parent_contexts=parent_contexts,
            rerank_applied=rerank_applied,
            rerank_error=rerank_error,
        )

    def search_sync(self, query: str) -> list[str]:
        """目的：为旧同步调用方提供安全降级的检索方法。
        结果：返回命中内容字符串列表，异常或已有事件循环时返回空列表。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            logger.debug("已在运行中的事件循环中调用 search_sync，返回空结果。")
            return []

        try:
            results = asyncio.run(self.search(query))
            return [result.content for result in results]
        except Exception as exc:
            logger.warning("知识检索同步调用异常: %s", exc)
            return []

    async def _dense_search(
        self,
        query: str,
        *,
        top_k: int,
        category: str | None,
        tenant_id: str = "default",
    ) -> list[RetrievalResult]:
        """目的：把 query 转为 embedding 后从 pgvector 检索 child chunk。
        结果：返回标准化后的 RetrievalResult 列表，异常时降级为空列表。
        """
        try:
            query_embedding = await self.embedding_service.embed_text(query)
            rows = self.vector_client.search_knowledge(
                query_embedding,
                top_k=top_k,
                category=category,
                chunk_role="child",
                tenant_id=tenant_id,
            )
            return self._normalize_results(rows, top_k=top_k)
        except RuntimeError:
            logger.warning("Embedding 服务未配置，向量检索降级为空结果。")
            return []
        except Exception as exc:
            logger.warning("向量检索异常，降级为空结果: %s", exc)
            return []

    def _normalize_results(
        self,
        rows: list[dict[str, Any]],
        *,
        top_k: int,
    ) -> list[RetrievalResult]:
        """目的：把 pgvector 原始行转换为 RetrievalResult，并过滤低价值和重复内容。
        结果：返回最多 top_k 条可参与融合排序的候选。
        """
        results: list[RetrievalResult] = []
        seen_keys: set[str] = set()

        for row in rows:
            metadata = row.get("metadata_json", {}) or {}
            if not isinstance(metadata, dict):
                metadata = {}

            content = str(row.get("content", "")).strip()
            if not content or self._is_low_value_heading(content, metadata):
                continue

            dedup_key = self._build_dedup_key(content, metadata)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            score = float(row.get("score", 0.0))
            results.append(
                RetrievalResult(
                    chunk_id=str(metadata.get("chunk_id") or metadata.get("logical_chunk_id") or row.get("id", "")),
                    parent_id=str(metadata.get("parent_id", "")),
                    doc_id=str(metadata.get("doc_id", "")),
                    content=content,
                    score=score,
                    dense_score=score,
                    category=str(row.get("category", "")),
                    source=str(row.get("source", "")),
                    title=str(row.get("title", "")),
                    heading_path=str(metadata.get("heading_path", "")),
                    locator=str(metadata.get("locator", "")),
                    metadata=metadata,
                )
            )
            if len(results) >= top_k:
                break
        return results

    def _build_parent_contexts(
        self,
        candidates: list[RetrievalResult],
        *,
        tenant_id: str = "default",
    ) -> list[RetrievedParentContext]:
        """目的：按候选 child 的 parent_id 聚合，并从向量库读取完整 parent 内容。
        结果：返回可进入 prompt 的 RetrievedParentContext 列表。
        """
        parent_order: list[str] = []
        grouped: dict[str, list[RetrievalResult]] = {}
        for item in candidates:
            parent_id = item.parent_id or item.chunk_id
            if parent_id not in grouped:
                grouped[parent_id] = []
                parent_order.append(parent_id)
            grouped[parent_id].append(item)

        selected_parent_ids = parent_order[: self.settings.prompt_parent_top_k]
        parent_rows = self.vector_client.get_parent_chunks(selected_parent_ids, tenant_id=tenant_id)
        parent_map = {
            str((row.get("metadata_json") or {}).get("parent_id", "")): row
            for row in parent_rows
        }

        contexts: list[RetrievedParentContext] = []
        for parent_id in selected_parent_ids:
            support = grouped.get(parent_id, [])
            parent_row = parent_map.get(parent_id)
            if parent_row is None:
                top_child = support[0]
                contexts.append(
                    RetrievedParentContext(
                        parent_id=parent_id,
                        doc_id=top_child.doc_id,
                        title=top_child.title,
                        source=top_child.source,
                        heading_path=top_child.heading_path,
                        locator=top_child.locator,
                        content=top_child.content,
                        metadata=top_child.metadata,
                        supporting_children=support,
                    )
                )
                continue

            metadata = parent_row.get("metadata_json", {}) or {}
            contexts.append(
                RetrievedParentContext(
                    parent_id=parent_id,
                    doc_id=str(metadata.get("doc_id", "")),
                    title=str(parent_row.get("title", "")),
                    source=str(parent_row.get("source", "")),
                    heading_path=str(metadata.get("heading_path", "")),
                    locator=str(metadata.get("locator", "")),
                    content=str(parent_row.get("content", "")),
                    metadata=metadata if isinstance(metadata, dict) else {},
                    supporting_children=support,
                )
            )
        return contexts

    def _merge_candidate(
        self,
        candidates: dict[str, RetrievalResult],
        item: RetrievalResult,
        *,
        source_type: str,
    ) -> None:
        """目的：把向量召回和 BM25 命中的同一 chunk 合并为一条候选记录。
        结果：保留更高分数、更完整内容和更完整元数据。
        """
        existing = candidates.get(item.chunk_id)
        if existing is None:
            candidates[item.chunk_id] = item
            return

        update: dict[str, Any] = {}
        if source_type == "dense":
            best_dense = max(existing.dense_score or 0.0, item.dense_score or item.score)
            update["dense_score"] = best_dense
            update["score"] = max(existing.score, best_dense)
        elif source_type == "bm25":
            best_bm25 = max(existing.bm25_score or 0.0, item.bm25_score or item.score)
            update["bm25_score"] = best_bm25
            update["score"] = max(existing.score, best_bm25)

        if len(item.content) > len(existing.content):
            update["content"] = item.content
        if item.heading_path and not existing.heading_path:
            update["heading_path"] = item.heading_path
        if item.locator and not existing.locator:
            update["locator"] = item.locator
        if item.title and not existing.title:
            update["title"] = item.title
        if item.parent_id and not existing.parent_id:
            update["parent_id"] = item.parent_id
        if item.doc_id and not existing.doc_id:
            update["doc_id"] = item.doc_id
        if item.metadata and not existing.metadata:
            update["metadata"] = item.metadata

        candidates[item.chunk_id] = existing.model_copy(update=update)

    def _is_low_value_heading(self, content: str, metadata: dict[str, Any]) -> bool:
        """目的：过滤只有一级短标题、缺少正文信息的召回噪声。
        结果：返回 True 表示该内容不应进入候选。
        """
        heading_level = metadata.get("heading_level")
        char_count = metadata.get("char_count")
        if heading_level == 1 and isinstance(char_count, int) and char_count <= 24:
            return "\n" not in content and len(content) <= 24
        return False

    def _build_dedup_key(self, content: str, metadata: dict[str, Any]) -> str:
        """目的：优先使用逻辑 chunk ID，缺失时基于文件位置或内容哈希去重。
        结果：返回稳定的候选去重字符串。
        """
        logical_chunk_id = str(metadata.get("logical_chunk_id", "")).strip()
        if logical_chunk_id:
            return logical_chunk_id

        filename = str(metadata.get("filename", "")).strip()
        section_index = str(metadata.get("section_index", "")).strip()
        chunk_index = str(metadata.get("chunk_index", "")).strip()
        if filename and section_index:
            return f"{filename}:{section_index}:{chunk_index}"

        normalized = " ".join(content.split())
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()


class KnowledgeRetriever(HybridRetriever):
    """目的：保留 KnowledgeRetriever 入口，避免已有调用方直接依赖 HybridRetriever 名称。
    结果：旧代码可继续获得相同的混合检索能力。
    """
