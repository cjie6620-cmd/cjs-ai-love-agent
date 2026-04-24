"""核心基础设施：配置与依赖装配。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings
    from .container import AppContainer

__all__ = [
    "AppContainer",
    "Settings",
    "build_app_container",
    "get_settings",
]


def __getattr__(name: str):
    """按需加载模块导出对象。
    
    目的：按需延迟加载目标对象，减少模块初始化阶段的耦合。
    结果：命中合法名称时返回对应对象，否则抛出 AttributeError。
    """
    if name == "Settings":
        from .config import Settings

        return Settings
    if name == "get_settings":
        from .config import get_settings

        return get_settings
    if name == "AppContainer":
        from .container import AppContainer

        return AppContainer
    if name == "build_app_container":
        from .container import build_app_container

        return build_app_container
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
