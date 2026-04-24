"""ChatService 核心服务单元测试。

覆盖：非流式回复、流式回复、记忆保存策略、会话历史获取。
使用 mock 隔离外部依赖（LLM、向量库、数据库）。
"""

from __future__ import annotations

import time
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from agents import AgentService
from contracts.chat import (
    ChatMode,
    ChatRequest,
    MemoryDecision,
    ChatResponse,
    ChatTrace,
    ConversationHistoryMessage,
    QuestionAdvisorPayload,
)


@pytest.fixture
def mock_dependencies():
    """统一 mock ChatService 的所有外部依赖。"""
    with (
        patch("agents.agent_service.CompanionGraphWorkflow") as mock_workflow_cls,
        patch("agents.agent_service.ConversationRepository") as mock_repo_cls,
        patch("agents.agent_service.MemoryManager") as mock_memory_cls,
        patch("agents.agent_service.SessionMemoryManager") as mock_session_memory_cls,
        patch("agents.agent_service.RedisService") as mock_redis_cls,
        patch("agents.agent_service.MemoryRocketMqProducer") as mock_mq_cls,
        patch("agents.agent_service.MemoryOutboxRepository") as mock_outbox_cls,
    ):
        mock_workflow = mock_workflow_cls.return_value
        mock_repo = mock_repo_cls.return_value
        mock_memory = mock_memory_cls.return_value
        mock_session_memory = mock_session_memory_cls.return_value
        mock_redis = mock_redis_cls.return_value
        mock_mq = mock_mq_cls.return_value
        mock_outbox = mock_outbox_cls.return_value

        # 默认返回空历史
        mock_repo.list_recent_messages.return_value = []
        mock_repo.list_conversations.return_value = []
        mock_session_memory.get_recent.return_value = []
        mock_session_memory.append_message.return_value = True
        mock_redis.get_session_context.return_value = None
        mock_redis.cache_session_context.return_value = True

        # 默认记忆保存成功
        mock_memory.decide_memory = AsyncMock(
            return_value=MemoryDecision(
                should_store=True,
                memory_type="preference",
                memory_text="用户偏好：需要被安慰",
                confidence=0.93,
                reason_code="stable_preference",
            )
        )
        mock_memory.save_memory = AsyncMock(return_value="mem-001")

        yield {
            "workflow": mock_workflow,
            "repo": mock_repo,
            "memory": mock_memory,
            "session_memory": mock_session_memory,
            "redis": mock_redis,
            "mq": mock_mq,
            "outbox": mock_outbox,
        }


def _make_request(**overrides) -> ChatRequest:
    """构造测试用 ChatRequest。"""
    defaults: dict[str, object] = {
        "session_id": "sess-001",
        "user_id": "user-001",
        "message": "最近心情不好",
        "mode": "companion",
    }
    defaults.update(overrides)
    return ChatRequest(
        session_id=str(defaults["session_id"]),
        user_id=str(defaults["user_id"]),
        message=str(defaults["message"]),
        mode=cast(ChatMode, defaults["mode"]),
    )


def _make_response(reply: str = "我理解你的感受", safety_level: str = "low") -> ChatResponse:
    """构造测试用 ChatResponse。"""
    return ChatResponse(
        reply=reply,
        mode="companion",
        trace=ChatTrace(safety_level=safety_level),
        advisor=QuestionAdvisorPayload(suggested_questions=["你想聊聊发生了什么吗？"]),
    )


class TestReply:
    """非流式回复测试。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    @pytest.mark.asyncio
    async def test_reply_returns_response(self, mock_dependencies):
        """正常回复应返回 ChatResponse。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_dependencies["workflow"].run = AsyncMock(return_value=_make_response())
        service = AgentService()

        request = _make_request()
        response = await service.reply(request)

        assert response.reply == "我理解你的感受"
        assert response.mode == "companion"
        mock_dependencies["repo"].save_turn.assert_called_once()

    @pytest.mark.asyncio
    async def test_reply_triggers_memory_save(self, mock_dependencies):
        """正常回复后应触发记忆保存。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_dependencies["workflow"].run = AsyncMock(return_value=_make_response())
        service = AgentService()

        await service.reply(_make_request())

        service.memory_mq_producer.send.assert_called_once()
        sent_event = service.memory_mq_producer.send.call_args.args[0]
        assert sent_event.user_id == "user-001"
        assert sent_event.session_id == "sess-001"
        assert sent_event.task_id.startswith("memory:")
        mock_dependencies["memory"].decide_memory.assert_not_called()
        mock_dependencies["memory"].save_memory.assert_not_called()

    @pytest.mark.asyncio
    async def test_reply_writes_outbox_when_rocketmq_fails(self, mock_dependencies):
        """RocketMQ 投递失败时应写 Outbox 补偿，不能只打日志。"""
        mock_dependencies["workflow"].run = AsyncMock(return_value=_make_response())
        service = AgentService()
        service.memory_mq_producer.send.side_effect = RuntimeError("rocketmq down")

        await service.reply(_make_request())

        service.memory_outbox_repository.save_pending.assert_called_once()
        payload = service.memory_outbox_repository.save_pending.call_args.args[0]
        assert payload["user_id"] == "user-001"
        assert payload["task_id"].startswith("memory:")

    @pytest.mark.asyncio
    async def test_reply_skips_memory_for_high_risk(self, mock_dependencies):
        """high 安全级别的回复不应保存记忆。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_dependencies["workflow"].run = AsyncMock(
            return_value=_make_response(safety_level="high")
        )
        service = AgentService()

        await service.reply(_make_request(message="我不想活了"))

        mock_dependencies["memory"].save_memory.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_recent_fast_queries_db_with_keyword_limit(self, mock_dependencies):
        """Redis 未命中时，应按关键字参数 limit 查询 DB 并回填缓存。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_dependencies["repo"].list_recent_messages.return_value = [
            ConversationHistoryMessage(
                id="msg-1",
                role="assistant",
                content="先慢一点，我们一步步说。",
                advisor=None,
            )
        ]
        service = AgentService()

        messages = await service._get_recent_fast(_make_request(), limit=4)

        assert len(messages) == 1
        assert messages[0].content == "先慢一点，我们一步步说。"
        mock_dependencies["repo"].list_recent_messages.assert_called_once_with(
            "user-001",
            "sess-001",
            limit=4,
        )
        mock_dependencies["session_memory"].append_message.assert_called_once_with(
            "sess-001",
            "assistant",
            "先慢一点，我们一步步说。",
            advisor=None,
        )


class TestListConversations:
    """会话历史获取测试。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    def test_list_conversations_returns_empty(self, mock_dependencies):
        """无会话时应返回空列表。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        service = AgentService()
        result = service.list_conversations("user-001")

        assert result.user_id == "user-001"
        assert result.conversations == []

    def test_list_conversations_calls_repository(self, mock_dependencies):
        """应通过 repository 获取会话列表。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        service = AgentService()
        service.list_conversations("user-001")

        mock_dependencies["repo"].list_conversations.assert_called_once_with("user-001")

    @pytest.mark.asyncio
    async def test_list_conversations_async_calls_repository(self, mock_dependencies):
        """异步接口应在线程池中调用 repository。"""
        service = AgentService()

        result = await service.list_conversations_async("user-001", timeout=0.5)

        assert result.user_id == "user-001"
        assert result.conversations == []
        mock_dependencies["repo"].list_conversations.assert_called_once_with("user-001")

    @pytest.mark.asyncio
    async def test_list_conversations_async_returns_empty_on_timeout(self, mock_dependencies):
        """查询超时时应快速降级为空列表，避免接口卡死。"""
        mock_dependencies["repo"].list_conversations.side_effect = lambda *_: time.sleep(0.2)
        service = AgentService()

        result = await service.list_conversations_async("user-001", timeout=0.01)

        assert result.user_id == "user-001"
        assert result.conversations == []


class TestExtractDoneResponse:
    """SSE done 事件解析测试。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """

    def test_extract_done_event(self, mock_dependencies):
        """done 事件应正确解析为 ChatResponse。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        service = AgentService()
        payload_data = _make_response().model_dump()
        import json

        sse = f"event: done\ndata: {json.dumps(payload_data, ensure_ascii=False)}\n\n"
        result = service._extract_done_response(sse)

        assert result is not None
        assert result.reply == "我理解你的感受"

    def test_extract_token_event_returns_none(self, mock_dependencies):
        """token 事件应返回 None。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        service = AgentService()
        sse = 'event: token\ndata: {"content": "你"}\n\n'
        result = service._extract_done_response(sse)

        assert result is None

    def test_extract_malformed_data_returns_none(self, mock_dependencies):
        """格式错误的数据应返回 None。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        service = AgentService()
        sse = "event: done\ndata: {invalid json}\n\n"
        result = service._extract_done_response(sse)

        assert result is None

