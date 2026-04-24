"""MCP Streamable HTTP 传输层测试。

目的：验证 McpStreamableHttpTransport 客户端的核心功能，包括会话管理、工具调用和 SSE 响应解析。
结果：确保传输层在各种场景下正确处理协议交互，捕获异常情况并抛出恰当错误。
"""

from __future__ import annotations

import json

import httpx
import pytest

from mcp.errors import McpProtocolError, McpTransportError
from mcp.transport import McpStreamableHttpTransport


SESSION_HEADER = "Mcp-Session-Id"


@pytest.mark.asyncio
async def test_streamable_http_initializes_once_and_reuses_session() -> None:
    """测试初始化流程和会话复用。

    目的：验证首次调用时执行握手初始化，后续调用复用同一会话 ID。
    结果：工具列表获取和工具调用共用一个会话，减少握手开销。
    """
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "DELETE":
            assert request.headers[SESSION_HEADER] == "session-1"
            return httpx.Response(204)
        payload = json.loads(request.content.decode()) if request.content else None

        if len(calls) == 1:
            assert payload[0]["method"] == "initialize"
            return httpx.Response(
                200,
                headers={
                    SESSION_HEADER: "session-1",
                    "content-type": "application/json",
                },
                json=[{
                    "jsonrpc": "2.0",
                    "id": payload[0]["id"],
                    "result": {"protocolVersion": "2025-03-26", "capabilities": {}},
                }],
            )

        if len(calls) == 2:
            assert payload[0]["method"] == "notifications/initialized"
            assert request.headers[SESSION_HEADER] == "session-1"
            return httpx.Response(202)

        if len(calls) == 3:
            assert payload[0]["method"] == "tools/list"
            assert request.headers[SESSION_HEADER] == "session-1"
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json=[{
                    "jsonrpc": "2.0",
                    "id": payload[0]["id"],
                    "result": {"tools": [{"name": "amap_geocode", "inputSchema": {}}]},
                }],
            )

        assert payload[0]["method"] == "tools/call"
        assert request.headers[SESSION_HEADER] == "session-1"
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json=[{
                "jsonrpc": "2.0",
                "id": payload[0]["id"],
                "result": {"content": [{"type": "text", "text": "ok"}]},
            }],
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = McpStreamableHttpTransport("http://test/mcp", client=client)

    tools = await transport.list_tools()
    result = await transport.call_tool("amap_geocode", {"address": "beijing"})

    assert [tool["name"] for tool in tools] == ["amap_geocode"]
    assert result["content"][0]["text"] == "ok"
    assert len(calls) == 4
    await transport.close()
    await client.aclose()


@pytest.mark.asyncio
async def test_streamable_http_raises_when_session_is_missing() -> None:
    """测试初始化响应缺少会话 ID 时的异常处理。

    目的：验证服务端未返回会话标识时，客户端能正确识别并报告协议错误。
    结果：抛出 McpProtocolError，提示会话标识缺失。
    """
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode()) if request.content else None
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json=[{
                "jsonrpc": "2.0",
                "id": payload[0]["id"],
                "result": {"protocolVersion": "2025-03-26", "capabilities": {}},
            }],
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = McpStreamableHttpTransport("http://test/mcp", client=client)

    with pytest.raises(McpProtocolError, match="会话标识"):
        await transport.list_tools()

    await client.aclose()


@pytest.mark.asyncio
async def test_streamable_http_raises_when_session_expires() -> None:
    """测试会话过期时的异常处理。

    目的：验证服务端返回 404 时，客户端能识别会话已失效并抛出传输错误。
    结果：抛出 McpTransportError，提示 session 不存在或已过期。
    """
    call_index = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_index
        call_index += 1
        if request.method == "DELETE":
            assert request.headers[SESSION_HEADER] == "session-1"
            return httpx.Response(204)
        payload = json.loads(request.content.decode()) if request.content else None

        if call_index == 1:
            return httpx.Response(
                200,
                headers={
                    SESSION_HEADER: "session-1",
                    "content-type": "application/json",
                },
                json=[{
                    "jsonrpc": "2.0",
                    "id": payload[0]["id"],
                    "result": {"protocolVersion": "2025-03-26", "capabilities": {}},
                }],
            )

        if call_index == 2:
            return httpx.Response(202)

        return httpx.Response(404, text="session gone")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = McpStreamableHttpTransport("http://test/mcp", client=client)

    with pytest.raises(McpTransportError, match="session"):
        await transport.list_tools()

    await client.aclose()


@pytest.mark.asyncio
async def test_streamable_http_reads_sse_payloads() -> None:
    """测试 Server-Sent Events 格式响应的解析。

    目的：验证客户端能正确解析 SSE 格式的响应流，提取其中的 JSON-RPC 数据。
    结果：成功从 SSE 事件流中获取工具列表数据。
    """
    call_index = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_index
        call_index += 1
        if request.method == "DELETE":
            assert request.headers[SESSION_HEADER] == "session-1"
            return httpx.Response(204)
        payload = json.loads(request.content.decode()) if request.content else None

        if call_index == 1:
            return httpx.Response(
                200,
                headers={
                    SESSION_HEADER: "session-1",
                    "content-type": "application/json",
                },
                json=[{
                    "jsonrpc": "2.0",
                    "id": payload[0]["id"],
                    "result": {"protocolVersion": "2025-03-26", "capabilities": {}},
                }],
            )

        if call_index == 2:
            return httpx.Response(202)

        body = (
            'event: message\n'
            'data: {"jsonrpc":"2.0","method":"notifications/message","params":{"level":"info"}}\n\n'
            f'event: message\ndata: {json.dumps({"jsonrpc": "2.0", "id": payload[0]["id"], "result": {"tools": [{"name": "amap_weather"}]}})}\n\n'
        )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=body.encode("utf-8"),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = McpStreamableHttpTransport("http://test/mcp", client=client)

    tools = await transport.list_tools()

    assert [tool["name"] for tool in tools] == ["amap_weather"]
    await transport.close()
    await client.aclose()
