from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from agents.memory_consumer import MemoryEventConsumerService
from agents.memory_events import build_memory_extraction_message
from agents.memory_outbox_relay import MemoryOutboxRelay
from contracts.chat import MemoryDecision


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
    service = MemoryEventConsumerService(memory_manager=memory, outbox_repository=outbox)

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
    service = MemoryEventConsumerService(memory_manager=memory, outbox_repository=outbox)

    assert service.consume_body(event.to_json_bytes()) is False


def test_consumer_ack_invalid_payload() -> None:
    service = MemoryEventConsumerService(memory_manager=Mock(), outbox_repository=Mock())

    assert service.consume_body(b'{"bad":true}') is True


def test_consumer_save_memory_with_task_metadata() -> None:
    outbox = Mock()
    outbox.has_processed_task.return_value = False
    memory = Mock()
    memory.decide_memory = AsyncMock(
        return_value=MemoryDecision(
            should_store=True,
            memory_type="preference",
            memory_text="用户喜欢被温柔提醒",
            canonical_key="preference:communication_style",
            importance_score=0.9,
            confidence=0.95,
            merge_strategy="replace",
            reason_code="stable_preference",
        )
    )
    memory.save_memory = AsyncMock(return_value="mem-001")
    event = build_memory_extraction_message(
        user_id="user-001",
        session_id="sess-001",
        user_message="我喜欢被温柔提醒",
        assistant_reply="我会尽量温柔一点",
    )

    service = MemoryEventConsumerService(memory_manager=memory, outbox_repository=outbox)

    assert service.consume_body(event.to_json_bytes()) is True
    memory.save_memory.assert_awaited_once()
    kwargs = memory.save_memory.await_args.kwargs
    assert kwargs["event_id"] == event.event_id
    assert kwargs["task_id"] == event.task_id
    outbox.mark_processed.assert_called_once_with(event.task_id)


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
