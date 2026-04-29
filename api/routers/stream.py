"""流式聊天路由。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from agents.stream_registry import StreamTaskConflictError
from api.deps import (
    attach_guest_cookie,
    attach_guest_debug_headers,
    consume_guest_quota,
    ensure_rate_limit,
    get_container,
    get_request_identity,
)
from contracts.chat import CancelStreamResponse, ChatRequest
from contracts.common import ApiErrorData, ApiResponse, error_response, success_response
from stream import sse_response

router = APIRouter()
logger = logging.getLogger(__name__)


async def _stream_until_disconnect(
    stream_id: str,
    body: asyncio.Queue[str | None],
    request: Request,
    *,
    remove_subscriber,
) -> AsyncIterator[str]:
    """目的：客户端断开时结束当前订阅，但不影响后台任务继续生成。
    结果：页面关闭、刷新或切走后，仅当前浏览器停止接收；上游流任务仍可在服务端继续执行。
    """
    try:
        while True:
            if await request.is_disconnected():
                logger.info("SSE 客户端已断开，移除本地订阅: stream_id=%s", stream_id)
                break
            try:
                chunk = await asyncio.wait_for(body.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if chunk is None:
                break
            yield chunk
            if await request.is_disconnected():
                logger.info("SSE 数据发送后检测到客户端断开，移除本地订阅: stream_id=%s", stream_id)
                break
    except asyncio.CancelledError:
        logger.info("SSE 响应任务被取消，结束当前订阅: stream_id=%s", stream_id)
        raise
    finally:
        await remove_subscriber(stream_id, body)


@router.post("/stream")
async def chat_stream(request_body: ChatRequest, request: Request):
    """目的：执行返回聊天 SSE 流相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    container = get_container(request)
    identity = get_request_identity(request, container)
    quota = None
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
    if quota is None:
        ensure_rate_limit(identity.user_id, container)

    authed_request = request_body.model_copy(update={"user_id": identity.user_id})
    stream_id = uuid4().hex
    try:
        upstream = await container.agent_service.start_stream(stream_id, authed_request)
    except StreamTaskConflictError as exc:
        payload = error_response(
            409,
            "当前会话仍在生成中，请稍候或先停止",
            {
                "error_code": "STREAM_ALREADY_RUNNING",
                "stream_id": exc.stream_id,
                "status": exc.status,
            },
        )
        response_payload = JSONResponse(
            status_code=409,
            content=jsonable_encoder(payload),
        )
        attach_guest_cookie(response_payload, identity, container)
        attach_guest_debug_headers(response_payload, identity, quota)
        return response_payload
    response = sse_response(
        _stream_until_disconnect(
            stream_id,
            upstream,
            request,
            remove_subscriber=container.agent_service.remove_stream_subscriber,
        )
    )
    response.headers["X-Stream-Id"] = stream_id
    attach_guest_cookie(response, identity, container)
    attach_guest_debug_headers(response, identity, quota)
    return response


@router.post("/streams/{stream_id}/cancel", response_model=ApiResponse[CancelStreamResponse])
async def cancel_stream(
    stream_id: str,
    request: Request,
    response: Response,
) -> ApiResponse[CancelStreamResponse]:
    """目的：执行取消当前流任务相关逻辑。
    结果：返回统一取消状态，供前端按幂等方式结束本地订阅。
    """
    container = get_container(request)
    identity = get_request_identity(request, container)
    attach_guest_cookie(response, identity, container)
    attach_guest_debug_headers(response, identity)
    result = await container.agent_service.cancel_stream(stream_id, identity.user_id)
    return success_response(result)
