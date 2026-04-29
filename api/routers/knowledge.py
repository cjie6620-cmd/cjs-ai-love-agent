"""知识库管理路由。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile

from api.deps import get_container
from contracts.common import ApiResponse, success_response
from contracts.rag import (
    KnowledgeBatchIndexResponse,
    KnowledgeIndexResponse,
    KnowledgeIndexTextRequest,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from rag.storage import MinioClient

router = APIRouter()

_CONTENT_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".html": "text/html",
    ".json": "application/json",
    ".csv": "text/csv",
    ".xml": "application/xml",
}


@router.post("/files", response_model=ApiResponse[KnowledgeIndexResponse])
async def upload_knowledge(
    request: Request,
    file: UploadFile = File(..., description="待索引的知识文件"),
    category: str = Form(default="relationship_knowledge"),
    source: str = Form(default=""),
) -> ApiResponse[KnowledgeIndexResponse]:
    """目的：执行上传知识文件并索引相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    data = await file.read()
    filename = file.filename or "unknown"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    content_type = _CONTENT_TYPE_MAP.get(suffix, "application/octet-stream")

    container = get_container(request)
    minio_client: MinioClient = container.minio_client
    minio_client.upload_file(data, filename, content_type=content_type, prefix="knowledge")
    result = await container.rag_service.index_file(
        data,
        filename,
        category=category,
        source=source or f"upload:{filename}",
    )
    return success_response(result)


@router.post("/text", response_model=ApiResponse[KnowledgeIndexResponse])
async def index_knowledge_text(
    request_body: KnowledgeIndexTextRequest,
    request: Request,
) -> ApiResponse[KnowledgeIndexResponse]:
    """目的：执行直接索引文本相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    container = get_container(request)
    result = await container.rag_service.index_text(request_body)
    return success_response(result)


@router.post("/reindex", response_model=ApiResponse[KnowledgeBatchIndexResponse])
async def reindex_knowledge(
    request: Request,
    category: str = "relationship_knowledge",
) -> ApiResponse[KnowledgeBatchIndexResponse]:
    """目的：执行重建内置知识库索引相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    knowledge_dir = Path(__file__).resolve().parents[2] / "docs" / "knowledge_base"
    container = get_container(request)
    result = await container.rag_service.index_knowledge_directory(
        knowledge_dir,
        category=category,
        source="builtin:knowledge_base",
    )
    return success_response(result)


@router.post("/search", response_model=ApiResponse[KnowledgeSearchResponse])
async def search_knowledge(
    request_body: KnowledgeSearchRequest,
    request: Request,
) -> ApiResponse[KnowledgeSearchResponse]:
    """目的：执行搜索知识库相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    container = get_container(request)
    result = await container.rag_service.search(request_body)
    return success_response(result)
