"""API 路由总入口。"""

from fastapi import APIRouter

from api.routers.chat import router as chat_router
from api.routers.health import router as health_router
from api.routers.knowledge import router as knowledge_router
from api.routers.stream import router as stream_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(stream_router, prefix="/chat", tags=["chat-stream"])
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["knowledge"])

__all__ = ["api_router"]
