"""MCP 工具适配层：桥接协议客户端与统一工具接口。"""

from __future__ import annotations

from typing import Any

from llm.tools.base import BaseToolClient
from mcp.transport import BaseMcpTransport


class McpToolClient(BaseToolClient):
    """目的：封装统一工具接口下的 MCP 适配客户端相关的调用能力与资源管理。
    结果：上层可通过统一客户端接口完成访问。
    """

    def __init__(
        self,
        transport: BaseMcpTransport,
    ) -> None:
        """目的：初始化McpToolClient所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        super().__init__()
        self._transport = transport
        self._initialized = True

    async def list_tools(self) -> list[dict[str, Any]]:
        """目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        return [dict(tool) for tool in await self._transport.list_tools()]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        return await self._transport.call_tool(tool_name, arguments)

    async def close(self) -> None:
        """目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        await self._transport.close()
