"""独立 reranker 服务客户端。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from core.config import Settings, get_settings
from .schemas import RetrievalResult

logger = logging.getLogger(__name__)


class RerankClient:
    """通过 HTTP 调用独立 reranker-api 服务。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        *,
        top_n: int | None = None,
    ) -> tuple[list[RetrievalResult], bool, str]:
        """返回重排后的候选和是否成功应用。"""
        if not query.strip() or not candidates:
            return candidates, False, ""

        top_n = top_n or self.settings.rerank_top_n
        payload = {
            "query": query,
            "model": self.settings.rerank_model_name,
            "top_n": top_n,
            "documents": [
                {
                    "document_id": item.chunk_id,
                    "text": self._build_text(item),
                }
                for item in candidates
            ],
        }
        headers: dict[str, str] = {}
        if self.settings.rerank_api_key:
            headers["Authorization"] = f"Bearer {self.settings.rerank_api_key}"

        try:
            async with httpx.AsyncClient(
                base_url=self.settings.rerank_service_url.rstrip("/"),
                timeout=self.settings.rerank_timeout_ms / 1000,
            ) as client:
                response = await client.post("/rerank", json=payload, headers=headers)
                response.raise_for_status()
                items = response.json().get("results", [])
        except Exception as exc:
            logger.warning("重排服务不可用，回退融合结果: %s", exc)
            return candidates, False, str(exc)

        by_id: dict[str, dict[str, Any]] = {
            str(item.get("document_id", "")): item
            for item in items
            if item.get("document_id")
        }
        reranked: list[RetrievalResult] = []
        for candidate in candidates:
            matched = by_id.get(candidate.chunk_id)
            if not matched:
                continue
            reranked.append(
                candidate.model_copy(
                    update={
                        "rerank_score": float(matched.get("score", 0.0)),
                        "rank": int(matched.get("rank", 0)),
                        "score": float(matched.get("score", 0.0)),
                    }
                )
            )
        if not reranked:
            return candidates, False, "rerank 返回空结果"
        reranked.sort(key=lambda item: (-(item.rerank_score or 0.0), item.chunk_id))
        for rank, item in enumerate(reranked, start=1):
            item.rank = rank
        return reranked[:top_n], True, ""

    @staticmethod
    def _build_text(item: RetrievalResult) -> str:
        heading_path = item.heading_path.strip()
        content = item.content.strip()
        if heading_path and content:
            return f"{heading_path}\n\n{content}"
        return content or heading_path
