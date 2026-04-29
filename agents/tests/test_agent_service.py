"""ChatService 核心服务单元测试。

覆盖：非流式回复、流式回复、记忆保存策略、会话历史获取。
使用 mock 隔离外部依赖（LLM、向量库、数据库）。
"""

from __future__ import annotations

import asyncio
import time
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from agents import AgentService
from agents.response_cache import CachedResponse
from contracts.chat import (
    ChatMode,
    ChatRequest,
    ConversationContext,
    ConversationHistoryItem,
    ConversationHistoryMessage,
    MemoryDecision,
    MemoryDecisionBatch,
    ChatResponse,
    ChatTrace,
    QuestionAdvisorPayload,
)


@pytest.fixture
def mock_dependencies():
    """统一 mock ChatService 的所有外部依赖。"""
    with (
        patch("agents.agent_service.CompanionGraphWorkflow") as mock_workflow_cls,
        patch("agents.agent_service.ConversationRepository") as mock_repo_cls,
        patch("agents.agent_service.MemoryManager") as mock_memory_cls,
        patch("agents.agent_service.ConversationContextManager") as mock_context_manager_cls,
        patch("agents.agent_service.RedisService") as mock_redis_cls,
        patch("agents.agent_service.MemoryOutboxRepository") as mock_outbox_cls,
        patch("agents.agent_service.MemorySettingsRepository") as mock_settings_cls,
        patch("agents.agent_service.MemoryAuditRepository") as mock_audit_cls,
        patch("agents.agent_service.ResponseCacheService") as mock_response_cache_cls,
    ):
        mock_workflow = mock_workflow_cls.return_value
        mock_repo = mock_repo_cls.return_value
        mock_memory = mock_memory_cls.return_value
        mock_context_manager = mock_context_manager_cls.return_value
        mock_redis = mock_redis_cls.return_value
        mock_outbox = mock_outbox_cls.return_value
        mock_settings = mock_settings_cls.return_value
        mock_audit = mock_audit_cls.return_value
        mock_response_cache = mock_response_cache_cls.return_value

        # 默认返回空历史
        mock_repo.list_recent_messages.return_value = []
        mock_repo.list_conversations.return_value = []
        mock_repo.get_conversation_context_seed.return_value = {"recent_messages": []}
        mock_repo.get_summary_checkpoint.return_value = {
            "summary_text": "",
            "covered_message_count": 0,
            "last_message_id": "",
        }
        mock_repo.list_messages_after.return_value = []
        mock_context_manager.build_context = AsyncMock(return_value=ConversationContext())
        mock_context_manager.refresh_cache.return_value = None
        mock_redis.get_session_context.return_value = None
        mock_redis.cache_session_context.return_value = True
        mock_settings.is_enabled.return_value = False
        mock_audit.record.return_value = "audit-001"
        mock_response_cache.get_cached_response = AsyncMock(return_value=None)
        mock_response_cache.set_response = AsyncMock(return_value=None)
        mock_response_cache.wait_for_exact_response = AsyncMock(return_value=None)
        mock_response_cache.acquire_generation_lock.return_value = True

        # 默认记忆保存成功
        mock_memory.decide_memory = AsyncMock(
            return_value=MemoryDecisionBatch(
                items=[
                    MemoryDecision(
                        should_store=True,
                        memory_type="preference",
                        memory_text="用户偏好：需要被安慰",
                        canonical_key="preference:comfort_style",
                        confidence=0.93,
                        importance_score=0.9,
                        merge_strategy="replace",
                        reason_code="stable_preference",
                    )
                ]
            )
        )
        mock_memory.save_memory = AsyncMock(return_value="mem-001")

        yield {
            "workflow": mock_workflow,
            "repo": mock_repo,
            "memory": mock_memory,
            "context_manager": mock_context_manager,
            "redis": mock_redis,
            "outbox": mock_outbox,
            "settings": mock_settings,
            "audit": mock_audit,
            "response_cache": mock_response_cache,
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
        mock_dependencies["workflow"].run.assert_called_once()
        assert "conversation_context" in mock_dependencies["workflow"].run.call_args.kwargs
        assert response.trace.cache_level == "l3_api"
        mock_dependencies["response_cache"].set_response.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reply_uses_cached_response_without_workflow(self, mock_dependencies):
        """L1/L2 命中时不应再调用工作流，但仍要保存本轮对话。"""
        cached_response = _make_response("这是缓存回答").model_copy(
            update={
                "trace": ChatTrace(
                    safety_level="low",
                    cache_hit=True,
                    cache_level="l1_exact",
                )
            }
        )
        mock_dependencies["response_cache"].get_cached_response = AsyncMock(
            return_value=CachedResponse(response=cached_response, level="l1_exact")
        )
        service = AgentService()

        response = await service.reply(_make_request())

        assert response.reply == "这是缓存回答"
        assert response.trace.cache_hit is True
        assert response.trace.cache_level == "l1_exact"
        mock_dependencies["workflow"].run.assert_not_called()
        mock_dependencies["repo"].save_turn.assert_called_once()
        mock_dependencies["response_cache"].set_response.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reply_skips_memory_event_when_memory_disabled(self, mock_dependencies):
        """长期记忆默认关闭时不应写入 Outbox。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        mock_dependencies["workflow"].run = AsyncMock(return_value=_make_response())
        service = AgentService()

        await service.reply(_make_request())

        service.memory_outbox_repository.save_pending.assert_not_called()
        mock_dependencies["memory"].decide_memory.assert_not_called()
        mock_dependencies["memory"].save_memory.assert_not_called()

    @pytest.mark.asyncio
    async def test_reply_writes_memory_event_to_outbox_when_enabled(self, mock_dependencies):
        """开启长期记忆后，正常回复应写入 Outbox。"""
        mock_dependencies["settings"].is_enabled.return_value = True
        mock_dependencies["workflow"].run = AsyncMock(return_value=_make_response())
        service = AgentService()

        await service.reply(_make_request())

        service.memory_outbox_repository.save_pending.assert_called_once()
        payload = service.memory_outbox_repository.save_pending.call_args.args[0]
        assert payload["user_id"] == "user-001"
        assert payload["session_id"] == "sess-001"
        assert payload["task_id"].startswith("memory:")
        mock_dependencies["memory"].decide_memory.assert_not_called()
        mock_dependencies["memory"].save_memory.assert_not_called()

    @pytest.mark.asyncio
    async def test_reply_skips_memory_event_for_sensitive_raw_text(self, mock_dependencies):
        """原始消息包含手机号时，即使已开启长期记忆也不写 Outbox。"""
        mock_dependencies["settings"].is_enabled.return_value = True
        mock_dependencies["workflow"].run = AsyncMock(return_value=_make_response())
        service = AgentService()

        await service.reply(_make_request(message="我的手机号是13800138000，以后提醒我"))

        service.memory_outbox_repository.save_pending.assert_not_called()
        service.memory_audit_repository.record.assert_called()

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
    async def test_build_conversation_context_uses_context_manager(self, mock_dependencies):
        """主链路应通过统一上下文管理器构造 ConversationContext。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        context = ConversationContext(
            recent_messages=[
                ConversationHistoryMessage(
                    id="msg-1",
                    role="assistant",
                    content="先慢一点，我们一步步说。",
                    advisor=None,
                )
            ]
        )
        mock_dependencies["context_manager"].build_context = AsyncMock(return_value=context)
        service = AgentService()

        result = await service._build_conversation_context(_make_request())

        assert result.recent_messages[0].content == "先慢一点，我们一步步说。"
        mock_dependencies["context_manager"].build_context.assert_awaited_once_with(
            user_id="user-001",
            session_id="sess-001",
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

    def test_extract_token_content(self, mock_dependencies):
        """token 事件应提取 content，用于中断后保存部分回复。"""
        service = AgentService()
        sse = 'event: token\ndata: {"content": "你"}\n\n'

        result = service._extract_token_content(sse)

        assert result == "你"


class TestStreamTasks:
    """后台流任务与取消语义测试。"""

    @pytest.mark.asyncio
    async def test_stream_reply_uses_cached_response(self, mock_dependencies):
        """流式入口命中缓存时应输出标准 SSE，并跳过工作流。"""
        cached_response = _make_response("缓存流式回答").model_copy(
            update={
                "trace": ChatTrace(
                    safety_level="low",
                    cache_hit=True,
                    cache_level="l2_semantic",
                    cache_similarity=0.97,
                )
            }
        )
        mock_dependencies["response_cache"].get_cached_response = AsyncMock(
            return_value=CachedResponse(
                response=cached_response,
                level="l2_semantic",
                similarity=0.97,
            )
        )
        service = AgentService()

        chunks = [chunk async for chunk in service.stream_reply(_make_request())]

        joined = "".join(chunks)
        assert "event: thinking_start" in joined
        assert "event: token" in joined
        assert "event: done" in joined
        assert '"cache_level": "l2_semantic"' in joined
        mock_dependencies["workflow"].stream.assert_not_called()
        mock_dependencies["repo"].save_user_message.assert_called_once()
        mock_dependencies["repo"].save_assistant_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_stream_can_be_cancelled(self, mock_dependencies):
        """后台流任务应支持服务端取消，并以 None 哨兵结束本地订阅。"""
        release_event = asyncio.Event()

        async def fake_stream(*args, **kwargs):
            del args, kwargs
            yield 'event: token\ndata: {"content":"你"}\n\n'
            await release_event.wait()
            yield (
                'event: done\ndata: '
                '{"reply":"你好","mode":"companion","trace":{"memory_hits":[],"knowledge_hits":[],'
                '"retrieval_query":"","safety_level":"low","mcp_calls":[]},"advisor":null}\n\n'
            )

        mock_dependencies["workflow"].stream = fake_stream
        service = AgentService()

        queue = await service.start_stream("stream-001", _make_request())
        first_chunk = await asyncio.wait_for(queue.get(), timeout=0.5)

        assert first_chunk is not None
        assert "event: token" in first_chunk

        cancel_result = await service.cancel_stream("stream-001", "user-001")
        end_marker = await asyncio.wait_for(queue.get(), timeout=0.5)

        assert cancel_result.status == "cancelling"
        assert cancel_result.accepted is True
        assert end_marker is None
        mock_dependencies["repo"].save_interrupted_assistant_message.assert_called_once()
        call_args = mock_dependencies["repo"].save_interrupted_assistant_message.call_args
        assert call_args.args[1] == "你"
        assert call_args.kwargs["stream_id"] == "stream-001"
        mock_dependencies["outbox"].save_pending.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_conversations_async_includes_active_stream(self, mock_dependencies):
        """会话历史应带出当前会话的后台流任务状态。"""
        release_event = asyncio.Event()

        async def fake_stream(*args, **kwargs):
            del args, kwargs
            yield 'event: token\ndata: {"content":"你"}\n\n'
            await release_event.wait()

        mock_dependencies["workflow"].stream = fake_stream
        mock_dependencies["repo"].list_conversations.return_value = [
            ConversationHistoryItem(
                id="sess-001",
                title="新对话",
                preview="最近心情不好",
                mode="companion",
                messages=[],
            )
        ]
        service = AgentService()

        queue = await service.start_stream("stream-002", _make_request())
        await asyncio.wait_for(queue.get(), timeout=0.5)
        result = await service.list_conversations_async("user-001", timeout=0.5)

        assert result.conversations[0].active_stream_id == "stream-002"
        assert result.conversations[0].active_stream_status == "running"

        await service.cancel_stream("stream-002", "user-001")
        await asyncio.wait_for(queue.get(), timeout=0.5)

    def test_extract_malformed_data_returns_none(self, mock_dependencies):
        """格式错误的数据应返回 None。

        目的：验证当前场景下的输入、分支或边界行为是否符合预期。
        结果：确保相关逻辑回归稳定，异常行为能被测试及时发现。
        """
        service = AgentService()
        sse = "event: done\ndata: {invalid json}\n\n"
        result = service._extract_done_response(sse)

        assert result is None

