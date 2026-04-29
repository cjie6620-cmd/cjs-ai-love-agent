"""持久化层统一出口：聚合数据库基座、模型与仓储实现。"""

from .conversation_repository import ConversationRepository
from .db_base import Base, get_engine, get_session_factory, reset_database_engine
from .models import (
    AgentProfile,
    AuditEvent,
    AuthAccount,
    AuthRefreshToken,
    ConversationMessage,
    ConversationSession,
    KnowledgeDocument,
    KnowledgeJob,
    MemoryEventOutbox,
    UserMemorySetting,
    Permission,
    Role,
    RolePermission,
    SafetyEvent,
    Tenant,
    User,
    UserRole,
)
from .admin_repository import AdminRepository
from .auth_repository import AuthRepository
from .knowledge_repository import KnowledgeRepository
from .memory_audit_repository import MemoryAuditRepository
from .memory_outbox_repository import MemoryOutboxRepository
from .memory_settings_repository import MemorySettingsRepository
from .safety_event_repository import SafetyEventRepository

__all__ = [
    "AdminRepository",
    "AgentProfile",
    "AuditEvent",
    "AuthAccount",
    "AuthRefreshToken",
    "AuthRepository",
    "Base",
    "ConversationMessage",
    "ConversationRepository",
    "ConversationSession",
    "KnowledgeDocument",
    "KnowledgeJob",
    "KnowledgeRepository",
    "MemoryEventOutbox",
    "MemoryAuditRepository",
    "MemoryOutboxRepository",
    "MemorySettingsRepository",
    "Permission",
    "Role",
    "RolePermission",
    "SafetyEvent",
    "SafetyEventRepository",
    "Tenant",
    "User",
    "UserMemorySetting",
    "UserRole",
    "get_engine",
    "get_session_factory",
    "reset_database_engine",
]
