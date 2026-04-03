from datetime import datetime, timezone

from fastapi import APIRouter

from ....schemas.common import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="backend",
        timestamp=datetime.now(timezone.utc),
    )
