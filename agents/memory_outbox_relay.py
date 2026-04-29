"""长期记忆 Outbox 补投任务。

目的：扫描本地 Outbox 中待补偿投递的长期记忆事件。
结果：RocketMQ 临时失败后的消息可以被重新投递并更新状态。
"""

from __future__ import annotations

import logging

from messaging import MemoryRocketMqProducer
from persistence import MemoryOutboxRepository

from .memory_events import MemoryExtractionMessage

logger = logging.getLogger(__name__)


class MemoryOutboxRelay:
    """目的：把待补投事件从数据库重新发送到 RocketMQ。
    结果：成功消息被标记为 sent，失败消息记录重试信息。
    """

    def __init__(
        self,
        *,
        repository: MemoryOutboxRepository | None = None,
        producer: MemoryRocketMqProducer | None = None,
    ) -> None:
        """目的：装配 Outbox 仓储和 RocketMQ 生产者，支持测试替身注入。
        结果：实例具备读取待投递事件和发送消息的能力。
        """
        self.repository = repository or MemoryOutboxRepository()
        self.producer = producer or MemoryRocketMqProducer()

    def run_once(self, *, limit: int = 50) -> dict[str, int]:
        """目的：按批次读取到期事件并逐条补投到 RocketMQ。
        结果：返回 total、sent、failed 统计，并关闭生产者连接。
        """
        try:
            rows = self.repository.list_due(limit=limit)
            stats = {"total": len(rows), "sent": 0, "failed": 0}
            for row in rows:
                try:
                    event = MemoryExtractionMessage.model_validate(row.payload)
                    self.producer.send(event)
                    self.repository.mark_sent(event.event_id)
                    stats["sent"] += 1
                except Exception as exc:
                    self.repository.mark_retry(row.event_id, error=str(exc))
                    stats["failed"] += 1
                    logger.warning(
                        "长期记忆 Outbox 补投失败: event_id=%s task_id=%s retry_count=%s error=%s",
                        row.event_id,
                        row.task_id,
                        row.retry_count + 1,
                        exc,
                    )
            return stats
        finally:
            self.producer.shutdown()


def run_once() -> dict[str, int]:
    """目的：为定时任务或手工命令提供一轮 Outbox 补投能力。
    结果：返回本轮补投统计。
    """
    return MemoryOutboxRelay().run_once()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run_once())
