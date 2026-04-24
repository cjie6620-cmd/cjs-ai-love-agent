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

from contracts.chat import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryItem,
    ConversationHistoryMessage,
    ConversationHistoryResponse,
)
from observability import get_langsmith_service
from persistence import ConversationRepository
from security import RedisService, SafetyGuard

from .memory import MemoryManager, SessionMemoryManager
from .workflows import CompanionGraphWorkflow, build_workflow_runtime

logger = logging.getLogger(__name__)

DEFAULT_CONVERSATION_HISTORY_TIMEOUT_SECONDS = 3.0


class AgentService:
    """对外提供稳定服务入口，协调工作流、记忆和缓存组件。

    目的：承载聚合后的业务能力，对外暴露稳定且清晰的调用入口。
    结果：上层模块可以直接复用核心能力，减少重复编排并提升可维护性。
    """

    def __init__(
        self,
        redis_service: RedisService | None = None,
        *,
        workflow: CompanionGraphWorkflow | None = None,
        conversation_repository: ConversationRepository | None = None,
        memory_manager: MemoryManager | None = None,
        session_memory: SessionMemoryManager | None = None,
        safety_guard: SafetyGuard | None = None,
    ) -> None:
        """初始化 AgentService。
        
        目的：初始化AgentService所需的依赖、配置和初始状态。
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
        self.session_memory = session_memory or SessionMemoryManager(redis_service=redis_service)
        # Redis 服务：用于缓存 workflow 上下文（memory_hits / knowledge_hits）
        self._redis = redis_service or RedisService()
        # DB 同步方法在异步上下文中用线程池执行，避免阻塞事件循环
        self._db_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat_db_")

    def shutdown(self) -> None:
        """关闭服务，释放线程池资源。

        目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        self._db_executor.shutdown(wait=False, cancel_futures=True)

    async def reply(self, request: ChatRequest) -> ChatResponse:
        """处理非流式对话请求。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
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

        # 优先从 Redis 读取最近消息，Cache-Aside 读路径
        recent_messages = await self._get_recent_fast(request)

        # B2: 尝试从 Redis 读取上下文缓存（memory_hits / knowledge_hits）
        cached_context = self._redis.get_session_context(request.session_id)
        if cached_context:
            logger.debug(
                "上下文缓存命中: session=%s, memory_hits=%d, knowledge_hits=%d",
                request.session_id,
                len(cached_context.get("memory_hits", [])),
                len(cached_context.get("knowledge_hits", [])),
            )

        response = await self.workflow.run(
            request,
            recent_messages=recent_messages,
            risk_level=risk_level,
            langsmith_metadata=request_metadata,
        )

        # 主路径写 DB（持久化），同步仓储放到线程池，避免阻塞事件循环。
        await self._save_turn_async(request, response)

        # Cache-Aside 回填：同步写入 Redis 缓存
        self.session_memory.append_message(request.session_id, "user", request.message)
        self.session_memory.append_message(
            request.session_id,
            "assistant",
            response.reply,
            advisor=response.advisor,
        )

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
        return response

    async def stream_reply(self, request: ChatRequest) -> AsyncIterator[str]:
        """处理流式对话请求，逐块返回 SSE 数据。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
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

        # B2: Cache-Aside 读：优先 Redis，未命中则异步查 DB 回填
        recent_messages = await self._get_recent_fast(request)

        # B8: 尝试从 Redis 读取上下文缓存（memory_hits / knowledge_hits）
        cached_context = self._redis.get_session_context(request.session_id)
        if cached_context:
            logger.debug(
                "流式对话上下文缓存命中: session=%s, memory_hits=%d, knowledge_hits=%d",
                request.session_id,
                len(cached_context.get("memory_hits", [])),
                len(cached_context.get("knowledge_hits", [])),
            )

        # 写 Redis（不阻塞 SSE 流），用户消息 DB 保存改为 fire-and-forget
        self.session_memory.append_message(request.session_id, "user", request.message)
        asyncio.create_task(self._save_user_message_async(request))

        async for chunk in self.workflow.stream(
            request,
            recent_messages=recent_messages,
            risk_level=risk_level,
            langsmith_metadata=request_metadata,
        ):
            response = self._extract_done_response(chunk)
            if response is not None:
                # 写 Redis 即完成，DB 异步补写
                self.session_memory.append_message(
                    request.session_id,
                    "assistant",
                    response.reply,
                    advisor=response.advisor,
                )
                asyncio.create_task(self._save_assistant_message_async(request, response))
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
            yield chunk

    def list_conversations(self, user_id: str) -> ConversationHistoryResponse:
        """获取用户的历史会话列表。

        目的：按指定条件读取目标数据、资源或结果集合。
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
        """异步获取会话历史，避免同步查库阻塞事件循环。

        目的：通过线程池执行同步仓储查询，并在超时或异常时快速降级。
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

        return ConversationHistoryResponse(user_id=user_id, conversations=conversations)

    async def _get_recent_fast(
        self,
        request: ChatRequest,
        limit: int = 6,
    ) -> list[ConversationHistoryMessage]:
        """快速获取最近消息，优先 Redis 缓存。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        # 第一步：优先从 Redis 读取（O(1) 网络延迟），不阻塞事件循环
        redis_messages = self.session_memory.get_recent(request.session_id, limit=limit)
        if redis_messages:
            logger.debug(
                "短期记忆命中 Redis: session=%s, count=%d",
                request.session_id,
                len(redis_messages),
            )
            return [
                ConversationHistoryMessage(
                    id="",  # Redis 短期记忆不存储自增 ID
                    role=msg.role,
                    content=msg.content,
                    created_at=msg.created_at,
                    advisor=msg.advisor,
                )
                for msg in redis_messages
            ]

        # 第二步：Redis 未命中，异步查 DB（通过线程池，不阻塞事件循环）
        logger.debug(
            "短期记忆 Redis 未命中，异步查 DB 回填: session=%s",
            request.session_id,
        )
        try:
            loop = asyncio.get_running_loop()
            db_task = partial(
                self.conversation_repository.list_recent_messages,
                request.user_id,
                request.session_id,
                limit=limit,
            )
            db_messages: list[ConversationHistoryMessage] = await loop.run_in_executor(
                self._db_executor,
                db_task,
            )
        except Exception as exc:
            logger.warning(
                "异步查询 DB 失败，返回空列表: session=%s, error=%s",
                request.session_id,
                exc,
            )
            return []

        if not db_messages:
            return []

        # 第三步：回填 Redis（Cache-Aside 写路径）
        for msg in db_messages:
            self.session_memory.append_message(
                request.session_id,
                msg.role,
                msg.content,
                advisor=msg.advisor,
            )

        return db_messages

    async def _save_user_message_async(self, request: ChatRequest) -> None:
        """异步保存用户消息到数据库。

        目的：持久化、上传或补充目标数据，保持状态同步。
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
                "异步保存用户消息失败（Redis 已写入，数据未丢失）: session=%s, error=%s",
                request.session_id,
                exc,
            )

    async def _save_turn_async(self, request: ChatRequest, response: ChatResponse) -> None:
        """异步保存完整非流式对话轮次，避免同步数据库操作阻塞事件循环。"""
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
        """异步保存助手消息到数据库。

        目的：持久化、上传或补充目标数据，保持状态同步。
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
                "异步保存助手消息失败（Redis 已写入，数据未丢失）: session=%s, error=%s",
                request.session_id,
                exc,
            )

    def _extract_done_response(self, sse_payload: str) -> ChatResponse | None:
        """从 SSE 数据中提取最终回复。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        event_name = ""
        data_line = ""

        for line in sse_payload.splitlines():
            if line.startswith("event:"):
                event_name = line.replace("event:", "", 1).strip()
            elif line.startswith("data:"):
                data_line = line.replace("data:", "", 1).strip()

        if event_name != "done" or not data_line:
            return None

        try:
            return ChatResponse.model_validate(json.loads(data_line))
        except (ValueError, TypeError) as exc:
            logger.warning("解析 SSE done 事件失败，跳过持久化: %s", exc)
            return None

    def _cache_workflow_context(self, session_id: str, response: ChatResponse) -> None:
        """缓存工作流上下文到 Redis。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
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
        """对话结束后异步保存记忆到向量库。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        # 高风险对话不写入记忆，避免敏感内容被持久化
        if safety_level == "high":
            logger.debug("安全级别为 high，跳过记忆保存: user_id=%s", user_id)
            return

        # 优先尝试 Celery 异步任务（LLM 驱动的智能提炼）
        try:
            from .worker import extract_and_save_memory

            extract_and_save_memory.delay(
                user_id=user_id,
                user_message=user_message,
                assistant_reply=assistant_reply,
                session_id=session_id,
            )
            logger.debug("记忆保存已提交 Celery 异步任务: user_id=%s", user_id)
            return
        except Exception as exc:
            logger.debug("Celery 不可用，fallback 到同步 LLM 记忆提炼: %s", exc)

        # Fallback：直接走结构化记忆决策，不再依赖魔法字符串。
        try:
            decision = await self.memory_manager.decide_memory(
                user_message=user_message,
                assistant_reply=assistant_reply,
            )
            if not decision.should_store or not decision.memory_text:
                logger.debug(
                    "结构化记忆决策跳过保存: user_id=%s, reason=%s",
                    user_id,
                    decision.reason_code,
                )
                return

            await self.memory_manager.save_memory(
                user_id,
                decision.memory_text,
                memory_type=decision.memory_type,
                session_id=session_id,
            )
            logger.debug(
                "结构化记忆提炼完成: user_id=%s, type=%s, confidence=%.2f",
                user_id,
                decision.memory_type,
                decision.confidence,
            )
        except Exception as exc:
            # fire-and-forget：记忆保存失败不影响主对话流程
            logger.warning("记忆自动保存失败，跳过: user_id=%s, error=%s", user_id, exc)
