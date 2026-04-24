"""LLM Provider 统一接口定义。

目的：定义 LLM 提供者的标准 Protocol 接口，确保上层 LlmClient 透明调用底层实现。
结果：支持 XaiRouterProvider 和 DeepseekMcpProvider 等多种 Provider 实现。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from contracts.chat import ChatReplyModel, MemoryDecision
from llm.core.types import LlmMessage, McpCallInfo
from prompt import PromptSpec

# 对外暴露常用 Provider 类型，统一作为 providers 包入口。
from llm.providers.base import BaseLLmProvider
from llm.providers.openai_remote import DeepseekMcpProvider
from llm.providers.xai_router import XaiRouterProvider

__all__ = [
    "LlmProvider",
    "BaseLLmProvider",
    "XaiRouterProvider",
    "DeepseekMcpProvider",
]


class LlmProvider(Protocol):
    """LLM 提供者统一接口协议。
    
    目的：封装LLM 提供者统一接口协议相关的模型或能力实现。
    结果：上层可按统一 Provider 接口发起调用。
    """

    supports_structured_output: bool

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[LlmMessage] | None = None,
    ) -> tuple[str, list[McpCallInfo]]:
        """非流式生成：直接返回完整响应。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        ...

    def generate_stream(
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
        ...

    async def finalize_chat_reply(
        self,
        prompt_spec: PromptSpec,
    ) -> tuple[ChatReplyModel, list[McpCallInfo]]:
        """基于最近一次工具上下文生成最终结构化聊天回复。"""
        ...

    async def decide_memory(
        self,
        prompt_spec: PromptSpec,
        *,
        history: list[LlmMessage] | None = None,
    ) -> tuple[MemoryDecision, list[McpCallInfo]]:
        """执行长期记忆决策专用 structured 输出。"""
        ...

    def has_pending_tool_history(self) -> bool:
        """返回是否存在待终结的工具上下文。"""
        ...
