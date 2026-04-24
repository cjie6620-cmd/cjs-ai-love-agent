from __future__ import annotations

from typing import Any

import pytest

from llm.core.types import McpCallInfo
from llm.providers.xai_router import XaiRouterProvider
from llm.tools.clients import McpToolClient
from llm.tools.registry import ToolRegistry
from mcp.errors import McpTransportError


class FakeTransport:
    """FakeTransport 测试替身对象。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """
    def __init__(
        self,
        tools: list[dict[str, Any]] | None = None,
        result: dict[str, Any] | None = None,
        should_fail: bool = False,
    ) -> None:
        """初始化 FakeTransport 实例。

        目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self.tools = tools or []
        self.result = result or {"content": [{"type": "text", "text": "ok"}]}
        self.should_fail = should_fail
        self.list_calls = 0
        self.call_calls = 0
        self.closed = False

    async def list_tools(self) -> list[dict[str, Any]]:
        """返回当前可用的列表结果。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        self.list_calls += 1
        if self.should_fail:
            raise McpTransportError("boom")
        return self.tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """调用目标能力并返回执行结果。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        self.call_calls += 1
        if self.should_fail:
            raise McpTransportError(f"failed: {tool_name}")
        return {
            **self.result,
            "tool_name": tool_name,
            "arguments": arguments,
        }

    async def close(self) -> None:
        """关闭并释放相关资源。

        目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        self.closed = True


class FakeSearchClient:
    """FakeSearchClient 测试替身对象。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """
    async def ensure_tools_loaded(self) -> list[dict[str, Any]]:
        """确保目标资源处于可用状态。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        return [{
            "name": "tavily_search",
            "description": "search",
            "inputSchema": {"type": "object", "properties": {}},
        }]


class FlakyTransport(FakeTransport):
    """首轮失败、后续成功的传输测试替身。"""

    def __init__(self, tools: list[dict[str, Any]]) -> None:
        super().__init__(tools=tools)
        self._should_fail_once = True

    async def list_tools(self) -> list[dict[str, Any]]:
        self.list_calls += 1
        if self._should_fail_once:
            self._should_fail_once = False
            raise McpTransportError("temporary unavailable")
        return self.tools


@pytest.mark.asyncio
async def test_mcp_tool_client_caches_tools_after_first_load() -> None:
    """验证 mcp tool client caches tools after first load。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    transport = FakeTransport(tools=[{
        "name": "amap_weather",
        "description": "weather",
        "inputSchema": {"type": "object", "properties": {}},
    }])
    client = McpToolClient(transport=transport)

    first = await client.ensure_tools_loaded()
    second = await client.ensure_tools_loaded()

    assert first == second
    assert transport.list_calls == 1


@pytest.mark.asyncio
async def test_mcp_tool_client_call_with_tracking_contains_error() -> None:
    """验证 mcp tool client call with tracking contains error。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    transport = FakeTransport(should_fail=True)
    client = McpToolClient(transport=transport)
    calls: list[McpCallInfo] = []

    result = await client.call_with_tracking(
        tool_name="amap_route",
        arguments={"origin": "a", "destination": "b"},
        call_list=calls,
        server_label="amap",
    )

    assert "error" in result
    assert calls[0].status == "error"
    assert calls[0].tool_name == "amap_route"


@pytest.mark.asyncio
async def test_tool_registry_loads_generic_mcp_tools() -> None:
    """验证 tool registry loads generic mcp tools。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    transport = FakeTransport(tools=[{
        "name": "amap_geocode",
        "description": "geo",
        "inputSchema": {"type": "object", "properties": {"address": {"type": "string"}}},
    }])
    registry = ToolRegistry(
        mcp_client=McpToolClient(transport=transport),
        tavily_client=FakeSearchClient(),
        mcp_server_name="高德地图",
    )

    await registry.load_mcp_tools()
    functions = registry.get_all_functions()

    assert registry.mcp_tool_count == 1
    assert [item["function"]["name"] for item in functions] == ["amap_geocode", "tavily_search"]


@pytest.mark.asyncio
async def test_mcp_tool_client_retries_after_initial_load_failure() -> None:
    """验证首次失败后，下次加载仍可恢复。"""
    transport = FlakyTransport(tools=[{
        "name": "amap_weather",
        "description": "weather",
        "inputSchema": {"type": "object", "properties": {}},
    }])
    client = McpToolClient(transport=transport)

    first = await client.ensure_tools_loaded()
    second = await client.ensure_tools_loaded()

    assert first == []
    assert second[0]["name"] == "amap_weather"
    assert transport.list_calls == 2


@pytest.mark.asyncio
async def test_xai_router_marks_tools_loaded_only_after_success() -> None:
    """验证 provider 在首次失败后允许下一次继续加载。"""
    provider = object.__new__(XaiRouterProvider)
    provider._mcp_client = object()
    provider._tools_loaded = False

    class _FlakyRegistry:
        def __init__(self) -> None:
            self.calls = 0

        async def load_mcp_tools(self) -> bool:
            self.calls += 1
            return self.calls > 1

    registry = _FlakyRegistry()
    provider._tool_registry = registry

    await provider._ensure_tools_loaded()
    assert provider._tools_loaded is False

    await provider._ensure_tools_loaded()
    assert provider._tools_loaded is True


@pytest.mark.asyncio
async def test_xai_router_routes_tavily_and_mcp_without_cross_talk() -> None:
    """验证 xai router routes tavily and mcp without cross talk。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    provider = object.__new__(XaiRouterProvider)
    provider._tavily_client = object()
    provider._mcp_client = object()

    async def fake_tavily(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"source": "tavily", "tool_name": tool_name, "arguments": arguments}

    async def fake_mcp(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"source": "mcp", "tool_name": tool_name, "arguments": arguments}

    provider._execute_tavily_call_async = fake_tavily  # type: ignore[method-assign]
    provider._execute_mcp_call_async = fake_mcp  # type: ignore[method-assign]

    tavily_result = await provider._execute_tool_call_async("tavily_search", {"query": "news"})
    mcp_result = await provider._execute_tool_call_async("amap_geocode", {"address": "beijing"})

    assert tavily_result["source"] == "tavily"
    assert mcp_result["source"] == "mcp"
