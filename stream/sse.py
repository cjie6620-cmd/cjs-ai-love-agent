"""SSE 事件工具。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def format_sse_event(event: str, payload: dict[str, Any]) -> str:
    """目的：执行将事件和负载格式化为 SSE 文本相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_response(body: AsyncIterator[str]) -> StreamingResponse:
    """目的：执行构建标准 SSE 响应相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
