"""LLM 客户端 Facade：统一大语言模型调用入口。

目的：封装底层 Provider 切换逻辑，根据 llm_provider 配置动态选择实现。
结果：上层 nodes.py 无需感知 Provider 差异，统一调用 generate/generate_stream 接口。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from contracts.chat import ChatReplyModel, MemoryDecision
from core.config import get_settings
from llm.factory import build_llm_provider
from llm.providers import LlmProvider
from llm.core.types import LlmMessage, McpCallInfo
from observability import traceable_chain
from prompt import PromptSpec

logger = logging.getLogger(__name__)


class LlmClient:
    """统一大语言模型客户端：委托给对应 Provider 执行。
    
    目的：封装统一大语言模型客户端：委托给对应 Provider 执行相关的调用能力与资源管理。
    结果：上层可通过统一客户端接口完成访问。
    """

    def __init__(self) -> None:
        """初始化 LlmClient。
        
        目的：初始化LlmClient所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        self.settings = get_settings()
        self._provider: LlmProvider = build_llm_provider(self.settings)

    @traceable_chain("llm.generate")
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[LlmMessage] | None = None,
    ) -> str:
        """非流式生成：直接返回完整响应文本。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        reply, _ = await self._provider.generate(system_prompt, user_prompt, history=history)
        return reply

    def get_mcp_calls(self) -> list[McpCallInfo]:
        """获取最近一次 generate() 调用的 MCP 调用追踪信息。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        if hasattr(self._provider, "_mcp_calls"):
            return list(self._provider._mcp_calls)  # type: ignore[attr-defined]
        return []

    def get_mcp_tools_info(self) -> list[dict[str, Any]]:
        """获取当前 Provider 注册的 MCP 工具信息。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        if hasattr(self._provider, "_mcp_tools"):
            return list(self._provider._mcp_tools)  # type: ignore[attr-defined]
        return []

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[LlmMessage] | None = None,
    ) -> AsyncIterator[tuple[str, list[McpCallInfo]]]:
        """流式生成：逐步返回响应内容。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        async for chunk in self._provider.generate_stream(
            system_prompt, user_prompt, history=history
        ):
            yield chunk

    @traceable_chain("llm.finalize_chat_reply")
    async def finalize_chat_reply(
        self,
        prompt_spec: PromptSpec,
    ) -> ChatReplyModel:
        """工具 / MCP 完成后，基于 provider 缓存的上下文生成最终结构化回复。"""
        payload, _ = await self._provider.finalize_chat_reply(prompt_spec)
        return payload

    @traceable_chain("llm.decide_memory")
    async def decide_memory(
        self,
        prompt_spec: PromptSpec,
        *,
        history: list[LlmMessage] | None = None,
    ) -> MemoryDecision:
        """执行长期记忆决策专用 structured 输出。"""
        payload, _ = await self._provider.decide_memory(prompt_spec, history=history)
        return payload

    def has_pending_tool_history(self) -> bool:
        """返回 provider 是否保留了待终结的工具上下文。"""
        return self._provider.has_pending_tool_history()

    def generate_sync(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[LlmMessage] | None = None,
    ) -> str:
        """同步调用 LLM：用于 Celery Worker 和非异步上下文。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        messages: list[LlmMessage] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.deepseek_model,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"] or ""
