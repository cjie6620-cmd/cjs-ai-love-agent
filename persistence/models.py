from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db_base import Base


def generate_uuid() -> str:
    """目的：执行统一使用字符串主键，方便多端生成与后续分库分表扩展相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return str(uuid4())


class User(Base):
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    # 目的：保存 __tablename__ 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "users"

    # 目的：保存 id 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 tenant_id 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant_id 值。
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), default="default", index=True)
    # 目的：保存 external_user_id 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 external_user_id 值。
    external_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 目的：保存 nickname 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 nickname 值。
    nickname: Mapped[str] = mapped_column(String(64), default="")
    # 目的：保存 avatar_url 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 avatar_url 值。
    avatar_url: Mapped[str] = mapped_column(String(512), default="")
    # 目的：保存 status 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    # 目的：保存 profile_summary 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 profile_summary 值。
    profile_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    # 目的：保存 created_at 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 目的：保存 updated_at 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # 目的：保存 last_active_at 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 last_active_at 值。
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 目的：保存 conversations 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversations 值。
    conversations: Mapped[list["ConversationSession"]] = relationship(back_populates="user")
    # 目的：保存 safety_events 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 safety_events 值。
    safety_events: Mapped[list["SafetyEvent"]] = relationship(back_populates="user")
    # 目的：保存 tenant 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant 值。
    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    # 目的：保存 user_roles 字段，用于 User 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_roles 值。
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Tenant(Base):
    """目的：企业租户表，是用户、角色、知识库和审计数据的隔离边界。
    结果：提供 Tenant 的结构化能力，供业务流程复用。
    """

    # 目的：保存 __tablename__ 字段，用于 Tenant 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "tenants"

    # 目的：保存 id 字段，用于 Tenant 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # 目的：保存 name 字段，用于 Tenant 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name: Mapped[str] = mapped_column(String(64))
    # 目的：保存 code 字段，用于 Tenant 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 code 值。
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 目的：保存 status 字段，用于 Tenant 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    # 目的：保存 created_at 字段，用于 Tenant 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 目的：保存 updated_at 字段，用于 Tenant 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 目的：保存 users 字段，用于 Tenant 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 users 值。
    users: Mapped[list[User]] = relationship(back_populates="tenant")


class Permission(Base):
    """目的：权限点表，按 code 驱动后端依赖和前端按钮可见性。
    结果：提供 Permission 的结构化能力，供业务流程复用。
    """

    # 目的：保存 __tablename__ 字段，用于 Permission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "permissions"

    # 目的：保存 id 字段，用于 Permission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 code 字段，用于 Permission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 code 值。
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 目的：保存 name 字段，用于 Permission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name: Mapped[str] = mapped_column(String(64))
    # 目的：保存 description 字段，用于 Permission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 description 值。
    description: Mapped[str] = mapped_column(String(255), default="")
    # 目的：保存 module 字段，用于 Permission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 module 值。
    module: Mapped[str] = mapped_column(String(32), default="", index=True)


class Role(Base):
    """目的：租户内角色表。
    结果：提供 Role 的结构化能力，供业务流程复用。
    """

    # 目的：保存 __tablename__ 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "roles"
    # 目的：保存 __table_args__ 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __table_args__ 值。
    __table_args__ = (
        Index("idx_roles_tenant_code", "tenant_id", "code", unique=True),
    )

    # 目的：保存 id 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 tenant_id 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant_id 值。
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    # 目的：保存 code 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 code 值。
    code: Mapped[str] = mapped_column(String(32), index=True)
    # 目的：保存 name 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name: Mapped[str] = mapped_column(String(64))
    # 目的：保存 description 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 description 值。
    description: Mapped[str] = mapped_column(String(255), default="")
    # 目的：保存 is_system 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 is_system 值。
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    # 目的：保存 created_at 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 目的：保存 user_roles 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_roles 值。
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    # 目的：保存 role_permissions 字段，用于 Role 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 role_permissions 值。
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )


class UserRole(Base):
    """目的：用户与角色关系表。
    结果：提供 UserRole 的结构化能力，供业务流程复用。
    """

    # 目的：保存 __tablename__ 字段，用于 UserRole 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "user_roles"
    # 目的：保存 __table_args__ 字段，用于 UserRole 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __table_args__ 值。
    __table_args__ = (
        Index("idx_user_roles_user_role", "user_id", "role_id", unique=True),
    )

    # 目的：保存 id 字段，用于 UserRole 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 user_id 字段，用于 UserRole 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # 目的：保存 role_id 字段，用于 UserRole 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 role_id 值。
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), index=True)

    # 目的：保存 user 字段，用于 UserRole 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user 值。
    user: Mapped[User] = relationship(back_populates="user_roles")
    # 目的：保存 role 字段，用于 UserRole 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 role 值。
    role: Mapped[Role] = relationship(back_populates="user_roles")


class UserMemorySetting(Base):
    """目的：保存用户长期记忆授权开关。
    结果：长期记忆写入和召回可以按用户授权做统一拦截。
    """

    __tablename__ = "user_memory_settings"
    __table_args__ = (
        Index("idx_user_memory_settings_user", "user_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    memory_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class RolePermission(Base):
    """目的：角色与权限关系表。
    结果：提供 RolePermission 的结构化能力，供业务流程复用。
    """

    # 目的：保存 __tablename__ 字段，用于 RolePermission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "role_permissions"
    # 目的：保存 __table_args__ 字段，用于 RolePermission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __table_args__ 值。
    __table_args__ = (
        Index("idx_role_permissions_role_permission", "role_id", "permission_id", unique=True),
    )

    # 目的：保存 id 字段，用于 RolePermission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 role_id 字段，用于 RolePermission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 role_id 值。
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), index=True)
    # 目的：保存 permission_id 字段，用于 RolePermission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 permission_id 值。
    permission_id: Mapped[str] = mapped_column(ForeignKey("permissions.id"), index=True)

    # 目的：保存 role 字段，用于 RolePermission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 role 值。
    role: Mapped[Role] = relationship(back_populates="role_permissions")
    # 目的：保存 permission 字段，用于 RolePermission 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 permission 值。
    permission: Mapped[Permission] = relationship()


class AgentProfile(Base):
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    # 目的：保存 __tablename__ 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "agent_profiles"

    # 目的：保存 id 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 code 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 code 值。
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    # 目的：保存 display_name 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 display_name 值。
    display_name: Mapped[str] = mapped_column(String(64))
    # 目的：保存 mode 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mode 值。
    mode: Mapped[str] = mapped_column(String(32), index=True)
    # 目的：保存 description 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 description 值。
    description: Mapped[str] = mapped_column(String(255), default="")
    # 目的：保存 system_prompt_version 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 system_prompt_version 值。
    system_prompt_version: Mapped[str] = mapped_column(String(32), default="v1")
    # 目的：保存 settings_json 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 settings_json 值。
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # 目的：保存 is_enabled 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 is_enabled 值。
    is_enabled: Mapped[bool] = mapped_column(default=True)
    # 目的：保存 created_at 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 目的：保存 updated_at 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 目的：保存 conversations 字段，用于 AgentProfile 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversations 值。
    conversations: Mapped[list["ConversationSession"]] = relationship(
        back_populates="agent_profile"
    )


class ConversationSession(Base):
    """目的：定义会话表，只保留会话级元数据，正文消息单独拆表对应的持久化字段结构。
    结果：ORM 在建表、读写和序列化时保持一致。
    """

    # 目的：保存 __tablename__ 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "conversation_sessions"

    # 目的：保存 id 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 user_id 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # 目的：保存 agent_profile_id 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 agent_profile_id 值。
    agent_profile_id: Mapped[str | None] = mapped_column(ForeignKey("agent_profiles.id"))
    # 目的：保存 title 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: Mapped[str] = mapped_column(String(128), default="新对话")
    # 目的：保存 mode 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 mode 值。
    mode: Mapped[str] = mapped_column(String(32), index=True)
    # 目的：保存 summary 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 summary 值。
    summary: Mapped[str] = mapped_column(Text, default="")
    # 目的：保存 memory_digest 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 memory_digest 值。
    memory_digest: Mapped[dict] = mapped_column(JSON, default=dict)
    # 目的：保存 message_count 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 message_count 值。
    message_count: Mapped[int] = mapped_column(BigInteger, default=0)
    # 目的：保存 risk_level 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 risk_level 值。
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    # 目的：保存 created_at 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 目的：保存 updated_at 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 目的：保存 user 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user 值。
    user: Mapped["User"] = relationship(back_populates="conversations")
    # 目的：保存 agent_profile 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 agent_profile 值。
    agent_profile: Mapped["AgentProfile | None"] = relationship(back_populates="conversations")
    # 目的：保存 messages 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 messages 值。
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )
    # 目的：保存 safety_events 字段，用于 ConversationSession 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 safety_events 值。
    safety_events: Mapped[list["SafetyEvent"]] = relationship(back_populates="conversation")


class ConversationMessage(Base):
    """目的：定义消息明细表，保存用户与智能体逐条消息及命中信息对应的持久化字段结构。
    结果：ORM 在建表、读写和序列化时保持一致。
    """

    # 目的：保存 __tablename__ 字段，用于 ConversationMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "conversation_messages"

    # 目的：保存 id 字段，用于 ConversationMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 conversation_id 字段，用于 ConversationMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_id 值。
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversation_sessions.id"), index=True)
    # 目的：保存 role 字段，用于 ConversationMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 role 值。
    role: Mapped[str] = mapped_column(String(16), index=True)
    # 目的：保存 content 字段，用于 ConversationMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 content 值。
    content: Mapped[str] = mapped_column(Text)
    # 目的：保存 trace_json 字段，用于 ConversationMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 trace_json 值。
    trace_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # 目的：保存 safety_tags 字段，用于 ConversationMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 safety_tags 值。
    safety_tags: Mapped[dict] = mapped_column(JSON, default=dict)
    # 目的：保存 token_count 字段，用于 ConversationMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 token_count 值。
    token_count: Mapped[int] = mapped_column(BigInteger, default=0)
    # 目的：保存 created_at 字段，用于 ConversationMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 目的：保存 conversation 字段，用于 ConversationMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation 值。
    conversation: Mapped["ConversationSession"] = relationship(back_populates="messages")


class SafetyEvent(Base):
    """目的：定义风控事件表，用于审计输入输出命中规则和处理结果对应的持久化字段结构。
    结果：ORM 在建表、读写和序列化时保持一致。
    """

    # 目的：保存 __tablename__ 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "safety_events"

    # 目的：保存 id 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 user_id 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # 目的：保存 conversation_id 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation_id 值。
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_sessions.id"), index=True
    )
    # 目的：保存 scene 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 scene 值。
    scene: Mapped[str] = mapped_column(String(32), index=True)
    # 目的：保存 risk_type 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 risk_type 值。
    risk_type: Mapped[str] = mapped_column(String(64), index=True)
    # 目的：保存 risk_level 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 risk_level 值。
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    # 目的：保存 input_snapshot 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 input_snapshot 值。
    input_snapshot: Mapped[str] = mapped_column(Text, default="")
    # 目的：保存 output_snapshot 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 output_snapshot 值。
    output_snapshot: Mapped[str] = mapped_column(Text, default="")
    # 目的：保存 action 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 action 值。
    action: Mapped[str] = mapped_column(String(32), default="pass")
    # 目的：保存 detail_json 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 detail_json 值。
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # 目的：保存 created_at 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 目的：保存 user 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user 值。
    user: Mapped["User"] = relationship(back_populates="safety_events")
    # 目的：保存 conversation 字段，用于 SafetyEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 conversation 值。
    conversation: Mapped["ConversationSession | None"] = relationship(
        back_populates="safety_events"
    )


class AuthAccount(Base):
    """目的：登录账号表，把认证凭据和业务用户信息拆开管理。
    结果：提供 AuthAccount 的结构化能力，供业务流程复用。
    """

    # 目的：保存 __tablename__ 字段，用于 AuthAccount 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "auth_accounts"

    # 目的：保存 id 字段，用于 AuthAccount 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 user_id 字段，用于 AuthAccount 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # 目的：保存 login_name 字段，用于 AuthAccount 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 login_name 值。
    login_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # 目的：保存 password_hash 字段，用于 AuthAccount 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 password_hash 值。
    password_hash: Mapped[str] = mapped_column(String(255))
    # 目的：保存 status 字段，用于 AuthAccount 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    # 目的：保存 created_at 字段，用于 AuthAccount 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 目的：保存 updated_at 字段，用于 AuthAccount 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 目的：保存 user 字段，用于 AuthAccount 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user 值。
    user: Mapped["User"] = relationship()


class AuthRefreshToken(Base):
    """目的：刷新令牌表，只保存 token 哈希，支持退出和轮换。
    结果：提供 AuthRefreshToken 的结构化能力，供业务流程复用。
    """

    # 目的：保存 __tablename__ 字段，用于 AuthRefreshToken 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "auth_refresh_tokens"
    # 目的：保存 __table_args__ 字段，用于 AuthRefreshToken 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __table_args__ 值。
    __table_args__ = (
        Index("idx_auth_refresh_tokens_user_id_revoked", "user_id", "revoked"),
    )

    # 目的：保存 id 字段，用于 AuthRefreshToken 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 user_id 字段，用于 AuthRefreshToken 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # 目的：保存 token_hash 字段，用于 AuthRefreshToken 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 token_hash 值。
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # 目的：保存 user_agent 字段，用于 AuthRefreshToken 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_agent 值。
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    # 目的：保存 expires_at 字段，用于 AuthRefreshToken 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 expires_at 值。
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # 目的：保存 revoked 字段，用于 AuthRefreshToken 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 revoked 值。
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # 目的：保存 created_at 字段，用于 AuthRefreshToken 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 目的：保存 user 字段，用于 AuthRefreshToken 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user 值。
    user: Mapped["User"] = relationship()


class KnowledgeDocument(Base):
    """目的：知识库文档元数据表，索引明细存放在 pgvector/ES。
    结果：提供 KnowledgeDocument 的结构化能力，供业务流程复用。
    """

    # 目的：保存 __tablename__ 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "knowledge_documents"
    # 目的：保存 __table_args__ 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __table_args__ 值。
    __table_args__ = (
        Index("idx_knowledge_documents_tenant_status", "tenant_id", "status"),
        Index("idx_knowledge_documents_tenant_doc", "tenant_id", "doc_id", unique=True),
    )

    # 目的：保存 id 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 tenant_id 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant_id 值。
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    # 目的：保存 doc_id 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 doc_id 值。
    doc_id: Mapped[str] = mapped_column(String(64), index=True)
    # 目的：保存 title 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 title 值。
    title: Mapped[str] = mapped_column(String(255), default="")
    # 目的：保存 filename 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 filename 值。
    filename: Mapped[str] = mapped_column(String(255), default="")
    # 目的：保存 category 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 category 值。
    category: Mapped[str] = mapped_column(String(64), default="relationship_knowledge", index=True)
    # 目的：保存 source 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 source 值。
    source: Mapped[str] = mapped_column(String(255), default="")
    # 目的：保存 object_name 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 object_name 值。
    object_name: Mapped[str] = mapped_column(String(512), default="")
    # 目的：保存 content_text 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 content_text 值。
    content_text: Mapped[str] = mapped_column(Text, default="")
    # 目的：保存 status 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    # 目的：保存 chunk_count 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 chunk_count 值。
    chunk_count: Mapped[int] = mapped_column(BigInteger, default=0)
    # 目的：保存 created_by 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_by 值。
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # 目的：保存 last_job_id 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 last_job_id 值。
    last_job_id: Mapped[str] = mapped_column(String(36), default="", index=True)
    # 目的：保存 error_message 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 error_message 值。
    error_message: Mapped[str] = mapped_column(Text, default="")
    # 目的：保存 created_at 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 目的：保存 updated_at 字段，用于 KnowledgeDocument 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class KnowledgeJob(Base):
    """目的：知识库异步任务表。
    结果：提供 KnowledgeJob 的结构化能力，供业务流程复用。
    """

    # 目的：保存 __tablename__ 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "knowledge_jobs"
    # 目的：保存 __table_args__ 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __table_args__ 值。
    __table_args__ = (
        Index("idx_knowledge_jobs_tenant_status", "tenant_id", "status"),
        Index("idx_knowledge_jobs_document", "document_id"),
    )

    # 目的：保存 id 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 tenant_id 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant_id 值。
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    # 目的：保存 job_type 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 job_type 值。
    job_type: Mapped[str] = mapped_column(String(32), index=True)
    # 目的：保存 status 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    # 目的：保存 document_id 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 document_id 值。
    document_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_documents.id"), nullable=True)
    # 目的：保存 filename 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 filename 值。
    filename: Mapped[str] = mapped_column(String(255), default="")
    # 目的：保存 progress 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 progress 值。
    progress: Mapped[int] = mapped_column(BigInteger, default=0)
    # 目的：保存 result_json 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 result_json 值。
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # 目的：保存 error_message 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 error_message 值。
    error_message: Mapped[str] = mapped_column(Text, default="")
    # 目的：保存 created_by 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_by 值。
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # 目的：保存 started_at 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 started_at 值。
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 目的：保存 finished_at 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 finished_at 值。
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 目的：保存 created_at 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 目的：保存 updated_at 字段，用于 KnowledgeJob 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditEvent(Base):
    """目的：后台管理审计日志。
    结果：提供 AuditEvent 的结构化能力，供业务流程复用。
    """

    # 目的：保存 __tablename__ 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "audit_events"

    # 目的：保存 id 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 tenant_id 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant_id 值。
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    # 目的：保存 actor_user_id 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 actor_user_id 值。
    actor_user_id: Mapped[str] = mapped_column(String(36), default="", index=True)
    # 目的：保存 action 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 action 值。
    action: Mapped[str] = mapped_column(String(64), index=True)
    # 目的：保存 resource_type 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 resource_type 值。
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    # 目的：保存 resource_id 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 resource_id 值。
    resource_id: Mapped[str] = mapped_column(String(96), default="", index=True)
    # 目的：保存 ip 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 ip 值。
    ip: Mapped[str] = mapped_column(String(64), default="")
    # 目的：保存 user_agent 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_agent 值。
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    # 目的：保存 detail_json 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 detail_json 值。
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # 目的：保存 created_at 字段，用于 AuditEvent 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MemoryEventOutbox(Base):
    """目的：当 RocketMQ 暂时不可用时先保存待投递事件，避免长期记忆提取消息丢失。
    结果：后台补偿任务可以按状态和下次重试时间扫描并重新投递。
    """

    # 目的：保存 __tablename__ 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __tablename__ 值。
    __tablename__ = "memory_event_outbox"
    # 目的：保存 __table_args__ 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 __table_args__ 值。
    __table_args__ = (
        Index("idx_memory_event_outbox_status_next_retry", "status", "next_retry_at"),
        Index("idx_memory_event_outbox_task_id", "task_id"),
    )

    # 目的：保存 id 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # 目的：保存 event_id 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 event_id 值。
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    # 目的：保存 task_id 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 task_id 值。
    task_id: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    # 目的：保存 user_id 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 目的：保存 session_id 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 session_id 值。
    session_id: Mapped[str] = mapped_column(String(36), default="")
    # 目的：保存 payload 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 payload 值。
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    # 目的：保存 status 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    # 目的：保存 retry_count 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 retry_count 值。
    retry_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # 目的：保存 next_retry_at 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 next_retry_at 值。
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 目的：保存 last_error 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 last_error 值。
    last_error: Mapped[str] = mapped_column(Text, default="")
    # 目的：保存 created_at 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 目的：保存 updated_at 字段，用于 MemoryEventOutbox 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 updated_at 值。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
