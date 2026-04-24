"""聊天路由。"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from api.deps import ensure_rate_limit, get_container
from contracts.chat import ChatRequest, ChatResponse, ConversationHistoryResponse

router = APIRouter()


@router.post("/reply", response_model=ChatResponse)
async def chat_reply(request_body: ChatRequest, request: Request) -> ChatResponse:
    """非流式聊天回复。
    
    目的：执行非流式聊天回复相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    container = get_container(request)
    ensure_rate_limit(request_body.user_id, container)
    return await container.agent_service.reply(request_body)


@router.get("/conversations", response_model=ConversationHistoryResponse)
async def conversations(
    request: Request,
    user_id: str = Query(..., description="外部用户 ID"),
) -> ConversationHistoryResponse:
    """获取用户会话历史。
    
    目的：执行获取用户会话历史相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    container = get_container(request)
    return await container.agent_service.list_conversations_async(user_id)
