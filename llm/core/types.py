"""LLM 模块核心数据类型定义。

目的：定义跨 Provider 共用的数据类型，确保类型一致性。
结果：提供 LlmMessage、McpCallInfo 等跨模块共享的类型。

注意：McpTool 类型已迁移到 mcp/types.py，此处保留导入以保持向后兼容。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 从 mcp 模块导入 McpTool，保持类型一致性
from mcp.types import McpTool as McpTool


# ============================ 消息类型 ============================ #


# LLM 消息格式：允许包含 role/content，以及 tool_calls、tool_call_id 等扩展字段
LlmMessage = dict[str, Any]


# ============================ MCP 调用追踪 ============================ #


@dataclass
class McpCallInfo:
    """目的：描述MCP 工具调用追踪信息的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """
    # 目的：保存 server_label 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 server_label 值。
    server_label: str
    # 目的：保存 tool_name 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tool_name 值。
    tool_name: str
    # 目的：保存 status 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: str
    # 目的：保存 duration_ms 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 duration_ms 值。
    duration_ms: int
    # 目的：保存 input_summary 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 input_summary 值。
    input_summary: str = ""
    # 目的：保存 output_summary 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 output_summary 值。
    output_summary: str = ""
    # 目的：保存 error_message 字段，用于 McpCallInfo 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 error_message 值。
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        return {
            "server_label": self.server_label,
            "tool_name": self.tool_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "error_message": self.error_message,
        }


# ============================ 工具相关类型 ============================ #

# OpenAI Function 定义格式
OpenAIFunction = dict[str, Any]

# 工具执行结果格式
ToolResult = dict[str, Any]


# ============================ 配置相关类型 ============================ #


@dataclass
class LlmConfig:
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """
    # 目的：保存 provider_name 字段，用于 LlmConfig 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 provider_name 值。
    provider_name: str
    # 目的：保存 model 字段，用于 LlmConfig 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 model 值。
    model: str
    # 目的：保存 base_url 字段，用于 LlmConfig 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 base_url 值。
    base_url: str
    # 目的：保存 api_key 字段，用于 LlmConfig 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 api_key 值。
    api_key: str = ""

    @property
    def api_key_masked(self) -> str:
        """目的：按需获取并返回目标配置或资源，避免重复构建。
        结果：调用方可以拿到可直接使用的结果，简化后续处理。
        """
        if not self.api_key or len(self.api_key) < 8:
            return "****"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"
