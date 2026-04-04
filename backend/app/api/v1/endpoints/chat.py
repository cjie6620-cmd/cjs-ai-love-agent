from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ...deps import get_chat_service
from ....schemas.chat import ChatRequest, ChatResponse, ConversationHistoryResponse
from ....services.chat_service import ChatService

router = APIRouter()


@router.post("/reply", response_model=ChatResponse)
async def reply(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return await chat_service.reply(request)


@router.post("/reply/stream")
async def reply_stream(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    return StreamingResponse(
        chat_service.stream_reply(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations", response_model=ConversationHistoryResponse)
async def list_conversations(
    user_id: str = Query(..., description="外部用户 ID"),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationHistoryResponse:
    return chat_service.list_conversations(user_id)
