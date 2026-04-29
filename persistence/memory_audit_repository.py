"""长期记忆治理审计仓储。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from .db_base import get_session_factory
from .models import AuditEvent

logger = logging.getLogger(__name__)


class MemoryAuditRepository:
    """目的：记录长期记忆授权、跳过、删除等治理动作。
    结果：后续可以在审计日志中追踪为什么保存或跳过某条记忆。
    """

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self.session_factory = session_factory or get_session_factory()

    def record(
        self,
        *,
        action: str,
        user_id: str,
        tenant_id: str = "default",
        resource_id: str = "",
        detail_json: dict[str, Any] | None = None,
        ip: str = "",
        user_agent: str = "",
    ) -> str | None:
        """目的：写入一条长期记忆治理审计事件。
        结果：成功返回审计 ID，失败只记录日志，不阻断主流程。
        """
        try:
            with self.session_factory() as session:
                event = AuditEvent(
                    tenant_id=tenant_id or "default",
                    actor_user_id=user_id,
                    action=action,
                    resource_type="long_term_memory",
                    resource_id=resource_id,
                    ip=ip[:64],
                    user_agent=user_agent[:255],
                    detail_json=detail_json or {},
                )
                session.add(event)
                session.commit()
                return event.id
        except Exception as exc:
            logger.debug("长期记忆审计写入失败，已忽略: action=%s user_id=%s error=%s", action, user_id, exc)
            return None
