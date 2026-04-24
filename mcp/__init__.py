"""MCP (Model Context Protocol) 模块。

目的：提供 MCP 协议的类型定义、异常处理和传输层实现，支持与 MCP 服务器通信。
结果：AI 应用可通过此模块发现并调用远程工具，实现上下文扩展和能力增强。

模块结构：
- errors: 异常类型定义
- types: 数据结构定义
- transport: 传输层实现（HTTP）
"""

from __future__ import annotations

from mcp.errors import McpError, McpProtocolError, McpTimeoutError, McpTransportError
from mcp.transport import BaseMcpTransport, McpStreamableHttpTransport
from mcp.types import McpTool

__all__ = [
    "McpError",
    "McpProtocolError",
    "McpTimeoutError",
    "McpTransportError",
    "BaseMcpTransport",
    "McpStreamableHttpTransport",
    "McpTool",
]
