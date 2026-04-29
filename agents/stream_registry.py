"""流任务注册表。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from contracts.chat import CancelStreamResponse, StreamTaskStatus

ACTIVE_STREAM_STATUSES = {"running", "cancelling"}


class StreamTaskConflictError(Exception):
    """同一会话存在进行中流任务时抛出。"""

    def __init__(self, *, stream_id: str, status: str) -> None:
        self.stream_id = stream_id
        self.status = status
        super().__init__(f"stream already active: {stream_id} ({status})")


@dataclass(slots=True)
class StreamTaskRecord:
    """单个流任务的运行时状态。"""

    stream_id: str
    user_id: str
    session_id: str
    status: StreamTaskStatus = "running"
    task: asyncio.Task[None] | None = None
    subscribers: set[asyncio.Queue[str | None]] = field(default_factory=set)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    error_message: str = ""


@dataclass(slots=True)
class ActiveStreamSnapshot:
    """会话活动流的只读快照。"""

    stream_id: str
    status: str


class StreamTaskRegistry:
    """管理进程内流任务与订阅者。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._streams: dict[str, StreamTaskRecord] = {}
        self._active_by_session: dict[tuple[str, str], str] = {}

    async def create(
        self,
        *,
        stream_id: str,
        user_id: str,
        session_id: str,
        subscriber: asyncio.Queue[str | None] | None = None,
    ) -> StreamTaskRecord:
        """注册新的流任务。"""
        async with self._lock:
            active_key = (user_id, session_id)
            existing_id = self._active_by_session.get(active_key)
            if existing_id is not None:
                existing = self._streams.get(existing_id)
                if existing is not None and existing.status in ACTIVE_STREAM_STATUSES:
                    raise StreamTaskConflictError(
                        stream_id=existing.stream_id,
                        status=existing.status,
                    )

            record = StreamTaskRecord(
                stream_id=stream_id,
                user_id=user_id,
                session_id=session_id,
            )
            if subscriber is not None:
                record.subscribers.add(subscriber)
            self._streams[stream_id] = record
            self._active_by_session[active_key] = stream_id
            return record

    async def add_subscriber(self, stream_id: str, subscriber: asyncio.Queue[str | None]) -> bool:
        """为指定流任务追加订阅者。"""
        async with self._lock:
            record = self._streams.get(stream_id)
            if record is None:
                return False
            record.subscribers.add(subscriber)
            return True

    async def remove_subscriber(self, stream_id: str, subscriber: asyncio.Queue[str | None]) -> None:
        """移除指定订阅者。"""
        async with self._lock:
            record = self._streams.get(stream_id)
            if record is not None:
                record.subscribers.discard(subscriber)

    async def publish(self, stream_id: str, chunk: str) -> None:
        """向当前在线订阅者广播 SSE 数据。"""
        subscribers = await self._snapshot_subscribers(stream_id)
        for subscriber in subscribers:
            await subscriber.put(chunk)

    async def close_subscribers(self, stream_id: str) -> None:
        """向订阅者发送结束哨兵，让本地 SSE 迭代器自然收尾。"""
        subscribers = await self._snapshot_subscribers(stream_id)
        for subscriber in subscribers:
            await subscriber.put(None)

    async def cancel_for_user(self, stream_id: str, user_id: str) -> CancelStreamResponse:
        """按用户身份取消指定流任务。"""
        task_to_cancel: asyncio.Task[None] | None = None
        async with self._lock:
            record = self._streams.get(stream_id)
            if record is None or record.user_id != user_id:
                return CancelStreamResponse(stream_id=stream_id, status="not_found", accepted=False)

            if record.status == "running":
                record.status = "cancelling"
                task_to_cancel = record.task
                response = CancelStreamResponse(stream_id=stream_id, status="cancelling", accepted=True)
            elif record.status == "cancelling":
                response = CancelStreamResponse(stream_id=stream_id, status="cancelling", accepted=False)
            elif record.status == "cancelled":
                response = CancelStreamResponse(stream_id=stream_id, status="cancelled", accepted=False)
            else:
                response = CancelStreamResponse(stream_id=stream_id, status="completed", accepted=False)

        if task_to_cancel is not None:
            task_to_cancel.cancel()
        return response

    async def mark_terminal(
        self,
        stream_id: str,
        status: StreamTaskStatus,
        *,
        error_message: str = "",
    ) -> None:
        """更新任务为终态，并解除会话占用。"""
        async with self._lock:
            record = self._streams.get(stream_id)
            if record is None:
                return
            record.status = status
            record.finished_at = datetime.now(UTC)
            record.error_message = error_message
            active_key = (record.user_id, record.session_id)
            if self._active_by_session.get(active_key) == stream_id:
                self._active_by_session.pop(active_key, None)

    async def list_active_for_user(self, user_id: str) -> dict[str, ActiveStreamSnapshot]:
        """返回当前用户所有活跃会话的流任务状态。"""
        async with self._lock:
            result: dict[str, ActiveStreamSnapshot] = {}
            for record in self._streams.values():
                if record.user_id != user_id or record.status not in ACTIVE_STREAM_STATUSES:
                    continue
                result[record.session_id] = ActiveStreamSnapshot(
                    stream_id=record.stream_id,
                    status=record.status,
                )
            return result

    async def _snapshot_subscribers(self, stream_id: str) -> list[asyncio.Queue[str | None]]:
        async with self._lock:
            record = self._streams.get(stream_id)
            if record is None:
                return []
            return list(record.subscribers)
