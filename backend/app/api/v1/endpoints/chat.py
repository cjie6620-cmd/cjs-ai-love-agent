from fastapi import APIRouter, Depends

from ...deps import get_chat_service
from ....schemas.chat import ChatRequest, ChatResponse
from ....services.chat_service import ChatService

router = APIRouter()


@router.post("/reply", response_model=ChatResponse)
async def reply(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return await chat_service.reply(request)
