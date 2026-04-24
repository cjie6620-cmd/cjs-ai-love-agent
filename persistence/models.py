from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db_base import Base


def generate_uuid() -> str:
    """统一使用字符串主键，方便多端生成与后续分库分表扩展。
    
    目的：执行统一使用字符串主键，方便多端生成与后续分库分表扩展相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return str(uuid4())


class User(Base):
    """用户主表，保存账号、画像与最近活跃信息。

    目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    external_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    avatar_url: Mapped[str] = mapped_column(String(512), default="")
    profile_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    conversations: Mapped[list["ConversationSession"]] = relationship(back_populates="user")
    safety_events: Mapped[list["SafetyEvent"]] = relationship(back_populates="user")


class AgentProfile(Base):
    """智能体配置表，用于沉淀不同模式的人设和 Prompt 版本。

    目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    __tablename__ = "agent_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(32), index=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    system_prompt_version: Mapped[str] = mapped_column(String(32), default="v1")
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    conversations: Mapped[list["ConversationSession"]] = relationship(
        back_populates="agent_profile"
    )


class ConversationSession(Base):
    """会话表，只保留会话级元数据，正文消息单独拆表。
    
    目的：定义会话表，只保留会话级元数据，正文消息单独拆表对应的持久化字段结构。
    结果：ORM 在建表、读写和序列化时保持一致。
    """

    __tablename__ = "conversation_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    agent_profile_id: Mapped[str | None] = mapped_column(ForeignKey("agent_profiles.id"))
    title: Mapped[str] = mapped_column(String(128), default="新对话")
    mode: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[str] = mapped_column(String(500), default="")
    memory_digest: Mapped[dict] = mapped_column(JSON, default=dict)
    message_count: Mapped[int] = mapped_column(BigInteger, default=0)
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
    agent_profile: Mapped["AgentProfile | None"] = relationship(back_populates="conversations")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )
    safety_events: Mapped[list["SafetyEvent"]] = relationship(back_populates="conversation")


class ConversationMessage(Base):
    """消息明细表，保存用户与智能体逐条消息及命中信息。
    
    目的：定义消息明细表，保存用户与智能体逐条消息及命中信息对应的持久化字段结构。
    结果：ORM 在建表、读写和序列化时保持一致。
    """

    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversation_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), index=True)
    content: Mapped[str] = mapped_column(Text)
    trace_json: Mapped[dict] = mapped_column(JSON, default=dict)
    safety_tags: Mapped[dict] = mapped_column(JSON, default=dict)
    token_count: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["ConversationSession"] = relationship(back_populates="messages")


class SafetyEvent(Base):
    """风控事件表，用于审计输入输出命中规则和处理结果。
    
    目的：定义风控事件表，用于审计输入输出命中规则和处理结果对应的持久化字段结构。
    结果：ORM 在建表、读写和序列化时保持一致。
    """

    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_sessions.id"), index=True
    )
    scene: Mapped[str] = mapped_column(String(32), index=True)
    risk_type: Mapped[str] = mapped_column(String(64), index=True)
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    input_snapshot: Mapped[str] = mapped_column(Text, default="")
    output_snapshot: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(String(32), default="pass")
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="safety_events")
    conversation: Mapped["ConversationSession | None"] = relationship(
        back_populates="safety_events"
    )
