"""MCP 协议层异常定义。

目的：定义 MCP 协议中可能出现的各类异常类型，为错误处理提供统一规范。
结果：上层调用方可根据异常类型执行对应的降级、重试或告警逻辑，提升系统健壮性。
"""

from __future__ import annotations


class McpError(Exception):
    """目的：提供 MCP 异常的通用父类，便于统一捕获和处理。
    结果：调用方可通过 except McpError 捕获所有 MCP 相关异常。
    """


class McpTransportError(McpError):
    """目的：区分传输层错误与协议层错误，便于针对性处理。
    结果：调用方可区分网络故障（超时、连接失败等）与协议解析错误。
    """


class McpTimeoutError(McpTransportError):
    """目的：标识请求执行时间超出预期限制的情况。
    结果：调用方可据此执行超时重试或降级策略。
    """


class McpProtocolError(McpError):
    """目的：标识 JSON-RPC 响应格式不合法或协议交互异常。
    结果：调用方可据此判定为服务端实现问题或版本不兼容。
    """
