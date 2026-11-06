"""Anonymous guest session lifecycle endpoints."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Path, status

from services.recommendation_planner.config import settings
from services.recommendation_planner.dependencies import get_repository
from services.recommendation_planner.repository import PlannerRepository
from services.recommendation_planner.schemas import GuestSessionResponse

router = APIRouter(prefix="/api/v1/guest-sessions", tags=["Guest Sessions"])


@router.post(
    "",
    response_model=GuestSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize a new anonymous guest session",
    description=(
        "Generates a persistent UUID guest session token stored in meal_planner.guest_sessions. "
        "Enables pantry inventory and meal plan persistence without requiring username, password, "
        "or personal identification. Sessions default to a 30-day expiration window."
    ),
)
def create_guest_session(
    repo: PlannerRepository = Depends(get_repository),
) -> GuestSessionResponse:
    """Initialize anonymous guest session."""
    return repo.create_guest_session(ttl_days=settings.guest_session_ttl_days)


@router.get(
    "/{session_id}",
    response_model=GuestSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify and touch an existing guest session",
    description="Validates session existence and updates last_active_at timestamp.",
)
def get_guest_session(
    session_id: str = Path(..., description="UUID guest session identifier"),
    repo: PlannerRepository = Depends(get_repository),
) -> GuestSessionResponse:
    """Validate and touch existing guest session."""
    try:
        uuid.UUID(session_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SESSION_EXPIRED",
                "message": "Guest session has expired or does not exist",
                "details": [],
            },
        )

    session = repo.touch_guest_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SESSION_EXPIRED",
                "message": "Guest session has expired or does not exist",
                "details": [],
            },
        )
    return session

