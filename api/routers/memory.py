"""长期记忆治理路由。"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from api.deps import get_container, require_login
from contracts.common import ApiResponse, success_response
from contracts.memory import (
    MemoryDeleteResponse,
    MemoryItemPayload,
    MemoryItemsResponse,
    MemorySettingsPayload,
    UpdateMemorySettingsRequest,
)
from persistence import MemoryAuditRepository, MemorySettingsRepository

router = APIRouter()


def _settings_repository(request: Request) -> MemorySettingsRepository:
    container = get_container(request)
    return getattr(container, "memory_settings_repository", None) or MemorySettingsRepository()


def _audit_repository(request: Request) -> MemoryAuditRepository:
    container = get_container(request)
    return getattr(container, "memory_audit_repository", None) or MemoryAuditRepository()


def _vector_client(request: Request):
    container = get_container(request)
    return container.memory_manager.vector_client


@router.get("/settings", response_model=ApiResponse[MemorySettingsPayload])
async def get_memory_settings(request: Request) -> ApiResponse[MemorySettingsPayload]:
    """目的：查询当前登录用户长期记忆开关。
    结果：未创建设置记录时默认返回关闭。
    """
    current_user = require_login(request)
    settings = _settings_repository(request).get_settings(current_user.id)
    return success_response(MemorySettingsPayload(**settings))


@router.put("/settings", response_model=ApiResponse[MemorySettingsPayload])
async def update_memory_settings(
    payload: UpdateMemorySettingsRequest,
    request: Request,
) -> ApiResponse[MemorySettingsPayload]:
    """目的：开启或关闭当前用户的长期记忆能力。
    结果：关闭后停止新记忆写入和旧记忆召回，但不删除已有记忆。
    """
    current_user = require_login(request)
    settings = _settings_repository(request).set_enabled(
        current_user.id,
        payload.memory_enabled,
    )
    _audit_repository(request).record(
        action="memory.settings_enabled" if payload.memory_enabled else "memory.settings_disabled",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        resource_id=current_user.id,
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("User-Agent", ""),
        detail_json={"memory_enabled": payload.memory_enabled},
    )
    return success_response(MemorySettingsPayload(**settings))


@router.get("/items", response_model=ApiResponse[MemoryItemsResponse])
async def list_memory_items(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ApiResponse[MemoryItemsResponse]:
    """目的：分页查看当前用户自己的 active 长期记忆。
    结果：只返回当前登录用户且未删除的记忆。
    """
    current_user = require_login(request)
    vector_client = _vector_client(request)
    rows = vector_client.list_user_memories(user_id=current_user.id, limit=limit, offset=offset)
    total = vector_client.count_user_memories(user_id=current_user.id)
    return success_response(
        MemoryItemsResponse(
            items=[MemoryItemPayload(**row) for row in rows],
            total=total,
        )
    )


@router.delete("/items/{item_id}", response_model=ApiResponse[MemoryDeleteResponse])
async def delete_memory_item(
    item_id: str,
    request: Request,
) -> ApiResponse[MemoryDeleteResponse]:
    """目的：软删除当前用户的一条长期记忆。
    结果：该记忆状态变为 deleted，后续召回不会再命中。
    """
    current_user = require_login(request)
    deleted_count = _vector_client(request).soft_delete_memory(
        user_id=current_user.id,
        record_id=item_id,
    )
    if deleted_count:
        _audit_repository(request).record(
            action="memory.item_deleted",
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            resource_id=item_id,
            ip=request.client.host if request.client else "",
            user_agent=request.headers.get("User-Agent", ""),
            detail_json={"deleted_count": deleted_count},
        )
    return success_response(MemoryDeleteResponse(deleted_count=deleted_count))


@router.delete("/items", response_model=ApiResponse[MemoryDeleteResponse])
async def clear_memory_items(request: Request) -> ApiResponse[MemoryDeleteResponse]:
    """目的：软删除当前用户全部 active 长期记忆。
    结果：用户的长期记忆列表清空，向量记录保留 deleted 状态用于审计。
    """
    current_user = require_login(request)
    deleted_count = _vector_client(request).soft_delete_user_memories(user_id=current_user.id)
    if deleted_count:
        _audit_repository(request).record(
            action="memory.items_cleared",
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            resource_id=current_user.id,
            ip=request.client.host if request.client else "",
            user_agent=request.headers.get("User-Agent", ""),
            detail_json={"deleted_count": deleted_count},
        )
    return success_response(MemoryDeleteResponse(deleted_count=deleted_count))
