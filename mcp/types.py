"""MCP 类型定义模块：定义 MCP 协议中使用的数据类型。

目的：提供协议层数据结构定义，确保类型安全和序列化一致性。
结果：各模块间传递数据时保持类型统一，便于校验和调试。
"""
from __future__ import annotations

from typing import Any, TypedDict


class McpTool(TypedDict, total=False):
    """MCP 工具定义结构。

    目的：描述 MCP 工具的元数据信息，包括名称、描述和输入参数模式。
    结果：工具注册、调用和文档生成时可引用此结构，确保数据格式统一。
    """
    name: str
    description: str
    inputSchema: dict[str, Any]


class McpCallResult(TypedDict, total=False):
    """MCP 工具调用结果结构。

    目的：统一工具执行后的返回格式，包含内容、错误状态和错误信息。
    结果：调用方可根据 isError 字段判断执行是否成功，并获取相应内容或错误详情。
    """
    content: list[dict[str, Any]]
    isError: bool
    error: str
