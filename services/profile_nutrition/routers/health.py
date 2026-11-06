"""Health and operational readiness probe endpoints for Profile & Nutrition Service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from services.common.database import ServiceDatabaseManager
from services.common.models import HealthResponse, ReadinessResponse
from services.profile_nutrition.config import settings
from services.profile_nutrition.database import get_db_manager

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service health check",
    description="Returns service runtime status, name, and version for load balancers and orchestrators.",
)
def get_health() -> HealthResponse:
    """Standard OpenAPI health probe."""
    return HealthResponse(
        status="healthy",
        service=settings.service_name,
        version=settings.version,
    )


@router.get(
    "/health/live",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Confirms service process is executing without probing external dependencies.",
)
def get_liveness() -> HealthResponse:
    """Orchestrator liveness probe."""
    return HealthResponse(
        status="healthy",
        service=settings.service_name,
        version=settings.version,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_200_OK: {"model": ReadinessResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse},
    },
    summary="Readiness probe",
    description="Verifies database connectivity, role permissions, and schema accessibility.",
)
def get_readiness(
    db: ServiceDatabaseManager = Depends(get_db_manager),
) -> JSONResponse:
    """Orchestrator readiness probe checking database subsystem status."""
    readiness_info = db.check_readiness()
    if readiness_info.connected:
        payload = ReadinessResponse(
            status="ready",
            service=settings.service_name,
            version=settings.version,
            database=readiness_info,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=payload.model_dump(by_alias=True),
        )
    else:
        payload = ReadinessResponse(
            status="not_ready",
            service=settings.service_name,
            version=settings.version,
            database=readiness_info,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(by_alias=True),
        )

