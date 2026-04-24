"""长期记忆 RocketMQ 适配器。

目的：隔离 rocketmq-client-python 具体 API，让业务代码只关注“投递长期记忆事件”。
结果：生产者、补偿任务和测试都可以通过统一接口协作。
"""

from __future__ import annotations

import logging
from typing import Any

from agents.memory_events import MemoryExtractionMessage
from core.config import get_settings

logger = logging.getLogger(__name__)


class RocketMqUnavailableError(RuntimeError):
    """RocketMQ 不可用或投递失败。"""


class MemoryRocketMqProducer:
    """长期记忆事件 RocketMQ 生产者。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._producer: Any | None = None

    def send(self, event: MemoryExtractionMessage) -> None:
        """同步投递消息并等待 broker ack；失败抛出异常交给 Outbox。"""
        try:
            producer = self._get_producer()
            message = self._build_message(event)
            result = producer.send_sync(message)
            logger.info(
                "RocketMQ 记忆事件投递成功: event_id=%s task_id=%s result=%s",
                event.event_id,
                event.task_id,
                result,
            )
        except Exception as exc:  # pragma: no cover - SDK 细节由集成环境覆盖
            raise RocketMqUnavailableError(str(exc)) from exc

    def shutdown(self) -> None:
        """关闭底层 producer。"""
        if self._producer is not None and hasattr(self._producer, "shutdown"):
            self._producer.shutdown()
        self._producer = None

    def _get_producer(self) -> Any:
        if self._producer is not None:
            return self._producer
        try:
            from rocketmq.client import Producer
        except Exception as exc:  # pragma: no cover - 本地未安装 SDK 时只走测试 mock
            raise RocketMqUnavailableError("未安装 rocketmq-client-python") from exc

        producer = Producer(self.settings.rocketmq_producer_group)
        producer.set_name_server_address(self.settings.rocketmq_namesrv_addr)
        producer.start()
        self._producer = producer
        return producer

    def _build_message(self, event: MemoryExtractionMessage) -> Any:
        try:
            from rocketmq.client import Message
        except Exception as exc:  # pragma: no cover
            raise RocketMqUnavailableError("未安装 rocketmq-client-python") from exc

        message = Message(self.settings.rocketmq_memory_topic)
        message.set_tags(self.settings.rocketmq_memory_tag)
        message.set_keys(event.task_id)
        message.set_body(event.to_json_bytes())
        return message
