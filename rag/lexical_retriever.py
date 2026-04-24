"""Elasticsearch 关键词召回。"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from core.config import Settings, get_settings
from .schemas import RetrievalResult

logger = logging.getLogger(__name__)


class LexicalRetriever:
    """基于 Elasticsearch 的 BM25 召回。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def ensure_index(self) -> None:
        """确保索引存在。"""
        payload = {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
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
    ) -> int:
        """按文档范围删除索引。"""
        del filename
        filters: list[dict[str, Any]] = [{"term": {"source": source}}]
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
        """批量写入 child chunk 到 ES。"""
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
    ) -> list[RetrievalResult]:
        """执行 BM25 检索。"""
        if not query.strip():
            return []

        filters: list[dict[str, Any]] = []
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
        auth = None
        if self.settings.es_username:
            auth = (self.settings.es_username, self.settings.es_password)
        base_url = self.settings.es_host_list[0] if self.settings.es_host_list else "http://127.0.0.1:9200"
        return httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=auth,
            timeout=self.settings.es_timeout_ms / 1000,
        )
