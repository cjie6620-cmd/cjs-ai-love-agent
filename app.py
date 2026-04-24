"""FastAPI 应用入口：只负责装配容器、中间件和路由。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.workflows.compiler import initialize_graph_resources, shutdown_graph_resources
from api import api_router
from core import build_app_container, get_settings
from core.startup_probe import run_startup_probes
from observability import (
    get_langsmith_service,
    register_logging_middleware,
    setup_logging,
)
from security import ApiKeyMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """初始化运行时资源并在关闭时释放。
    
    目的：执行初始化运行时资源并在关闭时释放相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    settings = get_settings()
    setup_logging(app_env=settings.app_env)
    get_langsmith_service().configure_environment()
    owns_container = False

    try:
        await initialize_graph_resources()
    except Exception as exc:  # pragma: no cover
        logger.warning("LangGraph 初始化失败，将按降级模式运行: %s", exc)

    startup_probe_results = await run_startup_probes(settings)
    application.state.startup_probe_results = [item.to_dict() for item in startup_probe_results]
    failed_items = [item.name for item in startup_probe_results if not item.ok]
    application.state.startup_probe_summary = (
        f"success={sum(1 for item in startup_probe_results if item.ok)}/"
        f"{len(startup_probe_results)}, failed={','.join(failed_items) or '-'}"
    )

    if not hasattr(application.state, "container"):
        application.state.container = build_app_container(settings)
        owns_container = True

    try:
        yield
    finally:
        container = getattr(application.state, "container", None) if owns_container else None
        shutdown = getattr(container, "shutdown", None)
        if callable(shutdown):
            shutdown()
        await shutdown_graph_resources()


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。
    
    目的：执行创建并配置 FastAPI 应用相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    register_logging_middleware(application)
    application.add_middleware(ApiKeyMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="debug" if settings.debug else "info",
    )
