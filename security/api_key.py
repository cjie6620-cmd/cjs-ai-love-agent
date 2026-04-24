from __future__ import annotations

from collections.abc import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from core.config import get_settings


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """可选 API Key 中间件：验证请求头中的 API Key 认证信息。
    
    目的：在请求链路中处理可选 API Key 中间件：验证请求头中的 API Key 认证信息相关逻辑。
    结果：请求在进入业务前会完成对应拦截或增强。
    """

    def __init__(self, app, exempt_paths: Iterable[str] | None = None) -> None:
        """初始化 ApiKeyMiddleware。
        
        目的：初始化ApiKeyMiddleware所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        super().__init__(app)
        self.settings = get_settings()
        self.exempt_paths = set(exempt_paths or {"/health", "/docs", "/redoc", "/openapi.json"})

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """处理当前请求并决定后续链路。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        if not self.settings.api_key_enabled:
            return await call_next(request)

        if request.url.path in self.exempt_paths:
            return await call_next(request)

        request_key = request.headers.get("X-API-Key", "")
        if not request_key or request_key != self.settings.api_key_value:
            return JSONResponse(status_code=401, content={"detail": "无效的 API Key。"})
        return await call_next(request)
