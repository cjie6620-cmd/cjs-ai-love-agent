"""管理员后台 API。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from api.deps import get_container, require_permission
from contracts.admin import (
    AdminDashboardResponse,
    AdminMeResponse,
    AdminPermissionPayload,
    AdminPermissionsResponse,
    AdminRolePayload,
    AdminRolesResponse,
    AdminRoleSaveRequest,
    AdminUpdateUserRequest,
    AdminUserPayload,
    AdminUsersResponse,
    AuditEventPayload,
    AuditEventsResponse,
    KnowledgeDocumentPayload,
    KnowledgeDocumentsResponse,
    KnowledgeJobPayload,
    KnowledgeJobsResponse,
    KnowledgeTextAdminRequest,
    SafetyEventPayload,
    SafetyEventsResponse,
)
from contracts.common import ApiResponse, success_response
from contracts.rag import KnowledgeSearchRequest, KnowledgeSearchResponse

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


def _client_ip(request: Request) -> str:
    """目的：执行 _client_ip 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    return request.client.host if request.client is not None else ""


def _user_agent(request: Request) -> str:
    """目的：执行 _user_agent 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    return request.headers.get("User-Agent", "")


def _doc_payload(document) -> KnowledgeDocumentPayload:
    """目的：执行 _doc_payload 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    return KnowledgeDocumentPayload(
        id=document.id,
        doc_id=document.doc_id,
        title=document.title,
        filename=document.filename,
        category=document.category,
        source=document.source,
        status=document.status,
        chunk_count=document.chunk_count,
        created_by=document.created_by,
        last_job_id=document.last_job_id,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _job_payload(job) -> KnowledgeJobPayload:
    """目的：执行 _job_payload 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    return KnowledgeJobPayload(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        document_id=job.document_id,
        filename=job.filename,
        progress=job.progress,
        result_json=job.result_json or {},
        error_message=job.error_message,
        created_by=job.created_by,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _safe_filename(filename: str) -> str:
    """目的：执行 _safe_filename 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    value = Path(filename or "unknown").name.strip()
    return value or f"knowledge_{uuid4().hex}.txt"


def _build_doc_id(*, title: str, filename: str = "", source: str, category: str) -> str:
    """目的：与 RAG pipeline 保持一致的稳定文档 ID 规则。
    结果：完成当前业务处理并返回约定结果。
    """
    digest = hashlib.blake2s(
        "||".join([source, filename, title, title, category]).encode("utf-8"),
        digest_size=8,
    ).hexdigest()
    return f"doc_{digest}"


def _record_audit(request: Request, *, action: str, resource_type: str, resource_id: str = "", detail=None) -> None:
    """目的：执行 _record_audit 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "admin:access", container)
    container.admin_repository.record_audit(
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        detail_json=detail or {},
    )


def _dispatch_job_task(container, job, task, *args):
    """目的：投递 Celery 任务；投递失败时保留任务记录并标记失败。
    结果：完成当前业务处理并返回约定结果。
    """
    try:
        task.delay(*args)
    except Exception as exc:
        container.knowledge_repository.mark_job_failed(
            job.id,
            error_message=f"任务投递失败: {exc}",
        )
        refreshed = container.knowledge_repository.get_job(job.tenant_id, job.id)
        if refreshed is not None:
            return refreshed
    return job


@router.get("/me", response_model=ApiResponse[AdminMeResponse])
async def admin_me(request: Request) -> ApiResponse[AdminMeResponse]:
    """目的：执行 admin_me 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    current_user = require_permission(request, "admin:access")
    return success_response(AdminMeResponse(
        user=AdminUserPayload(
            id=current_user.id,
            tenant_id=current_user.tenant_id,
            login_name=current_user.external_user_id,
            nickname=current_user.nickname,
            avatar_url=current_user.avatar_url,
            roles=current_user.roles,
        ),
        permissions=current_user.permissions,
    ))


@router.get("/dashboard", response_model=ApiResponse[AdminDashboardResponse])
async def dashboard(request: Request) -> ApiResponse[AdminDashboardResponse]:
    """目的：执行 dashboard 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "admin:access", container)
    metrics = container.admin_repository.dashboard_metrics(current_user.tenant_id)
    jobs = container.knowledge_repository.list_jobs(current_user.tenant_id)[:10]
    safety_events = container.admin_repository.list_safety_events(current_user.tenant_id, limit=10)
    return success_response(AdminDashboardResponse(
        metrics=metrics,
        recent_jobs=[_job_payload(item) for item in jobs],
        recent_safety_events=[SafetyEventPayload(**item) for item in safety_events],
    ))


@router.get("/users", response_model=ApiResponse[AdminUsersResponse])
async def list_users(request: Request, keyword: str = "", status: str = "") -> ApiResponse[AdminUsersResponse]:
    """目的：执行 list_users 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "user:read", container)
    users = container.admin_repository.list_users(
        current_user.tenant_id,
        keyword=keyword,
        status=status,
    )
    return success_response(AdminUsersResponse(users=[AdminUserPayload(**item) for item in users]))


@router.get("/users/{user_id}", response_model=ApiResponse[AdminMeResponse])
async def user_detail(user_id: str, request: Request) -> ApiResponse[AdminMeResponse]:
    """目的：执行 user_detail 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    require_permission(request, "user:read", container)
    authz = container.admin_repository.get_user_authz(user_id)
    if authz is None:
        raise HTTPException(status_code=404, detail="用户不存在。")
    return success_response(AdminMeResponse(
        user=AdminUserPayload(
            id=str(authz["id"]),
            tenant_id=str(authz["tenant_id"]),
            login_name=str(authz["login_name"]),
            nickname=str(authz["nickname"]),
            avatar_url=str(authz["avatar_url"]),
            status=authz["status"],
            roles=list(authz["roles"]),
            created_at=authz["created_at"],
            last_active_at=authz["last_active_at"],
        ),
        permissions=list(authz["permissions"]),
    ))


@router.patch("/users/{user_id}", response_model=ApiResponse[AdminMeResponse])
async def update_user(user_id: str, payload: AdminUpdateUserRequest, request: Request) -> ApiResponse[AdminMeResponse]:
    """目的：执行 update_user 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "user:disable", container)
    authz = container.admin_repository.update_user_status(
        current_user.tenant_id,
        user_id,
        status=payload.status,
    )
    if authz is None:
        raise HTTPException(status_code=404, detail="用户不存在。")
    _record_audit(request, action="user.update_status", resource_type="user", resource_id=user_id, detail=payload.model_dump())
    return success_response(AdminMeResponse(
        user=AdminUserPayload(
            id=str(authz["id"]),
            tenant_id=str(authz["tenant_id"]),
            login_name=str(authz["login_name"]),
            nickname=str(authz["nickname"]),
            avatar_url=str(authz["avatar_url"]),
            status=authz["status"],
            roles=list(authz["roles"]),
            created_at=authz["created_at"],
            last_active_at=authz["last_active_at"],
        ),
        permissions=list(authz["permissions"]),
    ))


@router.get("/roles", response_model=ApiResponse[AdminRolesResponse])
async def list_roles(request: Request) -> ApiResponse[AdminRolesResponse]:
    """目的：执行 list_roles 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "role:read", container)
    return success_response(AdminRolesResponse(
        roles=[AdminRolePayload(**item) for item in container.admin_repository.list_roles(current_user.tenant_id)]
    ))


@router.post("/roles", response_model=ApiResponse[AdminRolePayload])
async def create_role(payload: AdminRoleSaveRequest, request: Request) -> ApiResponse[AdminRolePayload]:
    """目的：执行 create_role 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "role:write", container)
    role = container.admin_repository.create_or_update_role(
        current_user.tenant_id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        permission_codes=payload.permissions,
    )
    _record_audit(request, action="role.create", resource_type="role", resource_id=role["id"], detail=payload.model_dump())
    return success_response(AdminRolePayload(**role))


@router.patch("/roles/{role_id}", response_model=ApiResponse[AdminRolePayload])
async def update_role(role_id: str, payload: AdminRoleSaveRequest, request: Request) -> ApiResponse[AdminRolePayload]:
    """目的：执行 update_role 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "role:write", container)
    role = container.admin_repository.create_or_update_role(
        current_user.tenant_id,
        role_id=role_id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        permission_codes=payload.permissions,
    )
    _record_audit(request, action="role.update", resource_type="role", resource_id=role_id, detail=payload.model_dump())
    return success_response(AdminRolePayload(**role))


@router.post("/users/{user_id}/roles/{role_id}", response_model=ApiResponse[dict[str, bool]])
async def assign_role(user_id: str, role_id: str, request: Request) -> ApiResponse[dict[str, bool]]:
    """目的：执行 assign_role 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "role:write", container)
    ok = container.admin_repository.assign_role(current_user.tenant_id, user_id, role_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户或角色不存在。")
    _record_audit(request, action="user.assign_role", resource_type="user", resource_id=user_id, detail={"role_id": role_id})
    return success_response({"ok": True})


@router.delete("/users/{user_id}/roles/{role_id}", response_model=ApiResponse[dict[str, bool]])
async def remove_role(user_id: str, role_id: str, request: Request) -> ApiResponse[dict[str, bool]]:
    """目的：执行 remove_role 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "role:write", container)
    ok = container.admin_repository.remove_role(current_user.tenant_id, user_id, role_id)
    if not ok:
        raise HTTPException(status_code=404, detail="角色不存在。")
    _record_audit(request, action="user.remove_role", resource_type="user", resource_id=user_id, detail={"role_id": role_id})
    return success_response({"ok": True})


@router.get("/permissions", response_model=ApiResponse[AdminPermissionsResponse])
async def permissions(request: Request) -> ApiResponse[AdminPermissionsResponse]:
    """目的：执行 permissions 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    require_permission(request, "role:read", container)
    return success_response(AdminPermissionsResponse(
        permissions=[AdminPermissionPayload(**item) for item in container.admin_repository.list_permissions()]
    ))


@router.get("/knowledge/documents", response_model=ApiResponse[KnowledgeDocumentsResponse])
async def knowledge_documents(request: Request, status: str = "", keyword: str = "") -> ApiResponse[KnowledgeDocumentsResponse]:
    """目的：执行 knowledge_documents 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:read", container)
    documents = container.knowledge_repository.list_documents(
        current_user.tenant_id,
        status=status,
        keyword=keyword,
    )
    return success_response(KnowledgeDocumentsResponse(documents=[_doc_payload(item) for item in documents]))


@router.get("/knowledge/documents/{document_id}", response_model=ApiResponse[KnowledgeDocumentPayload])
async def knowledge_document(document_id: str, request: Request) -> ApiResponse[KnowledgeDocumentPayload]:
    """目的：执行 knowledge_document 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:read", container)
    document = container.knowledge_repository.get_document(current_user.tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="知识文档不存在。")
    return success_response(_doc_payload(document))


@router.post("/knowledge/files", response_model=ApiResponse[KnowledgeJobPayload])
async def upload_knowledge_file(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form(default="relationship_knowledge"),
    source: str = Form(default=""),
) -> ApiResponse[KnowledgeJobPayload]:
    """目的：执行 upload_knowledge_file 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:write", container)
    filename = _safe_filename(file.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in _CONTENT_TYPE_MAP:
        raise HTTPException(status_code=400, detail="不支持的知识文件类型。")
    data = await file.read()
    max_bytes = container.settings.knowledge_max_upload_mb * 1024 * 1024
    if not data:
        raise HTTPException(status_code=400, detail="文件不能为空。")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"文件不能超过 {container.settings.knowledge_max_upload_mb}MB。")
    object_name = container.minio_client.upload_file(
        data,
        filename,
        content_type=_CONTENT_TYPE_MAP[suffix],
        prefix=f"knowledge/{current_user.tenant_id}",
    )
    if object_name is None:
        raise HTTPException(status_code=503, detail="文件存储服务暂不可用。")
    normalized_source = source.strip() or f"upload:{object_name}"
    doc_id = _build_doc_id(
        title=filename,
        filename=filename,
        source=normalized_source,
        category=category,
    )
    _, job = container.knowledge_repository.create_document_job(
        tenant_id=current_user.tenant_id,
        doc_id=doc_id,
        title=filename,
        filename=filename,
        category=category,
        source=normalized_source,
        object_name=object_name,
        created_by=current_user.id,
        job_type="upload_file",
    )
    from agents.worker import index_knowledge_file

    job = _dispatch_job_task(container, job, index_knowledge_file, job.id)
    _record_audit(request, action="knowledge.upload_file", resource_type="knowledge_document", resource_id=str(job.document_id), detail={"filename": filename})
    return success_response(_job_payload(job))


@router.post("/knowledge/text", response_model=ApiResponse[KnowledgeJobPayload])
async def index_knowledge_text(payload: KnowledgeTextAdminRequest, request: Request) -> ApiResponse[KnowledgeJobPayload]:
    """目的：执行 index_knowledge_text 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:write", container)
    doc_id = _build_doc_id(
        title=payload.title,
        filename="",
        source=payload.source,
        category=payload.category,
    )
    _, job = container.knowledge_repository.create_document_job(
        tenant_id=current_user.tenant_id,
        doc_id=doc_id,
        title=payload.title,
        filename="",
        category=payload.category,
        source=payload.source,
        object_name="",
        created_by=current_user.id,
        job_type="index_text",
        content_text=payload.text,
    )
    from agents.worker import index_knowledge_text as index_text_task

    job = _dispatch_job_task(container, job, index_text_task, job.id, payload.model_dump())
    _record_audit(request, action="knowledge.index_text", resource_type="knowledge_document", resource_id=str(job.document_id), detail={"title": payload.title})
    return success_response(_job_payload(job))


@router.delete("/knowledge/documents/{document_id}", response_model=ApiResponse[KnowledgeDocumentPayload])
async def delete_knowledge_document(document_id: str, request: Request) -> ApiResponse[KnowledgeDocumentPayload]:
    """目的：执行 delete_knowledge_document 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:delete", container)
    document = container.knowledge_repository.soft_delete_document(current_user.tenant_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="知识文档不存在。")
    await container.rag_service._replace_existing_document(  # noqa: SLF001 - 后台删除需要复用索引清理逻辑
        filename=document.filename,
        category=document.category,
        source=document.source,
        doc_id=document.doc_id,
        tenant_id=current_user.tenant_id,
    )
    _record_audit(request, action="knowledge.delete", resource_type="knowledge_document", resource_id=document.id)
    return success_response(_doc_payload(document))


@router.post("/knowledge/documents/{document_id}/reindex", response_model=ApiResponse[KnowledgeJobPayload])
async def reindex_document(document_id: str, request: Request) -> ApiResponse[KnowledgeJobPayload]:
    """目的：执行 reindex_document 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:reindex", container)
    job = container.knowledge_repository.create_document_reindex_job(
        tenant_id=current_user.tenant_id,
        document_id=document_id,
        created_by=current_user.id,
    )
    if job is None:
        raise HTTPException(status_code=404, detail="知识文档不存在。")
    from agents.worker import reindex_knowledge_document

    job = _dispatch_job_task(container, job, reindex_knowledge_document, job.id)
    _record_audit(request, action="knowledge.reindex_document", resource_type="knowledge_document", resource_id=document_id)
    return success_response(_job_payload(job))


@router.post("/knowledge/reindex", response_model=ApiResponse[KnowledgeJobPayload])
async def reindex_all(request: Request) -> ApiResponse[KnowledgeJobPayload]:
    """目的：执行 reindex_all 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:reindex", container)
    lock_key = f"knowledge:reindex:{current_user.tenant_id}"
    lock_result = container.redis_service.acquire_lock(lock_key, ttl=60 * 30)
    if lock_result is None:
        raise HTTPException(status_code=503, detail="知识库重建锁暂不可用。")
    if not lock_result:
        raise HTTPException(status_code=423, detail="已有知识库重建任务正在执行。")
    job = container.knowledge_repository.create_reindex_all_job(
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
    )
    from agents.worker import reindex_knowledge_all

    job = _dispatch_job_task(container, job, reindex_knowledge_all, job.id)
    if job.status == "failed":
        container.redis_service.delete(lock_key)
    _record_audit(request, action="knowledge.reindex_all", resource_type="knowledge_job", resource_id=job.id)
    return success_response(_job_payload(job))


@router.post("/knowledge/search", response_model=ApiResponse[KnowledgeSearchResponse])
async def search_knowledge(payload: KnowledgeSearchRequest, request: Request) -> ApiResponse[KnowledgeSearchResponse]:
    """目的：执行 search_knowledge 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:read", container)
    result = await container.rag_service.search(payload, tenant_id=current_user.tenant_id)
    return success_response(result)


@router.get("/knowledge/jobs", response_model=ApiResponse[KnowledgeJobsResponse])
async def knowledge_jobs(request: Request, status: str = "") -> ApiResponse[KnowledgeJobsResponse]:
    """目的：执行 knowledge_jobs 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:job:read", container)
    return success_response(KnowledgeJobsResponse(
        jobs=[_job_payload(item) for item in container.knowledge_repository.list_jobs(current_user.tenant_id, status=status)]
    ))


@router.get("/knowledge/jobs/{job_id}", response_model=ApiResponse[KnowledgeJobPayload])
async def knowledge_job(job_id: str, request: Request) -> ApiResponse[KnowledgeJobPayload]:
    """目的：执行 knowledge_job 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:job:read", container)
    job = container.knowledge_repository.get_job(current_user.tenant_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return success_response(_job_payload(job))


@router.post("/knowledge/jobs/{job_id}/retry", response_model=ApiResponse[KnowledgeJobPayload])
async def retry_job(job_id: str, request: Request) -> ApiResponse[KnowledgeJobPayload]:
    """目的：执行 retry_job 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:job:retry", container)
    job = container.knowledge_repository.get_job(current_user.tenant_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在。")
    if job.status not in {"failed", "canceled"}:
        raise HTTPException(status_code=400, detail="只有失败或已取消的任务可以重试。")
    job = container.knowledge_repository.reset_job_for_retry(current_user.tenant_id, job.id)
    if job is None:
        raise HTTPException(status_code=400, detail="任务当前状态不可重试。")
    if job.job_type in {"upload_file", "reindex_document"}:
        from agents.worker import reindex_knowledge_document

        job = _dispatch_job_task(container, job, reindex_knowledge_document, job.id)
    elif job.job_type == "index_text":
        from agents.worker import index_knowledge_text as index_text_task

        document = container.knowledge_repository.get_document(current_user.tenant_id, str(job.document_id or ""))
        if document is None or not document.content_text:
            raise HTTPException(status_code=400, detail="文本任务缺少可重试的原文内容。")
        job = _dispatch_job_task(
            container,
            job,
            index_text_task,
            job.id,
            {
                "title": document.title,
                "text": document.content_text,
                "category": document.category,
                "source": document.source,
            },
        )
    else:
        from agents.worker import reindex_knowledge_all

        job = _dispatch_job_task(container, job, reindex_knowledge_all, job.id)
    _record_audit(request, action="knowledge.job_retry", resource_type="knowledge_job", resource_id=job.id)
    return success_response(_job_payload(job))


@router.post("/knowledge/jobs/{job_id}/cancel", response_model=ApiResponse[dict[str, bool]])
async def cancel_job(job_id: str, request: Request) -> ApiResponse[dict[str, bool]]:
    """目的：执行 cancel_job 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "knowledge:job:retry", container)
    ok = container.knowledge_repository.mark_job_canceled(current_user.tenant_id, job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="任务不存在或当前状态不可取消。")
    _record_audit(request, action="knowledge.job_cancel", resource_type="knowledge_job", resource_id=job_id)
    return success_response({"ok": True})


@router.get("/audit-events", response_model=ApiResponse[AuditEventsResponse])
async def audit_events(request: Request) -> ApiResponse[AuditEventsResponse]:
    """目的：执行 audit_events 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "audit:read", container)
    return success_response(AuditEventsResponse(
        events=[AuditEventPayload(**item) for item in container.admin_repository.list_audit_events(current_user.tenant_id)]
    ))


@router.get("/safety-events", response_model=ApiResponse[SafetyEventsResponse])
async def safety_events(request: Request) -> ApiResponse[SafetyEventsResponse]:
    """目的：执行 safety_events 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    current_user = require_permission(request, "safety:read", container)
    return success_response(SafetyEventsResponse(
        events=[SafetyEventPayload(**item) for item in container.admin_repository.list_safety_events(current_user.tenant_id)]
    ))


@router.get("/system/health", response_model=ApiResponse[dict[str, object]])
async def system_health(request: Request) -> ApiResponse[dict[str, object]]:
    """目的：执行 system_health 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    require_permission(request, "system:read")
    return success_response({
        "summary": str(getattr(request.app.state, "startup_probe_summary", "")),
        "dependencies": getattr(request.app.state, "startup_probe_results", []),
    })


@router.get("/system/dependencies", response_model=ApiResponse[dict[str, object]])
async def system_dependencies(request: Request) -> ApiResponse[dict[str, object]]:
    """目的：执行 system_dependencies 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    require_permission(request, "system:read")
    return success_response({"dependencies": getattr(request.app.state, "startup_probe_results", [])})


@router.get("/system/config-summary", response_model=ApiResponse[dict[str, object]])
async def config_summary(request: Request) -> ApiResponse[dict[str, object]]:
    """目的：执行 config_summary 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    require_permission(request, "system:read", container)
    settings = container.settings
    return success_response({
        "app_env": settings.app_env,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "default_tenant_id": settings.default_tenant_id,
        "knowledge_max_upload_mb": settings.knowledge_max_upload_mb,
        "guest_daily_message_limit": settings.guest_daily_message_limit,
        "guest_ip_daily_message_limit": settings.guest_ip_daily_message_limit,
    })


@router.get("/system/queues", response_model=ApiResponse[dict[str, object]])
async def system_queues(request: Request) -> ApiResponse[dict[str, object]]:
    """目的：执行 system_queues 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    require_permission(request, "system:read", container)
    return success_response({
        "celery_broker": "redis",
        "rocketmq_namesrv_addr": container.settings.rocketmq_namesrv_addr,
        "memory_topic": container.settings.rocketmq_memory_topic,
    })
