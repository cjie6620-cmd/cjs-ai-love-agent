"""长期记忆授权设置仓储。"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .db_base import get_session_factory
from .models import UserMemorySetting

logger = logging.getLogger(__name__)


class MemorySettingsRepository:
    """目的：集中管理用户长期记忆开关。
    结果：主聊天链路、消费者和 API 可以共用同一套授权判断。
    """

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self.session_factory = session_factory or get_session_factory()

    def is_enabled(self, user_id: str) -> bool:
        """目的：判断用户是否授权长期记忆。
        结果：没有设置记录时按默认关闭处理。
        """
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id or normalized_user_id.startswith("guest:"):
            return False
        try:
            with self.session_factory() as session:
                record = session.scalar(
                    select(UserMemorySetting).where(UserMemorySetting.user_id == normalized_user_id)
                )
                return bool(record and record.memory_enabled)
        except Exception as exc:
            logger.debug("读取长期记忆开关失败，按关闭处理: user_id=%s error=%s", normalized_user_id, exc)
            return False

    def get_settings(self, user_id: str) -> dict[str, bool]:
        """目的：读取长期记忆设置并补默认值。
        结果：返回前端可直接消费的开关状态。
        """
        return {"memory_enabled": self.is_enabled(user_id)}

    def set_enabled(self, user_id: str, enabled: bool) -> dict[str, bool]:
        """目的：创建或更新用户长期记忆授权开关。
        结果：返回更新后的设置状态。
        """
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id or normalized_user_id.startswith("guest:"):
            return {"memory_enabled": False}
        with self.session_factory() as session:
            record = session.scalar(
                select(UserMemorySetting).where(UserMemorySetting.user_id == normalized_user_id)
            )
            if record is None:
                record = UserMemorySetting(
                    user_id=normalized_user_id,
                    memory_enabled=enabled,
                )
                session.add(record)
            else:
                record.memory_enabled = enabled
            session.commit()
        return {"memory_enabled": enabled}
