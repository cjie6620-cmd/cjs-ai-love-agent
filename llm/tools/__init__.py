"""LLM 工具层：统一管理 MCP 客户端、Tavily 客户端和工具注册表。

目的：提供统一的工具调用接口，支持 MCP HTTP 协议和 Tavily REST API 两种工具来源。
结果：上层 Provider 无需感知底层工具协议差异，统一通过工具注册表获取函数定义和调用结果。
"""

from __future__ import annotations

from llm.tools.base import BaseToolClient
from llm.tools.clients import AmapMcpClient, McpToolClient, TavilyClient
from llm.tools.registry import ToolRegistry

__all__ = [
    "AmapMcpClient",
    "BaseToolClient",
    "McpToolClient",
    "TavilyClient",
    "ToolRegistry",
]
