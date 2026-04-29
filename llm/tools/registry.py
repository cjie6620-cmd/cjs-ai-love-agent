"""工具注册表：将 MCP 工具转换为 OpenAI Function 格式并统一管理。

目的：统一管理不同来源的工具定义，将 MCP 工具和 Tavily 工具转换为 OpenAI function 格式。
结果：提供简洁的函数定义接口，支持工具列表管理和系统提示词构建。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from llm.tools.base import BaseToolClient

logger = logging.getLogger(__name__)


class ToolRegistry:
    """目的：封装工具注册表：管理 MCP 工具和 Tavily 工具的函数定义相关能力。
    结果：对外提供稳定、可复用的调用入口。
    """

    def __init__(
        self,
        mcp_client: BaseToolClient | None = None,
        tavily_client: BaseToolClient | None = None,
        *,
        mcp_server_name: str = "高德地图",
    ) -> None:
        """目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self._mcp_client = mcp_client
        self._tavily_client = tavily_client
        self._mcp_server_name = mcp_server_name
        self._mcp_tools: list[dict[str, Any]] = []

    def convert_mcp_to_function(self, tool: dict[str, Any]) -> dict[str, Any]:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")
        input_schema = tool.get("inputSchema", {})

        # 处理 inputSchema 可能是字符串的情况
        if isinstance(input_schema, str):
            try:
                input_schema = json.loads(input_schema)
            except Exception:
                # JSON 解析失败时使用空 schema
                input_schema = {"type": "object", "properties": {}}
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            input_schema = {"type": "object", "properties": {}}

        return {
            "type": "function",
            "function": {
                "name": name,
                "description": desc or f"高德地图工具: {name}",
                "parameters": input_schema,
            },
        }

    def get_tavily_function(self) -> dict[str, Any]:
        """目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        return {
            "type": "function",
            "function": {
                "name": "tavily_search",
                "description": (
                    "执行网络搜索，查询实时信息、新闻、天气、最新数据等外部事实。"
                    "用于用户询问需要最新资讯、实时数据或你不确定的事实时。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询字符串，应简洁、明确，包含关键实体（如地点、人名、事件）。",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最大返回结果数，默认 5。",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    def get_all_functions(self) -> list[dict[str, Any]]:
        """目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        functions: list[dict[str, Any]] = []

        # 通用 MCP 工具
        for tool in self._mcp_tools:
            functions.append(self.convert_mcp_to_function(tool))

        # Tavily 直接 API 函数
        if self._tavily_client:
            functions.append(self.get_tavily_function())

        return functions

    def is_allowed_tool(self, tool_name: str) -> bool:
        """目的：避免模型幻觉出的未注册工具被执行。
        结果：返回 True 表示该工具名存在于当前可用函数列表。
        """
        return tool_name in {
            function["function"]["name"]
            for function in self.get_all_functions()
            if isinstance(function.get("function"), dict)
        }

    def build_system_prompt_tools_section(self) -> str:
        """目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        has_tools = bool(self._mcp_tools or self._tavily_client)
        if not has_tools:
            return ""

        tools_section = "\n\n【可调用工具】\n"

        # MCP 工具列表
        if self._mcp_tools:
            tool_names = [t.get("name", "?") for t in self._mcp_tools]
            tools_section += (
                f"{self._mcp_server_name}工具（共 {len(self._mcp_tools)} 个）："
                f"{', '.join(tool_names)}\n"
            )

        # Tavily 搜索说明
        if self._tavily_client:
            tools_section += "Tavily 网络搜索 (tavily_search)：用于查询实时信息、新闻、天气、最新数据。\n"

        # 使用原则
        tools_section += (
            "\n使用原则：\n"
            "- 不要为了炫耀工具而调用，只在真正需要外部信息时使用。\n"
            "- 如果用户只是聊天、倾诉、共情，不需要调用任何工具。\n"
            "- 调用工具后，将返回的信息自然融入回复中，不要原文复述工具输出。\n"
            "- 如果工具调用失败，记录错误并继续以无工具方式回复。\n"
            "- 当需要查询天气、地点、路线、地理编码时使用地图类 MCP 工具。\n"
            "- 当需要查询实时新闻、最新数据、网络信息时使用 tavily_search。\n"
        )

        return tools_section

    async def load_mcp_tools(self) -> bool:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        if not self._mcp_client:
            return False

        try:
            tools = await self._mcp_client.ensure_tools_loaded()
            self._mcp_tools = tools
            logger.info("MCP 工具已加载，共 %d 个", len(tools))
            for t in tools:
                logger.debug("  - %s: %s", t.get("name"), t.get("description", ""))
            return True
        except Exception as exc:
            logger.warning("MCP 工具加载失败: %s", exc)
            return False

    @property
    def has_tools(self) -> bool:
        """目的：按需获取并返回目标配置或资源，避免重复构建。
        结果：调用方可以拿到可直接使用的结果，简化后续处理。
        """
        return bool(self._mcp_tools or self._tavily_client)

    @property
    def mcp_tool_count(self) -> int:
        """目的：按需获取并返回目标配置或资源，避免重复构建。
        结果：调用方可以拿到可直接使用的结果，简化后续处理。
        """
        return len(self._mcp_tools)
