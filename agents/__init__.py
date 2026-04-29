"""Agent 包公共入口。"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_service import AgentService

__all__ = ["AgentService"]


def __getattr__(name: str):
    """目的：按需延迟加载目标对象，减少模块初始化阶段的耦合。
    结果：命中合法名称时返回对应对象，否则抛出 AttributeError。
    """
    if name == "AgentService":
        from .agent_service import AgentService

        return AgentService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
