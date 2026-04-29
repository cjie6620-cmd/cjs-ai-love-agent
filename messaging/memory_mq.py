"""长期记忆 RocketMQ 适配器。

目的：隔离 rocketmq-client-python 具体 API，让业务代码只关注“投递长期记忆事件”。
结果：生产者、补偿任务和测试都可以通过统一接口协作。
"""

from __future__ import annotations

import logging
import platform
from typing import Any

from agents.memory_events import MemoryExtractionMessage
from core.config import get_settings

logger = logging.getLogger(__name__)


class RocketMqUnavailableError(RuntimeError):
    """目的：把 MQ SDK 导入、连接和发送异常统一包装成业务异常。
    结果：上层 Outbox 可以用同一种异常语义触发补偿。
    """


def _format_rocketmq_import_error(exc: Exception) -> str:
    """目的：把不同运行环境下的 SDK 缺失或动态库缺失问题转换为明确提示。
    结果：返回可写入日志和异常的中文错误说明。
    """
    message = str(exc)
    if isinstance(exc, NotImplementedError) and platform.system().lower() == "windows":
        return "rocketmq-client-python 不支持 Windows，请在 Linux/WSL/Docker 中运行 MQ 生产者/消费者"
    if "rocketmq dynamic library not found" in message:
        return "已安装 rocketmq-client-python，但缺少 RocketMQ C++ 动态库 librocketmq.so"
    return "未安装 rocketmq-client-python"



class MemoryRocketMqProducer:
    """目的：封装 rocketmq-client-python 的 Producer 生命周期和消息构造。
    结果：业务层可以通过 send 投递 MemoryExtractionMessage。
    """

    def __init__(self) -> None:
        """目的：读取 MQ 配置并延迟创建底层 Producer。
        结果：实例可在首次发送时再连接 RocketMQ。
        """
        self.settings = get_settings()
        self._producer: Any | None = None

    def send(self, event: MemoryExtractionMessage) -> None:
        """目的：构造 RocketMQ 消息并等待 broker ack，保证投递结果可感知。
        结果：成功写日志，失败抛出 RocketMqUnavailableError 交给 Outbox。
        """
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
        """目的：释放 RocketMQ SDK 持有的连接和线程资源。
        结果：本地 producer 引用被清空，后续发送可重新初始化。
        """
        if self._producer is not None and hasattr(self._producer, "shutdown"):
            self._producer.shutdown()
        self._producer = None

    def _get_producer(self) -> Any:
        """目的：延迟导入 SDK 并按配置启动 Producer，降低本地测试依赖。
        结果：返回已启动的 Producer 实例。
        """
        if self._producer is not None:
            return self._producer
        try:
            from rocketmq.client import Producer
        except Exception as exc:  # pragma: no cover - 本地未安装 SDK 时只走测试 mock
            raise RocketMqUnavailableError(_format_rocketmq_import_error(exc)) from exc

        producer = Producer(self.settings.rocketmq_producer_group)
        producer.set_name_server_address(self.settings.rocketmq_namesrv_addr)
        producer.start()
        self._producer = producer
        return producer

    def _build_message(self, event: MemoryExtractionMessage) -> Any:
        """目的：把长期记忆事件映射为 topic、tag、key 和 body 完整的 MQ 消息。
        结果：返回可直接 send_sync 的 Message 实例。
        """
        try:
            from rocketmq.client import Message
        except Exception as exc:  # pragma: no cover
            raise RocketMqUnavailableError(_format_rocketmq_import_error(exc)) from exc

        message = Message(self.settings.rocketmq_memory_topic)
        message.set_tags(self.settings.rocketmq_memory_tag)
        message.set_keys(event.task_id)
        message.set_body(event.to_json_bytes())
        return message
