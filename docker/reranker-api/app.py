"""独立 reranker API：基于 bge-reranker-v2-m3 提供 HTTP 重排服务。"""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI
from pydantic import BaseModel, Field


class RerankDocument(BaseModel):
    """待重排文档。"""

    document_id: str = Field(..., description="文档 ID")
    text: str = Field(..., description="文档内容")


class RerankRequest(BaseModel):
    """重排请求。"""

    query: str = Field(..., description="查询文本")
    documents: list[RerankDocument] = Field(default_factory=list, description="候选文档")
    top_n: int = Field(default=5, ge=1, le=50, description="返回数量")
    model: str = Field(default="BAAI/bge-reranker-v2-m3", description="模型名")


class RerankResult(BaseModel):
    """单条重排结果。"""

    document_id: str
    score: float
    rank: int


class RerankResponse(BaseModel):
    """重排响应。"""

    results: list[RerankResult] = Field(default_factory=list)


@lru_cache(maxsize=1)
def get_reranker():
    """惰性加载模型，避免容器启动时重复初始化。"""
    from FlagEmbedding import FlagReranker

    model_name = os.getenv("RERANK_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
    device = os.getenv("RERANK_DEVICE", "cpu").lower()
    use_fp16 = device.startswith("cuda")
    return FlagReranker(
        model_name,
        use_fp16=use_fp16,
    )


app = FastAPI(title="AI Love Reranker API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    """健康检查。"""
    return {"status": "ok"}


@app.post("/rerank", response_model=RerankResponse)
def rerank(request: RerankRequest) -> RerankResponse:
    """重排候选文档。"""
    if not request.query.strip() or not request.documents:
        return RerankResponse(results=[])

    reranker = get_reranker()
    batch_size = max(int(os.getenv("RERANK_BATCH_SIZE", "8")), 1)
    pairs = [[request.query, doc.text] for doc in request.documents]
    scores = reranker.compute_score(
        pairs,
        batch_size=batch_size,
        normalize=True,
    )

    if not isinstance(scores, list):
        scores = [float(scores)]

    ranked = sorted(
        zip(request.documents, scores, strict=False),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    results = [
        RerankResult(
            document_id=doc.document_id,
            score=float(score),
            rank=index,
        )
        for index, (doc, score) in enumerate(ranked[: request.top_n], start=1)
    ]
    return RerankResponse(results=results)
