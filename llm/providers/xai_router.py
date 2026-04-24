"""XaiRouterProvider：OpenAI Chat Completions API + 手动函数调用循环。

目的：通过 Streamable HTTP MCP 调用高德地图工具，直接 REST API 调用 Tavily 搜索。
结果：支持多工具函数调用循环，流式返回结果。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from llm.core.types import LlmMessage, McpCallInfo
from llm.providers.base import (
    _MAX_FUNCTION_CALL_ROUNDS,
    BaseLLmProvider,
)
from observability import get_langsmith_service

from llm.tools.base import BaseToolClient
from llm.tools.clients import AmapMcpClient, TavilyClient
from llm.tools.registry import ToolRegistry
from mcp.transport import McpStreamableHttpTransport

logger = logging.getLogger(__name__)


class XaiRouterProvider(BaseLLmProvider):
    """XAI Router 提供者：使用 OpenAI Chat Completions API，通过手动函数调用循环支持 MCP 工具。
    
    目的：封装XAI Router 提供者：使用 OpenAI Chat Completions API，通过手动函数调用循环支持 MCP 工具相关的模型或能力实现。
    结果：上层可按统一 Provider 接口发起调用。
    """

    def __init__(self, settings: Any) -> None:
        """初始化 XaiRouterProvider。
        
        目的：初始化XaiRouterProvider所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        super().__init__(settings)

        # Chat Completions API 使用 AsyncOpenAI
        self._async_client = AsyncOpenAI(
            api_key=settings.xai_api_key,
            base_url=settings.llm_base_url,
        )
        self._async_client = get_langsmith_service().wrap_openai_client(self._async_client)
        self._mcp_calls: list[McpCallInfo] = []

        # 初始化 MCP 客户端（使用 Streamable HTTP 连接高德 MCP 服务）
        self._mcp_client: AmapMcpClient | None = None
        if settings.mcp_amap_enabled:
            if settings.mcp_transport != "streamable_http":
                raise ValueError("当前仅支持 streamable_http 传输")
            if not settings.amap_mcp_url:
                raise ValueError("启用高德 MCP 时必须配置 AMAP_MCP_URL")
            transport = McpStreamableHttpTransport(
                mcp_url=settings.amap_mcp_url,
                api_key=settings.amap_maps_api_key or None,
                extra_headers=settings.amap_mcp_headers,
            )
            self._mcp_client = AmapMcpClient(transport=transport)

        # 初始化 Tavily 直接 API 客户端
        self._tavily_client: TavilyClient | None = None
        if settings.tavily_api_key:
            self._tavily_client = TavilyClient(settings.tavily_api_key)

        # 创建工具注册表，管理函数定义和系统提示词工具说明
        self._tool_registry = ToolRegistry(
            mcp_client=self._mcp_client,
            tavily_client=self._tavily_client,
            mcp_server_name="高德地图",
        )

        # MCP 工具列表采用惰性加载（在 generate() 中使用 running loop 加载）
        self._tools_loaded = False

    def _get_model_name(self) -> str:
        """返回当前 Provider 的模型名，供 tokenizer 路由使用。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        return self.settings.llm_model

    def _get_structured_client_options(self) -> dict[str, Any]:
        """返回工具终结阶段使用的 ChatOpenAI 配置。"""
        return {
            "model": self.settings.llm_model,
            "api_key": self.settings.xai_api_key,
            "base_url": self.settings.llm_base_url,
        }

    async def _ensure_tools_loaded(self) -> None:
        """确保 MCP 工具列表已加载（在 running event loop 中惰性加载一次）。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        if self._tools_loaded or self._mcp_client is None:
            return

        try:
            self._tools_loaded = await self._tool_registry.load_mcp_tools()
        except Exception as exc:
            logger.warning("MCP 工具加载失败: %s", exc)

    def _build_system_prompt(self, base_system_prompt: str) -> str:
        """构建系统提示词，告知模型可用的工具及调用原则。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        return base_system_prompt + self._tool_registry.build_system_prompt_tools_section()

    def _execute_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """执行单个工具调用，优先走 MCP，否则走直接 API。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        registry = getattr(self, "_tool_registry", None)
        if registry is not None and not registry.is_allowed_tool(tool_name):
            return {"error": f"工具 {tool_name} 未注册或未启用"}
        arguments = self._normalize_tool_arguments(arguments)

        # 判断工具来源：tavily_search 走直接 API，其余走 MCP
        if tool_name == "tavily_search":
            if self._tavily_client:
                return self._execute_tavily_call(tool_name, arguments)
            return {"error": f"工具 {tool_name} 未配置 Tavily 客户端"}

        # MCP 工具
        if self._mcp_client:
            return self._execute_mcp_call(tool_name, arguments)

        return {"error": f"工具 {tool_name} 未找到对应处理器"}

    async def _execute_tool_call_async(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """异步执行单个工具调用（供 generate_stream 使用）。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        registry = getattr(self, "_tool_registry", None)
        if registry is not None and not registry.is_allowed_tool(tool_name):
            return {"error": f"工具 {tool_name} 未注册或未启用"}
        arguments = self._normalize_tool_arguments(arguments)

        if tool_name == "tavily_search":
            if self._tavily_client:
                return await self._execute_tavily_call_async(tool_name, arguments)
            return {"error": f"工具 {tool_name} 未配置 Tavily 客户端"}

        if self._mcp_client:
            return await self._execute_mcp_call_async(tool_name, arguments)

        return {"error": f"工具 {tool_name} 未找到对应处理器"}

    @staticmethod
    def _normalize_tool_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
        """限制工具入参形态和大小，避免异常参数进入外部服务。"""
        if not isinstance(arguments, dict):
            return {}

        normalized: dict[str, Any] = {}
        for key, value in arguments.items():
            if not isinstance(key, str) or not key:
                continue
            if isinstance(value, str):
                normalized[key] = value[:1000]
            elif isinstance(value, (int, float, bool)) or value is None:
                normalized[key] = value
            else:
                normalized[key] = json.dumps(value, ensure_ascii=False, default=str)[:1000]
            if len(normalized) >= 20:
                break
        return normalized

    def _run_tool_call_sync(
        self,
        client: BaseToolClient,
        tool_name: str,
        arguments: dict[str, Any],
        server_label: str,
    ) -> dict[str, Any]:
        """通过统一基类接口执行同步工具调用并记录追踪。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            client.call_with_tracking(
                tool_name=tool_name,
                arguments=arguments,
                call_list=self._mcp_calls,
                server_label=server_label,
            )
        )

    async def _run_tool_call_async(
        self,
        client: BaseToolClient,
        tool_name: str,
        arguments: dict[str, Any],
        server_label: str,
    ) -> dict[str, Any]:
        """通过统一基类接口执行异步工具调用并记录追踪。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        return await client.call_with_tracking(
            tool_name=tool_name,
            arguments=arguments,
            call_list=self._mcp_calls,
            server_label=server_label,
        )

    def _execute_tavily_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """执行 Tavily 搜索调用（同步版本）。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        return self._run_tool_call_sync(
            client=self._tavily_client,  # type: ignore[arg-type]
            tool_name=tool_name,
            arguments=arguments,
            server_label="tavily",
        )

    async def _execute_tavily_call_async(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """执行 Tavily 搜索调用（异步版本）。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        return await self._run_tool_call_async(
            client=self._tavily_client,  # type: ignore[arg-type]
            tool_name=tool_name,
            arguments=arguments,
            server_label="tavily",
        )

    def _execute_mcp_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """执行 MCP 调用（同步版本）。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        return self._run_tool_call_sync(
            client=self._mcp_client,  # type: ignore[arg-type]
            tool_name=tool_name,
            arguments=arguments,
            server_label=self._detect_mcp_server_label(tool_name),
        )

    async def _execute_mcp_call_async(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """执行 MCP 调用（异步版本）。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        return await self._run_tool_call_async(
            client=self._mcp_client,  # type: ignore[arg-type]
            tool_name=tool_name,
            arguments=arguments,
            server_label=self._detect_mcp_server_label(tool_name),
        )

    def _detect_mcp_server_label(self, tool_name: str) -> str:
        """根据工具名称识别 MCP 服务器标签。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        if any(k in tool_name for k in ["weather", "temp", "temperature"]):
            return "amap_weather"
        elif any(k in tool_name for k in ["geo", "geocode", "location", "address"]):
            return "amap_geo"
        elif any(k in tool_name for k in ["nav", "route", "direction", "driving", "walking", "transit"]):
            return "amap_nav"
        elif any(k in tool_name for k in ["search", "poi", "around"]):
            return "amap_search"
        else:
            return "amap"

    def _record_mcp_call(
        self,
        server_label: str,
        tool_name: str,
        status: str,
        duration_ms: int,
        input_summary: str,
        error_message: str | None = None,
    ) -> None:
        """记录 MCP 调用信息到追踪列表。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        self._mcp_calls.append(McpCallInfo(
            server_label=server_label,
            tool_name=tool_name,
            status=status,
            duration_ms=duration_ms,
            input_summary=input_summary,
            error_message=error_message or "",
        ))

    def _format_tool_result(
        self,
        tool_name: str,
        result: dict[str, Any],
    ) -> str:
        """将工具执行结果格式化为文本，注入到模型上下文中。

        目的：按约定协议整理输出内容，统一格式细节。
        结果：返回格式一致的结果，降低上下游对接成本。
        """
        if "error" in result:
            return f"[工具 {tool_name} 执行失败] {result['error']}"

        # Tavily 搜索结果格式
        if "results" in result and isinstance(result["results"], list):
            items = result["results"]
            if "answer" in result and result["answer"]:
                return result["answer"]
            lines = []
            for item in items[:3]:
                title = item.get("title", "")
                snippet = item.get("content", item.get("snippet", ""))
                url = item.get("url", "")
                if url:
                    lines.append(f"- {title}: {snippet} (来源: {url})")
                else:
                    lines.append(f"- {title}: {snippet}")
            return "\n".join(lines) if lines else str(result)

        # MCP 工具结果格式
        if "content" in result:
            content = result["content"]
            if isinstance(content, list):
                parts = []
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        parts.append(c["text"])
                return "\n".join(parts) if parts else str(result)
            return str(content)

        return json.dumps(result, ensure_ascii=False, indent=2)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[LlmMessage] | None = None,
    ) -> tuple[str, list[McpCallInfo]]:
        """非流式生成（内部使用流式模式）：Chat Completions API + 手动函数调用循环。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        if not self.settings.xai_api_key:
            raise RuntimeError("未配置 XAI_API_KEY，无法调用真实模型。")

        self._reset_pending_tool_history()
        self._mcp_calls = []
        await self._ensure_tools_loaded()
        enhanced_system = self._build_system_prompt(system_prompt)
        messages = self._build_messages(enhanced_system, user_prompt, history)
        functions = self._tool_registry.get_all_functions()

        start_time = time.monotonic()
        used_tools = False

        try:
            for _ in range(_MAX_FUNCTION_CALL_ROUNDS):
                # 发送 Chat Completions 请求（内部使用流式模式以规避空 content bug）
                request_kwargs: dict[str, Any] = {
                    "model": self.settings.llm_model,
                    "messages": messages,
                    "stream": True,  # 强制使用流式模式，xai-router 非流式返回空 content
                }
                if functions:
                    request_kwargs["tools"] = functions
                    request_kwargs["tool_choice"] = "auto"

                stream = await self._async_client.chat.completions.create(**request_kwargs)

                # 聚合计数器
                assistant_content = ""
                tool_calls_batch: list[Any] = []

                async for chunk in stream:
                    delta = chunk.choices[0].delta

                    # 收集文本内容
                    if delta.content:
                        assistant_content += delta.content

                    # 收集 tool_calls 分片（增量追加）
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            while len(tool_calls_batch) <= idx:
                                tool_calls_batch.append({
                                    "id": "",
                                    "function": {"name": "", "arguments": ""},
                                })
                            if tc.id:
                                tool_calls_batch[idx]["id"] = tc.id
                            if tc.function and tc.function.name:
                                tool_calls_batch[idx]["function"]["name"] = tc.function.name
                            if tc.function and tc.function.arguments:
                                tool_calls_batch[idx]["function"]["arguments"] = (
                                    tool_calls_batch[idx]["function"]["arguments"] or ""
                                ) + tc.function.arguments

                # 调试日志：记录聚合计数后的内容
                logger.info(
                    "[XaiRouter generate] API 响应: content长度=%d, tool_calls=%s",
                    len(assistant_content),
                    [tc["function"]["name"] for tc in tool_calls_batch],
                )

                # 将模型回复追加到 messages
                messages.append({
                    "role": "assistant",
                    "content": assistant_content or None,
                    "tool_calls": tool_calls_batch if tool_calls_batch else None,
                })

                # 检查是否有函数调用
                if not tool_calls_batch:
                    if used_tools:
                        self._set_pending_tool_history(messages[1:])
                    reply_text = assistant_content
                    if not used_tools and not self._mcp_calls:
                        duration_ms = int((time.monotonic() - start_time) * 1000)
                        self._record_mcp_call(
                            server_label="none",
                            tool_name="none",
                            status="skipped",
                            duration_ms=duration_ms,
                            input_summary="未调用任何工具",
                        )
                    return reply_text, list(self._mcp_calls)

                # 执行所有函数调用
                used_tools = True
                for tc in tool_calls_batch:
                    tool_name = tc["function"]["name"]
                    try:
                        arguments = json.loads(tc["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                    tool_result = await self._execute_tool_call_async(tool_name, arguments)
                    formatted_result = self._format_tool_result(tool_name, tool_result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": formatted_result,
                    })

            # 达到最大轮次限制，返回聚合回复
            logger.warning("函数调用循环达到最大轮次 %d，终止循环", _MAX_FUNCTION_CALL_ROUNDS)
            messages.append(
                {
                    "role": "user",
                    "content": "请基于之前的工具调用结果完成回答，不要继续调用工具。",
                }
            )
            self._set_pending_tool_history(messages[1:])
            return "", list(self._mcp_calls)

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning("XaiRouter Chat Completions 调用失败: %s", exc)
            self._record_mcp_call(
                server_label="xai_router",
                tool_name="chat.completions.create",
                status="error",
                duration_ms=duration_ms,
                input_summary=f"调用异常: {str(exc)[:200]}",
                error_message=str(exc),
            )
            return "抱歉，服务处理时遇到了问题，请稍后再试。", list(self._mcp_calls)
        finally:
            # 清理资源
            if self._mcp_client:
                await self._mcp_client.close()
            if self._tavily_client:
                await self._tavily_client.close()

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[LlmMessage] | None = None,
    ) -> AsyncIterator[tuple[str, list[McpCallInfo]]]:
        """流式生成：Chat Completions API + 手动函数调用循环。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        if not self.settings.xai_api_key:
            raise RuntimeError("未配置 XAI_API_KEY，无法调用真实模型。")

        self._reset_pending_tool_history()
        self._mcp_calls = []
        await self._ensure_tools_loaded()
        enhanced_system = self._build_system_prompt(system_prompt)
        messages = self._build_messages(enhanced_system, user_prompt, history)
        functions = self._tool_registry.get_all_functions()
        start_time = time.monotonic()
        used_tools = False

        try:
            for _ in range(_MAX_FUNCTION_CALL_ROUNDS):
                request_kwargs: dict[str, Any] = {
                    "model": self.settings.llm_model,
                    "messages": messages,
                    "stream": True,
                }
                if functions:
                    request_kwargs["tools"] = functions
                    request_kwargs["tool_choice"] = "auto"

                stream = await self._async_client.chat.completions.create(**request_kwargs)

                assistant_content = ""
                tool_calls_batch: list[Any] = []
                saw_tool_calls = False
                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        assistant_content += delta.content
                        if not saw_tool_calls:
                            yield delta.content, []
                    if delta.tool_calls:
                        saw_tool_calls = True
                        for tc in delta.tool_calls:
                            idx = tc.index
                            while len(tool_calls_batch) <= idx:
                                tool_calls_batch.append({"id": "", "function": {"name": "", "arguments": ""}})
                            if tc.id:
                                tool_calls_batch[idx]["id"] = tc.id
                            if tc.function and tc.function.name:
                                tool_calls_batch[idx]["function"]["name"] = tc.function.name
                            if tc.function and tc.function.arguments:
                                tool_calls_batch[idx]["function"]["arguments"] = (
                                    tool_calls_batch[idx]["function"]["arguments"] or ""
                                ) + tc.function.arguments

                # 追加 assistant 消息
                messages.append({
                    "role": "assistant",
                    "content": assistant_content or None,
                    "tool_calls": tool_calls_batch if tool_calls_batch else None,
                })

                # 检查函数调用
                if not tool_calls_batch:
                    if used_tools:
                        self._set_pending_tool_history(messages[1:])
                        return

                    if not self._mcp_calls:
                        duration_ms = int((time.monotonic() - start_time) * 1000)
                        self._record_mcp_call(
                            server_label="none",
                            tool_name="none",
                            status="skipped",
                            duration_ms=duration_ms,
                            input_summary="未调用任何工具",
                        )
                    return

                # 执行函数调用
                used_tools = True
                for tc in tool_calls_batch:
                    tool_name = tc["function"]["name"]
                    try:
                        arguments = json.loads(tc["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                    tool_result = await self._execute_tool_call_async(tool_name, arguments)
                    formatted_result = self._format_tool_result(tool_name, tool_result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": formatted_result,
                    })

            # 达到最大轮次
            logger.warning("流式函数调用循环达到最大轮次 %d", _MAX_FUNCTION_CALL_ROUNDS)
            if used_tools:
                messages.append(
                    {
                        "role": "user",
                        "content": "请基于之前的工具调用结果完成回答，不要继续调用工具。",
                    }
                )
                self._set_pending_tool_history(messages[1:])

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning("XaiRouter 流式调用失败: %s", exc)
            self._record_mcp_call(
                server_label="xai_router",
                tool_name="chat.completions.stream",
                status="error",
                duration_ms=duration_ms,
                input_summary=f"流异常: {str(exc)[:200]}",
                error_message=str(exc),
            )
            yield "抱歉，服务处理时遇到了问题，请稍后再试。", list(self._mcp_calls)
        finally:
            if self._mcp_client:
                await self._mcp_client.close()
            if self._tavily_client:
                await self._tavily_client.close()
