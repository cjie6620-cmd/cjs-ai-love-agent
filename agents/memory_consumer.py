"""RocketMQ 长期记忆消费者。

目的：消费聊天结束事件，用 DeepSeek 结构化抽取长期记忆并治理落库。
结果：聊天链路与记忆提取解耦，消费失败可交给 RocketMQ 重试和 DLQ。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic import ValidationError

from core.config import get_settings
from persistence import MemoryOutboxRepository

from .memory import MemoryManager
from .memory_events import MemoryExtractionMessage

logger = logging.getLogger(__name__)


class MemoryEventConsumerService:
    """长期记忆事件消费服务。"""

    def __init__(
        self,
        *,
        memory_manager: MemoryManager | None = None,
        outbox_repository: MemoryOutboxRepository | None = None,
    ) -> None:
        self.memory_manager = memory_manager or MemoryManager()
        self.outbox_repository = outbox_repository or MemoryOutboxRepository()

    def consume_body(self, body: bytes | str | dict[str, Any]) -> bool:
        """消费单条消息；True 表示 ACK，False 表示让 RocketMQ 重试。"""
        try:
            event = self._parse_event(body)
        except ValidationError as exc:
            logger.warning("长期记忆消息非法，直接 ACK: error=%s", exc)
            return True
        except Exception as exc:
            logger.warning("长期记忆消息解析失败，直接 ACK: error=%s", exc)
            return True

        if self.outbox_repository.has_processed_task(event.task_id):
            logger.info("长期记忆消息重复消费，直接 ACK: task_id=%s", event.task_id)
            return True

        try:
            result = asyncio.run(self._handle_event(event))
            self.outbox_repository.mark_processed(event.task_id)
            logger.info(
                "长期记忆消息消费完成: event_id=%s task_id=%s status=%s record_id=%s",
                event.event_id,
                event.task_id,
                result.get("status"),
                result.get("record_id", ""),
            )
            return True
        except Exception as exc:
            logger.exception(
                "长期记忆消息消费失败，交给 RocketMQ 重试: event_id=%s task_id=%s error=%s",
                event.event_id,
                event.task_id,
                exc,
            )
            return False

    async def _handle_event(self, event: MemoryExtractionMessage) -> dict[str, object]:
        decision = await self.memory_manager.decide_memory(
            user_message=event.user_message,
            assistant_reply=event.assistant_reply,
        )
        if not decision.should_store or not decision.memory_text:
            return {"status": "skipped", "reason": decision.reason_code}

        record_id = await self.memory_manager.save_memory(
            event.user_id,
            decision,
            session_id=event.session_id,
            event_id=event.event_id,
            task_id=event.task_id,
            trace_id=event.trace_id,
        )
        return {
            "status": "saved" if record_id else "skipped",
            "record_id": record_id,
            "reason": decision.reason_code,
        }

    def _parse_event(self, body: bytes | str | dict[str, Any]) -> MemoryExtractionMessage:
        if isinstance(body, bytes):
            payload = json.loads(body.decode("utf-8"))
        elif isinstance(body, str):
            payload = json.loads(body)
        else:
            payload = body
        return MemoryExtractionMessage.model_validate(payload)


def start_memory_consumer() -> None:
    """启动 RocketMQ PushConsumer。"""
    settings = get_settings()
    service = MemoryEventConsumerService()

    try:
        from rocketmq.client import ConsumeStatus, PushConsumer
    except Exception as exc:  # pragma: no cover - 依赖安装问题由运行环境暴露
        raise RuntimeError("未安装 rocketmq-client-python，无法启动长期记忆消费者") from exc

    consumer = PushConsumer(settings.rocketmq_memory_consumer_group)
    consumer.set_name_server_address(settings.rocketmq_namesrv_addr)

    def _callback(message: Any) -> Any:
        body = message.body if hasattr(message, "body") else message.get_body()
        ok = service.consume_body(body)
        return ConsumeStatus.CONSUME_SUCCESS if ok else ConsumeStatus.RECONSUME_LATER

    consumer.subscribe(settings.rocketmq_memory_topic, _callback, settings.rocketmq_memory_tag)
    consumer.start()
    logger.info(
        "长期记忆 RocketMQ Consumer 已启动: topic=%s group=%s namesrv=%s",
        settings.rocketmq_memory_topic,
        settings.rocketmq_memory_consumer_group,
        settings.rocketmq_namesrv_addr,
    )
    try:
        while True:
            input("按 Enter 退出长期记忆消费者...\n")
            break
    finally:
        consumer.shutdown()


if __name__ == "__main__":
    start_memory_consumer()
