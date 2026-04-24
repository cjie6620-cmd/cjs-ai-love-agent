"""安全事件仓储。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .db_base import get_session_factory
from .models import ConversationSession, SafetyEvent, User


class SafetyEventRepository:
    """负责持久化安全审计事件。

    目的：封装持久化读写逻辑，隔离数据库访问细节和查询实现。
    结果：业务层可以通过统一仓储接口完成数据操作，降低存储实现耦合。
    """

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        """初始化 SafetyEventRepository。
        
        目的：初始化SafetyEventRepository所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        self.session_factory = session_factory or get_session_factory()

    def create_event(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        scene: str,
        risk_type: str,
        risk_level: str,
        input_snapshot: str,
        action: str,
        detail_json: dict[str, object] | None = None,
    ) -> None:
        """写入一条安全审计事件。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        with self.session_factory() as session:
            user = self._get_or_create_user(session, user_id)
            resolved_conversation_id = self._resolve_conversation_id(
                session,
                user.id,
                conversation_id,
            )
            event = SafetyEvent(
                user_id=user.id,
                conversation_id=resolved_conversation_id,
                scene=scene,
                risk_type=risk_type,
                risk_level=risk_level,
                input_snapshot=input_snapshot[:500],
                action=action,
                detail_json=detail_json or {},
            )
            session.add(event)
            session.commit()

    def _get_or_create_user(self, session: Session, external_user_id: str) -> User:
        statement = select(User).where(User.external_user_id == external_user_id)
        user = session.scalar(statement)
        if user is not None:
            return user

        user = User(external_user_id=external_user_id, nickname=external_user_id)
        session.add(user)
        session.flush()
        return user

    def _resolve_conversation_id(
        self,
        session: Session,
        user_id: str,
        conversation_id: str | None,
    ) -> str | None:
        if not conversation_id:
            return None
        statement = select(ConversationSession.id).where(
            ConversationSession.id == conversation_id,
            ConversationSession.user_id == user_id,
        )
        return session.scalar(statement)
