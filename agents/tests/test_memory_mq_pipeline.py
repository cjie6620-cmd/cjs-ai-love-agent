from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from agents.memory_consumer import MemoryEventConsumerService
from agents.memory_events import build_memory_extraction_message
from agents.memory_outbox_relay import MemoryOutboxRelay
from agents.memory_policy import MemoryPolicyService
from contracts.chat import MemoryDecision, MemoryDecisionBatch


def _memory_settings(enabled: bool = True) -> Mock:
    settings = Mock()
    settings.is_enabled.return_value = enabled
    return settings


def test_consumer_ack_duplicate_task() -> None:
    outbox = Mock()
    outbox.has_processed_task.return_value = True
    memory = Mock()
    event = build_memory_extraction_message(
        user_id="user-001",
        session_id="sess-001",
        user_message="我叫小明",
        assistant_reply="好的，我记住你的称呼",
    )
    service = MemoryEventConsumerService(
        memory_manager=memory,
        outbox_repository=outbox,
        memory_settings_repository=_memory_settings(),
    )

    assert service.consume_body(event.to_json_bytes()) is True
    memory.decide_memory.assert_not_called()


def test_consumer_retry_on_temporary_failure() -> None:
    outbox = Mock()
    outbox.has_processed_task.return_value = False
    memory = Mock()
    memory.decide_memory = AsyncMock(side_effect=RuntimeError("deepseek timeout"))
    event = build_memory_extraction_message(
        user_id="user-001",
        user_message="我喜欢被温柔提醒",
        assistant_reply="我会尽量温柔一点",
    )
    service = MemoryEventConsumerService(
        memory_manager=memory,
        outbox_repository=outbox,
        memory_settings_repository=_memory_settings(),
    )

    assert service.consume_body(event.to_json_bytes()) is False


def test_consumer_ack_invalid_payload() -> None:
    service = MemoryEventConsumerService(memory_manager=Mock(), outbox_repository=Mock())

    assert service.consume_body(b'{"bad":true}') is True


def test_consumer_save_memory_with_task_metadata() -> None:
    outbox = Mock()
    outbox.has_processed_task.return_value = False
    memory = Mock()
    memory.decide_memory = AsyncMock(
        return_value=MemoryDecisionBatch(
            items=[
                MemoryDecision(
                    should_store=True,
                    memory_type="preference",
                    memory_text="用户喜欢被温柔提醒",
                    canonical_key="preference:communication_style",
                    importance_score=0.9,
                    confidence=0.95,
                    merge_strategy="replace",
                    reason_code="stable_preference",
                )
            ]
        )
    )
    memory.deduplicate_decisions = Mock(
        return_value=[
            MemoryDecision(
                should_store=True,
                memory_type="preference",
                memory_text="用户喜欢被温柔提醒",
                canonical_key="preference:communication_style",
                importance_score=0.9,
                confidence=0.95,
                merge_strategy="replace",
                reason_code="stable_preference",
            )
        ]
    )
    memory.save_memory = AsyncMock(return_value="mem-001")
    event = build_memory_extraction_message(
        user_id="user-001",
        session_id="sess-001",
        user_message="我喜欢被温柔提醒",
        assistant_reply="我会尽量温柔一点",
    )

    service = MemoryEventConsumerService(
        memory_manager=memory,
        outbox_repository=outbox,
        memory_settings_repository=_memory_settings(),
    )

    assert service.consume_body(event.to_json_bytes()) is True
    memory.save_memory.assert_awaited_once()
    kwargs = memory.save_memory.await_args.kwargs
    assert kwargs["event_id"] == event.event_id
    assert kwargs["task_id"] == event.task_id
    outbox.mark_processed.assert_called_once_with(event.task_id)


def test_consumer_deduplicates_same_canonical_key_within_batch() -> None:
    outbox = Mock()
    outbox.has_processed_task.return_value = False
    memory = Mock()
    memory.decide_memory = AsyncMock(
        return_value=MemoryDecisionBatch(
            items=[
                MemoryDecision(
                    should_store=True,
                    memory_type="preference",
                    memory_text="用户不喜欢吃辣",
                    canonical_key="preference:food_spicy",
                    importance_score=0.7,
                    confidence=0.8,
                    merge_strategy="replace",
                    reason_code="stable_preference",
                ),
                MemoryDecision(
                    should_store=True,
                    memory_type="preference",
                    memory_text="用户明确表示不喜欢吃辣",
                    canonical_key="preference:food_spicy",
                    importance_score=0.9,
                    confidence=0.95,
                    merge_strategy="replace",
                    reason_code="explicit_preference",
                ),
            ]
        )
    )
    memory.deduplicate_decisions = Mock(
        return_value=[
            MemoryDecision(
                should_store=True,
                memory_type="preference",
                memory_text="用户明确表示不喜欢吃辣",
                canonical_key="preference:food_spicy",
                importance_score=0.9,
                confidence=0.95,
                merge_strategy="replace",
                reason_code="explicit_preference",
            )
        ]
    )
    memory.save_memory = AsyncMock(return_value="mem-001")
    event = build_memory_extraction_message(
        user_id="user-001",
        user_message="我不喜欢吃辣，也别给我推荐辣的",
        assistant_reply="好的，我记住你不喜欢吃辣",
    )
    service = MemoryEventConsumerService(
        memory_manager=memory,
        outbox_repository=outbox,
        memory_settings_repository=_memory_settings(),
    )

    assert service.consume_body(event.to_json_bytes()) is True
    memory.save_memory.assert_awaited_once()


def test_consumer_saves_multiple_memory_items_from_single_turn() -> None:
    outbox = Mock()
    outbox.has_processed_task.return_value = False
    memory = Mock()
    decisions = [
        MemoryDecision(
            should_store=True,
            memory_type="profile_summary",
            memory_text="用户的名字是小陈",
            canonical_key="profile:name",
            importance_score=0.95,
            confidence=0.98,
            merge_strategy="replace",
            reason_code="explicit_identity",
        ),
        MemoryDecision(
            should_store=True,
            memory_type="preference",
            memory_text="用户不喜欢吃辣",
            canonical_key="preference:food_spicy",
            importance_score=0.9,
            confidence=0.96,
            merge_strategy="replace",
            reason_code="stable_preference",
        ),
    ]
    memory.decide_memory = AsyncMock(return_value=MemoryDecisionBatch(items=decisions))
    memory.deduplicate_decisions = Mock(return_value=decisions)
    memory.save_memory = AsyncMock(side_effect=["mem-001", "mem-002"])
    event = build_memory_extraction_message(
        user_id="user-001",
        session_id="sess-001",
        user_message="我叫小陈，不喜欢吃辣",
        assistant_reply="记住了，小陈，之后我会按不辣来理解你的饮食偏好",
    )
    service = MemoryEventConsumerService(
        memory_manager=memory,
        outbox_repository=outbox,
        memory_settings_repository=_memory_settings(),
    )

    assert service.consume_body(event.to_json_bytes()) is True
    assert memory.save_memory.await_count == 2


def test_consumer_skips_when_batch_is_empty() -> None:
    outbox = Mock()
    outbox.has_processed_task.return_value = False
    memory = Mock()
    memory.decide_memory = AsyncMock(return_value=MemoryDecisionBatch(items=[]))
    memory.deduplicate_decisions = Mock(return_value=[])
    event = build_memory_extraction_message(
        user_id="user-001",
        user_message="今天有点累，想随便聊聊",
        assistant_reply="可以，我们慢慢聊，不用急着整理清楚",
    )
    service = MemoryEventConsumerService(
        memory_manager=memory,
        outbox_repository=outbox,
        memory_settings_repository=_memory_settings(),
    )

    assert service.consume_body(event.to_json_bytes()) is True
    memory.save_memory.assert_not_called()


def test_consumer_skips_when_memory_is_disabled() -> None:
    outbox = Mock()
    outbox.has_processed_task.return_value = False
    memory = Mock()
    memory.decide_memory = AsyncMock(return_value=MemoryDecisionBatch(items=[]))
    event = build_memory_extraction_message(
        user_id="user-001",
        user_message="我喜欢简洁一点",
        assistant_reply="好的，我会简洁回复",
    )
    service = MemoryEventConsumerService(
        memory_manager=memory,
        outbox_repository=outbox,
        memory_settings_repository=_memory_settings(enabled=False),
    )

    assert service.consume_body(event.to_json_bytes()) is True
    memory.decide_memory.assert_not_called()
    outbox.mark_processed.assert_called_once_with(event.task_id)


def test_consumer_skips_sensitive_memory_text_after_decision() -> None:
    outbox = Mock()
    outbox.has_processed_task.return_value = False
    audit = Mock()
    memory = Mock()
    decisions = [
        MemoryDecision(
            should_store=True,
            memory_type="profile_summary",
            memory_text="用户手机号是13800138000",
            canonical_key="profile:phone",
            importance_score=0.95,
            confidence=0.98,
            merge_strategy="replace",
            reason_code="explicit_identity",
        )
    ]
    memory.decide_memory = AsyncMock(return_value=MemoryDecisionBatch(items=decisions))
    memory.deduplicate_decisions = Mock(return_value=decisions)
    memory.save_memory = AsyncMock(return_value="mem-001")
    event = build_memory_extraction_message(
        user_id="user-001",
        user_message="我手机号是13800138000",
        assistant_reply="好的",
    )
    service = MemoryEventConsumerService(
        memory_manager=memory,
        outbox_repository=outbox,
        memory_settings_repository=_memory_settings(),
        memory_policy_service=MemoryPolicyService(),
        memory_audit_repository=audit,
    )

    assert service.consume_body(event.to_json_bytes()) is True
    memory.save_memory.assert_not_called()
    audit.record.assert_called_once()


def test_outbox_relay_marks_sent_after_success() -> None:
    event = build_memory_extraction_message(
        user_id="user-001",
        user_message="我叫小明",
        assistant_reply="好的，小明",
    )
    row = Mock(event_id=event.event_id, task_id=event.task_id, payload=event.to_payload(), retry_count=0)
    repository = Mock()
    repository.list_due.return_value = [row]
    producer = Mock()

    stats = MemoryOutboxRelay(repository=repository, producer=producer).run_once()

    assert stats == {"total": 1, "sent": 1, "failed": 0}
    producer.send.assert_called_once()
    repository.mark_sent.assert_called_once_with(event.event_id)
    producer.shutdown.assert_called_once()


def test_outbox_relay_shutdowns_producer_after_failure() -> None:
    event = build_memory_extraction_message(
        user_id="user-001",
        user_message="我叫小明",
        assistant_reply="好的，小明",
    )
    row = Mock(event_id=event.event_id, task_id=event.task_id, payload=event.to_payload(), retry_count=0)
    repository = Mock()
    repository.list_due.return_value = [row]
    producer = Mock()
    producer.send.side_effect = RuntimeError("broker timeout")

    stats = MemoryOutboxRelay(repository=repository, producer=producer).run_once()

    assert stats == {"total": 1, "sent": 0, "failed": 1}
    repository.mark_retry.assert_called_once()
    producer.shutdown.assert_called_once()
