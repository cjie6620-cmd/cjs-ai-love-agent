"""Agent 工具基类与统一结果模型。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolResult(dict):
    """统一工具执行结果。

    目的：约束工具层返回结构，避免上层分别处理不同工具的结果格式。
    结果：调用方可稳定读取 `status`、`tool`、`message`、`data` 等公共字段。
    """

    @classmethod
    def success(
        cls,
        tool: str,
        message: str = "",
        data: dict[str, Any] | None = None,
    ) -> "ToolResult":
        """构造成功结果。"""
        return cls(
            status="success",
            tool=tool,
            enabled=True,
            message=message,
            data=data or {},
        )

    @classmethod
    def error(
        cls,
        tool: str,
        message: str,
        *,
        enabled: bool = True,
        data: dict[str, Any] | None = None,
    ) -> "ToolResult":
        """构造失败结果。"""
        return cls(
            status="error",
            tool=tool,
            enabled=enabled,
            message=message,
            data=data or {},
        )


class BaseTool(ABC):
    """Agent 工具统一抽象。

    目的：约束所有工具暴露一致的启用判断、调用入口和结果结构。
    结果：新增工具时只需关注自身能力实现，上层可按统一方式编排。
    """

    name = "base_tool"
    description = "Agent 工具基类"

    def is_enabled(self) -> bool:
        """判断工具是否可用，默认启用。"""
        return True

    def invoke(self, **kwargs: Any) -> ToolResult:
        """统一执行入口，负责启用检查和异常收敛。"""
        if not self.is_enabled():
            return ToolResult.error(
                self.name,
                self.disabled_message(),
                enabled=False,
            )

        try:
            return self._invoke(**kwargs)
        except Exception as exc:
            return ToolResult.error(self.name, str(exc))

    @abstractmethod
    def _invoke(self, **kwargs: Any) -> ToolResult:
        """子类实现具体工具逻辑。"""

    def disabled_message(self) -> str:
        """返回工具不可用时的统一提示。"""
        return f"{self.name} 当前不可用"


class PlaceholderTool(BaseTool):
    """占位工具，用于未接入真实能力时保持工具接口稳定。"""

    name = "placeholder"
    description = "占位工具"

    def _invoke(self, **kwargs: Any) -> ToolResult:
        """返回不可用提示，不执行外部调用。"""
        return ToolResult.error(self.name, "工具尚未实现", enabled=False)
