"""LLM 模块核心层：类型定义和接口协议。

目的：定义 LLM 提供者标准接口和数据类型，作为整个 LLM 模块的基础抽象层。
结果：导出 LlmMessage、McpCallInfo、McpTool、OpenAIFunction、ToolResult、LlmConfig 等核心类型。
"""

from __future__ import annotations

from .types import (
    LlmConfig,
    LlmMessage,
    McpCallInfo,
    McpTool,
    OpenAIFunction,
    ToolResult,
)

__all__ = [
    "LlmMessage",
    "McpCallInfo",
    "McpTool",
    "OpenAIFunction",
    "ToolResult",
    "LlmConfig",
]
