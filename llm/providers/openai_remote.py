"""DeepSeek MCP Provider：挂载远程 MCP 工具，支持 Tavily 搜索和高德地图。

目的：使用 DeepSeek API 通过 Function Calling 实现 MCP 工具调用。
结果：支持 Tavily 搜索和高德地图，通过 SSE 流式返回结果。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Literal, cast

from openai import AsyncOpenAI, OpenAI

from llm.core.types import LlmMessage, McpCallInfo
from llm.providers.base import BaseLLmProvider
from observability import get_langsmith_service, traceable_tool

if TYPE_CHECKING:
    from core.config import Settings

logger = logging.getLogger(__name__)


class DeepseekMcpProvider(BaseLLmProvider):
    """DeepSeek MCP 提供者：挂载远程 MCP 工具，支持 Tavily 搜索和高德地图。
    
    目的：封装DeepSeek MCP 提供者：挂载远程 MCP 工具，支持 Tavily 搜索和高德地图相关的模型或能力实现。
    结果：上层可按统一 Provider 接口发起调用。
    """

    def __init__(self, settings: "Settings") -> None:
        """初始化 DeepseekMcpProvider。
        
        目的：初始化DeepseekMcpProvider所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        super().__init__(settings)
        # DeepSeek API 兼容 OpenAI 格式，使用标准 OpenAI 客户端
        self._sync_client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self._async_client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        langsmith = get_langsmith_service()
        self._sync_client = langsmith.wrap_openai_client(self._sync_client)
        self._async_client = langsmith.wrap_openai_client(self._async_client)
        self._mcp_calls: list[McpCallInfo] = []
        self._mcp_tools = self._build_mcp_tools()

    def _get_model_name(self) -> str:
        """返回当前 Provider 的模型名，供 tokenizer 路由使用。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        return self.settings.deepseek_model

    def _get_structured_client_options(self) -> dict[str, Any]:
        """返回工具终结阶段和 memory structured 阶段使用的 ChatOpenAI 配置。"""
        return {
            "model": self.settings.deepseek_model,
            "api_key": self.settings.deepseek_api_key,
            "base_url": self.settings.deepseek_base_url,
        }

    def _build_mcp_tools(self) -> list[dict[str, Any]]:
        """根据配置构建 MCP 工具列表。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        tools: list[dict[str, Any]] = []

        if self.settings.mcp_tavily_enabled and self.settings.tavily_api_key:
            # Tavily 搜索工具定义
            tools.append({
                "type": "function",
                "function": {
                    "name": "tavily_search",
                    "description": "使用 Tavily 搜索引擎查询实时信息、新闻、天气、最新数据等外部事实。当用户询问需要最新资讯、实时数据或你不确定的事实时请使用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索查询关键词，用于查询用户需要的实时信息",
                            }
                        },
                        "required": ["query"],
                    },
                },
            })
            logger.info("Tavily 搜索工具已注册")

        if self.settings.mcp_amap_enabled and self.settings.amap_maps_api_key:
            # 高德地图工具定义
            tools.append({
                "type": "function",
                "function": {
                    "name": "amap_geocode",
                    "description": "使用高德地图 API 进行地理编码，将地址转换为经纬度坐标。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "address": {
                                "type": "string",
                                "description": "需要查询的地址",
                            },
                            "city": {
                                "type": "string",
                                "description": "城市名称，用于限定搜索范围",
                            },
                        },
                        "required": ["address"],
                    },
                },
            })
            tools.append({
                "type": "function",
                "function": {
                    "name": "amap_direction",
                    "description": "使用高德地图 API 查询两地之间的导航路线。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origin": {
                                "type": "string",
                                "description": "起点坐标，格式：经度,纬度",
                            },
                            "destination": {
                                "type": "string",
                                "description": "终点坐标，格式：经度,纬度",
                            },
                            "strategy": {
                                "type": "string",
                                "description": "导航策略：1-走高速、2-少换乘、3-少步行、4-不坐地铁",
                                "enum": ["1", "2", "3", "4"],
                            },
                        },
                        "required": ["origin", "destination"],
                    },
                },
            })
            logger.info("高德地图工具已注册")

        if not tools:
            logger.warning("MCP 工具列表为空，请检查 mcp_tavily_enabled / mcp_amap_enabled 配置")

        return tools

    def _build_mcp_system_prompt(self, base_system_prompt: str) -> str:
        """将 MCP 工具使用策略注入系统提示词。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        tools_section = ""

        if self.settings.mcp_tavily_enabled and self.settings.tavily_api_key:
            tools_section += (
                "你有权限使用 Tavily 搜索工具 (tavily_search)：\n"
                "  - 用于查询实时信息、新闻、天气、最新数据等外部事实\n"
                "  - 当用户询问需要最新资讯、实时数据或你不确定的事实时请使用\n"
            )

        if self.settings.mcp_amap_enabled and self.settings.amap_maps_api_key:
            tools_section += (
                "你有权限使用高德地图工具：\n"
                "  - amap_geocode：查询地址的经纬度坐标\n"
                "  - amap_direction：查询两地之间的导航路线\n"
                "  - 当用户询问具体地址、两地之间路线、或需要地理定位时请使用\n"
            )

        if tools_section:
            tools_section = "\n\n【MCP 工具使用策略】\n" + tools_section + (
                "\n使用原则：\n"
                "- 不要为了炫耀工具而调用，只在真正需要外部信息时使用\n"
                "- 如果用户只是聊天、倾诉、共情，不需要调用任何工具\n"
                "- 调用工具后，将工具返回的信息自然融入你的回复中\n"
            )

        return base_system_prompt + tools_section

    def _append_mcp_call(
        self,
        *,
        tool_name: str,
        status: Literal["success", "error", "skipped"],
        duration_ms: int,
        tool_args: dict[str, Any] | None = None,
        error_message: str = "",
        output_summary: str = "",
    ) -> None:
        """追加目标数据到结果集合。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        self._mcp_calls.append(McpCallInfo(
            server_label=tool_name.split("_")[0] if "_" in tool_name else "mcp",
            tool_name=tool_name,
            status=status,
            duration_ms=min(duration_ms, 5000),
            input_summary=json.dumps(tool_args or {}, ensure_ascii=False)[:200],
            output_summary=output_summary[:200],
            error_message=error_message[:200],
        ))

    @traceable_tool("tool.deepseek_mcp_call")
    async def _call_mcp_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> str:
        """调用 MCP 工具并返回结果。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        start_time = time.monotonic()

        try:
            tool_result = ""
            if tool_name == "tavily_search":
                # 调用 Tavily 搜索 API
                import httpx

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": self.settings.tavily_api_key,
                            "query": tool_args.get("query", ""),
                            "search_depth": "basic",
                            "max_results": 5,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()

                    # 格式化结果
                    results = data.get("results", [])
                    if not results:
                        tool_result = "未找到相关结果"
                    else:
                        formatted = []
                        for i, r in enumerate(results[:5], 1):
                            formatted.append(
                                f"{i}. {r.get('title', '无标题')}\n"
                                f"   {r.get('url', '')}\n"
                                f"   {r.get('content', '')[:200]}"
                            )
                        tool_result = "\n\n".join(formatted)

            elif tool_name == "amap_geocode":
                # 调用高德地图地理编码 API
                import httpx

                async with httpx.AsyncClient(timeout=30.0) as client:
                    params = {
                        "key": self.settings.amap_maps_api_key,
                        "address": tool_args.get("address", ""),
                        "city": tool_args.get("city", ""),
                    }
                    response = await client.get(
                        "https://restapi.amap.com/v3/geocode/geo",
                        params=params,
                    )
                    response.raise_for_status()
                    data = response.json()

                    if data.get("status") == "1" and data.get("geocodes"):
                        geocode = data["geocodes"][0]
                        tool_result = (
                            f"地址：{geocode.get('province', '')}{geocode.get('city', '')}"
                            f"{geocode.get('district', '')}{geocode.get('township', '')}"
                            f"{geocode.get('street', '')}{geocode.get('number', '')}\n"
                            f"坐标：经度 {geocode.get('location', '').split(',')[0] if ',' in geocode.get('location', '') else 'N/A'}, "
                            f"纬度 {geocode.get('location', '').split(',')[1] if ',' in geocode.get('location', '') else 'N/A'}"
                        )
                    else:
                        tool_result = f"地理编码失败：{data.get('info', '未知错误')}"

            elif tool_name == "amap_direction":
                # 调用高德地图路径规划 API
                import httpx

                async with httpx.AsyncClient(timeout=30.0) as client:
                    params = {
                        "key": self.settings.amap_maps_api_key,
                        "origin": tool_args.get("origin", ""),
                        "destination": tool_args.get("destination", ""),
                        "strategy": tool_args.get("strategy", "1"),
                    }
                    response = await client.get(
                        "https://restapi.amap.com/v3/direction/driving",
                        params=params,
                    )
                    response.raise_for_status()
                    data = response.json()

                    if data.get("status") == "1":
                        routes = data.get("route", {}).get("paths", [])
                        if routes:
                            route = routes[0]
                            tool_result = (
                                f"总距离：{route.get('distance', 'N/A')} 米\n"
                                f"预计时间：{int(route.get('duration', 0)) // 60} 分钟\n"
                                f"路线：{route.get('strategy', '未知策略')}"
                            )
                        else:
                            tool_result = f"路径规划失败：{data.get('info', '未知错误')}"
                    else:
                        tool_result = f"路径规划失败：{data.get('info', '未知错误')}"
            else:
                tool_result = "未知工具"

            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._append_mcp_call(
                tool_name=tool_name,
                status="success",
                duration_ms=duration_ms,
                tool_args=tool_args,
                output_summary=tool_result,
            )
            return tool_result

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("MCP 工具调用失败: %s - %s", tool_name, exc)
            self._append_mcp_call(
                tool_name=tool_name,
                status="error",
                duration_ms=duration_ms,
                tool_args=tool_args,
                error_message=str(exc),
            )
            return f"工具调用失败: {str(exc)}"

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[LlmMessage] | None = None,
    ) -> tuple[str, list[McpCallInfo]]:
        """非流式生成（DeepSeek Chat API）。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        if not self.settings.deepseek_api_key:
            raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法调用 DeepSeek API。")

        self._reset_pending_tool_history()
        self._mcp_calls = []
        enhanced_system = self._build_mcp_system_prompt(system_prompt)

        messages = self._build_messages(enhanced_system, user_prompt, history)

        start_time = time.monotonic()
        max_iterations = 5  # 防止无限循环
        used_tools = False

        try:
            for iteration in range(max_iterations):
                # 调用 Chat Completions API
                completion_create = cast(Any, self._sync_client.chat.completions.create)
                response = completion_create(
                    model=self.settings.deepseek_model,
                    messages=messages,
                    tools=self._mcp_tools if self._mcp_tools else None,
                    temperature=0.7,
                )

                assistant_message = response.choices[0].message
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in (assistant_message.tool_calls or [])
                    ] if assistant_message.tool_calls else None,
                })

                # 检查是否有工具调用
                if not assistant_message.tool_calls:
                    if used_tools:
                        self._set_pending_tool_history(messages[1:])

                    duration_ms = int((time.monotonic() - start_time) * 1000)
                    if not used_tools and not self._mcp_calls:
                        self._mcp_calls.append(McpCallInfo(
                            server_label="none",
                            tool_name="none",
                            status="skipped",
                            duration_ms=duration_ms,
                            input_summary="未调用任何 MCP 工具",
                        ))
                    return assistant_message.content or "", list(self._mcp_calls)

                # 处理工具调用
                used_tools = True
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        tool_args = {}

                    # 调用工具
                    tool_result = await self._call_mcp_tool(tool_name, tool_args)

                    # 将工具结果添加到消息
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    })

            # 达到最大迭代次数，返回最后一条消息
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._mcp_calls.append(McpCallInfo(
                server_label="deepseek",
                tool_name="chat",
                status="error",
                duration_ms=duration_ms,
                input_summary="达到最大工具调用迭代次数",
            ))
            if used_tools:
                messages.append({
                    "role": "user",
                    "content": "请基于之前的工具调用结果完成回答，不要继续调用工具。",
                })
                self._set_pending_tool_history(messages[1:])
            return "", list(self._mcp_calls)

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning("DeepSeek API 调用失败: %s", exc)
            self._mcp_calls.append(McpCallInfo(
                server_label="deepseek",
                tool_name="chat.completions",
                status="error",
                duration_ms=duration_ms,
                input_summary=f"调用异常: {str(exc)[:200]}",
            ))
            return "抱歉，服务处理时遇到了问题，请稍后再试。", list(self._mcp_calls)

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        history: list[LlmMessage] | None = None,
    ) -> AsyncIterator[tuple[str, list[McpCallInfo]]]:
        """流式生成（DeepSeek Chat API SSE 格式）。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        if not self.settings.deepseek_api_key:
            raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法调用 DeepSeek API。")

        self._reset_pending_tool_history()
        self._mcp_calls = []
        enhanced_system = self._build_mcp_system_prompt(system_prompt)

        messages = self._build_messages(enhanced_system, user_prompt, history)

        start_time = time.monotonic()
        max_iterations = 5
        used_tools = False

        try:
            for _ in range(max_iterations):
                completion_create = cast(Any, self._sync_client.chat.completions.create)
                stream = completion_create(
                    model=self.settings.deepseek_model,
                    messages=messages,
                    tools=self._mcp_tools if self._mcp_tools else None,
                    temperature=0.7,
                    stream=True,
                )

                buffered_tokens: list[str] = []
                tool_calls_map: dict[int, dict[str, Any]] = {}

                for chunk in stream:
                    delta = chunk.choices[0].delta

                    if delta.content:
                        buffered_tokens.append(delta.content)
                        if not tool_calls_map:
                            yield delta.content, []

                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            entry = tool_calls_map.setdefault(
                                tc_delta.index,
                                {"id": "", "name": "", "arguments": ""},
                            )
                            if tc_delta.id:
                                entry["id"] = tc_delta.id
                            if tc_delta.function and tc_delta.function.name:
                                entry["name"] = tc_delta.function.name
                            if tc_delta.function and tc_delta.function.arguments:
                                entry["arguments"] = (
                                    entry["arguments"] or ""
                                ) + tc_delta.function.arguments

                tool_calls_to_process = [
                    tool_calls_map[index]
                    for index in sorted(tool_calls_map)
                ]

                messages.append({
                    "role": "assistant",
                    "content": "".join(buffered_tokens) or None,
                    "tool_calls": [
                        {
                            "id": tc.get("id"),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": tc.get("arguments", "{}"),
                            },
                        }
                        for tc in tool_calls_to_process
                    ] if tool_calls_to_process else None,
                })

                if not tool_calls_to_process:
                    if used_tools:
                        self._set_pending_tool_history(messages[1:])
                        return

                    if not self._mcp_calls:
                        duration_ms = int((time.monotonic() - start_time) * 1000)
                        self._mcp_calls.append(McpCallInfo(
                            server_label="none",
                            tool_name="none",
                            status="skipped",
                            duration_ms=duration_ms,
                            input_summary="未调用任何 MCP 工具",
                        ))
                    return

                used_tools = True
                for tc in tool_calls_to_process:
                    tool_name = tc.get("name", "")
                    try:
                        tool_args = json.loads(tc.get("arguments", "{}") or "{}")
                    except json.JSONDecodeError:
                        tool_args = {}
                    tool_result = await self._call_mcp_tool(tool_name, tool_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id"),
                        "content": tool_result,
                    })

            logger.warning("DeepSeek 流式函数调用循环达到最大轮次 %d", max_iterations)
            if used_tools:
                messages.append({
                    "role": "user",
                    "content": "请基于之前的工具调用结果完成回答，不要继续调用工具。",
                })
                self._set_pending_tool_history(messages[1:])

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning("DeepSeek API 流式调用失败: %s", exc)
            self._mcp_calls.append(McpCallInfo(
                server_label="deepseek",
                tool_name="chat.completions.stream",
                status="error",
                duration_ms=duration_ms,
                input_summary=f"流异常: {str(exc)[:200]}",
            ))
            yield "抱歉，服务处理时遇到了问题，请稍后再试。", list(self._mcp_calls)
