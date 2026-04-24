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
    """长期记忆事件 Outbox 仓储。"""

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self.session_factory = session_factory or get_session_factory()

    def save_pending(self, payload: dict[str, Any], *, error: str = "") -> str:
        """保存待补投事件；相同 event_id 已存在时只更新错误信息。"""
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
        """读取到期需要补投的事件。"""
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
        """标记事件已成功投递。"""
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
        """记录补投失败并计算下一次重试时间。"""
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
        """判断 task_id 是否已投递成功，用于消费者幂等前置判断。"""
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
        """标记 task_id 已消费完成。"""
        with self.session_factory() as session:
            rows = session.scalars(
                select(MemoryEventOutbox).where(MemoryEventOutbox.task_id == task_id)
            ).all()
            for row in rows:
                row.status = "processed"
                row.last_error = ""
            session.commit()

    def mark_invalid(self, task_id: str, *, error: str) -> None:
        """标记非法消息，避免无限重试。"""
        with self.session_factory() as session:
            rows = session.scalars(
                select(MemoryEventOutbox).where(MemoryEventOutbox.task_id == task_id)
            ).all()
            for row in rows:
                row.status = "invalid_payload"
                row.last_error = error[:2000]
            session.commit()
