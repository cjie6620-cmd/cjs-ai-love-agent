"""RocketMQ 长期记忆消费者。

目的：消费聊天结束事件，用 DeepSeek 结构化抽取长期记忆并治理落库。
结果：聊天链路与记忆提取解耦，消费失败可交给 RocketMQ 重试和 DLQ。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from pydantic import ValidationError

from core.config import get_settings
from messaging.memory_mq import _format_rocketmq_import_error
from persistence import MemoryAuditRepository, MemoryOutboxRepository, MemorySettingsRepository

from .memory import MemoryManager
from .memory_events import MemoryExtractionMessage
from .memory_policy import MemoryPolicyService

logger = logging.getLogger(__name__)


class MemoryEventConsumerService:
    """目的：封装 RocketMQ 消息解析、幂等判断和长期记忆治理写入流程。
    结果：调用方只需提交消息体即可获得 ACK / 重试决策。
    """

    def __init__(
        self,
        *,
        memory_manager: MemoryManager | None = None,
        outbox_repository: MemoryOutboxRepository | None = None,
        memory_settings_repository: MemorySettingsRepository | None = None,
        memory_policy_service: MemoryPolicyService | None = None,
        memory_audit_repository: MemoryAuditRepository | None = None,
    ) -> None:
        """目的：装配长期记忆管理器和 Outbox 仓储，支持测试替身注入。
        结果：实例具备消费、判重和落库所需的协作对象。
        """
        self.memory_manager = memory_manager or MemoryManager()
        self.outbox_repository = outbox_repository or MemoryOutboxRepository()
        self.memory_settings_repository = memory_settings_repository or MemorySettingsRepository()
        self.memory_policy_service = memory_policy_service or MemoryPolicyService()
        self.memory_audit_repository = memory_audit_repository or MemoryAuditRepository()

    def consume_body(self, body: bytes | str | dict[str, Any]) -> bool:
        """目的：解析 MQ 消息并完成长期记忆抽取、保存和消费状态更新。
        结果：返回 True 表示 ACK，返回 False 表示交给 RocketMQ 重试。
        """
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
        """目的：调用模型判断本轮对话是否值得沉淀为长期记忆，并执行治理写入。
        结果：返回 saved 或 skipped 状态，供消费日志和幂等状态使用。
        """
        if not self.memory_settings_repository.is_enabled(event.user_id):
            return {"status": "skipped", "reason_code": "memory_disabled", "saved_count": 0, "skipped_count": 0, "record_ids": []}

        batch = await self.memory_manager.decide_memory(
            user_message=event.user_message,
            assistant_reply=event.assistant_reply,
        )
        decisions = self.memory_manager.deduplicate_decisions(batch.items)
        if not decisions:
            return {"status": "skipped", "saved_count": 0, "skipped_count": 0, "record_ids": []}

        saved_count = 0
        skipped_count = 0
        record_ids: list[str] = []
        for decision in decisions:
            policy_result = self.memory_policy_service.evaluate_decision(decision)
            if not policy_result.allowed:
                skipped_count += 1
                self.memory_audit_repository.record(
                    action="memory.decision_skipped",
                    user_id=event.user_id,
                    resource_id=event.session_id,
                    detail_json={
                        "event_id": event.event_id,
                        "task_id": event.task_id,
                        "canonical_key": decision.canonical_key,
                        "reason_code": policy_result.reason_code,
                        "matched_types": list(policy_result.matched_types),
                    },
                )
                continue
            record_id = await self.memory_manager.save_memory(
                event.user_id,
                decision,
                session_id=event.session_id,
                event_id=event.event_id,
                task_id=event.task_id,
                trace_id=event.trace_id,
            )
            if record_id:
                saved_count += 1
                record_ids.append(record_id)
            else:
                skipped_count += 1
        return {
            "status": "saved" if saved_count > 0 else "skipped",
            "saved_count": saved_count,
            "skipped_count": skipped_count,
            "record_ids": record_ids,
        }

    def _parse_event(self, body: bytes | str | dict[str, Any]) -> MemoryExtractionMessage:
        """目的：兼容 bytes、字符串和字典三种输入，并统一交给 Pydantic 校验。
        结果：返回结构化的 MemoryExtractionMessage，非法输入抛出异常。
        """
        if isinstance(body, bytes):
            payload = json.loads(body.decode("utf-8"))
        elif isinstance(body, str):
            payload = json.loads(body)
        else:
            payload = body
        return MemoryExtractionMessage.model_validate(payload)


def start_memory_consumer() -> None:
    """目的：注册长期记忆 topic 回调并保持消费者进程常驻。
    结果：聊天结束后的记忆提取任务可以被后台消费处理。
    """
    settings = get_settings()
    service = MemoryEventConsumerService()

    try:
        from rocketmq.client import ConsumeStatus, PushConsumer
    except Exception as exc:  # pragma: no cover - 依赖安装问题由运行环境暴露
        raise RuntimeError(f"{_format_rocketmq_import_error(exc)}，无法启动长期记忆消费者") from exc

    consumer = PushConsumer(settings.rocketmq_memory_consumer_group)
    consumer.set_name_server_address(settings.rocketmq_namesrv_addr)

    def _callback(message: Any) -> Any:
        """目的：把 SDK 消息对象转为业务消息体，并映射消费结果到 RocketMQ 状态。
        结果：返回 CONSUME_SUCCESS 或 RECONSUME_LATER。
        """
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
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Memory RocketMQ consumer received shutdown signal")
    finally:
        consumer.shutdown()


if __name__ == "__main__":
    start_memory_consumer()
