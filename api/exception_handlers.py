"""统一 API 异常处理。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from contracts.common import ApiErrorData, error_response

logger = logging.getLogger(__name__)


def _json_error(status_code: int, message: str, data: Any | None = None) -> JSONResponse:
    """目的：把错误信息转换为统一 JSON 响应。
    结果：调用方收到 code、message、data 结构一致的失败结果。
    """
    payload = error_response(status_code, message, data)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """目的：统一处理业务主动抛出的 HTTPException。
    结果：HTTP 错误会返回统一响应结构并保留原始状态码。
    """
    message = str(exc.detail or "请求处理失败")
    return _json_error(exc.status_code, message)


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """目的：统一处理请求参数校验异常。
    结果：前端可以在 data.errors 中读取结构化校验详情。
    """
    error_items = [dict(item) for item in exc.errors()]
    data = ApiErrorData(errors=error_items).model_dump()
    return _json_error(422, "参数校验失败", data)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """目的：兜底处理未捕获异常。
    结果：避免内部异常细节泄露给调用方，同时保留服务端日志。
    """
    logger.exception("未处理的接口异常: path=%s", request.url.path)
    return _json_error(500, "系统异常")


def register_exception_handlers(app: FastAPI) -> None:
    """目的：为 FastAPI 应用注册统一异常处理器。
    结果：应用内普通 JSON 错误响应格式保持一致。
    """
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
