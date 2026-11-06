"""Dependency injection providers for Recommendation & Meal Planner Service."""

from __future__ import annotations

import uuid
from typing import Optional
from fastapi import Depends, Header, HTTPException, status

from services.common.database import ServiceDatabaseManager
from services.recommendation_planner.client import ProfileServiceClient, RecipeServiceClient
from services.recommendation_planner.database import get_db_manager
from services.recommendation_planner.repository import PlannerRepository


def get_repository(
    db: ServiceDatabaseManager = Depends(get_db_manager),
) -> PlannerRepository:
    """Provide PlannerRepository instance using service database manager."""
    return PlannerRepository(db)


def get_recipe_client() -> RecipeServiceClient:
    """Provide configured RecipeServiceClient."""
    return RecipeServiceClient()


def get_profile_client() -> ProfileServiceClient:
    """Provide configured ProfileServiceClient."""
    return ProfileServiceClient()


def get_required_guest_session(
    x_guest_session_id: Optional[str] = Header(None, alias="X-Guest-Session-ID"),
    repo: PlannerRepository = Depends(get_repository),
) -> str:
    """
    Validate and enforce the required X-Guest-Session-ID header.
    Returns the valid session ID string, or raises HTTP 401 with code SESSION_EXPIRED.
    """
    if not x_guest_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "SESSION_EXPIRED",
                "message": "Missing required X-Guest-Session-ID header",
                "details": [],
            },
        )

    # Validate UUID syntax
    try:
        uuid.UUID(x_guest_session_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "SESSION_EXPIRED",
                "message": "Invalid X-Guest-Session-ID UUID format",
                "details": [],
            },
        )

    # Validate session exists and is unexpired in meal_planner.guest_sessions
    session = repo.get_guest_session(x_guest_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "SESSION_EXPIRED",
                "message": "Guest session has expired or does not exist",
                "details": [],
            },
        )

    return x_guest_session_id


def get_optional_guest_session(
    x_guest_session_id: Optional[str] = Header(None, alias="X-Guest-Session-ID"),
    repo: PlannerRepository = Depends(get_repository),
) -> Optional[str]:
    """
    Optional X-Guest-Session-ID header validator.
    Returns session_id if valid; None if absent or expired.
    """
    if not x_guest_session_id:
        return None

    try:
        uuid.UUID(x_guest_session_id)
    except (ValueError, AttributeError):
        return None

    session = repo.get_guest_session(x_guest_session_id)
    if not session:
        return None

    return x_guest_session_id

