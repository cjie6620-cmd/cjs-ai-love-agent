"""LangGraph 工作流入口：桥接 StateGraph 与 ChatService 调用约定。

设计目的：将 LangGraph 编译后的图封装为 ChatService 可直接调用的 run()/stream() 接口，
作为当前唯一的对话工作流实现，对外提供稳定的请求/响应与流式输出协议。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from contracts.chat import (
    ChatRequest,
    ChatResponse,
    ChatTrace,
    ConversationHistoryMessage,
)
from observability import TraceSanitizer, get_langsmith_service, traceable_chain
from stream import format_sse_event

from . import compiler
from .graph_state import CompanionState
from .nodes import (
    _build_chat_reply_fallback,
    _filter_meaningful_mcp_calls,
    build_advisor_draft,
    build_local_chat_reply,
    finalize_advisor,
    build_reply_generation_context,
    build_safe_fallback_reply,
    build_tool_final_prompt_context,
    output_guard,
    recall_memory,
    safety_check,
    search_knowledge,
)
from .runtime import (
    WorkflowRuntime,
    activate_workflow_runtime,
    build_workflow_runtime,
    reset_workflow_runtime,
)

logger = logging.getLogger(__name__)


def _aggregate_stream_chunks(outputs: list[str]) -> str:
    """_aggregate_stream_chunks 方法。
    
    目的：执行_aggregate_stream_chunks 方法相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return "".join(outputs)


def _iter_text_chunks(text: str, *, chunk_size: int = 8) -> list[str]:
    """把最终文本切成小块，保持前端打字机体验。"""
    if not text:
        return []
    return [text[index:index + chunk_size] for index in range(0, len(text), chunk_size)]


def _build_initial_state(
    request: ChatRequest,
    recent_messages: list[ConversationHistoryMessage] | None,
    *,
    risk_level: str,
    langsmith_metadata: dict[str, object] | None,
) -> CompanionState:
    """从 ChatRequest 构建 LangGraph 初始状态。
    
    目的：执行从 ChatRequest 构建 LangGraph 初始状态相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return CompanionState(
        request=request,
        recent_messages=recent_messages,
        safety_level="low",  # 由 safety_check 节点更新
        advisor_draft=None,
        memory_hits=[],
        knowledge_hits=[],
        knowledge_evidences=[],
        matched_topics=[],
        retrieval_query="",
        evidence_status="no_grounding",
        answer_confidence="low",
        answer_confidence_reason="暂无可验证证据，回答可信度较低。",
        rerank_applied=False,
        prompt_version="",
        output_contract_version="",
        fallback_reason="",
        reply="",
        reply_structured=None,
        advisor=None,
        mode=request.mode,
        streaming_chunks=[],
        mcp_calls=[],
        metadata={
            "risk_level": risk_level,
            "langsmith_metadata": langsmith_metadata or {},
        },
    )


def _state_to_response(
    state: CompanionState,
    request: ChatRequest,
) -> ChatResponse:
    """从最终状态构建 ChatResponse。
    
    目的：执行从最终状态构建 ChatResponse相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    trace = ChatTrace(
        memory_hits=state.get("memory_hits") or [],
        knowledge_hits=state.get("knowledge_hits") or [],
        knowledge_evidences=state.get("knowledge_evidences") or [],
        retrieval_query=state.get("retrieval_query") or "",
        safety_level=state.get("safety_level") or "low",
        mcp_calls=state.get("mcp_calls") or [],
        prompt_version=state.get("prompt_version") or "",
        output_contract_version=state.get("output_contract_version") or "",
        evidence_status=state.get("evidence_status") or "no_grounding",
        answer_confidence=state.get("answer_confidence") or "low",
        answer_confidence_reason=state.get("answer_confidence_reason") or "",
        rerank_applied=bool(state.get("rerank_applied")),
        fallback_reason=state.get("fallback_reason") or "",
    )
    return ChatResponse(
        reply=state.get("reply") or "",
        mode=request.mode,
        trace=trace,
        advisor=state.get("advisor"),
    )


class CompanionGraphWorkflow:
    """LangGraph 驱动的对话工作流：委托给编译后的 StateGraph。

    目的：定义运行时依赖或协作边界，统一工作流节点之间的调用约束。
    结果：相关模块可以围绕相同接口稳定协作，降低接入和替换成本。
    """

    def __init__(self, runtime: WorkflowRuntime | None = None) -> None:
        """初始化 CompanionGraphWorkflow。
        
        目的：初始化CompanionGraphWorkflow所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        self.runtime = runtime or build_workflow_runtime()
        self.graph = compiler.get_compiled_graph()

    async def run(
        self,
        request: ChatRequest,
        *,
        recent_messages: list[ConversationHistoryMessage] | None = None,
        risk_level: str = "low",
        langsmith_metadata: dict[str, object] | None = None,
    ) -> ChatResponse:
        """执行非流式对话工作流（LangGraph ainvoke）。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        initial_state = _build_initial_state(
            request,
            recent_messages,
            risk_level=risk_level,
            langsmith_metadata=langsmith_metadata,
        )
        langsmith = get_langsmith_service()
        config: dict[str, object] = {
            "configurable": {
                "thread_id": TraceSanitizer.thread_id(request.session_id),
            },
            "run_name": "companion_graph.run",
            "tags": langsmith.build_tags(
                mode=request.mode,
                risk_level=risk_level,
                provider=langsmith.settings.llm_provider,
                stream=False,
            ),
            "metadata": langsmith_metadata or {},
        }

        runtime_token = activate_workflow_runtime(self.runtime)
        try:
            with langsmith.tracing_scope():
                final_state = await self.graph.ainvoke(initial_state, config=config)
            return _state_to_response(final_state, request)
        except Exception as exc:
            logger.error("LangGraph 工作流执行失败: %s", exc)
            # 降级：返回空回复（ChatService 侧捕获异常）
            return ChatResponse(
                reply="抱歉，服务处理时遇到了问题，请稍后再试。",
                mode=request.mode,
                trace=ChatTrace(
                    memory_hits=[],
                    knowledge_hits=[],
                    retrieval_query="",
                    safety_level="low",
                ),
                advisor=None,
            )
        finally:
            reset_workflow_runtime(runtime_token)

    @traceable_chain("companion_graph.stream", reduce_fn=_aggregate_stream_chunks)
    async def stream(
        self,
        request: ChatRequest,
        *,
        recent_messages: list[ConversationHistoryMessage] | None = None,
        risk_level: str = "low",
        langsmith_metadata: dict[str, object] | None = None,
    ) -> AsyncIterator[str]:
        """执行流式对话工作流。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        initial_state = _build_initial_state(
            request,
            recent_messages,
            risk_level=risk_level,
            langsmith_metadata=langsmith_metadata,
        )
        langsmith = get_langsmith_service()

        runtime_token = activate_workflow_runtime(self.runtime)
        try:
            state = initial_state
            with langsmith.tracing_scope():
                state.update(await safety_check(state))
                state.update(build_advisor_draft(state))

                # 记忆召回和知识检索互不依赖，这里并发执行，减少首次 token 前的等待时间。
                memory_update, knowledge_update = await asyncio.gather(
                    recall_memory(state),
                    search_knowledge(state),
                )
                state.update(memory_update)
                state.update(knowledge_update)

                safe_reply = build_safe_fallback_reply(state["safety_level"])
                if safe_reply is not None:
                    structured = _build_chat_reply_fallback(
                        reply_text=safe_reply,
                        mode=state["mode"],
                        evidence_status=state["evidence_status"],
                        used_memory=bool(state["memory_hits"]),
                        fallback_reason="safety_short_circuit",
                        safety_level=state["safety_level"],
                    )
                    state.update({
                        "reply": safe_reply,
                        "reply_structured": structured,
                        "fallback_reason": structured.fallback_reason,
                        "prompt_version": "chat.reply.v1",
                        "output_contract_version": "chat_reply_text.v2",
                    })
                else:
                    prompt_spec, history = build_reply_generation_context(state)
                    client = self.runtime.build_llm_client()

                    yield self._format_sse("thinking_start", {})
                    yield self._format_sse("thinking_delta", {"content": "正在组织回复结构"})
                    if state["memory_hits"]:
                        yield self._format_sse(
                            "thinking_delta",
                            {"content": f"已吸收 {len(state['memory_hits'])} 条相关记忆线索"},
                        )
                    if state["knowledge_evidences"]:
                        yield self._format_sse(
                            "thinking_delta",
                            {"content": f"已命中 {len(state['knowledge_evidences'])} 条知识证据"},
                        )
                    yield self._format_sse("thinking_done", {})

                    streamed_reply_parts: list[str] = []
                    async for chunk, _ in client.generate_stream(
                        prompt_spec.render_system_prompt(),
                        prompt_spec.render_user_prompt(),
                        history=history,
                    ):
                        streamed_reply_parts.append(chunk)
                        state["streaming_chunks"].append(chunk)
                        yield self._format_sse("token", {"content": chunk})

                    raw_reply = "".join(streamed_reply_parts).strip()
                    reply = raw_reply or "抱歉，我刚才没有组织好这句话，我们再试一次。"

                    mcp_calls = client.get_mcp_calls()
                    meaningful_calls = _filter_meaningful_mcp_calls(mcp_calls)

                    if meaningful_calls and client.has_pending_tool_history():
                        final_prompt_spec = build_tool_final_prompt_context(state)
                        structured = await client.finalize_chat_reply(final_prompt_spec)
                        if not structured.reply_text.strip():
                            structured = structured.model_copy(
                                update={
                                    "reply_text": reply,
                                    "fallback_reason": structured.fallback_reason or "empty_reply",
                                }
                            )
                        reply = structured.reply_text
                        prompt_version = final_prompt_spec.prompt_version
                        output_contract_version = final_prompt_spec.output_contract_version
                    else:
                        structured = build_local_chat_reply(
                            reply_text=reply,
                            mode=state["mode"],
                            evidence_status=state["evidence_status"],
                            used_memory=bool(state["memory_hits"]),
                            safety_level=state["safety_level"],
                            knowledge_evidences=state["knowledge_evidences"],
                            fallback_reason="empty_reply" if not raw_reply else None,
                        )
                        prompt_version = prompt_spec.prompt_version
                        output_contract_version = prompt_spec.output_contract_version

                    state.update({
                        "reply": reply,
                        "reply_structured": structured,
                        "prompt_version": prompt_version,
                        "output_contract_version": output_contract_version,
                        "fallback_reason": structured.fallback_reason,
                    })
                    if meaningful_calls:
                        state["mcp_calls"] = meaningful_calls

                state.update(finalize_advisor(state))
                state.update(output_guard(state))

                response = _state_to_response(state, request)
                response.trace.knowledge_hits = [
                    TraceSanitizer.summarize_text(item, limit=100)
                    for item in response.trace.knowledge_hits
                ]
                response.trace.knowledge_evidences = [
                    item.model_copy(
                        update={
                            "snippet": TraceSanitizer.summarize_text(item.snippet, limit=120),
                        }
                    )
                    for item in response.trace.knowledge_evidences
                ]
                response.trace.memory_hits = [
                    {
                        **hit,
                        "content": TraceSanitizer.summarize_text(hit["content"], limit=100),
                    }
                    for hit in response.trace.memory_hits
                ]
                yield self._format_sse("done", response.model_dump())

        except Exception as exc:
            logger.error("LangGraph 流式工作流执行失败: %s", exc)
            yield self._format_sse("error", {"message": str(exc)})
        finally:
            reset_workflow_runtime(runtime_token)

    @staticmethod
    def _format_sse(event: str, payload: dict[str, object]) -> str:
        """格式化 SSE 事件数据，保持现有聊天接口协议不变。

        目的：按约定协议整理输出内容，统一格式细节。
        结果：返回格式一致的结果，降低上下游对接成本。
        """
        return format_sse_event(event, payload)
