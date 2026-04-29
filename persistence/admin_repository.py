"""后台 RBAC、用户和审计仓储。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from core.config import Settings, get_settings

from .db_base import get_session_factory
from .models import (
    AuditEvent,
    AuthAccount,
    ConversationSession,
    KnowledgeDocument,
    KnowledgeJob,
    Permission,
    Role,
    RolePermission,
    SafetyEvent,
    Tenant,
    User,
    UserRole,
)

DEFAULT_PERMISSIONS: tuple[tuple[str, str, str, str], ...] = (
    ("admin:access", "进入后台", "允许访问管理员后台", "admin"),
    ("user:read", "查看用户", "查看用户列表与详情", "user"),
    ("user:write", "编辑用户", "编辑用户基础状态和资料", "user"),
    ("user:disable", "禁用用户", "禁用或启用用户账号", "user"),
    ("role:read", "查看角色", "查看角色和权限", "role"),
    ("role:write", "编辑角色", "创建和编辑角色权限", "role"),
    ("knowledge:read", "查看知识库", "查看和检索知识库", "knowledge"),
    ("knowledge:write", "写入知识库", "上传文件和录入文本知识", "knowledge"),
    ("knowledge:delete", "删除知识", "删除知识文档和索引", "knowledge"),
    ("knowledge:reindex", "重建知识", "触发单文档或全量重建", "knowledge"),
    ("knowledge:job:read", "查看知识任务", "查看知识索引任务", "knowledge"),
    ("knowledge:job:retry", "重试知识任务", "重试或取消知识索引任务", "knowledge"),
    ("audit:read", "查看审计", "查看后台操作审计日志", "audit"),
    ("safety:read", "查看安全事件", "查看风控与安全事件", "safety"),
    ("system:read", "查看系统状态", "查看系统健康与配置摘要", "system"),
    ("system:manage", "管理系统", "执行系统级管理动作", "system"),
)


class AdminRepository:
    """目的：后台管理仓储，集中封装 RBAC、用户列表和审计查询。
    结果：提供 AdminRepository 的结构化能力，供业务流程复用。
    """

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        """目的：执行 __init__ 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        self.session_factory = session_factory or get_session_factory()
        self.settings = settings or get_settings()

    def bootstrap_defaults(self) -> None:
        """目的：初始化默认租户、权限和系统角色。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            tenant = session.get(Tenant, self.settings.default_tenant_id)
            if tenant is None:
                tenant = Tenant(
                    id=self.settings.default_tenant_id,
                    code=self.settings.default_tenant_id,
                    name="Default Tenant",
                    status="active",
                )
                session.add(tenant)

            permissions_by_code: dict[str, Permission] = {}
            for code, name, description, module in DEFAULT_PERMISSIONS:
                permission = session.scalar(select(Permission).where(Permission.code == code))
                if permission is None:
                    permission = Permission(
                        code=code,
                        name=name,
                        description=description,
                        module=module,
                    )
                    session.add(permission)
                    session.flush()
                permissions_by_code[code] = permission

            user_role = self._get_or_create_role(
                session,
                tenant_id=tenant.id,
                code="user",
                name="普通用户",
                description="普通聊天用户，不可进入后台",
                is_system=True,
            )
            admin_role = self._get_or_create_role(
                session,
                tenant_id=tenant.id,
                code="admin",
                name="管理员",
                description="拥有后台全部权限",
                is_system=True,
            )
            self._sync_role_permissions(session, user_role, [])
            self._sync_role_permissions(session, admin_role, list(permissions_by_code.values()))
            session.commit()

    def sync_user_bootstrap(self, user_id: str, *, login_name: str = "") -> None:
        """目的：保证用户具备默认角色，并按配置提升管理员。
        结果：完成当前实例行为并返回约定结果。
        """
        normalized_login = login_name.strip().lower()
        with self.session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return
            self._ensure_default_user_fields(user)
            role_codes = ["user"]
            if normalized_login and normalized_login in self.settings.admin_login_name_set:
                role_codes.append("admin")
            for code in role_codes:
                role = self._get_or_create_role(
                    session,
                    tenant_id=user.tenant_id,
                    code=code,
                    name="管理员" if code == "admin" else "普通用户",
                    description="系统内置角色",
                    is_system=True,
                )
                self._ensure_user_role(session, user.id, role.id)
            session.commit()

    def get_user_authz(self, user_id: str) -> dict[str, Any] | None:
        """目的：返回用户、角色和权限集合。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        with self.session_factory() as session:
            user = session.get(User, user_id)
            if user is None or user.status != "active":
                return None
            account = session.scalar(select(AuthAccount).where(AuthAccount.user_id == user.id))
            roles = self._role_codes_for_user(session, user.id)
            permissions = self._permission_codes_for_user(session, user.id)
            return {
                "id": user.id,
                "tenant_id": user.tenant_id,
                "external_user_id": user.external_user_id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "status": user.status,
                "login_name": account.login_name if account is not None else user.external_user_id,
                "roles": roles,
                "permissions": permissions,
                "created_at": user.created_at,
                "last_active_at": user.last_active_at,
            }

    def list_users(self, tenant_id: str, *, keyword: str = "", status: str = "") -> list[dict[str, Any]]:
        """目的：后台用户列表。
        结果：返回符合条件的数据列表。
        """
        normalized = keyword.strip().lower()
        with self.session_factory() as session:
            statement = (
                select(User)
                .where(User.tenant_id == tenant_id)
                .order_by(User.created_at.desc())
                .limit(200)
            )
            if status:
                statement = statement.where(User.status == status)
            users = list(session.scalars(statement))
            results: list[dict[str, Any]] = []
            for user in users:
                account = session.scalar(select(AuthAccount).where(AuthAccount.user_id == user.id))
                login_name = account.login_name if account is not None else user.external_user_id
                if normalized and normalized not in login_name.lower() and normalized not in user.nickname.lower():
                    continue
                results.append(
                    {
                        "id": user.id,
                        "tenant_id": user.tenant_id,
                        "login_name": login_name,
                        "nickname": user.nickname,
                        "avatar_url": user.avatar_url,
                        "status": user.status,
                        "roles": self._role_codes_for_user(session, user.id),
                        "created_at": user.created_at,
                        "last_active_at": user.last_active_at,
                    }
                )
            return results

    def update_user_status(self, tenant_id: str, user_id: str, *, status: str) -> dict[str, Any] | None:
        """目的：更新用户状态。
        结果：更新业务资源并返回最新结果。
        """
        if status not in {"active", "disabled"}:
            raise ValueError("用户状态只能是 active 或 disabled")
        with self.session_factory() as session:
            user = session.get(User, user_id)
            if user is None or user.tenant_id != tenant_id:
                return None
            user.status = status
            session.commit()
        return self.get_user_authz(user_id)

    def list_roles(self, tenant_id: str) -> list[dict[str, Any]]:
        """目的：列出角色及权限。
        结果：返回符合条件的数据列表。
        """
        with self.session_factory() as session:
            roles = list(
                session.scalars(
                    select(Role)
                    .where(Role.tenant_id == tenant_id)
                    .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
                    .order_by(Role.is_system.desc(), Role.code.asc())
                )
            )
            return [
                {
                    "id": role.id,
                    "code": role.code,
                    "name": role.name,
                    "description": role.description,
                    "permissions": sorted(
                        item.permission.code
                        for item in role.role_permissions
                        if item.permission is not None
                    ),
                    "is_system": role.is_system,
                }
                for role in roles
            ]

    def list_permissions(self) -> list[dict[str, str]]:
        """目的：列出全部权限点。
        结果：返回符合条件的数据列表。
        """
        with self.session_factory() as session:
            permissions = list(session.scalars(select(Permission).order_by(Permission.module, Permission.code)))
            return [
                {
                    "id": permission.id,
                    "code": permission.code,
                    "name": permission.name,
                    "description": permission.description,
                    "module": permission.module,
                }
                for permission in permissions
            ]

    def create_or_update_role(
        self,
        tenant_id: str,
        *,
        role_id: str | None = None,
        code: str,
        name: str,
        description: str,
        permission_codes: list[str],
    ) -> dict[str, Any]:
        """目的：创建或更新租户角色。
        结果：创建业务资源并返回创建结果。
        """
        normalized_code = code.strip().lower()
        if not normalized_code:
            raise ValueError("角色编码不能为空")
        with self.session_factory() as session:
            role = session.get(Role, role_id) if role_id else None
            if role is None:
                role = session.scalar(
                    select(Role).where(Role.tenant_id == tenant_id).where(Role.code == normalized_code)
                )
            if role is None:
                role = Role(
                    tenant_id=tenant_id,
                    code=normalized_code,
                    name=name.strip() or normalized_code,
                    description=description.strip(),
                    is_system=False,
                )
                session.add(role)
                session.flush()
            elif role.is_system:
                role.name = name.strip() or role.name
                role.description = description.strip()
            else:
                role.code = normalized_code
                role.name = name.strip() or normalized_code
                role.description = description.strip()

            permissions = list(
                session.scalars(select(Permission).where(Permission.code.in_(permission_codes)))
            )
            self._sync_role_permissions(session, role, permissions)
            session.commit()
            return next(item for item in self.list_roles(tenant_id) if item["id"] == role.id)

    def assign_role(self, tenant_id: str, user_id: str, role_id: str) -> bool:
        """目的：给用户分配角色。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            user = session.get(User, user_id)
            role = session.get(Role, role_id)
            if user is None or role is None or user.tenant_id != tenant_id or role.tenant_id != tenant_id:
                return False
            self._ensure_user_role(session, user.id, role.id)
            session.commit()
            return True

    def remove_role(self, tenant_id: str, user_id: str, role_id: str) -> bool:
        """目的：移除用户角色。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            role = session.get(Role, role_id)
            if role is None or role.tenant_id != tenant_id:
                return False
            session.execute(delete(UserRole).where(UserRole.user_id == user_id).where(UserRole.role_id == role_id))
            session.commit()
            return True

    def list_audit_events(self, tenant_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """目的：查询审计日志。
        结果：返回符合条件的数据列表。
        """
        with self.session_factory() as session:
            events = list(
                session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.tenant_id == tenant_id)
                    .order_by(AuditEvent.created_at.desc())
                    .limit(limit)
                )
            )
            return [
                {
                    "id": event.id,
                    "tenant_id": event.tenant_id,
                    "actor_user_id": event.actor_user_id,
                    "action": event.action,
                    "resource_type": event.resource_type,
                    "resource_id": event.resource_id,
                    "ip": event.ip,
                    "user_agent": event.user_agent,
                    "detail_json": event.detail_json,
                    "created_at": event.created_at,
                }
                for event in events
            ]

    def list_safety_events(self, tenant_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """目的：查询安全事件。
        结果：返回符合条件的数据列表。
        """
        with self.session_factory() as session:
            statement = (
                select(SafetyEvent)
                .join(User, SafetyEvent.user_id == User.id)
                .where(User.tenant_id == tenant_id)
                .order_by(SafetyEvent.created_at.desc())
                .limit(limit)
            )
            events = list(session.scalars(statement))
            return [
                {
                    "id": event.id,
                    "user_id": event.user_id,
                    "conversation_id": event.conversation_id,
                    "scene": event.scene,
                    "risk_type": event.risk_type,
                    "risk_level": event.risk_level,
                    "input_snapshot": event.input_snapshot,
                    "action": event.action,
                    "created_at": event.created_at,
                }
                for event in events
            ]

    def dashboard_metrics(self, tenant_id: str) -> dict[str, int]:
        """目的：后台仪表盘基础统计。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            return {
                "users": int(session.scalar(select(func.count()).select_from(User).where(User.tenant_id == tenant_id)) or 0),
                "knowledge_documents": int(
                    session.scalar(
                        select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.tenant_id == tenant_id)
                    )
                    or 0
                ),
                "running_jobs": int(
                    session.scalar(
                        select(func.count())
                        .select_from(KnowledgeJob)
                        .where(KnowledgeJob.tenant_id == tenant_id)
                        .where(KnowledgeJob.status.in_(["pending", "running"]))
                    )
                    or 0
                ),
                "failed_jobs": int(
                    session.scalar(
                        select(func.count())
                        .select_from(KnowledgeJob)
                        .where(KnowledgeJob.tenant_id == tenant_id)
                        .where(KnowledgeJob.status == "failed")
                    )
                    or 0
                ),
                "conversations": int(
                    session.scalar(
                        select(func.count())
                        .select_from(ConversationSession)
                        .join(User, ConversationSession.user_id == User.id)
                        .where(User.tenant_id == tenant_id)
                    )
                    or 0
                ),
            }

    def record_audit(
        self,
        *,
        tenant_id: str,
        actor_user_id: str,
        action: str,
        resource_type: str,
        resource_id: str = "",
        ip: str = "",
        user_agent: str = "",
        detail_json: dict[str, Any] | None = None,
    ) -> str:
        """目的：写入审计事件。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            event = AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip=ip[:64],
                user_agent=user_agent[:255],
                detail_json=detail_json or {},
            )
            session.add(event)
            session.commit()
            return event.id

    def _get_or_create_role(
        self,
        session: Session,
        *,
        tenant_id: str,
        code: str,
        name: str,
        description: str,
        is_system: bool,
    ) -> Role:
        """目的：执行 _get_or_create_role 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        role = session.scalar(select(Role).where(Role.tenant_id == tenant_id).where(Role.code == code))
        if role is None:
            role = Role(
                tenant_id=tenant_id,
                code=code,
                name=name,
                description=description,
                is_system=is_system,
            )
            session.add(role)
            session.flush()
        return role

    def _sync_role_permissions(
        self,
        session: Session,
        role: Role,
        permissions: list[Permission],
    ) -> None:
        """目的：执行 _sync_role_permissions 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        for permission in permissions:
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))

    def _ensure_user_role(self, session: Session, user_id: str, role_id: str) -> None:
        """目的：执行 _ensure_user_role 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        existing = session.scalar(
            select(UserRole).where(UserRole.user_id == user_id).where(UserRole.role_id == role_id)
        )
        if existing is None:
            session.add(UserRole(user_id=user_id, role_id=role_id))

    def _ensure_default_user_fields(self, user: User) -> None:
        """目的：执行 _ensure_default_user_fields 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        if not user.tenant_id:
            user.tenant_id = self.settings.default_tenant_id
        if not user.status:
            user.status = "active"

    def _role_codes_for_user(self, session: Session, user_id: str) -> list[str]:
        """目的：执行 _role_codes_for_user 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        rows = session.execute(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.code)
        ).all()
        return [str(row[0]) for row in rows]

    def _permission_codes_for_user(self, session: Session, user_id: str) -> list[str]:
        """目的：执行 _permission_codes_for_user 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        rows = session.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Permission.code)
        ).all()
        return sorted({str(row[0]) for row in rows})
