"""长期记忆事件 Outbox 仓储。

目的：实现 RocketMQ 可靠投递的本地补偿存储。
结果：生产者发送失败可落库，后台补投成功后可更新状态。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .db_base import get_session_factory
from .models import MemoryEventOutbox


class MemoryOutboxRepository:
    """目的：封装长期记忆事件的待投递、重试、成功和消费状态更新。
    结果：MQ 生产者、补偿任务和消费者共享一致的可靠投递状态。
    """

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        """目的：注入或创建数据库 session factory，方便生产和测试复用。
        结果：实例可以通过独立 session 执行 Outbox 状态读写。
        """
        self.session_factory = session_factory or get_session_factory()

    def save_pending(self, payload: dict[str, Any], *, error: str = "") -> str:
        """目的：在 MQ 投递失败时持久化事件，并对相同 event_id 做幂等更新。
        结果：返回 Outbox 记录 ID，已发送事件不会被重新置为待投递。
        """
        event_id = str(payload["event_id"])
        with self.session_factory() as session:
            existing = session.scalar(
                select(MemoryEventOutbox).where(MemoryEventOutbox.event_id == event_id)
            )
            if existing is not None:
                if existing.status == "sent":
                    return existing.id
                existing.status = "pending"
                existing.last_error = error[:2000]
                existing.next_retry_at = datetime.now(UTC)
                session.commit()
                return existing.id

            record = MemoryEventOutbox(
                event_id=event_id,
                task_id=str(payload["task_id"]),
                user_id=str(payload["user_id"]),
                session_id=str(payload.get("session_id") or ""),
                payload=payload,
                status="pending",
                retry_count=0,
                next_retry_at=datetime.now(UTC),
                last_error=error[:2000],
            )
            session.add(record)
            session.commit()
            return record.id

    def list_due(self, *, limit: int = 50) -> list[MemoryEventOutbox]:
        """目的：筛选 pending / retrying 且达到重试时间的 Outbox 记录。
        结果：按创建时间返回最多 limit 条待补偿事件。
        """
        now = datetime.now(UTC)
        with self.session_factory() as session:
            rows = session.scalars(
                select(MemoryEventOutbox)
                .where(MemoryEventOutbox.status.in_(["pending", "retrying"]))
                .where(MemoryEventOutbox.next_retry_at <= now)
                .order_by(MemoryEventOutbox.created_at.asc())
                .limit(limit)
            ).all()
            return list(rows)

    def mark_sent(self, event_id: str) -> None:
        """目的：在 MQ 补投成功后清除错误信息并结束投递重试。
        结果：对应 event_id 的记录状态变为 sent。
        """
        with self.session_factory() as session:
            record = session.scalar(
                select(MemoryEventOutbox).where(MemoryEventOutbox.event_id == event_id)
            )
            if record is None:
                return
            record.status = "sent"
            record.last_error = ""
            session.commit()

    def mark_retry(self, event_id: str, *, error: str, max_retries: int = 10) -> None:
        """目的：保存失败原因并按指数退避安排下一轮补偿。
        结果：未超限记录变为 retrying，超限记录变为 failed。
        """
        with self.session_factory() as session:
            record = session.scalar(
                select(MemoryEventOutbox).where(MemoryEventOutbox.event_id == event_id)
            )
            if record is None:
                return
            record.retry_count += 1
            record.last_error = error[:2000]
            if record.retry_count >= max_retries:
                record.status = "failed"
                record.next_retry_at = None
            else:
                delay_seconds = min(300, 2 ** min(record.retry_count, 8))
                record.status = "retrying"
                record.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
            session.commit()

    def has_processed_task(self, task_id: str) -> bool:
        """目的：在消费者处理前按 task_id 做幂等拦截。
        结果：返回 True 表示该任务已处理过，可直接 ACK。
        """
        with self.session_factory() as session:
            return (
                session.scalar(
                    select(MemoryEventOutbox.id)
                    .where(MemoryEventOutbox.task_id == task_id)
                    .where(MemoryEventOutbox.status == "processed")
                    .limit(1)
                )
                is not None
            )

    def mark_processed(self, task_id: str) -> None:
        """目的：在消费者成功处理后更新同 task_id 的所有 Outbox 记录。
        结果：相关记录状态变为 processed，并清空错误信息。
        """
        with self.session_factory() as session:
            rows = session.scalars(
                select(MemoryEventOutbox).where(MemoryEventOutbox.task_id == task_id)
            ).all()
            for row in rows:
                row.status = "processed"
                row.last_error = ""
            session.commit()

    def mark_invalid(self, task_id: str, *, error: str) -> None:
        """目的：记录无法解析或校验失败的消息，避免 RocketMQ 与 Outbox 无限重试。
        结果：相关记录状态变为 invalid_payload，并保存错误摘要。
        """
        with self.session_factory() as session:
            rows = session.scalars(
                select(MemoryEventOutbox).where(MemoryEventOutbox.task_id == task_id)
            ).all()
            for row in rows:
                row.status = "invalid_payload"
                row.last_error = error[:2000]
            session.commit()
