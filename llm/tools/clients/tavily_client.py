"""Tavily 搜索直接 REST API 客户端。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from llm.retry import async_retry_call
from llm.tools.base import BaseToolClient

logger = logging.getLogger(__name__)


class TavilyClient(BaseToolClient):
    """Tavily 搜索直接 REST API 客户端。
    
    目的：封装Tavily 搜索直接 REST API 客户端相关的调用能力与资源管理。
    结果：上层可通过统一客户端接口完成访问。
    """

    def __init__(self, api_key: str) -> None:
        """初始化 TavilyClient。
        
        目的：初始化TavilyClient所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        super().__init__()
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)
        self._initialized = True

    async def list_tools(self) -> list[dict[str, Any]]:
        """返回当前可用的列表结果。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        tools = [{
            "name": "tavily_search",
            "description": (
                "执行网络搜索，查询实时信息、新闻、天气、最新数据等外部事实。"
                "用于用户询问需要最新资讯、实时数据或你不确定的事实时。"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询字符串，应简洁、明确，包含关键实体。",
                    },
                    "search_depth": {
                        "type": "string",
                        "description": "搜索深度，支持 basic 或 advanced。",
                        "default": "basic",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回结果数，默认 5。",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        }]
        self._cached_tools = tools
        self._tools_loaded = True
        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """调用目标能力并返回执行结果。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        if tool_name != "tavily_search":
            return {"error": f"未知 Tavily 工具: {tool_name}"}

        return await self.search(
            query=str(arguments.get("query", "")),
            search_depth=str(arguments.get("search_depth", "basic")),
            max_results=int(arguments.get("max_results", 5)),
        )

    async def close(self) -> None:
        """关闭并释放相关资源。

        目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        await self._client.aclose()

    async def search(
        self,
        query: str,
        search_depth: str = "basic",
        max_results: int = 5,
    ) -> dict[str, Any]:
        """执行 search 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        try:
            response = await async_retry_call(
                lambda: self._client.post(
                    "https://api.tavily.com/search",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query,
                        "search_depth": search_depth,
                        "max_results": max_results,
                        "include_answer": True,
                    },
                )
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.warning("Tavily 搜索失败: %s", exc)
            return {
                "error": str(exc),
                "results": [],
                "query": query,
            }
