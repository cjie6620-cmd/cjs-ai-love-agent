"""MCP Streamable HTTP 传输实现。

目的：实现基于 HTTP 流式传输的 MCP 客户端，支持与 MCP 服务器进行 JSON-RPC 通信。
结果：上层可通过此传输层调用远程工具、获取工具列表，并接收服务端推送的事件。
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx

from mcp.errors import McpProtocolError, McpTimeoutError, McpTransportError
from mcp.transport.base import BaseMcpTransport
from mcp.types import McpTool

logger = logging.getLogger(__name__)

# MCP 协议版本标识，用于与服务端版本协商
_PROTOCOL_VERSION = "2025-11-25"
# HTTP 头名称，用于传递会话 ID 以实现请求与会话绑定
_SESSION_HEADER = "Mcp-Session-Id"


class McpStreamableHttpTransport(BaseMcpTransport):
    """基于 Streamable HTTP 的 MCP 传输客户端实现。

    目的：封装 HTTP 传输细节，提供面向业务的工具调用接口。
    结果：调用方可像使用本地服务一样调用远程 MCP 工具，传输细节对上层透明。
    """

    def __init__(
        self,
        mcp_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        *,
        extra_headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
        client_name: str = "ai-love",
        client_version: str = "1.0.0",
    ) -> None:
        """初始化 HTTP 传输客户端。

        目的：配置客户端连接参数，支持自定义 HTTP 客户端和认证信息。
        结果：创建可复用的传输实例，支持会话保持和长连接。
        """
        self.mcp_url = mcp_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.extra_headers = dict(extra_headers or {})
        self.client_name = client_name
        self.client_version = client_version
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None  # 标记是否由本类管理客户端生命周期
        self._initialized = False
        self._session_id: str | None = None
        self._protocol_version = _PROTOCOL_VERSION

    async def list_tools(self) -> list[McpTool]:
        """获取 MCP 服务器上注册的所有工具列表。

        目的：发现服务端提供的可用工具及其元数据。
        结果：返回工具列表，包含每个工具的名称、描述和输入参数模式。
        """
        await self._ensure_initialized()
        msg_id = str(uuid.uuid4())
        response = await self._send_jsonrpc(
            payload=[{
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": "tools/list",
                "params": {},
            }],
        )
        rpc_response = self._find_response_by_id(response, msg_id)
        tools = rpc_response.get("result", {}).get("tools", [])
        if not isinstance(tools, list):
            raise McpProtocolError("MCP tools/list 响应格式非法")
        return [cast(McpTool, tool) for tool in tools if isinstance(tool, dict)]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """调用指定工具并传入参数。

        目的：执行远程工具逻辑并获取执行结果。
        结果：返回工具执行结果字典，包含内容列表和错误状态字段。
        """
        await self._ensure_initialized()
        msg_id = str(uuid.uuid4())
        response = await self._send_jsonrpc(
            payload=[{
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            }],
        )
        rpc_response = self._find_response_by_id(response, msg_id)
        result = rpc_response.get("result", {})
        if not isinstance(result, dict):
            raise McpProtocolError("MCP tools/call 响应格式非法")
        return result

    async def open_event_stream(self) -> AsyncIterator[dict[str, Any]]:
        """打开服务端事件流订阅通道。

        目的：建立长连接以接收服务端主动推送的事件消息。
        结果：返回异步迭代器，调用方可遍历接收服务端事件数据。
        """
        await self._ensure_initialized()
        async def iterator() -> AsyncIterator[dict[str, Any]]:
            """内部事件迭代器，负责解析 SSE 数据并逐条 yield。

            目的：封装迭代逻辑，确保响应资源在迭代结束后被正确释放。
            结果：遍历完所有事件或异常退出时，自动关闭 HTTP 连接。
            """
            try:
                async with self._client.stream(
                    "GET",
                    self.mcp_url,
                    headers=self._build_headers(),
                    timeout=None,
                ) as response:
                    self._raise_for_status(response)
                    content_type = response.headers.get("content-type", "").lower()
                    if "text/event-stream" not in content_type:
                        raise McpProtocolError("MCP GET 事件流未返回 text/event-stream")

                    async for payload in self._iter_sse_payloads(response):
                        for item in self._normalize_payload(payload):
                            yield item
            except httpx.TimeoutException as exc:
                raise McpTimeoutError("MCP GET 事件流连接超时") from exc
            except httpx.HTTPError as exc:
                raise McpTransportError(f"MCP GET 事件流连接失败: {exc}") from exc

        return iterator()

    async def close(self) -> None:
        """关闭传输连接和会话。

        目的：安全终止会话，通知服务端释放资源，并关闭 HTTP 客户端。
        结果：连接关闭，所有待处理的请求完成或取消，客户端资源释放。
        """
        if self._session_id:
            try:
                response = await self._client.delete(
                    self.mcp_url,
                    headers=self._build_headers(),
                )
                if response.status_code not in {200, 202, 204, 404, 405}:
                    logger.warning("MCP session 关闭失败，状态码=%s", response.status_code)
            except httpx.HTTPError as exc:
                logger.warning("MCP session 关闭失败: %s", exc)
            finally:
                self._session_id = None
                self._initialized = False

        if self._owns_client:
            await self._client.aclose()

    async def _ensure_initialized(self) -> None:
        """确保会话已初始化。

        目的：延迟初始化会话，避免构造函数时立即建立连接。
        结果：首次调用时执行握手协议，后续调用直接返回已初始化状态。
        """
        if self._initialized:
            return

        msg_id = str(uuid.uuid4())
        response = await self._send_jsonrpc(
            payload=[{
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": _PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": self.client_name,
                        "version": self.client_version,
                    },
                },
            }],
            include_session=False,
            capture_session=True,
        )
        rpc_response = self._find_response_by_id(response, msg_id)
        result = rpc_response.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("protocolVersion"), str):
            raise McpProtocolError("MCP initialize 响应缺少 protocolVersion")
        if not self._session_id:
            raise McpProtocolError("MCP initialize 响应缺少会话标识")

        self._protocol_version = result["protocolVersion"]
        # 发送初始化完成通知，告知服务端可以开始发送消息
        await self._send_notification("notifications/initialized")
        self._initialized = True

    async def _send_notification(self, method: str) -> None:
        """发送无响应的通知消息。

        目的：向服务端发送单方向通知，无需等待响应。
        结果：服务端收到通知并执行相应动作，本端不阻塞等待回复。
        """
        payload = [{
            "jsonrpc": "2.0",
            "method": method,
        }]
        try:
            async with self._client.stream(
                "POST",
                self.mcp_url,
                headers=self._build_headers(),
                json=payload,
            ) as response:
                self._raise_for_status(response)
                await response.aread()
        except httpx.TimeoutException as exc:
            raise McpTimeoutError(f"MCP 通知 [{method}] 请求超时") from exc
        except httpx.HTTPError as exc:
            raise McpTransportError(f"MCP 通知 [{method}] 发送失败: {exc}") from exc

    async def _send_jsonrpc(
        self,
        *,
        payload: list[dict[str, Any]],
        include_session: bool = True,
        capture_session: bool = False,
    ) -> list[dict[str, Any]]:
        """发送 JSON-RPC 请求并接收响应。

        目的：封装请求发送和响应接收的完整流程，处理会话管理和流式响应。
        结果：返回解析后的响应数据列表，支持批量请求场景。
        """
        try:
            async with self._client.stream(
                "POST",
                self.mcp_url,
                headers=self._build_headers(include_session=include_session),
                json=payload,
            ) as response:
                self._raise_for_status(response)
                if capture_session:
                    # 从响应头中提取会话 ID，后续请求携带此 ID
                    self._session_id = response.headers.get(_SESSION_HEADER)
                return await self._read_response_payloads(response)
        except httpx.TimeoutException as exc:
            raise McpTimeoutError("MCP 请求超时") from exc
        except httpx.HTTPError as exc:
            raise McpTransportError(f"MCP 请求失败: {exc}") from exc

    def _build_headers(self, *, include_session: bool = True) -> dict[str, str]:
        """构建 HTTP 请求头。

        目的：统一组装认证信息、会话标识和协议版本等请求头。
        结果：返回完整的请求头字典，用于 HTTP 请求。
        """
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": self._protocol_version,
        }
        if include_session and self._session_id:
            headers[_SESSION_HEADER] = self._session_id
        if self.api_key:
            headers["x-api-key"] = self.api_key
        headers.update(self.extra_headers)
        return headers

    async def _read_response_payloads(self, response: httpx.Response) -> list[dict[str, Any]]:
        """读取并解析 HTTP 响应内容。

        目的：自动识别响应类型（JSON 或 SSE），统一转换为标准格式。
        结果：返回解析后的字典列表，支持单条或批量响应。
        """
        content_type = response.headers.get("content-type", "").lower()
        if "text/event-stream" in content_type:
            # SSE 响应：逐条解析事件数据
            payloads: list[dict[str, Any]] = []
            async for payload in self._iter_sse_payloads(response):
                payloads.extend(self._normalize_payload(payload))
            return payloads

        body = await response.aread()
        if not body.strip():
            raise McpProtocolError("MCP 响应为空")
        try:
            return self._normalize_payload(json.loads(body))
        except json.JSONDecodeError as exc:
            raise McpProtocolError("MCP 响应不是合法 JSON") from exc

    async def _iter_sse_payloads(self, response: httpx.Response) -> AsyncIterator[Any]:
        """迭代解析 Server-Sent Events 格式的响应流。

        目的：将 SSE 格式的流式数据拆分为独立的 JSON 事件。
        结果：逐个 yield 解析后的事件数据对象。
        """
        data_lines: list[str] = []
        async for line in response.aiter_lines():
            if not line:
                # 空行表示一个事件的结束，尝试解析已收集的行
                payload = self._consume_sse_event(data_lines)
                if payload is not None:
                    yield payload
                data_lines = []
                continue
            if line.startswith(":"):
                # SSE 注释行，忽略
                continue
            if line.startswith("data:"):
                # 提取 data: 后面的内容
                data_lines.append(line[5:].lstrip())

        # 处理最后可能残留的数据
        payload = self._consume_sse_event(data_lines)
        if payload is not None:
            yield payload

    @staticmethod
    def _consume_sse_event(data_lines: list[str]) -> Any | None:
        """解析 SSE 事件数据块。

        目的：将多行 data 字段合并后解析为 JSON 对象。
        结果：返回解析后的对象，或在遇到 [DONE] 标记时返回 None。
        """
        if not data_lines:
            return None
        raw = "\n".join(data_lines).strip()
        if not raw or raw == "[DONE]":
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise McpProtocolError("MCP SSE 事件数据不是合法 JSON") from exc

    @staticmethod
    def _normalize_payload(payload: Any) -> list[dict[str, Any]]:
        """规范化响应载荷格式。

        目的：统一处理单条字典或字典列表两种响应格式。
        结果：返回统一格式的字典列表，便于后续处理。
        """
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        raise McpProtocolError("MCP 响应格式非法，期望 dict 或 list")

    @staticmethod
    def _find_response_by_id(
        payloads: list[dict[str, Any]],
        msg_id: str,
    ) -> dict[str, Any]:
        """根据消息 ID 查找匹配的响应。

        目的：在响应列表中定位对应请求的响应数据。
        结果：返回匹配的响应字典，未找到时抛出协议错误。
        """
        for item in payloads:
            if item.get("id") == msg_id:
                return item
        raise McpProtocolError("MCP 响应中未找到匹配的 request id")

    def _raise_for_status(self, response: httpx.Response) -> None:
        """根据 HTTP 状态码抛出相应异常。

        目的：将 HTTP 错误转换为业务异常，提供更有意义的错误信息。
        结果：404 且存在会话时表示会话过期，其他状态码触发标准异常。
        """
        if response.status_code == 404 and self._session_id:
            raise McpTransportError("MCP session 不存在或已过期")
        response.raise_for_status()
