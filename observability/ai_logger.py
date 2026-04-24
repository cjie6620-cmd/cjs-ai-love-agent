"""结构化日志系统。"""

from __future__ import annotations

import json
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class JsonFormatter(logging.Formatter):
    """JSON 结构化日志格式器。

    目的：封装日志格式化或过滤逻辑，统一链路中的观测数据处理方式。
    结果：日志输出结构更加稳定，便于排查问题和追踪关键请求。
    """

    def format(self, record: logging.LogRecord) -> str:
        """执行 format 方法。

        目的：按约定协议整理输出内容，统一格式细节。
        结果：返回格式一致的结果，降低上下游对接成本。
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get("-"),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 correlation id。
    
    目的：在请求链路中处理为每个请求注入 correlation id相关逻辑。
    结果：请求在进入业务前会完成对应拦截或增强。
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """处理当前请求并决定后续链路。

        目的：封装一次外部能力或链路调用，统一入参与异常处理。
        结果：返回稳定的执行结果，便于业务层直接消费或继续编排。
        """
        cid = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex[:16]
        token = correlation_id_var.set(cid)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = cid
            return response
        finally:
            correlation_id_var.reset(token)


class _CorrelationIdFilter(logging.Filter):
    """向文本日志注入 correlation id。

    目的：封装日志格式化或过滤逻辑，统一链路中的观测数据处理方式。
    结果：日志输出结构更加稳定，便于排查问题和追踪关键请求。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """执行 filter 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        record.correlation_id = correlation_id_var.get("-")  # type: ignore[attr-defined]
        return True


def setup_logging(*, app_env: str = "local") -> None:
    """按环境初始化日志。
    
    目的：执行按环境初始化日志相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler()
    if app_env == "local":
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | [%(correlation_id)s] %(message)s",
                defaults={"correlation_id": "-"},
            )
        )
        handler.addFilter(_CorrelationIdFilter())
    else:
        handler.setFormatter(JsonFormatter())

    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    for noisy_logger in ("uvicorn.access", "httpx", "httpcore", "openai"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def register_logging_middleware(app: FastAPI) -> None:
    """注册日志中间件。
    
    目的：执行注册日志中间件相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    app.add_middleware(CorrelationIdMiddleware)
