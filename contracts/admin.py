"""管理员后台接口契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AdminUserPayload(BaseModel):
    """目的：封装 AdminUserPayload 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 id 字段，用于 AdminUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 tenant_id 字段，用于 AdminUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant_id 值。
    tenant_id: str
    # 目的：保存 login_name 字段，用于 AdminUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 login_name 值。
    login_name: str
    # 目的：保存 nickname 字段，用于 AdminUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 nickname 值。
    nickname: str
    # 目的：保存 avatar_url 字段，用于 AdminUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 avatar_url 值。
    avatar_url: str = ""
    # 目的：保存 status 字段，用于 AdminUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Literal["active", "disabled"] = "active"
    # 目的：保存 roles 字段，用于 AdminUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 roles 值。
    roles: list[str] = Field(default_factory=list)
    # 目的：保存 created_at 字段，用于 AdminUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: datetime | None = None
    # 目的：保存 last_active_at 字段，用于 AdminUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 last_active_at 值。
    last_active_at: datetime | None = None


class AdminMeResponse(BaseModel):
    """目的：封装 AdminMeResponse 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 user 字段，用于 AdminMeResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user 值。
    user: AdminUserPayload
    # 目的：保存 permissions 字段，用于 AdminMeResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 permissions 值。
    permissions: list[str] = Field(default_factory=list)


class AdminUsersResponse(BaseModel):
    """目的：封装 AdminUsersResponse 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 users 字段，用于 AdminUsersResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 users 值。
    users: list[AdminUserPayload] = Field(default_factory=list)


class AdminUpdateUserRequest(BaseModel):
    """目的：封装 AdminUpdateUserRequest 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 status 字段，用于 AdminUpdateUserRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Literal["active", "disabled"]


class AdminRolePayload(BaseModel):
    """目的：封装 AdminRolePayload 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 id 字段，用于 AdminRolePayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 code 字段，用于 AdminRolePayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 code 值。
    code: str
    # 目的：保存 name 字段，用于 AdminRolePayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name: str
    # 目的：保存 description 字段，用于 AdminRolePayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 description 值。
    description: str = ""
    # 目的：保存 permissions 字段，用于 AdminRolePayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 permissions 值。
    permissions: list[str] = Field(default_factory=list)
    # 目的：保存 is_system 字段，用于 AdminRolePayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 is_system 值。
    is_system: bool = False


class AdminRoleSaveRequest(BaseModel):
    """目的：封装 AdminRoleSaveRequest 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 code 字段，用于 AdminRoleSaveRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 code 值。
    code: str = Field(..., min_length=2, max_length=32)
    # 目的：保存 name 字段，用于 AdminRoleSaveRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name: str = Field(..., min_length=1, max_length=64)
    # 目的：保存 description 字段，用于 AdminRoleSaveRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 description 值。
    description: str = Field(default="", max_length=255)
    # 目的：保存 permissions 字段，用于 AdminRoleSaveRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 permissions 值。
    permissions: list[str] = Field(default_factory=list)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> str:
        """目的：执行 normalize_code 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        return str(value or "").strip().lower()


class AdminRolesResponse(BaseModel):
    """目的：封装 AdminRolesResponse 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 roles 字段，用于 AdminRolesResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 roles 值。
    roles: list[AdminRolePayload] = Field(default_factory=list)


class AdminPermissionPayload(BaseModel):
    """目的：封装 AdminPermissionPayload 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 id 字段，用于 AdminPermissionPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 code 字段，用于 AdminPermissionPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 code 值。
    code: str
    # 目的：保存 name 字段，用于 AdminPermissionPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name: str
    # 目的：保存 description 字段，用于 AdminPermissionPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 description 值。
    description: str = ""
    # 目的：保存 module 字段，用于 AdminPermissionPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 module 值。
    module: str = ""


class AdminPermissionsResponse(BaseModel):
    """目的：封装 AdminPermissionsResponse 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 permissions 字段，用于 AdminPermissionsResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 permissions 值。
    permissions: list[AdminPermissionPayload] = Field(default_factory=list)


class KnowledgeDocumentPayload(BaseModel):
    """目的：封装 KnowledgeDocumentPayload 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 id 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 doc_id 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 doc_id 值。
    doc_id: str
    # 目的：保存 title 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: str
    # 目的：保存 filename 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 filename 值。
    filename: str
    # 目的：保存 category 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 category 值。
    category: str
    # 目的：保存 source 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source 值。
    source: str
    # 目的：保存 status 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Literal["pending", "indexing", "active", "failed", "deleted"]
    # 目的：保存 chunk_count 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 chunk_count 值。
    chunk_count: int = 0
    # 目的：保存 created_by 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_by 值。
    created_by: str
    # 目的：保存 last_job_id 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 last_job_id 值。
    last_job_id: str = ""
    # 目的：保存 error_message 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 error_message 值。
    error_message: str = ""
    # 目的：保存 created_at 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: datetime | None = None
    # 目的：保存 updated_at 字段，用于 KnowledgeDocumentPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: datetime | None = None


class KnowledgeDocumentsResponse(BaseModel):
    """目的：封装 KnowledgeDocumentsResponse 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 documents 字段，用于 KnowledgeDocumentsResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 documents 值。
    documents: list[KnowledgeDocumentPayload] = Field(default_factory=list)


class KnowledgeJobPayload(BaseModel):
    """目的：封装 KnowledgeJobPayload 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 id 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 job_type 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 job_type 值。
    job_type: str
    # 目的：保存 status 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Literal["pending", "running", "succeeded", "failed", "canceled"]
    # 目的：保存 document_id 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 document_id 值。
    document_id: str | None = None
    # 目的：保存 filename 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 filename 值。
    filename: str = ""
    # 目的：保存 progress 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 progress 值。
    progress: int = 0
    # 目的：保存 result_json 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 result_json 值。
    result_json: dict[str, Any] = Field(default_factory=dict)
    # 目的：保存 error_message 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 error_message 值。
    error_message: str = ""
    # 目的：保存 created_by 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_by 值。
    created_by: str
    # 目的：保存 started_at 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 started_at 值。
    started_at: datetime | None = None
    # 目的：保存 finished_at 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 finished_at 值。
    finished_at: datetime | None = None
    # 目的：保存 created_at 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: datetime | None = None
    # 目的：保存 updated_at 字段，用于 KnowledgeJobPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: datetime | None = None


class KnowledgeJobsResponse(BaseModel):
    """目的：封装 KnowledgeJobsResponse 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 jobs 字段，用于 KnowledgeJobsResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 jobs 值。
    jobs: list[KnowledgeJobPayload] = Field(default_factory=list)


class KnowledgeTextAdminRequest(BaseModel):
    """目的：封装 KnowledgeTextAdminRequest 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 title 字段，用于 KnowledgeTextAdminRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: str = Field(..., min_length=1, max_length=255)
    # 目的：保存 text 字段，用于 KnowledgeTextAdminRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 text 值。
    text: str = Field(..., min_length=1, max_length=100_000)
    # 目的：保存 category 字段，用于 KnowledgeTextAdminRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 category 值。
    category: str = Field(default="relationship_knowledge", max_length=64)
    # 目的：保存 source 字段，用于 KnowledgeTextAdminRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source 值。
    source: str = Field(default="admin:text", max_length=255)


class AuditEventPayload(BaseModel):
    """目的：封装 AuditEventPayload 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 id 字段，用于 AuditEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 tenant_id 字段，用于 AuditEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant_id 值。
    tenant_id: str
    # 目的：保存 actor_user_id 字段，用于 AuditEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 actor_user_id 值。
    actor_user_id: str
    # 目的：保存 action 字段，用于 AuditEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 action 值。
    action: str
    # 目的：保存 resource_type 字段，用于 AuditEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 resource_type 值。
    resource_type: str
    # 目的：保存 resource_id 字段，用于 AuditEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 resource_id 值。
    resource_id: str = ""
    # 目的：保存 ip 字段，用于 AuditEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 ip 值。
    ip: str = ""
    # 目的：保存 user_agent 字段，用于 AuditEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_agent 值。
    user_agent: str = ""
    # 目的：保存 detail_json 字段，用于 AuditEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 detail_json 值。
    detail_json: dict[str, Any] = Field(default_factory=dict)
    # 目的：保存 created_at 字段，用于 AuditEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: datetime | None = None


class AuditEventsResponse(BaseModel):
    """目的：封装 AuditEventsResponse 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 events 字段，用于 AuditEventsResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 events 值。
    events: list[AuditEventPayload] = Field(default_factory=list)


class SafetyEventPayload(BaseModel):
    """目的：封装 SafetyEventPayload 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 id 字段，用于 SafetyEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 user_id 字段，用于 SafetyEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: str
    # 目的：保存 conversation_id 字段，用于 SafetyEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_id 值。
    conversation_id: str | None = None
    # 目的：保存 scene 字段，用于 SafetyEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 scene 值。
    scene: str
    # 目的：保存 risk_type 字段，用于 SafetyEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 risk_type 值。
    risk_type: str
    # 目的：保存 risk_level 字段，用于 SafetyEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 risk_level 值。
    risk_level: str
    # 目的：保存 input_snapshot 字段，用于 SafetyEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 input_snapshot 值。
    input_snapshot: str
    # 目的：保存 action 字段，用于 SafetyEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 action 值。
    action: str
    # 目的：保存 created_at 字段，用于 SafetyEventPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: datetime | None = None


class SafetyEventsResponse(BaseModel):
    """目的：封装 SafetyEventsResponse 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 events 字段，用于 SafetyEventsResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 events 值。
    events: list[SafetyEventPayload] = Field(default_factory=list)


class AdminDashboardResponse(BaseModel):
    """目的：封装 AdminDashboardResponse 相关的数据结构、业务状态或协作能力。
    结果：调用方可以通过清晰边界复用该对象，提升代码可读性和维护性。
    """
    # 目的：保存 metrics 字段，用于 AdminDashboardResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 metrics 值。
    metrics: dict[str, int] = Field(default_factory=dict)
    # 目的：保存 recent_jobs 字段，用于 AdminDashboardResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 recent_jobs 值。
    recent_jobs: list[KnowledgeJobPayload] = Field(default_factory=list)
    # 目的：保存 recent_safety_events 字段，用于 AdminDashboardResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 recent_safety_events 值。
    recent_safety_events: list[SafetyEventPayload] = Field(default_factory=list)
