"""聊天路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from api.deps import (
    attach_guest_cookie,
    attach_guest_debug_headers,
    consume_guest_quota,
    ensure_rate_limit,
    get_container,
    get_request_identity,
)
from contracts.chat import ChatRequest, ChatResponse, ConversationHistoryResponse
from contracts.common import ApiErrorData, ApiResponse, error_response, success_response

router = APIRouter()


@router.post("/reply", response_model=ApiResponse[ChatResponse])
async def chat_reply(request_body: ChatRequest, request: Request, response: Response) -> ApiResponse[ChatResponse] | JSONResponse:
    """目的：执行非流式聊天回复相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    container = get_container(request)
    identity = get_request_identity(request, container)
    attach_guest_cookie(response, identity, container)
    attach_guest_debug_headers(response, identity)
    quota = consume_guest_quota(identity, container, request)
    if quota is not None and not quota.allowed:
        status_code = 503 if quota.reason == "redis_unavailable" else 401
        code = "GUEST_QUOTA_UNAVAILABLE" if quota.reason == "redis_unavailable" else "LOGIN_REQUIRED"
        message = "试用服务暂不可用，请稍后再试" if quota.reason == "redis_unavailable" else "登录后可以继续发送"
        payload = error_response(
            status_code,
            message,
            ApiErrorData(error_code=code, remaining=quota.remaining, limit=quota.limit).model_dump(),
        )
        response_payload = JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(payload),
        )
        attach_guest_cookie(response_payload, identity, container)
        attach_guest_debug_headers(response_payload, identity, quota)
        return response_payload
    if quota is not None:
        attach_guest_debug_headers(response, identity, quota)
    else:
        ensure_rate_limit(identity.user_id, container)
    authed_request = request_body.model_copy(update={"user_id": identity.user_id})
    result = await container.agent_service.reply(authed_request)
    result.guest_quota_remaining = quota.remaining if quota is not None else None
    return success_response(result)


@router.get("/conversations", response_model=ApiResponse[ConversationHistoryResponse])
async def conversations(
    request: Request,
    response: Response,
) -> ApiResponse[ConversationHistoryResponse]:
    """目的：执行获取用户会话历史相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    container = get_container(request)
    identity = get_request_identity(request, container)
    attach_guest_cookie(response, identity, container)
    attach_guest_debug_headers(response, identity)
    result = await container.agent_service.list_conversations_async(identity.user_id)
    return success_response(result)
