"""MCP 传输抽象层。

目的：定义传输层的抽象接口规范，使上层业务逻辑与具体传输实现解耦。
结果：可灵活切换 HTTP、WebSocket 等不同传输方式，无需修改业务代码。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mcp.types import McpTool


class BaseMcpTransport(ABC):
    """MCP 传输统一接口抽象基类。

    目的：规范所有传输实现类必须提供的方法签名，保证接口一致性。
    结果：上层调用方通过此接口操作传输层，不感知具体实现细节。
    """

    @abstractmethod
    async def list_tools(self) -> list[McpTool]:
        """获取 MCP 服务器上注册的所有可用工具列表。

        目的：发现服务端提供的工具能力，供调用方选择使用。
        结果：返回工具元数据列表，包含名称、描述和输入参数模式。
        """

    @abstractmethod
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """调用指定名称的工具并传入参数执行。

        目的：执行远程工具逻辑并获取结果。
        结果：返回工具执行结果，包含内容列表和错误状态信息。
        """

    @abstractmethod
    async def close(self) -> None:
        """关闭传输连接并释放相关资源。

        目的：安全终止会话，清理网络连接和状态。
        结果：连接关闭，后续操作需重新初始化会话。
        """
