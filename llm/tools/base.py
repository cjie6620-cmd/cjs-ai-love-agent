"""LLM 工具层基类：定义工具客户端的统一接口和通用逻辑。

目的：抽象工具调用的通用模式（list_tools, call_tool），统一管理不同类型的工具客户端。
结果：上层 Provider 通过统一的工具客户端接口调用 MCP 工具或 Tavily 搜索，无需感知底层协议差异。
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from json import dumps
from typing import TYPE_CHECKING, Any

from observability import traceable_tool

if TYPE_CHECKING:
    from llm.core.types import McpCallInfo

logger = logging.getLogger(__name__)


class BaseToolClient(ABC):
    """目的：封装工具客户端抽象基类：定义工具客户端的通用接口相关的调用能力与资源管理。
    结果：上层可通过统一客户端接口完成访问。
    """

    def __init__(self) -> None:
        """目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self._initialized = False
        self._tools_loaded = False
        self._cached_tools: list[dict[str, Any]] = []

    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        """目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """

    @abstractmethod
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """

    @traceable_tool("tool.call_with_tracking")
    async def call_with_tracking(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        call_list: list["McpCallInfo"],
        server_label: str,
    ) -> dict[str, Any]:
        """目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        from llm.core.types import McpCallInfo

        start_time = time.monotonic()
        try:
            result = await self.call_tool(tool_name, arguments)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            error_message = None
            if isinstance(result, dict) and result.get("error"):
                error_message = str(result["error"])

            if error_message:
                logger.warning("工具 [%s] 调用失败: %s", tool_name, error_message)
                call_list.append(McpCallInfo(
                    server_label=server_label,
                    tool_name=tool_name,
                    status="error",
                    duration_ms=duration_ms,
                    input_summary=str(arguments)[:200],
                    error_message=error_message,
                ))
            else:
                call_list.append(McpCallInfo(
                    server_label=server_label,
                    tool_name=tool_name,
                    status="success",
                    duration_ms=duration_ms,
                    input_summary=str(arguments)[:200],
                    output_summary=dumps(result, ensure_ascii=False, default=str)[:200],
                ))
            return result
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning("工具 [%s] 调用失败: %s", tool_name, exc)
            call_list.append(McpCallInfo(
                server_label=server_label,
                tool_name=tool_name,
                status="error",
                duration_ms=duration_ms,
                input_summary=f"调用异常: {str(exc)[:200]}",
                error_message=str(exc),
            ))
            return {"error": str(exc)}

    async def close(self) -> None:
        """目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        pass

    async def ensure_tools_loaded(self) -> list[dict[str, Any]]:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        if not self._tools_loaded:
            try:
                self._cached_tools = await self.list_tools()
                self._tools_loaded = True
                logger.debug("工具列表已重新加载")
            except Exception as exc:
                logger.warning("工具列表加载失败: %s", exc)
                self._cached_tools = []
        return self._cached_tools
