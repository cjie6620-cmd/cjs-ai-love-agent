"""流式聊天路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from api.deps import ensure_rate_limit, get_container
from contracts.chat import ChatRequest
from stream import sse_response

router = APIRouter()


@router.post("/stream")
async def chat_stream(request_body: ChatRequest, request: Request):
    """返回聊天 SSE 流。
    
    目的：执行返回聊天 SSE 流相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    container = get_container(request)
    ensure_rate_limit(request_body.user_id, container)
    return sse_response(container.agent_service.stream_reply(request_body))
