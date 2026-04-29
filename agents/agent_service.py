"""Agent 服务层：封装对话工作流、记忆管理和缓存策略。

目的：对外提供统一、稳定的服务入口，协调工作流、记忆和存储组件。
结果：路由层无需感知具体实现细节，降低耦合度并提升可维护性。
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import partial
from typing import cast

from contracts.chat import (
    CancelStreamResponse,
    ChatRequest,
    ChatResponse,
    ConversationContext,
    ConversationHistoryItem,
    ConversationHistoryMessage,
    ConversationHistoryResponse,
)
from core.config import get_settings
from observability import format_pretty_json_log, get_langsmith_service
from persistence import ConversationRepository, MemoryAuditRepository, MemoryOutboxRepository, MemorySettingsRepository
from security import RedisService, SafetyGuard
from stream import format_sse_event

from .memory_policy import MemoryPolicyService
from .memory_events import build_memory_extraction_message
from .memory import ConversationContextManager, MemoryManager, estimate_text_tokens
from .response_cache import CachedResponse, ResponseCacheService
from .stream_registry import StreamTaskRegistry
from .workflows import CompanionGraphWorkflow, build_workflow_runtime

logger = logging.getLogger(__name__)

DEFAULT_CONVERSATION_HISTORY_TIMEOUT_SECONDS = 3.0


def _log_chat_payload(event: str, payload: dict[str, object]) -> None:
    """用小型 JSON 块打印聊天主链路日志，方便本地排查。"""
    logger.info("%s:\n%s", event, format_pretty_json_log(payload, max_string_length=1200))


class AgentService:
    """目的：承载聚合后的业务能力，对外暴露稳定且清晰的调用入口。
    结果：上层模块可以直接复用核心能力，减少重复编排并提升可维护性。
    """

    def __init__(
        self,
        redis_service: RedisService | None = None,
        *,
        workflow: CompanionGraphWorkflow | None = None,
        conversation_repository: ConversationRepository | None = None,
        memory_manager: MemoryManager | None = None,
        conversation_context_manager: ConversationContextManager | None = None,
        safety_guard: SafetyGuard | None = None,
        memory_outbox_repository: MemoryOutboxRepository | None = None,
        memory_settings_repository: MemorySettingsRepository | None = None,
        memory_policy_service: MemoryPolicyService | None = None,
        memory_audit_repository: MemoryAuditRepository | None = None,
        stream_task_registry: StreamTaskRegistry | None = None,
        response_cache_service: ResponseCacheService | None = None,
    ) -> None:
        """目的：初始化AgentService所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        self.memory_manager = memory_manager or MemoryManager()
        self.safety_guard = safety_guard or SafetyGuard()
        self.workflow = workflow or CompanionGraphWorkflow(
            runtime=build_workflow_runtime(
                memory_manager=self.memory_manager,
                safety_guard=self.safety_guard,
            )
        )
        self.conversation_repository = conversation_repository or ConversationRepository()
        # Redis 服务：用于会话热缓存、workflow 上下文和回答 L1 缓存
        self._redis = redis_service or RedisService()
        self.context_manager = conversation_context_manager or ConversationContextManager(
            redis_service=self._redis,
            conversation_repository=self.conversation_repository,
        )
        self.response_cache = response_cache_service or ResponseCacheService(
            redis_service=self._redis,
        )
        self.memory_outbox_repository = memory_outbox_repository or MemoryOutboxRepository()
        self.memory_settings_repository = memory_settings_repository or MemorySettingsRepository()
        self.memory_policy_service = memory_policy_service or MemoryPolicyService()
        self.memory_audit_repository = memory_audit_repository or MemoryAuditRepository()
        self.stream_task_registry = stream_task_registry or StreamTaskRegistry()
        # DB 同步方法在异步上下文中用线程池执行，避免阻塞事件循环
        self._db_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat_db_")

    def shutdown(self) -> None:
        """目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        self._db_executor.shutdown(wait=False, cancel_futures=True)

    async def reply(self, request: ChatRequest) -> ChatResponse:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        _log_chat_payload(
            "聊天请求",
            {
                "stream": False,
                "user_id": request.user_id,
                "session_id": request.session_id,
                "mode": request.mode,
                "message": request.message,
            },
        )
        risk_level = self.safety_guard.inspect_input(request.message)
        langsmith = get_langsmith_service()
        request_metadata = langsmith.build_metadata(
            user_id=request.user_id,
            session_id=request.session_id,
            message=request.message,
            mode=request.mode,
            risk_level=risk_level,
            stream=False,
            provider=getattr(langsmith.settings, "llm_provider", "unknown"),
        )

        conversation_context = await self._build_conversation_context(request)
        cached = await self._lookup_response_cache(request, conversation_context, risk_level)
        if cached is not None:
            response = cached.response
            await self._save_turn_async(request, response)
            await self._refresh_context_cache_async(request)
            await self._enqueue_summary_refresh_if_needed(request.session_id)
            self._cache_workflow_context(request.session_id, response)
            await self._try_save_memory(
                user_id=request.user_id,
                session_id=request.session_id,
                user_message=request.message,
                assistant_reply=response.reply,
                safety_level=response.trace.safety_level,
            )
            _log_chat_payload(
                "聊天响应",
                {
                    "stream": False,
                    "cache_level": response.trace.cache_level,
                    "user_id": request.user_id,
                    "session_id": request.session_id,
                    "mode": request.mode,
                    "reply": response.reply,
                },
            )
            return response

        lock_state = self._acquire_response_cache_lock(request, conversation_context, risk_level)
        if lock_state is False:
            cached = await self._wait_for_exact_response_cache(request, conversation_context)
            if cached is not None:
                response = cached.response
                await self._save_turn_async(request, response)
                await self._refresh_context_cache_async(request)
                await self._enqueue_summary_refresh_if_needed(request.session_id)
                self._cache_workflow_context(request.session_id, response)
                return response

        response = await self.workflow.run(
            request,
            conversation_context=conversation_context,
            risk_level=risk_level,
            langsmith_metadata=request_metadata,
        )
        response = self._mark_l3_response(response)
        await self.response_cache.set_response(
            request,
            conversation_context,
            response,
            safety_level=risk_level,
        )

        # 主路径写 DB（持久化），同步仓储放到线程池，避免阻塞事件循环。
        await self._save_turn_async(request, response)
        await self._refresh_context_cache_async(request)
        await self._enqueue_summary_refresh_if_needed(request.session_id)

        # B8: 缓存 workflow 上下文（memory_hits / knowledge_hits）供后续请求复用
        self._cache_workflow_context(request.session_id, response)

        # 对话结束后异步保存记忆（fire-and-forget，失败不影响主流程）
        await self._try_save_memory(
            user_id=request.user_id,
            session_id=request.session_id,
            user_message=request.message,
            assistant_reply=response.reply,
            safety_level=response.trace.safety_level,
        )
        _log_chat_payload(
            "聊天响应",
            {
                "stream": False,
                "user_id": request.user_id,
                "session_id": request.session_id,
                "mode": request.mode,
                "reply": response.reply,
            },
        )
        return response

    async def stream_reply(
        self,
        request: ChatRequest,
        *,
        stream_id: str = "",
    ) -> AsyncIterator[str]:
        """目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        _log_chat_payload(
            "聊天请求",
            {
                "stream": True,
                "user_id": request.user_id,
                "session_id": request.session_id,
                "mode": request.mode,
                "message": request.message,
            },
        )
        risk_level = self.safety_guard.inspect_input(request.message)
        langsmith = get_langsmith_service()
        request_metadata = langsmith.build_metadata(
            user_id=request.user_id,
            session_id=request.session_id,
            message=request.message,
            mode=request.mode,
            risk_level=risk_level,
            stream=True,
            provider=getattr(langsmith.settings, "llm_provider", "unknown"),
        )

        conversation_context = await self._build_conversation_context(request)
        cached = await self._lookup_response_cache(request, conversation_context, risk_level)
        if cached is None:
            lock_state = self._acquire_response_cache_lock(request, conversation_context, risk_level)
            if lock_state is False:
                cached = await self._wait_for_exact_response_cache(request, conversation_context)
        if cached is not None:
            response = cached.response
            user_save_task = asyncio.create_task(self._save_user_message_async(request))
            yield self._format_cached_sse("thinking_start", {})
            yield self._format_cached_sse(
                "thinking_delta",
                {"content": f"已命中{self._format_cache_level(response.trace.cache_level)}缓存"},
            )
            yield self._format_cached_sse("thinking_done", {})
            for chunk in self._iter_cached_reply_chunks(response.reply):
                yield self._format_cached_sse("token", {"content": chunk})
            await self._save_stream_turn_tail_async(request, response, user_save_task)
            self._cache_workflow_context(request.session_id, response)
            await self._try_save_memory(
                user_id=request.user_id,
                session_id=request.session_id,
                user_message=request.message,
                assistant_reply=response.reply,
                safety_level=response.trace.safety_level,
            )
            yield self._format_cached_sse("done", response.model_dump())
            return

        # 用户消息先异步落库；Redis 热缓存由 DB 成功写入后统一刷新。
        user_save_task = asyncio.create_task(self._save_user_message_async(request))

        tail_save_task: asyncio.Task[None] | None = None
        partial_reply_chunks: list[str] = []
        saw_done_response = False
        try:
            async for chunk in self.workflow.stream(
                request,
                conversation_context=conversation_context,
                risk_level=risk_level,
                langsmith_metadata=request_metadata,
            ):
                token_content = self._extract_token_content(chunk)
                if token_content:
                    partial_reply_chunks.append(token_content)
                response = self._extract_done_response(chunk)
                if response is not None:
                    response = self._mark_l3_response(response)
                    chunk = self._format_cached_sse("done", response.model_dump())
                    saw_done_response = True
                    tail_save_task = asyncio.create_task(
                        self._save_stream_turn_tail_async(request, response, user_save_task)
                    )
                    # B8: 流结束后缓存上下文
                    self._cache_workflow_context(request.session_id, response)
                    # 流式回复完成后保存记忆
                    await self._try_save_memory(
                        user_id=request.user_id,
                        session_id=request.session_id,
                        user_message=request.message,
                        assistant_reply=response.reply,
                        safety_level=response.trace.safety_level,
                    )
                    _log_chat_payload(
                        "聊天响应",
                        {
                            "stream": True,
                            "user_id": request.user_id,
                            "session_id": request.session_id,
                            "mode": request.mode,
                            "reply": response.reply,
                        },
                    )
                    await self.response_cache.set_response(
                        request,
                        conversation_context,
                        response,
                        safety_level=risk_level,
                    )
                yield chunk
        except asyncio.CancelledError:
            if not saw_done_response:
                logger.info("流式对话已取消，保存已生成的部分回复: session=%s", request.session_id)
                await self._save_interrupted_stream_tail_async(
                    request,
                    "".join(partial_reply_chunks),
                    stream_id=stream_id,
                    user_save_task=user_save_task,
                )
            raise
        finally:
            if tail_save_task is not None:
                try:
                    await tail_save_task
                except Exception as exc:
                    logger.warning("等待流式收尾持久化失败: session=%s, error=%s", request.session_id, exc)

    async def start_stream(
        self,
        stream_id: str,
        request: ChatRequest,
    ) -> asyncio.Queue[str | None]:
        """目的：启动后台流任务并返回当前订阅者对应的事件队列。
        结果：路由层可以把该队列封装为 SSE 响应，同时后台任务独立继续执行。
        """
        subscriber: asyncio.Queue[str | None] = asyncio.Queue()
        record = await self.stream_task_registry.create(
            stream_id=stream_id,
            user_id=request.user_id,
            session_id=request.session_id,
            subscriber=subscriber,
        )
        task = asyncio.create_task(
            self._run_stream_task(record.stream_id, request),
            name=f"chat-stream:{record.stream_id}",
        )
        record.task = task
        return subscriber

    async def remove_stream_subscriber(
        self,
        stream_id: str,
        subscriber: asyncio.Queue[str | None],
    ) -> None:
        """目的：移除断开连接对应的本地订阅者。
        结果：浏览器离开页面时不会影响后台继续生成。
        """
        await self.stream_task_registry.remove_subscriber(stream_id, subscriber)

    async def cancel_stream(self, stream_id: str, user_id: str) -> CancelStreamResponse:
        """目的：按用户身份取消指定流任务。
        结果：返回统一的幂等取消状态。
        """
        return await self.stream_task_registry.cancel_for_user(stream_id, user_id)

    def list_conversations(self, user_id: str) -> ConversationHistoryResponse:
        """目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        conversations = self.conversation_repository.list_conversations(user_id)
        return ConversationHistoryResponse(user_id=user_id, conversations=conversations)

    async def list_conversations_async(
        self,
        user_id: str,
        *,
        timeout: float = DEFAULT_CONVERSATION_HISTORY_TIMEOUT_SECONDS,
    ) -> ConversationHistoryResponse:
        """目的：通过线程池执行同步仓储查询，并在超时或异常时快速降级。
        结果：即使数据库偶发卡顿，接口也能及时返回，避免整站“假死”。
        """
        loop = asyncio.get_running_loop()
        db_task = loop.run_in_executor(
            self._db_executor,
            self.conversation_repository.list_conversations,
            user_id,
        )
        try:
            conversations: list[ConversationHistoryItem] = await asyncio.wait_for(
                db_task,
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "查询会话历史超时，已降级为空列表: user_id=%s, timeout=%.1fs",
                user_id,
                timeout,
            )
            return ConversationHistoryResponse(user_id=user_id, conversations=[])
        except Exception as exc:
            logger.warning(
                "查询会话历史失败，已降级为空列表: user_id=%s, error=%s",
                user_id,
                exc,
            )
            return ConversationHistoryResponse(user_id=user_id, conversations=[])

        active_streams = await self.stream_task_registry.list_active_for_user(user_id)
        for item in conversations:
            active_stream = active_streams.get(item.id)
            if active_stream is None:
                continue
            item.active_stream_id = active_stream.stream_id
            item.active_stream_status = active_stream.status
        return ConversationHistoryResponse(user_id=user_id, conversations=conversations)

    async def _build_conversation_context(
        self,
        request: ChatRequest,
    ) -> ConversationContext:
        """目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        try:
            return await self.context_manager.build_context(
                user_id=request.user_id,
                session_id=request.session_id,
            )
        except Exception as exc:
            logger.warning(
                "构建会话上下文失败，降级为空上下文: session=%s, error=%s",
                request.session_id,
                exc,
            )
            settings = get_settings()
            return ConversationContext(token_budget=settings.conversation_context_token_budget)

    async def _lookup_response_cache(
        self,
        request: ChatRequest,
        conversation_context: ConversationContext,
        risk_level: str,
    ) -> CachedResponse | None:
        """目的：按安全级别读取回答缓存。
        结果：仅低风险输入会尝试命中 L1/L2，异常时降级为未命中。
        """
        if risk_level != "low":
            return None
        try:
            return await self.response_cache.get_cached_response(request, conversation_context)
        except Exception as exc:
            logger.warning("回答缓存读取异常，继续走 L3: session=%s, error=%s", request.session_id, exc)
            return None

    def _acquire_response_cache_lock(
        self,
        request: ChatRequest,
        conversation_context: ConversationContext,
        risk_level: str,
    ) -> bool | None:
        """目的：低风险请求在缓存未命中后尝试获取生成短锁。
        结果：并发重复请求会优先等待首个请求回填缓存。
        """
        if risk_level != "low":
            return None
        try:
            return self.response_cache.acquire_generation_lock(request, conversation_context)
        except Exception as exc:
            logger.debug("回答缓存短锁异常，继续走 L3: session=%s, error=%s", request.session_id, exc)
            return None

    async def _wait_for_exact_response_cache(
        self,
        request: ChatRequest,
        conversation_context: ConversationContext,
    ) -> CachedResponse | None:
        """目的：短暂等待其他并发请求写入 L1 精确缓存。
        结果：命中则复用缓存，超时则由调用方继续走 L3。
        """
        try:
            return await self.response_cache.wait_for_exact_response(request, conversation_context)
        except Exception as exc:
            logger.debug("等待回答缓存回填失败，继续走 L3: session=%s, error=%s", request.session_id, exc)
            return None

    async def _save_user_message_async(self, request: ChatRequest) -> None:
        """目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self._db_executor,
                self.conversation_repository.save_user_message,
                request,
            )
        except Exception as exc:
            logger.warning(
                "异步保存用户消息失败（会话热缓存等待 DB 刷新）: session=%s, error=%s",
                request.session_id,
                exc,
            )

    async def _save_turn_async(self, request: ChatRequest, response: ChatResponse) -> None:
        """目的：把同步数据库写入放到线程池执行，避免阻塞事件循环。
        结果：用户消息和助手回复被持久化，失败时只记录日志不影响主回复。
        """
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self._db_executor,
                self.conversation_repository.save_turn,
                request,
                response,
            )
        except Exception as exc:
            logger.warning(
                "保存完整对话轮次失败，主回复已返回: session=%s, error=%s",
                request.session_id,
                exc,
            )

    async def _save_assistant_message_async(
        self,
        request: ChatRequest,
        response: ChatResponse,
    ) -> None:
        """目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self._db_executor,
                self.conversation_repository.save_assistant_message,
                request,
                response,
            )
        except Exception as exc:
            logger.warning(
                "异步保存助手消息失败（会话热缓存等待 DB 刷新）: session=%s, error=%s",
                request.session_id,
                exc,
            )

    async def _save_stream_turn_tail_async(
        self,
        request: ChatRequest,
        response: ChatResponse,
        user_save_task: asyncio.Task[None],
    ) -> None:
        """目的：流式回复完成后，按 DB -> Redis 热缓存 -> 摘要任务顺序收尾。
        结果：完成当前实例行为并返回约定结果。
        """
        try:
            await user_save_task
        except Exception as exc:
            logger.warning("等待用户消息落库失败，继续尝试保存助手消息: %s", exc)
        await self._save_assistant_message_async(request, response)
        await self._refresh_context_cache_async(request)
        await self._enqueue_summary_refresh_if_needed(request.session_id)

    async def _save_interrupted_stream_tail_async(
        self,
        request: ChatRequest,
        partial_reply: str,
        *,
        stream_id: str,
        user_save_task: asyncio.Task[None],
    ) -> None:
        """目的：流式回复被用户手动中断后，保存已生成部分并刷新短期上下文。
        结果：部分 assistant 回复可参与后续会话上下文，但不会进入长期记忆提取。
        """
        try:
            await user_save_task
        except Exception as exc:
            logger.warning("等待用户消息落库失败，跳过中断助手回复保存: %s", exc)
            return
        normalized_reply = partial_reply.strip()
        if normalized_reply:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    self._db_executor,
                    partial(
                        self.conversation_repository.save_interrupted_assistant_message,
                        request,
                        normalized_reply,
                        stream_id=stream_id,
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "保存中断助手回复失败: session=%s, stream_id=%s, error=%s",
                    request.session_id,
                    stream_id,
                    exc,
                )
        await self._refresh_context_cache_async(request)
        await self._enqueue_summary_refresh_if_needed(request.session_id)

    async def _refresh_context_cache_async(self, request: ChatRequest) -> None:
        """目的：从 DB 最近消息刷新 Redis 会话热缓存。
        结果：完成当前实例行为并返回约定结果。
        """
        try:
            loop = asyncio.get_running_loop()
            seed = await loop.run_in_executor(
                self._db_executor,
                partial(
                    self.conversation_repository.get_conversation_context_seed,
                    request.user_id,
                    request.session_id,
                    limit=get_settings().conversation_cache_max_messages,
                ),
            )
            seed_messages = seed.get("recent_messages", [])
            self.context_manager.refresh_cache(
                request.session_id,
                cast(
                    list[ConversationHistoryMessage],
                    seed_messages if isinstance(seed_messages, list) else [],
                ),
            )
        except Exception as exc:
            logger.warning("刷新会话热缓存失败: session=%s, error=%s", request.session_id, exc)

    async def _enqueue_summary_refresh_if_needed(self, session_id: str) -> None:
        """目的：达到阈值后投递异步会话摘要任务，不阻塞主回复。
        结果：完成当前实例行为并返回约定结果。
        """
        settings = get_settings()
        try:
            loop = asyncio.get_running_loop()
            checkpoint = await loop.run_in_executor(
                self._db_executor,
                self.conversation_repository.get_summary_checkpoint,
                session_id,
            )
            messages = await loop.run_in_executor(
                self._db_executor,
                partial(
                    self.conversation_repository.list_messages_after,
                    session_id,
                    str(checkpoint.get("last_message_id", "")),
                    limit=settings.conversation_cache_max_messages,
                ),
            )
        except Exception as exc:
            logger.warning("检查会话摘要刷新条件失败: session=%s, error=%s", session_id, exc)
            return
        pending_tokens = sum(estimate_text_tokens(item.content) for item in messages)
        should_refresh = (
            len(messages) >= settings.conversation_summary_trigger_messages
            or pending_tokens >= settings.conversation_summary_trigger_tokens
        )
        if not should_refresh:
            return
        try:
            from .worker import refresh_session_summary

            refresh_session_summary.delay(session_id)
            logger.debug(
                "会话摘要刷新任务已投递: session=%s, pending_messages=%d, pending_tokens=%d",
                session_id,
                len(messages),
                pending_tokens,
            )
        except Exception as exc:
            logger.warning("会话摘要刷新任务投递失败: session=%s, error=%s", session_id, exc)

    def _extract_done_response(self, sse_payload: str) -> ChatResponse | None:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        event_name, data = self._extract_sse_payload(sse_payload)
        if event_name != "done" or not data:
            return None

        try:
            return ChatResponse.model_validate(data)
        except (ValueError, TypeError) as exc:
            logger.warning("解析 SSE done 事件失败，跳过持久化: %s", exc)
            return None

    def _extract_token_content(self, sse_payload: str) -> str:
        """目的：从 token SSE 事件中提取已生成文本。
        结果：取消时可以持久化用户已经看到的 assistant 部分回复。
        """
        event_name, data = self._extract_sse_payload(sse_payload)
        if event_name != "token":
            return ""
        return str(data.get("content", "") or "")

    def _extract_sse_payload(self, sse_payload: str) -> tuple[str, dict[str, object]]:
        """目的：解析 SSE 文本中的 event 和 JSON data。
        结果：为 done 持久化和 token 累计提供统一解析入口。
        """
        event_name = ""
        data_lines: list[str] = []

        for line in sse_payload.splitlines():
            if line.startswith("event:"):
                event_name = line.replace("event:", "", 1).strip()
            elif line.startswith("data:"):
                data_lines.append(line.replace("data:", "", 1).strip())

        if not data_lines:
            return event_name, {}

        try:
            payload = json.loads("\n".join(data_lines))
        except (ValueError, TypeError) as exc:
            logger.warning("解析 SSE data 失败: event=%s, error=%s", event_name, exc)
            return event_name, {}
        return event_name, payload if isinstance(payload, dict) else {}

    def _extract_event_name(self, sse_payload: str) -> str:
        """目的：从 SSE 文本中提取事件名，供后台任务判断终态。
        结果：返回 event 字段值；无法识别时返回空字符串。
        """
        for line in sse_payload.splitlines():
            if line.startswith("event:"):
                return line.replace("event:", "", 1).strip()
        return ""

    @staticmethod
    def _iter_cached_reply_chunks(text: str, *, chunk_size: int = 8) -> list[str]:
        """目的：把缓存命中的完整回复拆成 token-like 片段。
        结果：流式接口命中缓存时仍保持前端消费协议一致。
        """
        return [text[index:index + chunk_size] for index in range(0, len(text), chunk_size)] or [""]

    @staticmethod
    def _format_cached_sse(event: str, payload: dict[str, object]) -> str:
        """目的：统一缓存命中时的 SSE 事件格式。
        结果：L1/L2 命中和 L3 生成使用同一前端协议。
        """
        return format_sse_event(event, payload)

    @staticmethod
    def _format_cache_level(cache_level: str) -> str:
        """目的：把缓存层级转成简短可读文案。
        结果：thinking_delta 中可以展示当前命中来源。
        """
        if cache_level == "l1_exact":
            return "精确"
        if cache_level == "l2_semantic":
            return "语义"
        return "回答"

    @staticmethod
    def _mark_l3_response(response: ChatResponse) -> ChatResponse:
        """目的：给实时 API 调用结果补充缓存 trace。
        结果：未命中缓存的主链路也能明确标记为 L3。
        """
        trace = response.trace.model_copy(
            update={
                "cache_hit": False,
                "cache_level": "l3_api",
                "cache_similarity": None,
            }
        )
        return response.model_copy(deep=True, update={"trace": trace})

    def _cache_workflow_context(self, session_id: str, response: ChatResponse) -> None:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        context = {
            "memory_hits": response.trace.memory_hits,
            "knowledge_hits": response.trace.knowledge_hits,
            "knowledge_evidences": [
                item.model_dump()
                for item in response.trace.knowledge_evidences
            ],
            "retrieval_query": response.trace.retrieval_query,
            "answer_confidence": response.trace.answer_confidence,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        ok = self._redis.cache_session_context(session_id, context, ttl=1800)
        if ok:
            logger.debug(
                "Workflow 上下文已缓存: session=%s, memory=%d, knowledge=%d",
                session_id,
                len(response.trace.memory_hits),
                len(response.trace.knowledge_hits),
            )
        else:
            logger.debug("Workflow 上下文缓存失败: session=%s", session_id)

    async def _try_save_memory(
        self,
        *,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_reply: str,
        safety_level: str,
    ) -> None:
        """目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        # 高风险对话不写入记忆，避免敏感内容被持久化
        if user_id.startswith("guest:"):
            logger.debug("匿名访客不写入长期记忆: user_id=%s", user_id)
            return
        if safety_level == "high":
            logger.debug("安全级别为 high，跳过记忆保存: user_id=%s", user_id)
            self._record_memory_audit(
                action="memory.outbox_skipped",
                user_id=user_id,
                session_id=session_id,
                reason_code="high_safety_risk",
            )
            return
        if not self.memory_settings_repository.is_enabled(user_id):
            logger.debug("用户未开启长期记忆，跳过 Outbox: user_id=%s", user_id)
            return

        policy_result = self.memory_policy_service.evaluate_raw_text(
            user_message=user_message,
            assistant_reply=assistant_reply,
        )
        if not policy_result.allowed:
            logger.info(
                "长期记忆原始文本命中隐私规则，跳过 Outbox: user_id=%s reason=%s matched=%s",
                user_id,
                policy_result.reason_code,
                ",".join(policy_result.matched_types),
            )
            self._record_memory_audit(
                action="memory.outbox_skipped",
                user_id=user_id,
                session_id=session_id,
                reason_code=policy_result.reason_code,
                matched_types=list(policy_result.matched_types),
            )
            return

        event = build_memory_extraction_message(
            user_id=user_id,
            session_id=session_id,
            user_message=user_message,
            assistant_reply=assistant_reply,
        )

        payload = event.to_payload()
        try:
            outbox_id = self.memory_outbox_repository.save_pending(
                payload,
                error="queued_for_docker_outbox_relay",
            )
            logger.debug(
                "长期记忆事件已写入 Outbox，等待 Docker Relay 投递: user_id=%s, event_id=%s, task_id=%s, outbox_id=%s",
                user_id,
                event.event_id,
                event.task_id,
                outbox_id,
            )
        except Exception as exc:
            logger.error(
                "长期记忆事件写入 Outbox 失败: user_id=%s, event_id=%s, task_id=%s, error=%s",
                user_id,
                event.event_id,
                event.task_id,
                exc,
            )

    def _record_memory_audit(
        self,
        *,
        action: str,
        user_id: str,
        session_id: str,
        reason_code: str,
        matched_types: list[str] | None = None,
    ) -> None:
        """目的：记录长期记忆治理审计，失败不影响聊天主链路。
        结果：隐私跳过、高风险跳过等动作可被后台审计追踪。
        """
        self.memory_audit_repository.record(
            action=action,
            user_id=user_id,
            resource_id=session_id,
            detail_json={
                "session_id": session_id,
                "reason_code": reason_code,
                "matched_types": matched_types or [],
            },
        )

    async def _run_stream_task(self, stream_id: str, request: ChatRequest) -> None:
        """目的：在后台执行流式生成，并把事件广播给在线订阅者。
        结果：前端断开后任务仍可继续；主动取消时统一由服务端停止上游。
        """
        saw_done = False
        saw_error = False
        try:
            async for chunk in self.stream_reply(request, stream_id=stream_id):
                event_name = self._extract_event_name(chunk)
                if event_name == "done":
                    saw_done = True
                elif event_name == "error":
                    saw_error = True
                await self.stream_task_registry.publish(stream_id, chunk)
        except asyncio.CancelledError:
            await self.stream_task_registry.mark_terminal(stream_id, "cancelled")
            await self.stream_task_registry.close_subscribers(stream_id)
            logger.info("后台流任务已取消: stream_id=%s, session=%s", stream_id, request.session_id)
            raise
        except Exception as exc:
            logger.exception("后台流任务执行失败: stream_id=%s, error=%s", stream_id, exc)
            await self.stream_task_registry.mark_terminal(
                stream_id,
                "failed",
                error_message=str(exc),
            )
            await self.stream_task_registry.publish(
                stream_id,
                format_sse_event("error", {"message": "流式输出失败"}),
            )
            await self.stream_task_registry.close_subscribers(stream_id)
            return

        final_status = "failed" if saw_error and not saw_done else "completed"
        await self.stream_task_registry.mark_terminal(stream_id, final_status)
        await self.stream_task_registry.close_subscribers(stream_id)
