"""Uvicorn 事件循环工厂。"""

from __future__ import annotations

import asyncio
import sys


def windows_compatible_loop_factory() -> asyncio.AbstractEventLoop:
    """目的：在 Windows 下避开 ProactorEventLoop 与部分异步依赖的兼容问题。
    结果：返回可交给 Uvicorn 使用的新事件循环实例。
    """
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()
