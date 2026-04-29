"""独立 reranker API：基于 bge-reranker-v2-m3 提供 HTTP 重排服务。

目的：为主应用的 RAG 检索链路提供 HTTP 化的候选文档重排能力。
结果：主应用可以通过 /rerank 获得按相关性排序后的候选结果。
"""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI
from pydantic import BaseModel, Field


class RerankDocument(BaseModel):
    """待重排文档。

    目的：描述 reranker 输入中的单个候选文档。
    结果：请求体可以稳定携带 document_id 和文本内容。
    """

    document_id: str = Field(..., description="文档 ID")
    text: str = Field(..., description="文档内容")


class RerankRequest(BaseModel):
    """重排请求。

    目的：描述一次 rerank 调用需要的 query、候选文档、返回数量和模型名。
    结果：接口层可以校验并传递完整重排参数。
    """

    query: str = Field(..., description="查询文本")
    documents: list[RerankDocument] = Field(default_factory=list, description="候选文档")
    top_n: int = Field(default=5, ge=1, le=50, description="返回数量")
    model: str = Field(default="BAAI/bge-reranker-v2-m3", description="模型名")


class RerankResult(BaseModel):
    """单条重排结果。

    目的：描述 reranker 对单个候选文档的评分和排序。
    结果：响应体可以稳定返回 document_id、score 和 rank。
    """

    document_id: str
    score: float
    rank: int


class RerankResponse(BaseModel):
    """重排响应。

    目的：承载本次重排后的候选结果列表。
    结果：客户端可以按 results 读取排序后的候选。
    """

    results: list[RerankResult] = Field(default_factory=list)


@lru_cache(maxsize=1)
def get_reranker():
    """惰性加载 reranker 模型。

    目的：避免容器启动和每次请求重复初始化大模型。
    结果：返回缓存后的 FlagReranker 实例。
    """
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
    """执行健康检查。

    目的：为 Docker healthcheck 和启动探针提供轻量存活接口。
    结果：返回 status=ok。
    """
    return {"status": "ok"}


@app.post("/rerank", response_model=RerankResponse)
def rerank(request: RerankRequest) -> RerankResponse:
    """重排候选文档。

    目的：用 query-document 对调用 reranker 模型并按分数排序。
    结果：返回最多 top_n 条带分数和名次的候选结果。
    """
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
