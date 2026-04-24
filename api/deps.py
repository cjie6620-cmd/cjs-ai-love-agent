"""FastAPI 依赖定义。"""

from __future__ import annotations

from fastapi import HTTPException, Request

from core.container import AppContainer


def get_container(request: Request) -> AppContainer:
    """从应用状态中获取容器。
    
    目的：获取从应用状态中获取容器。
    结果：返回当前流程需要的对象、配置或查询结果。
    """
    return request.app.state.container


def ensure_rate_limit(user_id: str, container: AppContainer) -> None:
    """统一限流检查。
    
    目的：执行统一限流检查相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    if not container.redis_service.check_rate_limit(user_id):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试。")
