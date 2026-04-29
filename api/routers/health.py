"""健康检查路由。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from contracts.common import ApiResponse, DependencyHealthItem, HealthResponse, success_response

router = APIRouter()


@router.get("/health", response_model=ApiResponse[HealthResponse])
async def health(request: Request) -> ApiResponse[HealthResponse]:
    """目的：执行返回服务健康状态相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    raw_dependencies = getattr(request.app.state, "startup_probe_results", [])
    dependencies = [
        DependencyHealthItem(**item)
        for item in raw_dependencies
        if isinstance(item, dict)
    ]
    overall_status = (
        "ok"
        if all(item.status == "ok" for item in dependencies)
        else "degraded"
    )
    payload = HealthResponse(
        status=overall_status,
        service="ai-love",
        timestamp=datetime.now(timezone.utc).isoformat(),
        summary=str(getattr(request.app.state, "startup_probe_summary", "")),
        dependencies=dependencies,
    )
    return success_response(payload)
