"""长期记忆治理接口契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MemorySettingsPayload(BaseModel):
    """目的：描述用户长期记忆授权开关。
    结果：前后端围绕同一字段读写授权状态。
    """

    memory_enabled: bool = Field(default=False, description="是否开启长期记忆")


class UpdateMemorySettingsRequest(BaseModel):
    """目的：修改长期记忆授权开关请求。
    结果：路由层可以安全校验布尔开关。
    """

    memory_enabled: bool = Field(default=False, description="是否开启长期记忆")


class MemoryItemPayload(BaseModel):
    """目的：长期记忆管理列表中的单条记忆。
    结果：前端可以展示、删除和审计用户自己的长期记忆。
    """

    id: str
    memory_type: str
    canonical_key: str
    content: str
    importance_score: float = 0.0
    confidence: float = 0.0
    status: str = "active"
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    last_seen_at: datetime | None = None
    updated_at: datetime | None = None


class MemoryItemsResponse(BaseModel):
    """目的：长期记忆分页列表响应。
    结果：调用方可以读取当前页数据和总数。
    """

    items: list[MemoryItemPayload] = Field(default_factory=list)
    total: int = 0


class MemoryDeleteResponse(BaseModel):
    """目的：长期记忆删除响应。
    结果：调用方可以确认实际删除数量。
    """

    deleted_count: int = 0
