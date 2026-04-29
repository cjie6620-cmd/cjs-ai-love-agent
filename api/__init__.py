"""API 路由总入口。"""

from fastapi import APIRouter

from api.routers.admin import router as admin_router
from api.routers.auth import router as auth_router
from api.routers.chat import router as chat_router
from api.routers.health import router as health_router
from api.routers.memory import router as memory_router
from api.routers.stream import router as stream_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(stream_router, prefix="/chat", tags=["chat-stream"])
api_router.include_router(memory_router, prefix="/memory", tags=["memory"])

__all__ = ["api_router"]
