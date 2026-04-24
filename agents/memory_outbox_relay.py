"""长期记忆 Outbox 补投任务。"""

from __future__ import annotations

import logging

from messaging import MemoryRocketMqProducer
from persistence import MemoryOutboxRepository

from .memory_events import MemoryExtractionMessage

logger = logging.getLogger(__name__)


class MemoryOutboxRelay:
    """扫描 Outbox 并补投 RocketMQ。"""

    def __init__(
        self,
        *,
        repository: MemoryOutboxRepository | None = None,
        producer: MemoryRocketMqProducer | None = None,
    ) -> None:
        self.repository = repository or MemoryOutboxRepository()
        self.producer = producer or MemoryRocketMqProducer()

    def run_once(self, *, limit: int = 50) -> dict[str, int]:
        """执行一轮补偿投递。"""
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


def run_once() -> dict[str, int]:
    """命令行入口：执行一轮 Outbox 补投。"""
    return MemoryOutboxRelay().run_once()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run_once())
