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
    """目的：描述一次“从一轮对话中抽取长期记忆”的异步任务。
    结果：消息可被 RocketMQ 投递、Outbox 补偿和消费者幂等处理。
    """

    # 目的：保存 event_id 字段，用于 MemoryExtractionMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 event_id 值。
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    # 目的：保存 task_id 字段，用于 MemoryExtractionMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 task_id 值。
    task_id: str
    # 目的：保存 user_id 字段，用于 MemoryExtractionMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: str
    # 目的：保存 session_id 字段，用于 MemoryExtractionMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 session_id 值。
    session_id: str | None = None
    # 目的：保存 user_message 字段，用于 MemoryExtractionMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_message 值。
    user_message: str
    # 目的：保存 assistant_reply 字段，用于 MemoryExtractionMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 assistant_reply 值。
    assistant_reply: str
    # 目的：保存 created_at 字段，用于 MemoryExtractionMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 created_at 值。
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    # 目的：保存 trace_id 字段，用于 MemoryExtractionMessage 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 trace_id 值。
    trace_id: str = ""

    @field_validator("user_id", "user_message", "assistant_reply", mode="before")
    @classmethod
    def _required_text(cls, value: object) -> str:
        """目的：统一清洗用户 ID、用户消息和助手回复，阻止空文本进入记忆链路。
        结果：返回去空格后的字符串，空值抛出校验异常。
        """
        text = str(value or "").strip()
        if not text:
            raise ValueError("字段不能为空")
        return text

    @field_validator("session_id", "trace_id", mode="before")
    @classmethod
    def _optional_text(cls, value: object) -> str | None:
        """目的：兼容 None 与字符串输入，避免空白字符污染幂等和追踪字段。
        结果：返回去空格后的字符串或 None。
        """
        if value is None:
            return None
        return str(value).strip()

    def to_payload(self) -> dict[str, Any]:
        """目的：把消息模型转换成可持久化、可投递的 JSON 字典。
        结果：返回 Pydantic JSON 模式下的字段字典。
        """
        return self.model_dump(mode="json")

    def to_json_bytes(self) -> bytes:
        """目的：按统一 JSON 格式序列化消息，避免 MQ 生产者重复处理编码细节。
        结果：返回 UTF-8 编码后的 bytes。
        """
        return json.dumps(self.to_payload(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def build_memory_extraction_message(
    *,
    user_id: str,
    user_message: str,
    assistant_reply: str,
    session_id: str | None = None,
    trace_id: str = "",
) -> MemoryExtractionMessage:
    """目的：根据一轮对话内容生成稳定 task_id，支撑 Outbox 和消费者幂等。
    结果：返回可投递到 RocketMQ 的 MemoryExtractionMessage。
    """
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
