"""Elasticsearch 关键词召回。

目的：提供基于 BM25 的关键词召回能力，补充向量召回的语义盲区。
结果：混合检索链路可以获得结构化的 RetrievalResult 列表。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from core.config import Settings, get_settings
from .schemas import RetrievalResult

logger = logging.getLogger(__name__)


class LexicalRetriever:
    """目的：封装 ES 索引创建、文档写入、删除和检索细节。
    结果：上层 RAG 管道可以用统一接口完成关键词召回。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """目的：注入或读取 Elasticsearch 相关配置。
        结果：实例具备创建客户端和访问目标索引的配置。
        """
        self.settings = settings or get_settings()

    async def ensure_index(self) -> None:
        """目的：在写入文档前创建包含中文分词字段的 ES 索引。
        结果：目标索引存在；已存在时直接返回。
        """
        payload = {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "tenant_id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},
                    "parent_id": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
                    "heading_path": {
                        "type": "text",
                        "analyzer": "ik_max_word",
                        "search_analyzer": "ik_smart",
                    },
                    "content": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
                    "category": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "locator": {"type": "keyword"},
                    "metadata": {"type": "object", "enabled": False},
                }
            },
        }
        async with self._client() as client:
            head = await client.head(f"/{self.settings.es_index}")
            if head.status_code == 200:
                return
            response = await client.put(f"/{self.settings.es_index}", json=payload)
            response.raise_for_status()

    async def delete_document(
        self,
        *,
        source: str,
        category: str | None = None,
        filename: str | None = None,
        doc_id: str | None = None,
        tenant_id: str = "default",
    ) -> int:
        """目的：重建知识文档前清理同来源、分类和 doc_id 的旧关键词索引。
        结果：返回 ES 删除的文档数量。
        """
        del filename
        filters: list[dict[str, Any]] = [{"term": {"tenant_id": tenant_id}}]
        if source:
            filters.append({"term": {"source": source}})
        if category:
            filters.append({"term": {"category": category}})
        if doc_id:
            filters.append({"term": {"doc_id": doc_id}})

        query = {"query": {"bool": {"filter": filters}}}
        async with self._client() as client:
            response = await client.post(
                f"/{self.settings.es_index}/_delete_by_query?refresh=true",
                json=query,
            )
            if response.status_code == 404:
                return 0
            response.raise_for_status()
            payload = response.json()
            return int(payload.get("deleted", 0))

    async def index_documents(self, documents: list[dict[str, Any]]) -> int:
        """目的：把切片后的子块写入 BM25 索引，支持关键词召回。
        结果：返回成功提交的文档数量，bulk 失败时抛出异常。
        """
        if not documents:
            return 0
        await self.ensure_index()
        lines: list[str] = []
        for doc in documents:
            chunk_id = str(doc["chunk_id"])
            lines.append(json.dumps({"index": {"_index": self.settings.es_index, "_id": chunk_id}}, ensure_ascii=False))
            lines.append(json.dumps(doc, ensure_ascii=False))
        body = "\n".join(lines) + "\n"

        async with self._client() as client:
            response = await client.post(
                "/_bulk?refresh=true",
                content=body,
                headers={"Content-Type": "application/x-ndjson"},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("errors"):
                raise RuntimeError("Elasticsearch bulk 索引存在失败项")
        return len(documents)

    async def search(
        self,
        query: str,
        *,
        top_k: int,
        category: str | None = None,
        tenant_id: str = "default",
    ) -> list[RetrievalResult]:
        """目的：按查询文本和可选分类从 ES 中召回关键词相关的 child chunk。
        结果：返回标准 RetrievalResult 列表，异常时降级为空列表。
        """
        if not query.strip():
            return []

        filters: list[dict[str, Any]] = [{"term": {"tenant_id": tenant_id}}]
        if category:
            filters.append({"term": {"category": category}})

        payload = {
            "size": top_k,
            "query": {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^3", "heading_path^2", "content"],
                            "type": "best_fields",
                        }
                    },
                    "filter": filters,
                }
            },
        }
        try:
            async with self._client() as client:
                response = await client.post(f"/{self.settings.es_index}/_search", json=payload)
                if response.status_code == 404:
                    return []
                response.raise_for_status()
                raw_hits = response.json().get("hits", {}).get("hits", [])
        except Exception as exc:
            logger.warning("ES 关键词召回失败，降级为空结果: %s", exc)
            return []

        results: list[RetrievalResult] = []
        for raw in raw_hits:
            source_payload = raw.get("_source", {}) or {}
            metadata = source_payload.get("metadata", {}) or {}
            results.append(
                RetrievalResult(
                    chunk_id=str(source_payload.get("chunk_id", raw.get("_id", ""))),
                    parent_id=str(source_payload.get("parent_id", "")),
                    doc_id=str(source_payload.get("doc_id", "")),
                    content=str(source_payload.get("content", "")),
                    score=float(raw.get("_score", 0.0)),
                    bm25_score=float(raw.get("_score", 0.0)),
                    category=str(source_payload.get("category", "")),
                    source=str(source_payload.get("source", "")),
                    title=str(source_payload.get("title", "")),
                    heading_path=str(source_payload.get("heading_path", "")),
                    locator=str(source_payload.get("locator", "")),
                    metadata=metadata if isinstance(metadata, dict) else {},
                )
            )
        return results

    def _client(self) -> httpx.AsyncClient:
        """目的：按配置组装 base_url、认证信息和超时时间。
        结果：返回可用于当前操作的 AsyncClient。
        """
        auth = None
        if self.settings.es_username:
            auth = (self.settings.es_username, self.settings.es_password)
        base_url = self.settings.es_host_list[0] if self.settings.es_host_list else "http://127.0.0.1:9200"
        return httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=auth,
            timeout=self.settings.es_timeout_ms / 1000,
        )
