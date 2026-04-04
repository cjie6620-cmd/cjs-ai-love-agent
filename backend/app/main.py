import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 兼容两种启动方式：
# 1. `uvicorn app.main:app --reload`
# 2. 直接运行 `python app/main.py`
if __package__ in {None, ""}:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from app.api.router import api_router
    from app.core.config import get_settings
    from app.core.logging import setup_logging
    from app.infra.db.bootstrap import initialize_mysql_tables
    from app.infra.vector.bootstrap import initialize_vector_tables
    from app.services.chat_service import ChatService
else:
    from .api.router import api_router
    from .core.config import get_settings
    from .core.logging import setup_logging
    from .infra.db.bootstrap import initialize_mysql_tables
    from .infra.vector.bootstrap import initialize_vector_tables
    from .services.chat_service import ChatService


@asynccontextmanager
async def lifespan(application: FastAPI):
    """在应用启动时注册共享服务，并执行可选的自动建表。"""
    settings = get_settings()
    setup_logging()
    application.state.settings = settings
    application.state.chat_service = ChatService()

    # 可选的自动建表，由配置开关控制，失败不阻塞启动。
    try:
        initialize_mysql_tables()
    except Exception:
        pass
    try:
        initialize_vector_tables()
    except Exception:
        pass

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
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info" if not settings.debug else "debug",
    )
