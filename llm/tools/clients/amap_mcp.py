"""高德地图 MCP 适配层。"""

from __future__ import annotations

from llm.tools.clients.mcp_tool_client import McpToolClient


class AmapMcpClient(McpToolClient):
    """目的：封装语义化命名的高德地图 MCP 客户端相关的调用能力与资源管理。
    结果：上层可通过统一客户端接口完成访问。
    """
