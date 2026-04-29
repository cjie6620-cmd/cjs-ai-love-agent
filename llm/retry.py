from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def async_retry_call(
    func: Callable[[], Awaitable[T]],
    *,
    retries: int = 3,
    base_delay: float = 0.5,
) -> T:
    """目的：在网络波动或临时故障时自动重试，提高系统容错能力。
    结果：成功时返回函数结果，失败时抛出最后一次异常。
    """
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return await func()
        except Exception as exc:  # pragma: no cover
            last_error = exc
            if attempt == retries - 1:
                break
            await asyncio.sleep(base_delay * (2**attempt))
    if last_error is None:  # pragma: no cover
        raise RuntimeError("async_retry_call 未获得异常但没有返回结果。")
    raise last_error
