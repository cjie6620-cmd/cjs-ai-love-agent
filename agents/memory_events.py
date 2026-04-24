"""长期记忆提取事件契约。

目的：把聊天主链路与后台长期记忆提取解耦，提供可幂等、可补偿的 MQ 消息体。
结果：生产者、Outbox 和消费者都使用同一份结构，避免字段漂移。
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class MemoryExtractionMessage(BaseModel):
    """长期记忆提取消息。

    目的：描述一次“从一轮对话中抽取长期记忆”的异步任务。
    结果：消息可被 RocketMQ 投递、Outbox 补偿和消费者幂等处理。
    """

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    user_id: str
    session_id: str | None = None
    user_message: str
    assistant_reply: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    trace_id: str = ""

    @field_validator("user_id", "user_message", "assistant_reply", mode="before")
    @classmethod
    def _required_text(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("字段不能为空")
        return text

    @field_validator("session_id", "trace_id", mode="before")
    @classmethod
    def _optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        return str(value).strip()

    def to_payload(self) -> dict[str, Any]:
        """返回稳定 JSON payload。"""
        return self.model_dump(mode="json")

    def to_json_bytes(self) -> bytes:
        """返回 RocketMQ 消息体。"""
        return json.dumps(self.to_payload(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def build_memory_extraction_message(
    *,
    user_id: str,
    user_message: str,
    assistant_reply: str,
    session_id: str | None = None,
    trace_id: str = "",
) -> MemoryExtractionMessage:
    """构建长期记忆提取消息，并生成稳定 task_id。"""
    normalized = {
        "user_id": str(user_id or "").strip(),
        "session_id": str(session_id or "").strip(),
        "user_message": str(user_message or "").strip(),
        "assistant_reply": str(assistant_reply or "").strip(),
    }
    digest = hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return MemoryExtractionMessage(
        task_id=f"memory:{digest}",
        user_id=normalized["user_id"],
        session_id=normalized["session_id"] or None,
        user_message=normalized["user_message"],
        assistant_reply=normalized["assistant_reply"],
        trace_id=trace_id,
    )
