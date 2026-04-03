from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .core.config import get_settings
from .core.logging import setup_logging
from .services.chat_service import ChatService


@asynccontextmanager
async def lifespan(application: FastAPI):
    """在应用启动时注册共享服务，方便后续扩展数据库和模型客户端。"""
    settings = get_settings()
    setup_logging()
    application.state.settings = settings
    application.state.chat_service = ChatService()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
