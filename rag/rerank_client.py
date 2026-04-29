"""独立 reranker 服务客户端。

目的：通过 HTTP 调用外部重排服务，对混合召回候选进行精排。
结果：RAG 检索链路可以获得更贴近 query 的排序结果。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from core.config import Settings, get_settings
from .schemas import RetrievalResult

logger = logging.getLogger(__name__)


class RerankClient:
    """目的：封装 rerank 请求体、认证头、超时和降级处理。
    结果：上层检索器只需要传入 query 和候选列表即可获得重排结果。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """目的：注入或读取 reranker 服务地址、模型名、top_n 和超时配置。
        结果：实例具备调用外部 reranker-api 的配置。
        """
        self.settings = settings or get_settings()

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        *,
        top_n: int | None = None,
    ) -> tuple[list[RetrievalResult], bool, str]:
        """目的：把候选 chunk 发送到 reranker-api，并按返回分数重新排序。
        结果：返回候选列表、是否应用重排和失败原因。
        """
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
        """目的：把标题路径和正文合并成 reranker 更容易理解的文档文本。
        结果：返回用于重排服务的字符串。
        """
        heading_path = item.heading_path.strip()
        content = item.content.strip()
        if heading_path and content:
            return f"{heading_path}\n\n{content}"
        return content or heading_path
