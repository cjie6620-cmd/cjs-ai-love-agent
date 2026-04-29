"""Agent 工具基类与统一结果模型。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolResult(dict):
    """目的：约束工具层返回结构，避免上层分别处理不同工具的结果格式。
    结果：调用方可稳定读取 `status`、`tool`、`message`、`data` 等公共字段。
    """

    @classmethod
    def success(
        cls,
        tool: str,
        message: str = "",
        data: dict[str, Any] | None = None,
    ) -> "ToolResult":
        """目的：统一工具成功返回的字段和默认值。
        结果：返回 status=success 的 ToolResult。
        """
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
        """目的：统一工具失败或禁用时的返回结构。
        结果：返回 status=error 的 ToolResult。
        """
        return cls(
            status="error",
            tool=tool,
            enabled=enabled,
            message=message,
            data=data or {},
        )


class BaseTool(ABC):
    """目的：约束所有工具暴露一致的启用判断、调用入口和结果结构。
    结果：新增工具时只需关注自身能力实现，上层可按统一方式编排。
    """

    # 目的：保存 name 字段，用于 BaseTool 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name = "base_tool"
    # 目的：保存 description 字段，用于 BaseTool 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 description 值。
    description = "Agent 工具基类"

    def is_enabled(self) -> bool:
        """目的：为所有工具提供统一启用检查入口。
        结果：默认返回 True，子类可按配置覆盖。
        """
        return True

    def invoke(self, **kwargs: Any) -> ToolResult:
        """目的：在进入具体工具逻辑前完成启用检查，并把异常收敛成 ToolResult。
        结果：返回成功、失败或禁用状态的统一工具结果。
        """
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
        """目的：把工具差异化能力留给子类实现。
        结果：返回子类生成的 ToolResult。
        """

    def disabled_message(self) -> str:
        """目的：为禁用工具提供可展示的统一文案。
        结果：返回说明当前工具不可用的字符串。
        """
        return f"{self.name} 当前不可用"


class PlaceholderTool(BaseTool):
    """目的：在真实工具尚未接入时保持工具接口稳定。
    结果：调用时返回未实现错误，不执行外部能力。
    """

    # 目的：保存 name 字段，用于 PlaceholderTool 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name = "placeholder"
    # 目的：保存 description 字段，用于 PlaceholderTool 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 description 值。
    description = "占位工具"

    def _invoke(self, **kwargs: Any) -> ToolResult:
        """目的：明确阻止未实现工具被误认为可用能力。
        结果：返回 enabled=False 的错误结果。
        """
        return ToolResult.error(self.name, "工具尚未实现", enabled=False)
